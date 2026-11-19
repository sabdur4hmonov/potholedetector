"""Shared pinned YOLOX installation for hosted GPU runners and Colab."""
import json
from pathlib import Path
import subprocess
import sys


def install_torch():
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'torch==2.6.0', 'torchvision==0.21.0',
                    '--index-url', 'https://download.pytorch.org/whl/cu124'], check=True)


def install_yolox(root, checkout):
    pins = json.loads((root / 'ml/pins.json').read_text())
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'ml/requirements-colab.txt'),
                    'setuptools==75.8.0', 'wheel==0.45.1', 'packaging==24.2'], check=True)
    if not checkout.exists():
        subprocess.run(['git', 'clone', 'https://github.com/Megvii-BaseDetection/YOLOX.git', str(checkout)], check=True)
    subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', pins['yolox_commit']], check=True)
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != pins['yolox_commit']:
        raise ValueError('YOLOX revision mismatch')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', str(checkout)], check=True)
