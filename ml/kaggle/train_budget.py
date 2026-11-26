"""YOLOX trainer with a wall-clock deadline and two durable checkpoints."""
import os
import json
from pathlib import Path
import shutil
import time
import numpy as np
import torch
from loguru import logger
from yolox.core import Trainer
from yolox.utils import adjust_status


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
        self.epoch_started = time.monotonic()

    def before_iter(self):
        if time.monotonic() >= float(os.environ['POTHOLE_DEADLINE']):
            raise TrainingBudgetReached('Training wall-clock deadline reached; evaluating last completed epoch')
        super().before_iter()

    def after_epoch(self):
        self.epoch_seconds = time.monotonic() - self.epoch_started
        super().after_epoch()
        directory = Path(self.file_name)
        progress = directory.parents[1] / 'resume_progress.json'
        temporary = progress.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(epochs=self.epoch+1, target_epoch=self.max_epoch,
                                             train_commit=os.environ['POTHOLE_TRAIN_COMMIT'])))
        temporary.replace(progress)
        # Retain a first-epoch fallback until validation can select a better checkpoint.
        if not (directory / 'best_ckpt.pth').exists():
            shutil.copyfile(directory / 'latest_ckpt.pth', directory / 'best_ckpt.pth')
        # The pinned trainer otherwise keeps an extra last_epoch checkpoint.
        for file in directory.glob('*_ckpt.pth'):
            if file.name not in ('latest_ckpt.pth', 'best_ckpt.pth'):
                file.unlink()

    def evaluate_and_save_model(self):
        started = time.monotonic()
        model = self.ema_model.ema if self.use_model_ema else self.model
        with adjust_status(model, training=False):
            ap, ap50, summary = self.exp.eval(model, self.evaluator, self.is_distributed)
        self.validation_seconds = time.monotonic() - started
        logger.info("\n{}", summary)
        self.tblogger.add_scalar('val/COCOAP50', ap50, self.epoch + 1)
        self.tblogger.add_scalar('val/COCOAP50_95', ap, self.epoch + 1)
        best = float(ap50) >= self.best_ap
        self.best_ap = max(float(ap50), self.best_ap)
        self.save_ckpt('last_epoch', best, ap=float(ap50))


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
    return latest, dict(epoch_seconds=getattr(trainer, 'epoch_seconds', 0),
                        validation_seconds=getattr(trainer, 'validation_seconds', 0))
