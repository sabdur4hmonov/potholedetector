"""YOLOX trainer with a wall-clock deadline and two durable checkpoints."""
import os
from pathlib import Path
import shutil
import time
import numpy as np
import torch
from yolox.core import Trainer


class TrainingBudgetReached(Exception):
    pass


def checkpoint_globals():
    # COCO AP saved as best_ap by the pinned trainer can be a NumPy float64.
    return torch.serialization.safe_globals([np.core.multiarray.scalar, np.dtype, np.dtypes.Float64DType])


class BudgetTrainer(Trainer):
    def resume_train(self, model):
        with checkpoint_globals():
            return super().resume_train(model)

    def before_train(self):
        # Pinned YOLOX restores optimizer and start_epoch, then constructs the
        # scheduler from Exp.max_epoch. Apply its LR before the first resumed step.
        super().before_train()
        if self.start_epoch:
            lr = self.lr_scheduler.update_lr(self.start_epoch * self.max_iter)
            for group in self.optimizer.param_groups:
                group['lr'] = lr
            print(f'Resume scheduler: epoch {self.start_epoch}, target {self.max_epoch}, LR {lr:.6g}', flush=True)

    def before_epoch(self):
        if self.epoch >= self.stop_epoch:
            raise TrainingBudgetReached(f'Planned epoch {self.stop_epoch} completed; evaluating checkpoint')
        super().before_epoch()

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


def train(exp, args, stop_epoch):
    trainer = BudgetTrainer(exp, args)
    trainer.stop_epoch = stop_epoch
    try:
        trainer.train()
    except TrainingBudgetReached as error:
        print(str(error), flush=True)
    latest = Path(trainer.file_name) / 'latest_ckpt.pth'
    if not latest.is_file():
        raise RuntimeError('Budget ended before one complete epoch; no resumable checkpoint')
    return latest
