#!/usr/bin/env python3
"""On-device detector contract: shared model-card/burst vectors, export loading, grouped
splits and whole-frame preprocessing in ml/train_on_device_detector.py. Needs only Pillow."""

import importlib.util
import io
import json
import pathlib
import re
import sys
import tempfile
import zipfile

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "ml" / "train_on_device_detector.py"
FIXTURE = ROOT / "android-app" / "android" / "app" / "src" / "test" / "resources" / \
    "ondevice-detector-v1.json"
CONTRACT = ROOT / "android-app" / "android" / "app" / "src" / "main" / "java" / "dev" / \
    "aiengg" / "potholereporter" / "drive" / "OnDeviceDetectorContract.kt"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


spec = importlib.util.spec_from_file_location("ondevice_tool", TOOL)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(tool)
fixture = json.loads(FIXTURE.read_text())

# ---- shared vectors (the Kotlin JVM test runs the same file) ----
mismatched = [case["name"] for case in fixture["specs"]
              if (tool.validate_model_card(case["card"]) is not None) != case["valid"]]
require(f"all {len(fixture['specs'])} shared model-card cases match", not mismatched)
baseline = fixture["specs"][0]
require("baseline card parses to the expected runnable fields",
        tool.validate_model_card(baseline["card"]) == {"model_file": "pothole_detector.tflite",
                                                       **baseline["expected"]})
bad_bursts = []
for case in fixture["bursts"]:
    got = tool.decide_burst([float(s) for s in case["scores"]], case["threshold"],
                            case["min_positive_frames"])
    want = {k: case[k] for k in ("decision", "positive_frames", "max_score")}
    if got != want:
        bad_bursts.append((case["name"], got))
require(f"all {len(fixture['bursts'])} shared burst decisions match", not bad_bursts)


