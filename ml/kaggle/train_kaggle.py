"""Single uploaded bootstrap. The local launcher substitutes the pushed commit before upload."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

TRAIN_COMMIT = "__PUSHED_TRAIN_COMMIT__"
RUN_BUDGET_SECONDS = 43_200
SMOKE = False
TARGET_EPOCH = 0
REPOSITORY = "https://github.com/sabdur4hmonov/potholedetector.git"


def cloud_python(scratch):
    # Kaggle's Python 3.13 has no wheel for the pinned ONNX 1.17.0.
    tools = scratch / 'uv-tools'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--only-binary=:all:',
                    '--target', str(tools), 'uv==0.10.0'], check=True)
    env = dict(os.environ, PYTHONPATH=str(tools), UV_PYTHON_INSTALL_DIR=str(scratch / 'python'))
    command = [sys.executable, '-m', 'uv']
    venv = scratch / 'train-env'
    subprocess.run([*command, 'venv', '--managed-python', '--python', '3.12.12', '--seed', str(venv)],
                   env=env, check=True)
    return venv / 'bin/python'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--smoke', action='store_true', default=SMOKE)
    args = parser.parse_args()
    started = time.monotonic()
    if args.dry_run:
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / 'ml/kaggle'))
        from cloud_run import dry_run
        dry_run(root)
        return
    smoke = args.smoke
    budget = min(RUN_BUDGET_SECONDS, 44*60) if smoke else RUN_BUDGET_SECONDS
    working = Path('/kaggle/working')
    working.mkdir(exist_ok=True)
    result = working / 'result.json'
    try:
        subprocess.run(['nvidia-smi'], check=True)
        if not re.fullmatch(r'[0-9a-f]{40}', TRAIN_COMMIT):
            raise ValueError('Launcher must supply an exact pushed train-001 commit')
        root = Path('/kaggle/tmp/pothole')
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--no-checkout', REPOSITORY, str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'checkout', '--detach', TRAIN_COMMIT], check=True)
        actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != TRAIN_COMMIT:
            raise ValueError('Training source revision mismatch')
        python = cloud_python(root.parent)
        env = dict(os.environ, PIP_NO_CACHE_DIR='1')
        env.pop('PYTHONPATH', None)
        command = [str(python), str(root / 'ml/kaggle/cloud_run.py'), str(root), TRAIN_COMMIT,
                   str(started), str(budget)]
        if smoke:
            command.append('--smoke')
        else:
            command += ['--target-epoch', str(TARGET_EPOCH)]
        subprocess.run(command, env=env, check=True)
    except Exception as error:
        if not result.exists():
            result.write_text(json.dumps(dict(status='error', reason=f'{type(error).__name__}: {error}',
                train_commit=TRAIN_COMMIT, mode='smoke' if smoke else 'full', epochs=0)))
        raise


if __name__ == '__main__':
    main()
