# Model weights and attribution

The application code retains its existing MIT license. The owner's selected distribution license for future trained `pothole_yolox_nano.onnx` weights is **Creative Commons Attribution-ShareAlike 4.0 International**, separately from the app. License: https://creativecommons.org/licenses/by-sa/4.0/legalcode . Retain attribution, note training/modification and distribute adapted model weights under the same license. No model weights are currently included and no accuracy claim is made.

Training source: **RDD2022**, Deeksha Arya, Hiroya Maeda, Sanjay Kumar Ghosh, Durga Toshniwal, Yoshihide Sekimoto and dataset contributors; “RDD2022: A multi-national image dataset for automatic Road Damage Detection”, 2022, https://arxiv.org/abs/2209.08538 ; official dataset https://doi.org/10.6084/m9.figshare.21431547 . D40 potholes only, other annotated damage/negative images retained, China_Drone excluded. Whole-frame conversion and training are modifications.

Source-license discrepancy: the task calls RDD2022 CC BY-SA 4.0, but the official Figshare article API (`https://api.figshare.com/v2/articles/21431547`, checked for ML-DETECT-001) returns **CC BY 4.0**, https://creativecommons.org/licenses/by/4.0/ . This document does not falsely attribute ShareAlike to that record; CC BY-SA is the owner's selected license for the resulting model. Review the downloaded archive's own notices before distributing trained weights, retain all contributor notices and the measured dataset pin. Owner-added data requires the owner's rights/authorization and must retain its provenance.

Architecture/training implementation: **YOLOX**, Copyright Megvii Inc. and affiliates, Apache License 2.0, pinned commit `6ddff4824372906469a7fae2dc3206c7aa4bbaee`, https://github.com/Megvii-BaseDetection/YOLOX . No third-party pretrained weights or Ultralytics code are used.

Runtime: **ONNX Runtime**, Microsoft, MIT, Android/JVM version **1.24.3**, https://github.com/microsoft/onnxruntime . This runtime's MIT license is independent of model and dataset licenses.