# ---- export loading ----
def jpeg(color, size=(64, 48)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG", quality=95)
    return out.getvalue()


def write_export(path, entries, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("labels.json", json.dumps({"count": len(entries), "images": entries}))


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    red, blue, green = jpeg((200, 0, 0)), jpeg((0, 0, 200)), jpeg((0, 200, 0))
    entries = [
        {"path": "images/frame-1.jpg", "label": "pothole", "labelled_by": "owner", "drive_id": "d1"},
        {"path": "images/frame-2.jpg", "label": "failed_patch", "labelled_by": "owner", "drive_id": "d1"},
        {"path": "images/frame-3.jpg", "label": "pothole_cavity", "labelled_by": "owner"},
        {"path": "images/frame-4.jpg", "label": "pothole", "labelled_by": "model"},
        {"path": "images/../labels.json", "label": "pothole", "labelled_by": "owner"},
        {"path": "images/missing.jpg", "label": "pothole", "labelled_by": "owner"},
        {"path": "images/frame-5.jpg", "label": "maybe", "labelled_by": "owner"},
    ]
    files = {"images/frame-1.jpg": red, "images/frame-2.jpg": blue, "images/frame-3.jpg": green,
             "images/frame-4.jpg": red, "images/frame-5.jpg": red}
    write_export(tmp / "a.zip", entries, files)
    samples, skipped = tool.load_export(tmp / "a.zip")
    require("owner pothole labels are positives and other road damage is negative",
            [(s.owner_label, s.label) for s in samples]
            == [("pothole", 1), ("failed_patch", 0), ("pothole_cavity", 1)])
    require("non-owner, traversal, missing and unknown-label entries are skipped",
            len(skipped) == 4)
    require("frames group by drive, and an unassigned frame is its own group",
            samples[0].group == samples[1].group == "drive:d1"
            and samples[2].group.startswith("frame:"))

    write_export(tmp / "b.zip", [
        {"path": "images/x.jpg", "label": "not_pothole", "labelled_by": "owner", "drive_id": "d9"},
        {"path": "images/y.jpg", "label": "pothole", "labelled_by": "owner", "drive_id": "d9"},
    ], {"images/x.jpg": green, "images/y.jpg": red})
    merged, notes = tool.load_all([str(tmp / "a.zip"), str(tmp / "b.zip")])
    require("identical bytes with conflicting owner labels are excluded, duplicates count once",
            sorted(s.sha256 for s in merged)
            == sorted(tool.hashlib.sha256(b).hexdigest() for b in (red, blue))
            and sum("conflicting labels" in n for n in notes) == 1)

    try:
        with zipfile.ZipFile(tmp / "c.zip", "w") as archive:
            archive.writestr("images/a.jpg", red)
        tool.load_export(tmp / "c.zip")
        raised = False
    except ValueError:
        raised = True
    require("a ZIP without labels.json is refused", raised)

# ---- grouped split ----
fake = [tool.Sample(f"{i:064x}", b"", i % 2, "pothole", f"drive:{i % 40}", str(i))
        for i in range(400)]
splits = tool.assign_splits(fake, "seed", 0.15, 0.15)
owners = {}
for name, members in splits.items():
    for sample in members:
        owners.setdefault(sample.group, set()).add(name)
require("no drive appears in two splits", all(len(v) == 1 for v in owners.values()))
require("the split is deterministic for a seed",
        tool.assign_splits(fake, "seed", 0.15, 0.15) == splits
        and sum(len(v) for v in splits.values()) == 400)

# ---- whole-frame preprocessing ----
source = Image.new("RGB", (400, 100))
draw = ImageDraw.Draw(source)
draw.rectangle((0, 0, 199, 49), fill=(255, 0, 0))
draw.rectangle((200, 0, 399, 49), fill=(0, 255, 0))
draw.rectangle((0, 50, 199, 99), fill=(0, 0, 255))
draw.rectangle((200, 50, 399, 99), fill=(255, 255, 0))
encoded = io.BytesIO()
source.save(encoded, "PNG")
frame = tool.whole_frame_image(encoded.getvalue(), 64, 64)
corners = [frame.getpixel(p) for p in ((2, 2), (61, 2), (2, 61), (61, 61))]
require("the complete 4:1 frame maps edge to edge onto the square input",
        frame.size == (64, 64)
        and corners[0][0] > 220 and corners[0][1] < 40
        and corners[1][1] > 220 and corners[1][0] < 40
        and corners[2][2] > 220 and corners[2][0] < 40
        and corners[3][0] > 220 and corners[3][1] > 220)
rotated = io.BytesIO()
exif = Image.Exif()
exif[0x0112] = 6  # stored sideways; display needs a 90 degree turn
source.save(rotated, "JPEG", quality=95, exif=exif)
upright = tool.whole_frame_image(rotated.getvalue(), 64, 64)
require("EXIF orientation is corrected on the whole frame before resizing",
        upright.getpixel((61, 2))[0] > 180 and upright.getpixel((61, 2))[2] < 90)

# ---- threshold selection ----
scores = [0.95, 0.9, 0.7, 0.6, 0.4, 0.2]
labels = [1, 1, 0, 1, 0, 0]
require("threshold maximises recall while meeting the validation precision target",
        tool.choose_threshold(scores, labels, 0.95) == 0.9
        and tool.choose_threshold(scores, labels, 0.7) == 0.6
        and tool.choose_threshold([0.9, 0.8], [0, 0], 0.5) is None)

# ---- no crop paths ----
ml_source = TOOL.read_text()
kotlin_source = CONTRACT.read_text()
forbidden = ("RandomCrop", "RandomZoom", "RandomTranslation", "RandomRotation", "central_crop",
             "crop_to_bounding_box", "random_crop", "resize_with_crop_or_pad", "Image.crop",
             ".crop(", "createBitmap(")
require("training never crops, zooms, translates or rotates frames",
        not [t for t in forbidden if t in ml_source]
        and not re.search(r"\.resize\([^)]*box\s*=", ml_source))
require("the model card enforces whole-frame resize and no crop on both sides",
        'RESIZE = "whole_frame_stretch"' in ml_source
        and 'const val RESIZE = "whole_frame_stretch"' in kotlin_source
        and 'input.opt("crop") != false' in kotlin_source
        and 'spec.get("crop") is not False' in ml_source
        and "createBitmap" not in kotlin_source)
require("only a human can mark a model as validated on real roads",
        '"validated_on_real_roads": False,' in ml_source
        and '"validated_on_real_roads": True' not in ml_source)

print("on-device detector contract checks passed")
