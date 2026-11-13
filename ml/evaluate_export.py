"""Validation-only threshold selection; untouched test metrics and raw-output ONNX parity."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import cv2
import numpy as np
import torch


def letterbox(image):
    h, w = image.shape[:2]
    scale = min(416 / w, 416 / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    canvas = np.full((416, 416, 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(canvas.transpose(2, 0, 1), dtype=np.float32)[None], scale


def iou(a, b):
    lo, hi = np.maximum(a[:2], b[:2]), np.minimum(a[2:4], b[2:4])
    inter = np.prod(np.maximum(0, hi - lo))
    union = np.prod(a[2:4] - a[:2]) + np.prod(b[2:4] - b[:2]) - inter
    return float(inter / union) if union > 0 else 0.


def decode(raw, threshold, scale, width, height, nms=.45):
    raw = np.asarray(raw).reshape(3549, 6)
    grids, strides = [], []
    for stride in (8, 16, 32):
        y, x = np.meshgrid(np.arange(416 // stride), np.arange(416 // stride), indexing='ij')
        grids.append(np.stack((x, y), -1).reshape(-1, 2))
        strides.append(np.full((len(grids[-1]), 1), stride))
    grid, stride = np.concatenate(grids), np.concatenate(strides)
    xy = (raw[:, :2] + grid) * stride
    wh = np.exp(np.clip(raw[:, 2:4], -20, 20)) * stride
    boxes = np.concatenate((xy - wh / 2, xy + wh / 2), -1) / scale
    boxes[:, 0::2] = boxes[:, 0::2].clip(0, width)
    boxes[:, 1::2] = boxes[:, 1::2].clip(0, height)
    scores = raw[:, 4].astype(np.float64) * raw[:, 5]
    probabilities = ((raw[:, 4:] >= 0) & (raw[:, 4:] <= 1)).all(axis=1)
    order = np.flatnonzero(probabilities & np.isfinite(raw).all(axis=1) & (scores >= threshold))
    order = sorted(order, key=lambda i: (-float(scores[i]), int(i)))
    kept = []
    for i in order:
        box = boxes[i]
        if np.isfinite(box).all() and (box[2:4] > box[:2]).all() and all(iou(box, b[:4]) <= nms for b in kept):
            kept.append(np.r_[boxes[i], scores[i]])
            if len(kept) == 100:
                break
    return kept


def matches(predictions, truth):
    remaining = set(range(len(truth)))
    for box in predictions:
        match = max(remaining, key=lambda i: iou(box, truth[i]), default=None)
        hit = match is not None and iou(box, truth[match]) >= .5
        if hit:
            remaining.remove(match)
        yield float(box[4]), hit


def metrics(samples, threshold):
    totals, countries = [0, 0, 0], {}
    for row, _, _, truth, predictions in samples:
        results = [hit for score, hit in matches(predictions, truth) if score >= threshold]
        tp, fp = sum(results), len(results) - sum(results)
        counts = [tp, fp, len(truth) - tp]
        totals = [a + b for a, b in zip(totals, counts)]
        c = countries.setdefault(row['country'], [0, 0, 0])
        c[:] = [a + b for a, b in zip(c, counts)]
    tp, fp, fn = totals
    precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return dict(precision=precision, recall=recall, F1=2*precision*recall/max(1e-12, precision+recall),
                tp=tp, fp=fp, fn=fn, per_country_recall={c: v[0]/(v[0]+v[2]) if v[0]+v[2] else None
                                                       for c, v in countries.items()}, iou=.5)


def choose_threshold(samples):
    from itertools import groupby
    truth_count = sum(len(row[3]) for row in samples)
    decisions = sorted((decision for _, _, _, truth, boxes in samples for decision in matches(boxes, truth)),
                       key=lambda item: -item[0])
    tp, fp, best = 0, 0, None
    for score, group in groupby(decisions, key=lambda item: item[0]):
        for _, hit in group:
            tp += int(hit)
            fp += int(not hit)
        precision = tp / (tp + fp)
        if tp and precision >= .8:
            candidate = (2 * tp / (truth_count + tp + fp), precision, score)
            best = candidate if best is None else max(best, candidate)
    if best is None:
        raise RuntimeError('Validation precision 0.80 not reached. Train longer, review data, or evaluate Tiny separately.')
    return min(best[2], float(np.nextafter(np.float32(1), np.float32(0))))


def collect(model, data, split):
    ann = json.loads((data / 'annotations' / f'{split}.json').read_text())
    truth = {}
    for a in ann['annotations']:
        x, y, w, h = a['bbox']
        truth.setdefault(a['image_id'], []).append(np.array([x, y, x+w, y+h]))
    result = []
    with torch.inference_mode():
        for row in ann['images']:
            image = cv2.imread(str(data / 'images' / row['file_name']))
            if image is None:
                raise ValueError('Unreadable full frame')
            tensor, scale = letterbox(image)
            raw = model(torch.from_numpy(tensor).cuda()).cpu().numpy()
            result.append((row, raw if split == 'test' and len(result) < 20 else None, scale,
                           truth.get(row['id'], []), decode(raw, np.finfo(np.float32).tiny, scale,
                                                           image.shape[1], image.shape[0])))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('/content/model_export'))
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('pothole_exp', here / 'yolox_pothole_exp.py')
    expmodule = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(expmodule)
    model = expmodule.Exp().get_model().cuda().eval()
    model.load_state_dict(torch.load(args.checkpoint, map_location='cpu', weights_only=False)['model'])
    model.head.decode_in_inference = False
    val = collect(model, args.data, 'val')
    threshold = choose_threshold(val)
    val_metrics = metrics(val, threshold)
    test = collect(model, args.data, 'test')
    test_metrics = metrics(test, threshold)
    print(json.dumps(dict(threshold=threshold, validation=val_metrics, test=test_metrics), indent=2))
    args.output.mkdir(parents=True, exist_ok=True)
    onnx_path = args.output / 'pothole_yolox_nano.onnx'
    torch.onnx.export(model, torch.zeros(1, 3, 416, 416, device='cuda'), str(onnx_path),
                      input_names=['images'], output_names=['output'], opset_version=17,
                      dynamic_axes=None, do_constant_folding=True, dynamo=False)
    import onnx
    import onnxruntime as ort
    onnx.checker.check_model(onnx.load(onnx_path))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    session = ort.InferenceSession(str(onnx_path), options, providers=['CPUExecutionProvider'])
    if len(test) < 20:
        raise ValueError('At least 20 test frames required for export parity')
    for row, expected, scale, _, _ in test[:20]:
        image = cv2.imread(str(args.data / 'images' / row['file_name']))
        tensor, _ = letterbox(image)
        actual = session.run(None, {'images': tensor})[0]
        assert actual.shape == (1, 3549, 6)
        np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-3)
        dimensions = (image.shape[1], image.shape[0])
        np.testing.assert_allclose(decode(actual, threshold, scale, *dimensions),
                                   decode(expected, threshold, scale, *dimensions), rtol=1e-3, atol=.1)
    pins = json.loads((here / 'pins.json').read_text())
    if not pins['rdd2022_sha256']:
        raise ValueError('Missing measured dataset SHA-256')
    metadata = dict(version='yolox-nano-rdd2022-v1', input_size=416, score_threshold=threshold,
                    nms_iou=.45, sha256=hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
                    metrics=dict(validation=val_metrics, test=test_metrics, parity_images=20),
                    dataset_sha256=pins['rdd2022_sha256'], yolox_commit=pins['yolox_commit'],
                    output_format='yolox_raw_bgr_0_255', opset=17, license='CC-BY-SA-4.0')
    (args.output / 'pothole_model.json').write_text(json.dumps(metadata, indent=2))
    print('Parity: 20/20. Exported model and manifest; field accuracy remains unverified.')


if __name__ == '__main__':
    main()
