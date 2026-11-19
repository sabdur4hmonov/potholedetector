"""Offline TRAIN-001 state/acceptance tests. No account, downloads, GPU or model inference."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml/kaggle'))
from watch_logic import classify_failure, next_action, run_budget, should_relaunch, verify_artifacts
import watch
sys.path.insert(0, str(ROOT / 'ml'))
from prepare_rdd2022 import extract


class WatcherTest(unittest.TestCase):
    def test_failure_classification_requires_explicit_transient_evidence(self):
        for reason in ('HTTP Error 503: Service Unavailable', 'ConnectionResetError: reset',
                       'Figshare download timed out', 'Kaggle infrastructure error: worker lost'):
            with self.subTest(reason=reason):
                self.assertTrue(should_relaunch(reason, '', False))
                self.assertFalse(should_relaunch(reason, '', True))
        for reason, log in (('KernelWorkerStatus.CANCEL_ACKNOWLEDGED', ''),
                            ('ModuleNotFoundError: yolox', 'HTTP Error 503'),
                            ('CalledProcessError: pip', 'ERROR: Failed building wheel for onnx'),
                            ('Training deadline reached', ''), ('RuntimeError: missing checkpoint', '')):
            with self.subTest(reason=reason):
                self.assertEqual('permanent', classify_failure(reason, log))
                self.assertFalse(should_relaunch(reason, log, False))
        self.assertEqual('account', classify_failure('GPU quota exceeded', 'HTTP Error 503'))

    def test_cancelled_version_downloads_evidence_and_never_relaunches_without_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = directory / 'state.json'
            state.write_text(json.dumps(dict(phase='running', version=7, mode='smoke', run_budget=2640)))
            log = ''.join(f'line {i}\n' for i in range(50))
            def kaggle(group, command, ref, *args, **kwargs):
                self.assertEqual(f'{watch.KERNEL}/7', ref)
                if command == 'status':
                    return f'{ref} has status "KernelWorkerStatus.CANCEL_ACKNOWLEDGED"'
                if command == 'output':
                    (Path(args[1]) / 'result.json').write_text('{"reason": "Cancelled by owner"}')
                if command == 'logs':
                    return log
            with patch.object(watch, 'HERE', directory), patch.object(watch, 'STATE', state), \
                 patch.object(watch, 'kaggle', side_effect=kaggle) as cli, patch.object(watch, 'report') as report:
                with self.assertRaisesRegex(RuntimeError, 'version 7 stopped'):
                    watch.tick(False)
                self.assertEqual(['status', 'output', 'logs'], [call.args[1] for call in cli.call_args_list])
                self.assertIn('Cancelled by owner', report.call_args.args[1])
                self.assertNotIn('line 9\n', report.call_args.args[1])
                self.assertIn('line 10\n', report.call_args.args[1])
                self.assertEqual(log, (directory / 'output/version-7/kernel.log').read_text())

    def test_verified_smoke_automatically_submits_full_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = directory / 'state.json'
            state.write_text(json.dumps(dict(phase='running', version=2, mode='smoke', run_budget=2640, commit='a'*40)))
            model = directory / 'output/version-2/model/pothole_yolox_nano.onnx'
            model.parent.mkdir(parents=True)
            model.write_bytes(b'smoke fixture')
            result_path = model.parents[1] / 'result.json'
            receipt = dict(status='smoke_success', train_commit='a'*40, epochs=1, parity_images=20, init='scratch',
                           model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(), wall_seconds=1200)
            def kaggle(group, command, ref, *args, **kwargs):
                if command == 'status':
                    return f'{ref} has status "KernelWorkerStatus.COMPLETE"'
            with patch.object(watch, 'HERE', directory), patch.object(watch, 'STATE', state), \
                 patch.object(watch, 'kaggle', side_effect=kaggle), patch.object(watch, 'report'), \
                 patch.object(watch, 'push') as push:
                bad = dict(receipt, parity_images=19)
                result_path.write_text(json.dumps(bad))
                initial = state.read_text()
                with self.assertRaisesRegex(ValueError, '20 export comparisons'):
                    watch.tick(False)
                push.assert_not_called()
                state.write_text(initial)
                result_path.write_text(json.dumps(receipt))
                watch.tick(False)
                promoted = push.call_args.args[0]
                self.assertEqual(('full', 'new', 2, 2640), (promoted['mode'], promoted['phase'],
                                                           promoted['smoke_version'], promoted['gpu_seconds']))

    def test_push_running_complete_and_failure_transitions(self):
        self.assertEqual('push', next_action('new', None, 0))
        for state in ('pushed', 'queued', 'running'):
            self.assertEqual('wait', next_action(state, None, 0))
        self.assertEqual('install', next_action('complete', 'success', 2))
        self.assertEqual('fail', next_action('error', None, 0))
        self.assertEqual('fail', next_action('complete', 'error', 0))

    def test_two_resumes_are_the_absolute_limit(self):
        self.assertEqual('resume', next_action('complete', 'gate_failed', 0))
        self.assertEqual('resume', next_action('complete', 'gate_failed', 1))
        for count in (2, 3, 100):
            self.assertEqual('fail', next_action('complete', 'gate_failed', count))

    def test_requested_gpu_time_cannot_exceed_thirty_hours(self):
        used = 0
        budgets = []
        for _ in range(3):
            budgets.append(run_budget(used))
            used += budgets[-1]
        self.assertEqual([43200, 43200, 21600], budgets)
        self.assertEqual(30*3600, used)
        with self.assertRaises(ValueError): run_budget(used)

    def test_success_digest_and_gate_are_required_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'model').mkdir()
            model = directory / 'model/pothole_yolox_nano.onnx'
            model.write_bytes(b'synthetic shape-independent acceptance fixture')
            digest = hashlib.sha256(model.read_bytes()).hexdigest()
            val = dict(precision=.81, recall=.2, F1=.32)
            manifest = dict(version='yolox-test', input_size=416, opset=17, output_format='yolox_raw_bgr_0_255',
                yolox_commit='6ddff4824372906469a7fae2dc3206c7aa4bbaee', score_threshold=.7, nms_iou=.45,
                dataset_sha256='1'*64, sha256=digest, init='scratch', metrics=dict(parity_images=20, validation=val, test=val))
            result = dict(status='success', train_commit='2'*40, dataset_sha256='1'*64, model_sha256=digest,
                          validation=val, test=val, epochs=1, threshold=.7, init='scratch')
            def write():
                (directory / 'result.json').write_text(json.dumps(result))
                (directory / 'model/pothole_model.json').write_text(json.dumps(manifest))
            write()
            self.assertEqual(model, verify_artifacts(directory, '2'*40)[0])
            result['status'] = 'gate_failed'; write()
            with self.assertRaises(ValueError): verify_artifacts(directory, '2'*40)
            result['status'] = 'success'; write()
            manifest['score_threshold'] = 0; write()
            with self.assertRaisesRegex(ValueError, 'numeric'): verify_artifacts(directory, '2'*40)
            manifest['score_threshold'] = .7; write()
            result['validation']['precision'] = .79; write()
            with self.assertRaisesRegex(ValueError, 'precision'): verify_artifacts(directory, '2'*40)
            result['validation']['precision'] = .81; write()
            model.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA-256'): verify_artifacts(directory, '2'*40)

    def test_cli_zero_exit_error_does_not_mark_a_run_submitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ('kernel-metadata.json', 'train_kaggle.py'):
                (directory / name).write_text((ROOT / 'ml/kaggle' / name).read_text())
            state = dict(phase='new', commit='2'*40, resumes=0)
            with patch.object(watch, 'HERE', directory), patch.object(watch, 'STATE', directory / 'state.json'), \
                 patch.object(watch, 'kaggle', return_value='Kernel push error: GPU unavailable'), patch.object(watch, 'report') as report:
                with self.assertRaisesRegex(RuntimeError, 'acknowledge'): watch.push(state)
                self.assertEqual('pushing', state['phase'])
                report.assert_not_called()

    def test_dataset_processing_waits_before_resuming(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / 'state.json'
            state_path.write_text(json.dumps(dict(phase='waiting_dataset', commit='2'*40, resumes=1)))
            with patch.object(watch, 'STATE', state_path), patch.object(watch, 'report'), \
                 patch.object(watch, 'kaggle', return_value='processing'), patch.object(watch, 'push') as push:
                watch.tick(False)
                push.assert_not_called()
            with patch.object(watch, 'STATE', state_path), patch.object(watch, 'kaggle', return_value='ready'), patch.object(watch, 'push') as push:
                watch.tick(False)
                push.assert_called_once()

    def test_nested_country_extraction_excludes_drone_and_unlabelled_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            country = io.BytesIO()
            with tarfile.open(fileobj=country, mode='w:gz') as tar:
                for name in ('Japan/train/images/frame.jpg', 'Japan/train/annotations/xmls/frame.xml',
                             'Japan/test/images/unlabelled.jpg', 'China_Drone/train/images/air.jpg'):
                    entry = tarfile.TarInfo(name)
                    entry.size = 5
                    tar.addfile(entry, io.BytesIO(b'whole'))
            archive = directory / 'source.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('RDD2022/Japan.tar.gz', country.getvalue())
                z.writestr('RDD2022/China_Drone.zip', b'excluded archive')
            extract(archive, directory / 'out', annotated_only=True)
            files = sorted(str(p.relative_to(directory/'out')).replace('\\', '/') for p in (directory/'out').rglob('*') if p.is_file())
            self.assertEqual(['Japan/train/annotations/xmls/frame.xml', 'Japan/train/images/frame.jpg'], files)
            self.assertEqual(b'whole', (directory/'out/Japan/train/images/frame.jpg').read_bytes())

    def test_private_gpu_metadata_and_pinned_source_bootstrap(self):
        metadata = json.loads((ROOT / 'ml/kaggle/kernel-metadata.json').read_text())
        for field in ('is_private', 'enable_gpu', 'enable_internet'):
            self.assertEqual('true', metadata[field])
        self.assertEqual('NvidiaTeslaT4', metadata['machine_shape'])
        self.assertEqual('script', metadata['kernel_type'])
        bootstrap = (ROOT / 'ml/kaggle/train_kaggle.py').read_text()
        self.assertEqual(1, bootstrap.count('__PUSHED_TRAIN_COMMIT__'))
        for path in (ROOT / 'ml/kaggle').glob('*.py'):
            compile(path.read_text(), str(path), 'exec')
        sources = '\n'.join(p.read_text() for p in (ROOT / 'ml/kaggle').glob('*') if p.suffix in ('.py', '.ps1', '.json'))
        self.assertNotRegex(sources, r'KGAT_[A-Za-z0-9_-]+')
        self.assertNotIn('--public', (ROOT / 'ml/kaggle/watch.py').read_text().replace('# Official CLI defaults to private; never pass --public.', ''))
        self.assertNotIn('KAGGLE_API_TOKEN', sources)
        self.assertIn('-StartWhenAvailable', sources)
        self.assertIn('-LogonType Interactive -RunLevel Limited', sources)


if __name__ == '__main__':
    unittest.main(verbosity=2)
