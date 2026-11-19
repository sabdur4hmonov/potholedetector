"""One durable watcher tick. Scheduled every 15 minutes under the current Windows user."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from watch_logic import (MAX_RESUMES, SMOKE_BUDGET, classify_failure, log_lines, next_action, read_json,
                         run_budget, safe_diagnostic, should_relaunch, verify_artifacts, verify_smoke)

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STATE = HERE / '.state/state.json'
TASK_NAME = 'PotholeTrainWatch'
OWNER = 'sardor007'
KERNEL = OWNER + '/pothole-yolox-train'
DATASET = OWNER + '/pothole-yolox-ckpt'


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    tmp.replace(path)


def report(status, message):
    path = ROOT / 'ml/TRAINING_REPORT.md'
    labels = {'running': ('ishlayapti', 'running'), 'ready': ('tayyor', 'ready'), 'failed': ('xato', 'failed')}
    uz, en = labels[status]
    header = f'# TRAIN-001\n\nHolat: {uz}\nStatus: {en}\n'
    prior = path.read_text(encoding='utf-8') if path.exists() else ''
    marker = '\n## Progress / Jarayon\n'
    history = prior.split(marker, 1)[1] if marker in prior else ''
    stamp = datetime.now(timezone(timedelta(hours=5))).isoformat(timespec='seconds')
    path.write_text(header + marker + history + f'\n- {stamp} — {message}\n', encoding='utf-8')


def run_command(command, timeout=300):
    result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        codes = re.findall(r'\b(?:401|403|404|429|500|502|503)\b', result.stdout)
        detail = ' HTTP ' + ','.join(sorted(set(codes))) if codes else ''
        raise RuntimeError(f'{command[0]} command failed with exit {result.returncode}{detail}')
    return result.stdout


def kaggle(*args, timeout=300):
    return run_command([sys.executable, '-m', 'kaggle', *args], timeout)


def collect_failure(ref, directory, status_text):
    directory.mkdir(parents=True, exist_ok=True)
    problems = []
    try:
        kaggle('kernels', 'output', ref, '-p', str(directory), '--page-size', '100', timeout=900)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        problems.append(f'Output unavailable: {error}')
    reason = ''
    try:
        reason = str(read_json(directory / 'result.json').get('reason') or '')
    except (OSError, ValueError, AttributeError) as error:
        problems.append(f'No readable result.json: {error}')
    downloaded = directory / (KERNEL.split('/')[1] + '.log')
    raw = downloaded.read_text(encoding='utf-8-sig', errors='replace') if downloaded.is_file() else ''
    if not raw.strip():
        try:
            raw = kaggle('kernels', 'logs', ref)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            problems.append(f'Log unavailable: {error}')
    lines = [safe_diagnostic(line) for line in log_lines(raw)]
    if lines:
        (directory / 'kernel.log').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    reason = safe_diagnostic(reason)
    status_text = safe_diagnostic(status_text.strip())
    tail = '\n'.join(lines[-40:])
    message = f'Kaggle failure evidence for {ref}. {status_text}'
    if reason:
        message += f'\n\n  result.json reason: {reason}'
    if problems:
        message += '\n\n  ' + safe_diagnostic(' '.join(problems))
    if tail:
        message += '\n\n' + '\n'.join(('    ' + line).rstrip() for line in lines[-40:])
    return reason + '\n' + status_text, tail, message


def unregister():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "if(Get-ScheduledTask -TaskName 'PotholeTrainWatch' -ErrorAction SilentlyContinue){Unregister-ScheduledTask -TaskName 'PotholeTrainWatch' -Confirm:$false}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if result.returncode:
        raise RuntimeError('Could not unregister PotholeTrainWatch')


def push(state):
    if state['resumes'] > MAX_RESUMES:
        raise ValueError('Resume limit exceeded')
    metadata = json.loads((HERE / 'kernel-metadata.json').read_text())
    for field in ('is_private', 'enable_gpu', 'enable_internet'):
        if str(metadata[field]).lower() != 'true':
            raise ValueError('Private GPU/internet metadata required')
    if metadata['id'] != KERNEL:
        raise ValueError('Unexpected kernel owner')
    metadata['dataset_sources'] = [DATASET] if state['resumes'] else []
    upload = HERE / '.upload'
    upload.mkdir(exist_ok=True)
    atomic_json(upload / 'kernel-metadata.json', metadata)
    code = (HERE / 'train_kaggle.py').read_text(encoding='utf-8')
    if code.count('__PUSHED_TRAIN_COMMIT__') != 1:
        raise ValueError('Expected one source revision placeholder')
    budget = run_budget(state.get('gpu_seconds', 0))
    smoke = state.get('mode') == 'smoke'
    if smoke:
        budget = min(SMOKE_BUDGET, budget)
        code = code.replace('SMOKE = False', 'SMOKE = True')
    code = code.replace('RUN_BUDGET_SECONDS = 43_200', f'RUN_BUDGET_SECONDS = {budget}')
    (upload / 'train_kaggle.py').write_text(code.replace('__PUSHED_TRAIN_COMMIT__', state['commit']), encoding='utf-8')
    # Persist intent before the network mutation. A crash cannot trigger another automatic push.
    state['phase'] = 'pushing'
    atomic_json(STATE, state)
    response = kaggle('kernels', 'push', '-p', str(upload), '--accelerator', 'NvidiaTeslaT4', '--timeout', str(budget))
    # Some CLI API failures print an error while returning exit code zero.
    version = re.search(r'Kernel version (\d+) successfully pushed', response)
    if not version or 'not valid' in response.lower():
        raise RuntimeError('Kaggle did not acknowledge a successful GPU push; check account GPU/phone/internet access')
    state['run_budget'] = budget
    state['version'] = int(version.group(1))
    # Use the server link when available. The API version number is not the web script version ID.
    url = re.search(r'https://www\.kaggle\.com/code/' + re.escape(KERNEL) +
                    r'(?:/log)?(?:\?scriptVersionId=\d+)?(?=\s|$)', response)
    state['url'] = url.group() if url else f'https://www.kaggle.com/code/{KERNEL}/log'
    state['phase'] = 'pushed'
    atomic_json(STATE, state)
    mode = 'smoke' if smoke else 'full training'
    report('running', f'Private {mode} version {state["version"]} submitted. {state["url"]}')


def upload_checkpoint(directory, state):
    latest = directory / 'ckpt/pothole_nano/latest_ckpt.pth'
    if not latest.is_file() or not 0 < latest.stat().st_size <= 64*1024*1024:
        raise ValueError('Missing or oversize resume checkpoint')
    result = read_json(directory / 'result.json')
    if result.get('train_commit') != state['commit'] or result.get('init') != 'scratch':
        raise ValueError('Resume checkpoint source/init mismatch')
    stage = HERE / '.state/checkpoint_upload'
    stage.mkdir(exist_ok=True)
    for name in ('latest_ckpt.pth', 'best_ckpt.pth', 'training_init.json'):
        source = latest.with_name(name)
        if source.is_file():
            shutil.copyfile(source, stage / name)
    for name in ('measured_pins.json', 'dataset_stats.json'):
        shutil.copyfile(directory / name, stage / name)
    atomic_json(stage / 'dataset-metadata.json', {'id': DATASET, 'title': 'Pothole YOLOX ckpt',
                'licenses': [{'name': 'CC-BY-SA-4.0'}], 'isPrivate': True})
    if state.get('dataset_created'):
        response = kaggle('datasets', 'version', '-p', str(stage), '-m', f'Resume {state["resumes"]+1}', '--dir-mode', 'skip', '--keep-tabular', timeout=900)
        if 'Dataset version is being created.' not in response:
            raise RuntimeError('Kaggle did not acknowledge the private checkpoint version')
    else:
        # Official CLI defaults to private; never pass --public.
        response = kaggle('datasets', 'create', '-p', str(stage), '--dir-mode', 'skip', '--keep-tabular', timeout=900)
        if 'Your private Dataset is being created.' not in response:
            raise RuntimeError('Kaggle did not acknowledge private checkpoint dataset creation')
        state['dataset_created'] = True
    state['resumes'] += 1
    atomic_json(STATE, state)
    state['phase'] = 'waiting_dataset'
    atomic_json(STATE, state)
    report('running', 'Private checkpoint dataset uploaded; waiting for Kaggle dataset processing.')


def install_and_build(directory, state):
    model, manifest = verify_artifacts(directory, state['commit'])
    state['phase'] = 'installing'
    atomic_json(STATE, state)
    target = ROOT / 'android-app/android/app/src/main/assets/ml'
    target.mkdir(exist_ok=True)
    for source in (model, manifest):
        temporary = directory / ('install-' + source.name)
        shutil.copyfile(source, temporary)
        os.replace(temporary, target / source.name)
    state['phase'] = 'building'
    atomic_json(STATE, state)
    report('running', 'Model SHA-256 and metadata accepted. Building and running real ONNX JVM fixtures.')
    run_command(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(HERE/'build_model.ps1'),
                 '-OutputDirectory', str(directory)], timeout=7000)
    built = read_json(directory / 'build_report.json')
    if built.get('status') != 'ready' or not built.get('real_runtime_passed'):
        raise ValueError('Build verification did not complete')
    state['phase'] = 'ready'
    atomic_json(STATE, state)
    report('ready', 'Model and three split APKs verified. Physical-phone and road validation pending. ' + json.dumps(built['apks']))
    unregister()


def tick(launch):
    state = read_json(STATE) if STATE.exists() else None
    if launch and (state is None or state['phase'] == 'failed'):
        commit = run_command(['git', 'rev-parse', 'HEAD']).strip()
        if run_command(['git', 'branch', '--show-current']).strip() != 'train-001':
            raise ValueError('Launch requires train-001')
        remote = run_command(['git', 'ls-remote', 'origin', 'refs/heads/train-001'])
        if not remote.startswith(commit + '\t'):
            raise ValueError('The exact training revision must be pushed first')
        spent = 0
        if state is not None:
            if commit == state['commit']:
                raise ValueError('A stopped run requires a new pushed revision for manual launch')
            atomic_json(STATE.with_name(f'failed-{state["commit"][:12]}.json'), state)
            spent = state.get('gpu_seconds', state.get('run_budget', 0))
        state = {'phase': 'new', 'commit': commit, 'resumes': 0, 'mode': 'smoke', 'gpu_seconds': spent}
        atomic_json(STATE, state)
    if state is None:
        return
    if state['phase'] in ('ready', 'failed'):
        unregister()
        return
    if state['phase'] == 'new':
        push(state)
        return
    if state['phase'] == 'waiting_dataset':
        status = kaggle('datasets', 'status', DATASET).lower()
        if 'ready' in status:
            push(state)
        elif 'error' in status or 'failed' in status:
            raise RuntimeError('Private checkpoint dataset processing failed')
        else:
            report('running', 'Private checkpoint dataset is processing.')
        return
    if state['phase'] not in ('pushed', 'running'):
        raise RuntimeError('An interrupted step requires inspection; automatic retry stopped')
    version = state.get('version')
    ref = f'{KERNEL}/{version}' if version else KERNEL
    status_text = kaggle('kernels', 'status', ref)
    match = re.search(r'has status "(?:KernelWorkerStatus\.)?([A-Za-z_]+)"', status_text)
    if not match:
        raise ValueError('Unrecognized Kaggle status')
    status = match.group(1).lower()
    if status in ('running', 'queued', 'cancel_requested'):
        state['phase'] = 'running'
        atomic_json(STATE, state)
        report('running', f'Kaggle version {version} is {status}.')
        return
    state['phase'] = 'downloading'
    # Charge each requested run budget, even if it completed early. This also bounds failed/unknown durations.
    state['gpu_seconds'] = state.get('gpu_seconds', 0) + state['run_budget']
    atomic_json(STATE, state)
    directory = HERE / 'output' / f'version-{version or "legacy"}'
    if status == 'complete':
        kaggle('kernels', 'output', ref, '-p', str(directory), '--page-size', '100', timeout=900)
        result = read_json(directory / 'result.json')
    else:
        result = {'status': 'error'}
    if result.get('status') == 'error':
        reason, tail, evidence = collect_failure(ref, directory, status_text)
        if should_relaunch(reason, tail, state.get('transient_relaunch_used', False)):
            state['transient_relaunch_used'] = True
            state['phase'] = 'new'
            atomic_json(STATE, state)
            report('running', evidence + '\n\n  Transient failure confirmed. One automatic relaunch is scheduled.')
            return
        report('failed', evidence)
        if classify_failure(reason, tail) == 'account':
            report('failed', "Kaggle → Settings sahifasida telefon verifikatsiyasini tekshiring. "
                   "Notebook Settings’da GPU va Internet ruxsati borligini ko‘ring. "
                   "GPU kvotasi tugagan bo‘lsa, Kaggle ko‘rsatgan yangilanish vaqtini kuting.")
        raise RuntimeError(f'Kaggle version {version} stopped. See downloaded failure evidence in the report.')
    if state.get('mode') == 'smoke':
        verify_smoke(directory, result, state['commit'])
        state['mode'] = 'full'
        state['phase'] = 'new'
        state['smoke_version'] = version
        atomic_json(STATE, state)
        report('running', f'Smoke version {version} passed in {result["wall_seconds"]:.0f}s. '
               'One epoch and 20 ONNX comparisons verified. Submitting full training.')
        push(state)
        return
    action = next_action(status, result.get('status'), state['resumes'])
    if action == 'resume':
        report('running', 'Validation precision gate failed; uploading a private resumable checkpoint.')
        state['phase'] = 'uploading'
        atomic_json(STATE, state)
        upload_checkpoint(directory, state)
    elif action == 'install':
        install_and_build(directory, state)
    else:
        raise RuntimeError('Training failed or maximum two resumes exhausted')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--launch', action='store_true')
    args = p.parse_args()
    STATE.parent.mkdir(exist_ok=True)
    import msvcrt
    with (STATE.parent / 'watch.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            tick(args.launch)
        except Exception as error:
            state = read_json(STATE) if STATE.exists() else {}
            state['phase'] = 'failed'
            state['failure'] = type(error).__name__ + ': ' + str(error)
            atomic_json(STATE, state)
            report('failed', state['failure'])
            unregister()
            raise SystemExit(1)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
