#!/usr/bin/env python3
"""Train the on-device full-frame pothole classifier from the app's labelled exports.

Input is one or more ``road-damage-dataset-*.zip`` files written by the app's
"Export dataset" action (``images/*.jpg`` plus ``labels.json``). Only owner labels are
used; the cloud model's opinion stored next to a label is never training ground truth.

Every model input is the complete camera frame: EXIF orientation is applied to the whole
image and the whole image is resized edge to edge to the model input size
(``whole_frame_stretch``). Nothing here crops, tiles, masks, pads away or selects a road
region, and the only augmentations are whole-frame horizontal flips and whole-frame
brightness/contrast changes.

Splits are grouped by drive so frames from one drive never appear in two splits. The
threshold is chosen on validation scores from the exported TFLite model itself and the
test split is reported once at that threshold. The written model card always says
``validated_on_real_roads: false``; only a human who has checked the model on real
Uzbekistan roads may change that.

Commands::

    python3 ml/train_on_device_detector.py inspect --export a.zip --export b.zip
    python3 ml/train_on_device_detector.py train --export a.zip --out ml/.out
    python3 ml/train_on_device_detector.py check-card ml/.out/pothole_detector.json

``inspect`` and ``check-card`` need only Pillow; ``train`` also needs TensorFlow
(``pip install tensorflow-cpu``). Exports contain private photos and GPS positions:
keep them and the output directory out of Git.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import posixpath
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageOps

SCHEMA_VERSION = "pothole-ondevice-model-v1"
TASK = "binary_full_frame_pothole"
RESIZE = "whole_frame_stretch"
LABELS = ["not_pothole", "pothole"]
MODEL_FILE = "pothole_detector.tflite"
CARD_FILE = "pothole_detector.json"
MIN_INPUT_DIMENSION = 32
MAX_INPUT_DIMENSION = 640
MAX_MIN_POSITIVE_FRAMES = 8
MODEL_FILE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}\.tflite$")

# Owner labels the app accepts (static/standalone.js /api/reports/:id/label). Other road
# damage is a negative: this is a pothole detector, not a generic road-damage detector.
POSITIVE_LABELS = frozenset({"pothole", "pothole_cavity"})
NEGATIVE_LABELS = frozenset({
    "not_pothole", "not_reportable", "failed_patch", "surface_breakup",
    "rut_or_depression", "other_road_damage",
})
MAX_EXPORT_IMAGE_BYTES = 25 * 1024 * 1024
MAX_SOURCE_PIXELS = 40_000_000
SPLITS = ("train", "validation", "test")


# ---------- model card contract (mirrors OnDeviceDetectorContract.kt) ----------

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_model_card(card) -> Optional[dict]:
    """Returns the runnable fields, or None for a card the app must refuse."""
    if not isinstance(card, dict):
        return None
    if card.get("schema_version") != SCHEMA_VERSION or card.get("task") != TASK:
        return None
    if card.get("labels") != LABELS:
        return None
    model_file = card.get("model_file")
    if not isinstance(model_file, str) or not MODEL_FILE_PATTERN.match(model_file) \
            or ".." in model_file:
        return None
    spec = card.get("input")
    if not isinstance(spec, dict):
        return None
    width, height = spec.get("width"), spec.get("height")
    if not (_is_int(width) and _is_int(height)):
        return None
    if not (MIN_INPUT_DIMENSION <= width <= MAX_INPUT_DIMENSION
            and MIN_INPUT_DIMENSION <= height <= MAX_INPUT_DIMENSION):
        return None
    if not (_is_int(spec.get("channels")) and spec.get("channels") == 3
            and spec.get("color_order") == "RGB" and spec.get("layout") == "NHWC"
            and spec.get("dtype") == "float32"):
        return None
    value_range = spec.get("value_range")
    if not (isinstance(value_range, list) and len(value_range) == 2
            and all(_is_number(v) for v in value_range)
            and float(value_range[0]) == 0.0 and float(value_range[1]) == 255.0):
        return None
    if spec.get("resize") != RESIZE or spec.get("crop") is not False:
        return None
    output = card.get("output")
    if not isinstance(output, dict) or output.get("kind") != "sigmoid_pothole_probability":
        return None
    decision = card.get("decision")
    if not isinstance(decision, dict):
        return None
    threshold = decision.get("threshold")
    if not _is_number(threshold) or not math.isfinite(threshold) \
            or not 0.0 < float(threshold) < 1.0:
        return None
    min_positive = decision.get("min_positive_frames")
    if not _is_int(min_positive) or not 1 <= min_positive <= MAX_MIN_POSITIVE_FRAMES:
        return None
    validation = card.get("validation")
    if not isinstance(validation, dict):
        return None
    field_validated = validation.get("validated_on_real_roads")
    if not isinstance(field_validated, bool):
        return None
    if validation.get("smoke_test_only") is not False:
        return None
    return {
        "model_file": model_file, "input_width": width, "input_height": height,
        "threshold": float(threshold), "min_positive_frames": min_positive,
        "field_validated": field_validated,
    }


def decide_burst(scores: Sequence[float], threshold: float, min_positive_frames: int) -> dict:
    """One score per complete chronological frame; mirrors decideBurst in Kotlin."""
    values = [float(s) for s in scores]
    if any(not math.isfinite(s) or s < 0.0 or s > 1.0 for s in values):
        return {"decision": "invalid_score", "positive_frames": 0, "max_score": None}
    positives = sum(1 for s in values if s >= threshold)
    if len(values) < min_positive_frames:
        decision = "insufficient_frames"
    elif positives >= min_positive_frames:
        decision = "accept"
    else:
        decision = "reject"
    return {"decision": decision, "positive_frames": positives,
            "max_score": max(values) if values else None}


# ---------- dataset ----------

@dataclass(frozen=True)
class Sample:
    sha256: str
    data: bytes
    label: int
    owner_label: str
    group: str
    source: str


def label_value(owner_label) -> Optional[int]:
    if owner_label in POSITIVE_LABELS:
        return 1
    if owner_label in NEGATIVE_LABELS:
        return 0
    return None


def _safe_member(name) -> Optional[str]:
    if not isinstance(name, str) or "\\" in name or name.startswith("/"):
        return None
    normal = posixpath.normpath(name)
    if normal != name or not normal.startswith("images/") or ".." in normal.split("/"):
        return None
    return normal


def load_export(path: Path) -> Tuple[List[Sample], List[str]]:
    """Reads one app export. Returns samples and human-readable skip reasons."""
    samples: List[Sample] = []
    skipped: List[str] = []
    with zipfile.ZipFile(path) as archive:
        try:
            index = json.loads(archive.read("labels.json").decode("utf-8"))
        except KeyError:
            raise ValueError(f"{path}: labels.json is missing; is this an app dataset export?")
        images = index.get("images") if isinstance(index, dict) else None
        if not isinstance(images, list):
            raise ValueError(f"{path}: labels.json has no images list")
        names = set(archive.namelist())
        for position, entry in enumerate(images):
            where = f"{path.name}#{position}"
            if not isinstance(entry, dict):
                skipped.append(f"{where}: not an object")
                continue
            if entry.get("labelled_by") != "owner":
                skipped.append(f"{where}: not an owner label")
                continue
            label = label_value(entry.get("label"))
            if label is None:
                skipped.append(f"{where}: unknown label {entry.get('label')!r}")
                continue
            member = _safe_member(entry.get("path"))
            if member is None or member not in names:
                skipped.append(f"{where}: unsafe or missing image path")
                continue
            if archive.getinfo(member).file_size > MAX_EXPORT_IMAGE_BYTES:
                skipped.append(f"{where}: image larger than {MAX_EXPORT_IMAGE_BYTES} bytes")
                continue
            data = archive.read(member)
            drive = entry.get("drive_id")
            digest = hashlib.sha256(data).hexdigest()
            group = f"drive:{drive}" if isinstance(drive, str) and drive else f"frame:{digest}"
            samples.append(Sample(digest, data, label, entry["label"], group, where))
    return samples, skipped


def dedupe(samples: Iterable[Sample]) -> Tuple[List[Sample], List[str]]:
    """Identical image bytes count once; conflicting owner labels exclude the image."""
    by_hash: Dict[str, List[Sample]] = {}
    for sample in samples:
        by_hash.setdefault(sample.sha256, []).append(sample)
    kept: List[Sample] = []
    conflicts: List[str] = []
    for digest in sorted(by_hash):
        copies = by_hash[digest]
        if len({c.label for c in copies}) > 1:
            conflicts.append(f"{digest[:12]}: conflicting labels in "
                             + ", ".join(c.source for c in copies))
            continue
        kept.append(sorted(copies, key=lambda c: c.source)[0])
    return kept, conflicts


def split_of(group: str, seed: str, validation: float, test: float) -> str:
    """Deterministic grouped split: one drive is always wholly in one split."""
    value = int(hashlib.sha256(f"{seed}\0{group}".encode()).hexdigest()[:12], 16) / float(1 << 48)
    if value < test:
        return "test"
    if value < test + validation:
        return "validation"
    return "train"


def assign_splits(samples: Sequence[Sample], seed: str, validation: float,
                  test: float) -> Dict[str, List[Sample]]:
    out: Dict[str, List[Sample]] = {name: [] for name in SPLITS}
    for sample in samples:
        out[split_of(sample.group, seed, validation, test)].append(sample)
    return out


def class_counts(samples: Sequence[Sample]) -> Dict[str, int]:
    return {"pothole": sum(s.label for s in samples),
            "not_pothole": sum(1 - s.label for s in samples)}


def dataset_manifest_sha256(splits: Dict[str, List[Sample]]) -> str:
    rows = sorted(f"{name}\t{s.sha256}\t{s.label}" for name in SPLITS for s in splits[name])
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def whole_frame_image(data: bytes, width: int, height: int) -> Image.Image:
    """Decodes one image and resizes the complete, orientation-corrected frame."""
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_SOURCE_PIXELS:
            raise ValueError("image exceeds the decode pixel budget")
        frame = ImageOps.exif_transpose(source).convert("RGB")
        # No box argument: the entire source rectangle maps onto the entire output.
        return frame.resize((width, height), Image.Resampling.BILINEAR)


def whole_frame_pixels(data: bytes, width: int, height: int):
    import numpy as np

    return np.asarray(whole_frame_image(data, width, height), dtype=np.uint8)


# ---------- metrics ----------

def confusion(scores: Sequence[float], labels: Sequence[int], threshold: float) -> dict:
    tp = sum(1 for s, y in zip(scores, labels) if y == 1 and s >= threshold)
    fp = sum(1 for s, y in zip(scores, labels) if y == 0 and s >= threshold)
    fn = sum(1 for s, y in zip(scores, labels) if y == 1 and s < threshold)
    tn = sum(1 for s, y in zip(scores, labels) if y == 0 and s < threshold)
    return {
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else None,
    }


def choose_threshold(scores: Sequence[float], labels: Sequence[int],
                     min_precision: float) -> Optional[float]:
    """Lowest threshold whose validation precision meets the target (maximises recall)."""
    best = None
    for candidate in sorted(set(float(s) for s in scores), reverse=True):
        stats = confusion(scores, labels, candidate)
        if stats["true_positive"] == 0:
            continue
        if stats["precision"] is not None and stats["precision"] >= min_precision:
            best = candidate
    if best is None:
        return None
    return min(max(best, 0.001), 0.999)


# ---------- commands ----------

def load_all(exports: Sequence[str]) -> Tuple[List[Sample], List[str]]:
    collected: List[Sample] = []
    notes: List[str] = []
    for name in exports:
        samples, skipped = load_export(Path(name))
        collected.extend(samples)
        notes.extend(skipped)
    kept, conflicts = dedupe(collected)
    return kept, notes + conflicts


def summarize(args) -> Tuple[Dict[str, List[Sample]], dict]:
    samples, notes = load_all(args.export)
    splits = assign_splits(samples, args.seed, args.validation_fraction, args.test_fraction)
    summary = {
        "images": len(samples),
        "skipped_or_conflicting": len(notes),
        "notes": notes[:50],
        "splits": {name: {"groups": len({s.group for s in splits[name]}),
                          **class_counts(splits[name])} for name in SPLITS},
        "dataset_manifest_sha256": dataset_manifest_sha256(splits),
    }
    return splits, summary


def readiness_problems(splits: Dict[str, List[Sample]], min_per_class: int) -> List[str]:
    problems = []
    for name in SPLITS:
        counts = class_counts(splits[name])
        need = min_per_class if name == "train" else max(1, min_per_class // 4)
        for label, count in counts.items():
            if count < need:
                problems.append(f"{name} has {count} {label} images; at least {need} needed")
    return problems


def cmd_inspect(args) -> int:
    splits, summary = summarize(args)
    summary["readiness_problems"] = readiness_problems(splits, args.min_per_class)
    print(json.dumps(summary, indent=1))
    return 0


def cmd_check_card(args) -> int:
    card = json.loads(Path(args.card).read_text())
    spec = validate_model_card(card)
    print(json.dumps({"runnable": spec is not None, "spec": spec}, indent=1))
    return 0 if spec is not None else 1


def _arrays(samples: Sequence[Sample], width: int, height: int):
    import numpy as np

    images, labels = [], []
    for sample in samples:
        try:
            images.append(whole_frame_pixels(sample.data, width, height))
            labels.append(sample.label)
        except Exception as error:  # an undecodable export image is skipped, not guessed
            print(f"skipping {sample.source}: {error}", file=sys.stderr)
    if not images:
        return np.zeros((0, height, width, 3), np.uint8), np.zeros((0,), np.float32)
    return np.stack(images), np.asarray(labels, np.float32)


def _tflite_scores(model_bytes: bytes, images) -> List[float]:
    import numpy as np
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_content=model_bytes)
    interpreter.allocate_tensors()
    feed = interpreter.get_input_details()[0]
    fetch = interpreter.get_output_details()[0]
    scores = []
    for image in images:
        interpreter.set_tensor(feed["index"], image[None].astype(np.float32))
        interpreter.invoke()
        scores.append(float(interpreter.get_tensor(fetch["index"]).reshape(-1)[0]))
    return scores


def cmd_train(args) -> int:
    splits, summary = summarize(args)
    problems = readiness_problems(splits, args.min_per_class)
    if problems and not args.smoke_test:
        print(json.dumps({"refused": "not enough labelled data", "problems": problems,
                          "summary": summary}, indent=1))
        return 2

    import numpy as np
    import tensorflow as tf

    tf.keras.utils.set_random_seed(args.random_seed)
    width = height = args.input_size
    x_train, y_train = _arrays(splits["train"], width, height)
    x_val, y_val = _arrays(splits["validation"], width, height)
    x_test, y_test = _arrays(splits["test"], width, height)
    if len(x_train) == 0 or len(x_val) == 0 or len(x_test) == 0:
        print("refused: a split has no decodable images", file=sys.stderr)
        return 2

    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(height, width, 3), include_top=False, pooling="avg",
        weights=None if args.weights == "none" else "imagenet",
        include_preprocessing=True,  # the model itself maps 0..255 RGB to its own range
    )
    base.trainable = False
    inputs = tf.keras.Input((height, width, 3), dtype=tf.float32)
    features = base(inputs, training=False)
    features = tf.keras.layers.Dropout(0.2)(features)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid")(features)
    model = tf.keras.Model(inputs, outputs)

    def whole_frame_augment(image, label):
        # Whole-frame only: flip and photometric changes keep every pixel of the view.
        image = tf.image.random_flip_left_right(image)
        image = tf.image.random_brightness(image, 25.0)
        image = tf.image.random_contrast(image, 0.8, 1.2)
        return tf.clip_by_value(image, 0.0, 255.0), label

    positives = float(y_train.sum())
    negatives = float(len(y_train) - positives)
    class_weight = {0: len(y_train) / (2 * max(negatives, 1.0)),
                    1: len(y_train) / (2 * max(positives, 1.0))}
    train_ds = (tf.data.Dataset.from_tensor_slices((x_train.astype(np.float32), y_train))
                .shuffle(len(x_train), seed=args.random_seed)
                .map(whole_frame_augment).batch(args.batch_size))
    val_ds = tf.data.Dataset.from_tensor_slices(
        (x_val.astype(np.float32), y_val)).batch(args.batch_size)

    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy",
                  metrics=[tf.keras.metrics.AUC(name="auc")])
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs,
              class_weight=class_weight, verbose=2)
    if args.fine_tune_epochs > 0:
        base.trainable = True
        for layer in base.layers[:-args.fine_tune_layers]:
            layer.trainable = False
        for layer in base.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="binary_crossentropy",
                      metrics=[tf.keras.metrics.AUC(name="auc")])
        model.fit(train_ds, validation_data=val_ds, epochs=args.fine_tune_epochs,
                  class_weight=class_weight, verbose=2)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]  # int8 weights, float32 I/O
    model_bytes = converter.convert()

    # Threshold and every reported number come from the exported model, not from Keras.
    val_scores = _tflite_scores(model_bytes, x_val)
    test_scores = _tflite_scores(model_bytes, x_test)
    threshold = choose_threshold(val_scores, y_val.astype(int).tolist(), args.min_precision)
    if threshold is None:
        if not args.smoke_test:
            print(f"refused: no threshold reaches validation precision {args.min_precision}",
                  file=sys.stderr)
            return 3
        threshold = 0.5

    card = {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "labels": LABELS,
        "model_file": MODEL_FILE,
        "model_sha256": hashlib.sha256(model_bytes).hexdigest(),
        "model_bytes": len(model_bytes),
        "input": {"width": width, "height": height, "channels": 3, "color_order": "RGB",
                  "layout": "NHWC", "dtype": "float32", "value_range": [0, 255],
                  "resize": RESIZE, "crop": False},
        "output": {"kind": "sigmoid_pothole_probability"},
        "decision": {"threshold": round(threshold, 6),
                     "min_positive_frames": args.min_positive_frames,
                     "threshold_rule": f"lowest validation threshold with precision >= "
                                       f"{args.min_precision}"},
        "validation": {
            "validated_on_real_roads": False,
            "smoke_test_only": bool(args.smoke_test),
            "per_frame_validation": confusion(val_scores, y_val.astype(int).tolist(), threshold),
            "per_frame_test": confusion(test_scores, y_test.astype(int).tolist(), threshold),
            "note": "Per-frame numbers on the owner's held-out drives only. Not a claim of "
                    "real-world accuracy; Drive mode also requires burst consistency.",
        },
        "training": {
            "architecture": "MobileNetV3Small + global average pooling + sigmoid",
            "base_weights": "none" if args.weights == "none"
                            else "Keras Applications ImageNet MobileNetV3Small",
            "licence_review": "pending human review of base weights and training data",
            "tensorflow": tf.__version__,
            "epochs": args.epochs, "fine_tune_epochs": args.fine_tune_epochs,
            "seed": args.seed, "random_seed": args.random_seed,
            "augmentation": ["whole_frame_horizontal_flip", "whole_frame_brightness",
                             "whole_frame_contrast"],
            "dataset": summary["splits"],
            "dataset_manifest_sha256": summary["dataset_manifest_sha256"],
        },
    }
    if not args.smoke_test and validate_model_card(card) is None:
        print("internal error: written card would be refused by the app", file=sys.stderr)
        return 4
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / MODEL_FILE).write_bytes(model_bytes)
    (out / CARD_FILE).write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps({"written": str(out), "threshold": card["decision"]["threshold"],
                      "validation": card["validation"]["per_frame_validation"],
                      "test": card["validation"]["per_frame_test"]}, indent=1))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = root.add_subparsers(dest="command", required=True)

    def data_args(command):
        command.add_argument("--export", action="append", required=True,
                             help="app dataset export ZIP (repeatable)")
        command.add_argument("--seed", default="pothole-ondevice-v1",
                             help="grouped split seed")
        command.add_argument("--validation-fraction", type=float, default=0.15)
        command.add_argument("--test-fraction", type=float, default=0.15)
        command.add_argument("--min-per-class", type=int, default=40)

    inspect = commands.add_parser("inspect", help="count labels and splits; no TensorFlow")
    data_args(inspect)
    inspect.set_defaults(run=cmd_inspect)

    train = commands.add_parser("train", help="train and export TFLite + model card")
    data_args(train)
    train.add_argument("--out", required=True)
    train.add_argument("--input-size", type=int, default=224,
                       choices=range(MIN_INPUT_DIMENSION, MAX_INPUT_DIMENSION + 1),
                       metavar="N")
    train.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    train.add_argument("--epochs", type=int, default=12)
    train.add_argument("--fine-tune-epochs", type=int, default=0)
    train.add_argument("--fine-tune-layers", type=int, default=30)
    train.add_argument("--batch-size", type=int, default=16)
    train.add_argument("--min-precision", type=float, default=0.95)
    train.add_argument("--min-positive-frames", type=int, default=2,
                       choices=range(1, MAX_MIN_POSITIVE_FRAMES + 1), metavar="N")
    train.add_argument("--random-seed", type=int, default=7)
    train.add_argument("--smoke-test", action="store_true",
                       help="pipeline check on tiny data; the card is marked unrunnable")
    train.set_defaults(run=cmd_train)

    check = commands.add_parser("check-card", help="would the app accept this model card?")
    check.add_argument("card")
    check.set_defaults(run=cmd_check_card)
    return root


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
