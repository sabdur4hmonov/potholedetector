"""YOLOX trainer with a wall-clock deadline and two durable checkpoints."""
import os
from pathlib import Path
import shutil
import time
from yolox.core import Trainer


class TrainingBudgetReached(Exception):
    pass


class BudgetTrainer(Trainer):
    def before_iter(self):
        if time.monotonic() >= float(os.environ['POTHOLE_DEADLINE']):
            raise TrainingBudgetReached('Training wall-clock deadline reached; evaluating last completed epoch')
        super().before_iter()

    def after_epoch(self):
        super().after_epoch()
        directory = Path(self.file_name)
        # Retain a first-epoch fallback until validation can select a better checkpoint.
        if not (directory / 'best_ckpt.pth').exists():
            shutil.copyfile(directory / 'latest_ckpt.pth', directory / 'best_ckpt.pth')
        # The pinned trainer otherwise keeps an extra last_epoch checkpoint.
        for file in directory.glob('*_ckpt.pth'):
            if file.name not in ('latest_ckpt.pth', 'best_ckpt.pth'):
                file.unlink()


def train(exp, args):
    trainer = BudgetTrainer(exp, args)
    try:
        trainer.train()
    except TrainingBudgetReached as error:
        print(str(error), flush=True)
    latest = Path(trainer.file_name) / 'latest_ckpt.pth'
    if not latest.is_file():
        raise RuntimeError('Budget ended before one complete epoch; no resumable checkpoint')
    return latest
