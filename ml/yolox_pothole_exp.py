"""One complete image per sample; no spatial-subset augmentation, including no-aug epochs."""
import os
import numpy as np
import torch.nn as nn
from torch.utils.data import DataLoader
from yolox.exp import Exp as BaseExp


class FullFrameTransform:
    def __call__(self, image, targets, size):
        from yolox.data.data_augment import preproc
        image, ratio = preproc(image, size)  # Whole-frame BGR 0..255, top-left letterbox.
        if len(targets) > 120:
            raise ValueError('Too many boxes; never silently truncate labels')
        labels = np.zeros((120, 5), dtype=np.float32)
        if len(targets):
            labels[:len(targets), 0] = targets[:, 4]
            labels[:len(targets), 1:3] = (targets[:, :2] + targets[:, 2:4]) * .5 * ratio
            labels[:len(targets), 3:5] = (targets[:, 2:4] - targets[:, :2]) * ratio
        return image, labels


class FullFrameLoader(DataLoader):
    def close_mosaic(self):
        # YOLOX trainer calls this in its last epoch. No mosaic was installed.
        pass


class Exp(BaseExp):
    def __init__(self):
        super().__init__()
        self.num_classes = 1
        self.depth, self.width = .33, .25
        self.input_size = self.test_size = (416, 416)
        self.multiscale_range = 0
        self.random_size = (13, 13)
        self.enable_mosaic = False
        self.mosaic_prob = 0
        self.enable_mixup = False
        self.mixup_prob = 0
        self.translate = 0
        self.degrees = 0
        self.shear = 0
        self.mosaic_scale = self.mixup_scale = (1.0, 1.0)
        self.data_dir = os.environ.get('POTHOLE_DATA', '/content/pothole/ml/data')
        self.train_ann, self.val_ann, self.test_ann = 'train.json', 'val.json', 'test.json'
        self.seed = 20221105
        self.max_epoch = int(os.environ.get('POTHOLE_EPOCHS', '40'))
        self.no_aug_epochs = 0  # Trainer must never replace FullFrameTransform.
        self.eval_interval = 5
        self.data_num_workers = 2
        self.output_dir = os.environ.get('POTHOLE_CHECKPOINTS', '/content/drive/MyDrive/pothole-yolox')
        self.exp_name = 'pothole_nano'

    def get_model(self):
        from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
        if 'model' not in self.__dict__:
            channels = [256, 512, 1024]
            self.model = YOLOX(YOLOPAFPN(self.depth, self.width, in_channels=channels, depthwise=True),
                               YOLOXHead(1, self.width, in_channels=channels, depthwise=True))
            for m in self.model.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eps, m.momentum = 1e-3, .03
            self.model.head.initialize_biases(1e-2)
        return self.model

    def get_dataset(self, cache=False, cache_type='ram'):
        from yolox.data import COCODataset
        return COCODataset(data_dir=self.data_dir, json_file=self.train_ann, name='images',
                           img_size=self.input_size, preproc=FullFrameTransform(), cache=False)

    def get_data_loader(self, batch_size, is_distributed, no_aug=False, cache_img=None):
        from yolox.data import InfiniteSampler, worker_init_reset_seed
        if is_distributed:
            raise ValueError('This notebook uses one Colab GPU')
        self.dataset = self.get_dataset()
        sampler = InfiniteSampler(len(self.dataset), seed=self.seed)
        return FullFrameLoader(self.dataset, num_workers=self.data_num_workers, pin_memory=True,
                               sampler=sampler, batch_size=batch_size, worker_init_fn=worker_init_reset_seed)

    def get_eval_dataset(self, testdev=False, legacy=False):
        from yolox.data import COCODataset, ValTransform
        return COCODataset(data_dir=self.data_dir, json_file=self.test_ann if testdev else self.val_ann,
                           name='images', img_size=self.test_size, preproc=ValTransform(legacy=False))
