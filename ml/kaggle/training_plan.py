"""Whole-epoch planning from the measured TRAIN-002 v7 timing profile."""

# V7 log: seven train epochs (median), one full validation, and submit to train start.
EPOCH_SECONDS = 313
VALIDATION_SECONDS = 34
SETUP_SECONDS = 816
EVAL_INTERVAL = 5
EXPORT_RESERVE_SECONDS = 105 * 60
TRAINING_WINDOW_SECONDS = 10 * 3600 + 15 * 60


def training_deadline_seconds(kernel_budget):
    return min(TRAINING_WINDOW_SECONDS, kernel_budget - EXPORT_RESERVE_SECONDS)


def estimate_seconds(epochs):
    # Across arbitrary resume offsets, include periodic validation and the
    # validation YOLOX forces at the final epoch of the cosine schedule.
    return epochs * EPOCH_SECONDS + (epochs // EVAL_INTERVAL + 1) * VALIDATION_SECONDS


def epochs_per_run(kernel_budget):
    window = min(TRAINING_WINDOW_SECONDS, kernel_budget) - SETUP_SECONDS - EXPORT_RESERVE_SECONDS
    epochs = max(0, window // EPOCH_SECONDS)
    while epochs and estimate_seconds(epochs) > window:
        epochs -= 1
    if not epochs:
        raise ValueError('Kernel budget cannot fit a complete training epoch')
    return epochs


def resume_target(start_epoch, kernel_budget):
    if type(start_epoch) is not int or start_epoch <= 0:
        raise ValueError('Resume requires a completed checkpoint epoch')
    return start_epoch + epochs_per_run(kernel_budget)
