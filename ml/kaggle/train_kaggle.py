"""Single uploaded bootstrap. The local launcher substitutes the pushed commit before upload."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import time

TRAIN_COMMIT = "__PUSHED_TRAIN_COMMIT__"
RUN_BUDGET_SECONDS = 43_200
REPOSITORY = "https://github.com/sabdur4hmonov/potholedetector.git"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    started = time.monotonic()
    if args.dry_run:
        root = Path(__file__).resolve().parents[2]
    else:
        subprocess.run(['nvidia-smi'], check=True)
        subprocess.run([sys.executable, '-c', 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"'], check=True)
        if not re.fullmatch(r'[0-9a-f]{40}', TRAIN_COMMIT):
            raise ValueError('Launcher must supply an exact pushed train-001 commit')
        root = Path('/kaggle/tmp/pothole')
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--no-checkout', REPOSITORY, str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'checkout', '--detach', TRAIN_COMMIT], check=True)
        actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != TRAIN_COMMIT:
            raise ValueError('Training source revision mismatch')
    sys.path.insert(0, str(root / 'ml' / 'kaggle'))
    from cloud_run import run, dry_run
    if args.dry_run:
        dry_run(root)
    else:
        run(root, TRAIN_COMMIT, started, RUN_BUDGET_SECONDS)


if __name__ == '__main__':
    main()
