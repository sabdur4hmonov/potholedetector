"""Pure watcher decisions and model acceptance checks, independent of Kaggle/Windows."""
import hashlib
import json
import math
from pathlib import Path
import re

MAX_RESUMES = 2
SMOKE_BUDGET = 44*60


def classify_failure(reason, log):
    """Retry only explicit network or Kaggle infrastructure failures."""
    details = (reason + '\n' + log).lower()
    if re.search(r'\bquota\b|phone verif|account verif|gpu access denied|permission denied \(.*kaggle|'
                 r'kaggle[^\n]*\b(?:401|403|429)\b|(?:401|403) client error', details):
        return 'account'
    if re.search(r'failed building wheel|failed-wheel-build|no matching distribution|'
                 r'(?:modulenotfound|import|syntax|assertion|attribute|index|key|type|value)error:|out of memory|no space left', details):
        return 'permanent'
    if re.search(r'http(?: error| status|/\d(?:\.\d)?)?\s+(?:408|500|502|503|504)\b|'
                 r'(?:read|connect|download|connection) (?:timed out|timeout)|readtimeouterror|'
                 r'connectionreseterror|remote end closed connection|temporary failure in name resolution|'
                 r'download ended before content-length|kaggle infrastructure error|'
                 r'failed to provision (?:a )?(?:kernel|worker)|worker lost', details):
        return 'transient'
    return 'permanent'


def should_relaunch(reason, log, already_relaunched):
    return not already_relaunched and classify_failure(reason, log) == 'transient'


def log_lines(raw):
    """Decode Kaggle's JSON event array, with a plain-log fallback."""
    try:
        events = json.loads(raw)
    except ValueError:
        return raw.splitlines()
    if isinstance(events, list):
        return ''.join(event['data'] for event in events if isinstance(event, dict) and
                       isinstance(event.get('data'), str)).splitlines()
    return raw.splitlines()


def safe_diagnostic(text):
    text = re.sub(r'(?i)KGAT_[A-Za-z0-9_-]+|(?:Bearer|Basic)\s+\S+', '[credential removed]', text)
    text = re.sub(r'(https?://)[^/\s@]+@', r'\1[credential removed]@', text)
    return re.sub(r'(https?://[^\s"<>?]+)\?[^\s"<>]+', r'\1?[query removed]', text)


def run_budget(gpu_seconds):
    budget = min(43_200, int(30*3600 - gpu_seconds))
    if budget <= 105*60:
        raise ValueError('Thirty-hour GPU budget has insufficient time for another run')
    return budget


def next_action(kernel_status, result_status, resumes):
    if kernel_status in ('new',):
        return 'push'
    if kernel_status in ('queued', 'running', 'pushed'):
        return 'wait'
    if kernel_status != 'complete':
        return 'fail'
    if result_status == 'success':
        return 'install'
    if result_status == 'gate_failed' and resumes < MAX_RESUMES:
        return 'resume'
    return 'fail'


def read_json(path):
    if path.stat().st_size > 32_768:
        raise ValueError('Oversize result or manifest')
    return json.loads(path.read_text(encoding='utf-8'))


def verify_smoke(directory, result, commit):
    if (result.get('status') != 'smoke_success' or result.get('train_commit') != commit or
        result.get('epochs') != 1 or result.get('parity_images') != 20 or result.get('init') != 'scratch'):
        raise ValueError('Smoke run did not complete one epoch and 20 export comparisons')
    if not 0 < result.get('wall_seconds', 0) < 45*60:
        raise ValueError('Smoke run exceeded 45 minutes or has no duration')
    model = directory / 'model/pothole_yolox_nano.onnx'
    if (directory / 'model/pothole_model.json').exists() or not 0 < model.stat().st_size <= 32*1024*1024:
        raise ValueError('Invalid smoke model files')
    if hashlib.sha256(model.read_bytes()).hexdigest() != result.get('model_sha256'):
        raise ValueError('Smoke model digest mismatch')


def verify_artifacts(directory, commit):
    result = read_json(directory / 'result.json')
    if result.get('status') != 'success' or result.get('train_commit') != commit:
        raise ValueError('Training success and pinned source revision are required')
    model = directory / 'model/pothole_yolox_nano.onnx'
    manifest_path = directory / 'model/pothole_model.json'
    manifest = read_json(manifest_path)
    if not model.is_file() or not 0 < model.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError('Invalid model size')
    if manifest.get('input_size') != 416 or manifest.get('opset') != 17:
        raise ValueError('Invalid model input contract')
    if manifest.get('output_format') != 'yolox_raw_bgr_0_255':
        raise ValueError('Invalid model output contract')
    if manifest.get('yolox_commit') != '6ddff4824372906469a7fae2dc3206c7aa4bbaee':
        raise ValueError('Invalid YOLOX revision')
    if not re.fullmatch(r'yolox-[A-Za-z0-9._-]{1,74}', manifest.get('version', '')):
        raise ValueError('Invalid model version')
    for field in ('score_threshold', 'nms_iou'):
        value = manifest.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value < 1:
            raise ValueError('Invalid numeric model setting')
    dataset_hash = manifest.get('dataset_sha256', '')
    if not re.fullmatch(r'[0-9a-f]{64}', dataset_hash) or dataset_hash != result.get('dataset_sha256'):
        raise ValueError('Dataset receipt mismatch')
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    if digest != manifest.get('sha256') or digest != result.get('model_sha256'):
        raise ValueError('Model SHA-256 mismatch')
    if (manifest.get('init') != 'scratch' or result.get('init') != 'scratch' or
        manifest.get('init_weights_sha256') is not None or result.get('init_weights_sha256') is not None):
        raise ValueError('TRAIN-001 requires scratch initialization')
    metrics = manifest.get('metrics', {})
    if (metrics.get('parity_images') != 20 or metrics.get('validation') != result.get('validation') or
        metrics.get('test') != result.get('test') or result.get('threshold') != manifest['score_threshold']):
        raise ValueError('Missing export parity or validation receipt')
    if not isinstance(result.get('epochs'), int) or result['epochs'] <= 0:
        raise ValueError('Missing completed training epochs')
    for split in ('validation', 'test'):
        for field in ('precision', 'recall', 'F1'):
            value = result[split].get(field)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid measured metrics')
    precision = result['validation'].get('precision')
    if precision < .8:
        raise ValueError('Validation precision gate failed')
    return model, manifest_path
