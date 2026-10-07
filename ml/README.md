# On-device pothole detector: training

This folder turns frames you labelled in the app into a small model that can run inside
the phone (TensorFlow Lite, about 1 MB). **No trained model ships yet.** None exists
until labelled Uzbekistan road frames are available, and the app has no LiteRT runtime
wired into Drive mode yet. Both are the next tasks (see `PROJECT_MASTER/NEXT_STEPS.md`).

## What the model is

- A binary classifier over the **complete camera frame**: `pothole` or `not_pothole`.
  The whole, orientation-corrected frame is resized edge to edge to 224×224
  (`whole_frame_stretch`). Nothing is cropped, tiled, masked or reduced to a road band
  (see `AGENTS.md`). Training augmentation is whole-frame horizontal flip and whole-frame
  brightness/contrast only.
- Base network: Keras `MobileNetV3Small` with ImageNet weights (Apache-2.0 Keras
  Applications), not an AGPL detector. The licence of the base weights and of your
  training data still needs a human review before any release.
- A Drive burst is accepted only when at least `min_positive_frames` (default 2) complete
  frames score at or above the threshold. The model cannot estimate pothole size.

## 1. Collect labelled frames in the app

1. Settings: turn on "Save every analysed frame to the device" ("Har bir tahlil qilingan
   kadrni qurilmaga saqlash"), or use Photo for manual reports.
2. "Review and label frames" ("Kadrlarni ko'rib chiqish va belgilash"): tap Pothole /
   Not pothole ("Chuqur" / "Chuqur emas") for each frame.
3. "Export labelled dataset": you get `road-damage-dataset-<time>.zip` (`images/` +
   `labels.json`). Only your own labels are used; the cloud model's opinion is never
   treated as truth. Other road-damage labels count as **not** a pothole.

Note: Drive mode currently refuses to start without a cloud (OpenAI) key
(`DriveModePlugin`). Without a key, the frames you can label come from Photo reports.
Letting Drive mode record and save frames for labelling without a key is a separate task.

The ZIP holds private photos and GPS positions. Keep it out of Git (`.gitignore` already
excludes `road-damage-dataset-*.zip`, `ml/.exports/` and `ml/.out/`).

Aim for frames from many different drives, roads, times of day and weather. Splits are
grouped by drive, so one drive never appears in both training and testing. The default
minimum is 40 frames per class in training and 10 per class in validation and test;
several hundred per class, including hard negatives (patches, manholes, shadows,
speed bumps, wet asphalt), is a more realistic starting point.

## 2. Check the data (no TensorFlow needed)

```bash
python3 ml/train_on_device_detector.py inspect --export ml/.exports/a.zip --export ml/.exports/b.zip
```

It prints counts per split and any skipped, unsafe or conflicting entries.

## 3. Train (CPU is enough)

```bash
python3 -m venv ml/.venv && ml/.venv/bin/pip install tensorflow-cpu pillow numpy
ml/.venv/bin/python ml/train_on_device_detector.py train \
  --export ml/.exports/a.zip --export ml/.exports/b.zip --out ml/.out
```

Windows PowerShell: use `ml\.venv\Scripts\python.exe` with the same arguments.
Useful options: `--epochs 12`, `--fine-tune-epochs 4`, `--min-precision 0.95`,
`--min-positive-frames 2`. Training refuses to write a model when there is not enough
data or when no threshold reaches the validation precision target.

Output in `ml/.out/`: `pothole_detector.tflite` and `pothole_detector.json` (the model
card). The threshold and every number in the card come from the exported TFLite model:
chosen on the validation split and reported once on the test split. These are per-frame
numbers on your own held-out drives, **not** a claim of real-world accuracy.

`--smoke-test` checks the pipeline on tiny or synthetic data; such a card is marked
`smoke_test_only: true` and the app refuses it.

## 4. Check the card

```bash
python3 ml/train_on_device_detector.py check-card ml/.out/pothole_detector.json
```

The same rules run in the app (`OnDeviceDetectorContract.kt`). Both sides share the
vectors in `android-app/android/app/src/test/resources/ondevice-detector-v1.json`. The
card always says `validated_on_real_roads: false`. Only a person who has driven with the
model on real Uzbekistan roads and checked its reports may change that.
