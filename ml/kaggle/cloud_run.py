"""Cloud-only training orchestration. Large data stays under /kaggle/tmp."""
import argparse
import json
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request


def dry_run(root):
    sys.path.insert(0, str(root / 'ml'))
    from prepare_rdd2022 import prepare
    from training_init import SCRATCH
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        images = directory / 'Japan/train/images'
        annotations = directory / 'Japan/train/annotations/xmls'
        images.mkdir(parents=True)
        annotations.mkdir(parents=True)
        for i, damage in enumerate(('D40', 'D00', 'D20')):
            Image.new('RGB', (60, 30), (30*i, 45, 95)).save(images / f'frame{i}.jpg')
            xml = f'<annotation><size><width>60</width><height>30</height></size><object><name>{damage}</name><bndbox><xmin>4</xmin><ymin>3</ymin><xmax>20</xmax><ymax>15</ymax></bndbox></object></annotation>'
            (annotations / f'frame{i}.xml').write_text(xml)
        stats = prepare(directory / 'Japan', directory / 'prepared', link_images=True)
        assert stats['countries']['Japan'] == dict(images=3, boxes=1, positives=1, negatives=2)
        assert SCRATCH == {'init': 'scratch', 'init_weights_sha256': None}
    print('TRAIN-001 DRY RUN PASS: three full-frame VOC fixtures, COCO split and scratch wiring; no GPU/download')


def run(root, commit, started, budget_seconds, smoke=False):
    working = Path('/kaggle/working')
    working.mkdir(exist_ok=True)
    result_path = working / 'result.json'
    sys.path.insert(0, str(root / 'ml'))
    try:
        from runtime_setup import install_torch, install_yolox
        from prepare_rdd2022 import extract, prepare, verify_archive
        from training_init import SCRATCH, load_training_receipt
        install_torch()
        checkout = Path('/kaggle/tmp/YOLOX')
        install_yolox(root, checkout)
        # The editable wheel installs its import hook in a .pth file after this
        # interpreter starts. Process that site directory before importing YOLOX.
        site.addsitedir(sysconfig.get_path('purelib'))
        import torch
        from yolox_pothole_exp import Exp
        from yolox.tools.train import make_parser
        from train_budget import train
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable in the training environment')
        print(f'Python {sys.version.split()[0]} / torch {torch.__version__} / {torch.cuda.get_device_name(0)}', flush=True)
        pins_path = root / 'ml/pins.json'
        pins = json.loads(pins_path.read_text())
        attached = list(Path('/kaggle/input').rglob('latest_ckpt.pth'))
        if len(attached) > 1:
            raise ValueError('Ambiguous attached checkpoints')
        if smoke and attached:
            raise ValueError('Smoke run must train from scratch')
        if attached:
            saved = json.loads(attached[0].with_name('measured_pins.json').read_text())
            if saved['yolox_commit'] != pins['yolox_commit']:
                raise ValueError('Resume dataset/source pin mismatch')
            pins['rdd2022_sha256'] = saved['rdd2022_sha256']
            pins_path.write_text(json.dumps(pins))
        archive = Path('/kaggle/tmp/RDD2022.zip')
        print('Downloading RDD2022 to Kaggle temporary disk', flush=True)
        with urllib.request.urlopen(pins['rdd2022_url'], timeout=120) as response, archive.open('wb') as target:
            shutil.copyfileobj(response, target, 1024 * 1024)
            size = response.headers.get('Content-Length')
            if size is not None and target.tell() != int(size):
                raise ConnectionError('RDD2022 download ended before Content-Length')
        digest = verify_archive(archive, pins_path)
        source = Path('/kaggle/tmp/rdd_source')
        extract(archive, source, annotated_only=True)
        archive.unlink()
        data = Path('/kaggle/tmp/data')
        limits = {'train': 128, 'val': 24, 'test': 24} if smoke else None
        stats = prepare(source, data, pins['seed'], digest, link_images=True, split_limits=limits)
        print('Prepared full-frame splits:', stats['splits'], flush=True)
        shutil.rmtree(source)  # Data retains complete images through same-volume hard links.
        (working / 'dataset_stats.json').write_text(json.dumps(stats, indent=2))
        shutil.copyfile(pins_path, working / 'measured_pins.json')
        ckpt = working / 'ckpt/pothole_nano'
        ckpt.mkdir(parents=True, exist_ok=True)
        if attached:
            prior = attached[0]
            receipt = load_training_receipt(prior.with_name('training_init.json'), pins)
            if receipt != SCRATCH:
                raise ValueError('TRAIN-001 resumes scratch training only')
            for name in ('latest_ckpt.pth', 'best_ckpt.pth'):
                old = prior.with_name(name)
                if old.is_file():
                    shutil.copyfile(old, ckpt / name)
        (ckpt / 'training_init.json').write_text(json.dumps(SCRATCH))
        train_seconds = budget_seconds - 5*60 if smoke else min(10*3600 + 15*60, budget_seconds - 105*60)
        os.environ.update(POTHOLE_DATA=str(data), POTHOLE_CHECKPOINTS=str(working / 'ckpt'),
                          POTHOLE_EPOCHS='1' if smoke else '500', POTHOLE_DEADLINE=str(started + train_seconds))
        os.environ.pop('POTHOLE_INITIAL_WEIGHTS', None)
        args_list = ['-f', str(root / 'ml/yolox_pothole_exp.py'), '-d', '1', '-b', '16', '--fp16']
        if attached:
            args_list += ['--resume', '-c', str(ckpt / 'latest_ckpt.pth')]
        args = make_parser().parse_args(args_list)
        exp = Exp()
        exp.save_history_ckpt = False
        # Preserve the experiment's five-epoch validation and best-checkpoint selection.
        if args.experiment_name is None:
            args.experiment_name = exp.exp_name
        print('Training initialization: scratch', flush=True)
        latest = train(exp, args)
        epochs = int(torch.load(latest, map_location='cpu', weights_only=False)['start_epoch'])
        command = [sys.executable, str(root / 'ml/evaluate_export.py'), '--data', str(data),
            '--checkpoint', str(latest), '--output', str(working / 'model'), '--result', str(result_path),
            '--train-commit', commit, '--epochs', str(epochs)]
        if smoke:
            command.append('--smoke')
        evaluation = subprocess.run(command, check=False)
        if evaluation.returncode and not result_path.is_file():
            raise RuntimeError('Evaluation/export failed before writing a result')
        result = json.loads(result_path.read_text())
        result['wall_seconds'] = time.monotonic() - started
        result_path.write_text(json.dumps(result, indent=2))
        print(result_path.read_text(), flush=True)
    except Exception as error:
        result_path.write_text(json.dumps({'status': 'error', 'reason': f'{type(error).__name__}: {error}',
            'train_commit': commit, 'init': 'scratch', 'epochs': 0}, indent=2))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('commit')
    parser.add_argument('started', type=float)
    parser.add_argument('budget', type=int)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    run(args.root, args.commit, args.started, args.budget, args.smoke)
