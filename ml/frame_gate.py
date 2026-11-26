"""Frame-presence threshold selection and the shared export/install quality gate."""
from itertools import groupby
import math

MAX_THRESHOLD = 1 - 2**-24
GATE = {'frame_validation': (.80, .40), 'frame_test': (.75, .35)}


def frame_metrics(frames, threshold):
    tp = fp = fn = tn = 0
    for truth, score in frames:
        predicted = score is not None and score >= threshold
        tp += truth and predicted
        fp += not truth and predicted
        fn += truth and not predicted
        tn += not truth and not predicted
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=tp / max(1, tp + fp),
                recall=tp / max(1, tp + fn), F1=2 * tp / max(1, 2*tp + fp + fn))


def choose_frame_threshold(frames, min_precision=.80):
    scores = sorted(((min(score, MAX_THRESHOLD), truth) for truth, score in frames
                     if score is not None and math.isfinite(score) and 0 < score <= 1), reverse=True)
    tp = fp = 0
    best = None
    for score, group in groupby(scores, key=lambda row: row[0]):
        for _, truth in group:
            tp += bool(truth)
            fp += not truth
        precision = tp / (tp + fp)
        if tp and precision >= min_precision:
            candidate = (tp, precision, score)
            best = candidate if best is None else max(best, candidate)
    return best[2] if best else None


def frame_gate_passes(result):
    for key, (min_precision, min_recall) in GATE.items():
        metrics = result.get(key)
        if not isinstance(metrics, dict):
            return False
        counts = [metrics.get(k) for k in ('tp', 'fp', 'fn', 'tn')]
        if any(type(n) is not int or n < 0 for n in counts):
            return False
        tp, fp, fn, _ = counts
        precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
        f1 = 2 * tp / max(1, 2*tp + fp + fn)
        for field, derived in (('precision', precision), ('recall', recall), ('F1', f1)):
            value = metrics.get(field)
            if type(value) not in (int, float) or not math.isclose(value, derived, abs_tol=1e-12):
                return False
        if precision < min_precision or recall < min_recall:
            return False
    return True
