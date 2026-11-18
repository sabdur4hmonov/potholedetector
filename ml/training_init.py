"""Validate initialization provenance before downloading or loading a checkpoint."""

import json
from pathlib import Path
import re
from urllib.request import urlretrieve

from prepare_rdd2022 import sha256

PERMISSIVE_LICENSES = {"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause"}
SCRATCH = {"init": "scratch", "init_weights_sha256": None}


def initialization_receipt(pins, use_pretrained):
    if not use_pretrained:
        return SCRATCH.copy()
    weights = pins["nano_pretrained"]
    if weights["license"] not in PERMISSIVE_LICENSES:
        raise ValueError("Megvii checkpoint requires a verified permissive weights license")
    if not re.fullmatch(r"[0-9a-f]{64}", weights["sha256"]):
        raise ValueError("Missing pinned SHA-256 for the Megvii checkpoint")
    return {"init": "megvii_coco_pretrained", "init_weights_sha256": weights["sha256"]}


def verify_weights(path, expected):
    if sha256(path) != expected:
        raise ValueError("Megvii checkpoint SHA-256 mismatch")


def prepare_initial_weights(pins, target):
    receipt = initialization_receipt(pins, use_pretrained=True)
    expected = receipt["init_weights_sha256"]
    if not target.exists():
        partial = target.with_suffix(".partial")
        urlretrieve(pins["nano_pretrained"]["url"], partial)
        verify_weights(partial, expected)
        partial.replace(target)
    verify_weights(target, expected)


def load_training_receipt(path, pins):
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt == SCRATCH:
        return receipt
    if receipt == initialization_receipt(pins, use_pretrained=True):
        return receipt
    raise ValueError("Invalid training initialization receipt")
