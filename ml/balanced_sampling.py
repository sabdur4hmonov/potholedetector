"""Deterministic full-frame epoch composition for the pothole train split."""
from random import Random


def epoch_indices(positive, hard, clean, seed, epoch):
    count = len(positive)
    if not count or len(hard) + len(clean) < count:
        raise ValueError('Balanced training requires positives and enough distinct negatives')
    rng = Random(seed + epoch)
    hard_count = min(len(hard), max(count // 2, count - len(clean)))
    indices = list(positive) + rng.sample(hard, hard_count) + rng.sample(clean, count - hard_count)
    rng.shuffle(indices)
    return indices
