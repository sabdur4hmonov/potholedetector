# Telefon modeli / On-device model

## O‘zbekcha

Model hali o‘qitilmagan. Ilova model bo‘lmasa sensor, ogohlantirish, Photo va ixtiyoriy cloud bilan ishlaydi. Aniqlik yoki yo‘ldagi ishlash haqida da’vo yo‘q.

1. `ml/train_pothole_yolox.ipynb` ni Google Colab’da oching (GitHub’dan `ondevice-ml` tarmog‘ini tanlang yoki notebookni yuklang).
2. **Runtime → Change runtime type → GPU** ni tanlang, **Run all** ni bosing. Colab oynasida Google Drive’ni ulang; token/parollarni repoga yozmang.
3. Rasmiy RDD2022 arxivi taxminan 13.3 GB; ochilgan ma’lumot va checkpointlar uchun yetarli bo‘sh joy kerak. GPU va bepul sessiya vaqti o‘zgarishi mumkin. Sukut 40 epoch, batch 16; xotira yetmasa batchni kamaytiring. Checkpointlar `MyDrive/pothole-yolox/pothole_nano/` da saqlanadi; yangi sessiyada notebookni boshidan ishga tushirsangiz davom etadi.
4. Birinchi yuklash SHA-256 ni chiqaradi va `pins.json` ga yozadi; saqlangan pin boshqa yuklashda mos kelmasa jarayon to‘xtaydi. Bu birinchi pin mustaqil nashriyot tekshiruvi degani emas. Notebook pin va haqiqiy statistika nusxasini Drive’da saqlaydi.
5. Validation’da precision kamida 0.80 bo‘lgan eng yaxshi F1 chegarasi tanlanadi. Mos chegara bo‘lmasa eksport to‘xtaydi: ma’lumotni ko‘rib chiqish, ko‘proq o‘qitish yoki alohida Tiny tajribasi kerak. Test bo‘yicha precision/recall/F1 va mamlakatlar recall’i chiqariladi. 20 test rasmida PyTorch/ONNX tengligi tekshiriladi.
6. Yuklangan `pothole_yolox_nano.onnx` va `pothole_model.json` fayllarini **`android-app/android/app/src/main/assets/ml/`** ichiga qo‘ying. Pin/statistikani ham saqlang va Codex/Claude’ga model tayyorligini ayting. Vazn, dataset, checkpoint va APK’ni Git’ga qo‘shmang.
7. Yig‘ilgandan keyin avval to‘xtab turgan holatda, so‘ng ehtiyotkor amaliy safarda tekshiring. O‘qitish statistikasi O‘zbekiston yo‘llaridagi aniqlikni isbotlamaydi.

O‘z yo‘llaringiz: hisobotdagi **To‘g‘ri/Noto‘g‘ri** ni bosing, Settings’dan dataset ZIP’ni qo‘lda eksport qiling. GPS sukut bo‘yicha yo‘q; faqat tegishli katak belgilansa qo‘shiladi. ZIP’ni Colab’ga `/content/owner_export.zip` deb yuklash kifoya (`prepare_rdd2022.py --extra ...` ham mavjud). **No** rasmlari manfiy misollar sifatida ishlatiladi. **Yes** butun rasm yorlig‘i obyektdagi to‘rtburchak koordinatalarini bildirmaydi: `labels.json` ga inson belgilagan `boxes: [[x,y,width,height], ...]` (to‘liq, orientatsiyasi tuzatilgan rasm koordinatalari) kerak. Bunday belgilarsiz musbat rasmlar `owner_positive_review.json` da kutadi; ular manfiyga aylantirilmaydi va modelning o‘z taxmini ground truth qilinmaydi.

## English

No model has been trained or field-validated. The absent-model build preserves sensor warnings, Photo and optional cloud.

Open the notebook in Colab → Runtime → GPU → Run all → authorize Drive in Colab → download the two model files → put them in `android-app/android/app/src/main/assets/ml/` → tell Codex/Claude. Preserve the measured pins/statistics. Never commit weights, datasets, APKs or credentials. Forty epochs/batch sixteen is a resumable starting configuration, not a guaranteed free-session completion time. Latest/best checkpoints live on Drive. Re-running after disconnection resumes the latest checkpoint.

The official 13.3 GB archive is downloaded only by the notebook, SHA-256 printed/pinned on first download and enforced thereafter. The repository's initial null checksum and pending statistics are honest placeholders, not invented measurements. D40 alone is pothole; all other damage classes and annotated images without D40 are negatives. Unlabelled challenge-test images are excluded, never assumed negative. Country + positive/negative stratification uses a fixed 80/10/10 image split; duplicate image bytes are removed. Adjacent road frames may still be correlated: this is not geographic independence or a field benchmark. China_Drone is excluded.

Training uses YOLOX-Nano (depth .33, width .25, depthwise) from exact Apache-2.0 commit in `pins.json`, trained from scratch. No Ultralytics code or weights. Direct COCO loader avoids mosaic/mixup/affine transforms. Every input/evidence image is a complete frame. Whole-image BGR 0–255 resize to fit 416 square, top-left padding 114; raw YOLOX output `[1,3549,6]`, static input `[1,3,416,416]`, opset 17. The Android adapter uses this same contract, checks SHA-256 and fails closed on incompatible assets. ONNX Runtime Android is exactly `com.microsoft.onnxruntime:onnxruntime-android:1.24.3` (MIT); JVM tests use `onnxruntime:1.24.3`. Publisher sidecar observations are separately recorded, without closing NEW-002.

Validation alone selects the score threshold maximizing F1 with precision >= .80 (IoU .5, NMS .45). Test data is untouched by selection and reports per-country recall (null when no true potholes). Export aborts if no feasible threshold or parity fails. Twenty test frames compare raw PyTorch/ONNX output and postprocessing. Training/evaluation/export were not executed on this laptop. Tiny is an explicit future fallback experiment if Nano recall is inadequate; do not silently substitute incompatible weights.

Optional `--extra owner_export.zip`: negative full frames train directly. Positive image-level labels need human COCO boxes; unboxed positives are held for annotation rather than invented boxes/pseudo ground truth. See the Uzbek instructions above. GPS metadata is not used for learning. Owner data stays local until the owner explicitly uploads it to Colab/Drive.

Sources: [Megvii YOLOX](https://github.com/Megvii-BaseDetection/YOLOX/tree/6ddff4824372906469a7fae2dc3206c7aa4bbaee), [RDD2022 official repository record](https://doi.org/10.6084/m9.figshare.21431547), [Arya et al. article](https://arxiv.org/abs/2209.08538), [ONNX Runtime Java](https://onnxruntime.ai/docs/get-started/with-java.html). The task described RDD2022 as CC BY-SA 4.0; the official Figshare API currently labels this record **CC BY 4.0**. We preserve that discrepancy and the owner's chosen **CC BY-SA 4.0 model distribution** separately in MODEL_LICENSE.md. No weights are bundled yet.
