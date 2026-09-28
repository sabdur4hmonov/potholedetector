# SEC-010 remediation

Finding: **SEC-010 — LOW — Image decoded before an explicit size/pixel budget; possible local resource exhaustion.**

**STATUS: PARTIALLY RESOLVED**

Recorded 2026-09-14. The JavaScript import, preparation and repair-validation paths now inspect bounded raster metadata before requesting pixel decoding. Focused source/browser checks passed. The pinned native camera plugin still has an earlier full-resolution decode, and real Android decoder behavior has not been verified. This report does not claim device deployment, a hard process-memory ceiling or production approval.

## Original behavior and actual paths

- Manual browser selection enters the global `handleFile` in `static/index.html`. It assigned an object URL for the original file to `progressPhoto.src` before report processing. That preview could decode the original image before a later processing check.
- Native `beginPotholeCapture` calls `Camera.getPhoto` with URI output and `allowEditing: false`, fetches the returned URI, buffers `response.blob()`, creates a File and calls the same handler. A JavaScript check at this point cannot undo native work or the preceding encoded-response buffering.
- `static/standalone.js`'s `toDataUrl` previously called `createImageBitmap` at original resolution, then allocated a canvas and downscaled it. Its callers include photo/drive/civic reports, ordered burst frames, evidence preparation at 4000 pixels, email attachments at 1600 pixels and replay at 1280 pixels. The preparation helper is the shared protection point for these calls.
- `decodeRepairEvidence` already limited bytes, MIME types, signature and eventual dimensions, but used `createImageBitmap` or an Image fallback before checking dimensions/pixels. The dimension check therefore happened after expensive allocation. Data-URL/Blob/FileReader conversion helpers could also create encoded copies before checking size.
- The app-owned native drive path uses CameraX frames, complete-frame resizing and the existing `NativeStoredImagePolicy` for stored/bridged evidence. These controls were inspected, not rewritten. Native detection/enhancement and ordered evidence remain complete-frame operations.
- The installed, locked `@capacitor/camera@8.2.2` has earlier decodes in `android/src/main/java/com/capacitorjs/plugins/camera/LegacyCameraFlow.java`: `decodeFile` at line 384 and gallery `decodeStream` at lines 419 and 447. `IonCameraFlow.kt` calls `decodeFile` at lines 726 and 806. These dependency paths lack a preceding bounds/sample pass at those calls. Camera width/height settings resize after this decode; setting those options would not fix the initial allocation.
- Existing saved report images can also be displayed directly by the WebView. This change guards newly imported images and shared preparation/conversion paths; it does not migrate or certify historical database images. Packaged UI/catalog images and network/reference-pack loading are not the manual-image import decoder and were not rewritten. No remote exploit or decoder code-execution claim is made.

Root cause: encoded bytes and decoded geometry were not consistently constrained before preview/bitmap allocation. Resizing after full decoding limited final output but not the initial work.

## Protection and policy

`IMAGE_DECODE_POLICY` defines these inclusive limits:

| Budget | Limit | Purpose |
| --- | --- | --- |
| Encoded input | 32 MiB (33,554,432 bytes) | Reject before metadata reads, FileReader or data-URL conversion where the input size is available. |
| Source width and height | 12,000 pixels each | Reject pathological axes while allowing ordinary phone photos. |
| Source pixels | 64,000,000 | Accommodate common 12–48 MP images without accepting unlimited raster allocation. |
| Prepared longest edge | 4,000 pixels, or the smaller existing caller limit | Preserve the existing evidence requirement while bounding bitmap/canvas output to at most 16 million pixels. |
| Initial header read | 1 MiB | Inspect metadata without reading the entire encoded image. |
| Additional EXIF chunk | 64 KiB | Bound PNG/WebP orientation metadata, including metadata after pixel payload. |
| Header/chunk traversal | 4,096 items | Bound parser work; chunk headers are read in small slices and payloads are skipped. |

The limits are intentionally generous for legitimate phone evidence, rather than a small thumbnail-only gate. Very large 108 MP originals must be exported/downscaled before import. The existing repair-specific 8 MiB, 8192-axis, 40 × 1024 × 1024 pixel and minimum-dimension rules remain and now run before decoding.

The bounded header reader recognizes JPEG baseline/extended/progressive SOF, PNG, lossy/lossless/extended WebP, GIF and BMP with supported DIB headers. It checks container bounds, required endings, chunk lengths, dimensions and bounded EXIF orientation. Integer inputs must be positive safe integers; `width > floor(maxPixels / height)` rejects excessive pixels before multiplication, preventing integer-overflow bypass. Container checks are a gate, not proof that the underlying codec will accept the file.

`decodeBoundedImage` calculates the complete-frame aspect-preserving output dimensions and supplies `resizeWidth`, `resizeHeight`, `resizeQuality` and EXIF orientation to the two-argument `createImageBitmap` API. It never invokes a crop overload. It checks actual bitmap dimensions against both the output budget and the planned dimensions, closes a mismatched bitmap and fails safely. There is no unbounded Image fallback.

A DOMContentLoaded adapter guards the existing global manual handler before normal capture/import events. It validates and normalizes the original to a bounded JPEG Blob before the original handler creates its preview. File name, modification time and capture metadata are preserved. A busy gate admits one manual photo at a time. Preparation uses a promise queue to retain only one active preparation bitmap/canvas; inference remains unchanged. The normalization uses canvas `toBlob` to avoid an extra base64 copy. Finally blocks close bitmaps, reset canvas backing dimensions, release queue tickets and remove/revoke temporary preview URLs on success and failure.

`dataUrlToBlob`, `blobToDataUrl` and `photoToBase64` check encoded size before conversion where available. Base64 size is calculated from string length/padding without copying the body; repair data URLs are rejected before fetch when they exceed their existing byte budget. Existing normal conversion/output semantics and the enhancement kernel remain.

JPEG/PNG/WebP EXIF orientation and full-scene corners are covered by browser tests. GIF/BMP imports are normalized as still photos. SVG, AVIF, HEIC, ICO, unsupported JPEG variants and otherwise uninspectable formats are rejected with an explicit error instead of falling back to an unbounded decoder. This is a compatibility restriction; native camera output is normally JPEG. Browsers lacking the required bitmap resize behavior fail safely rather than allocating an original-resolution fallback.

## Files changed for this finding

- `static/standalone.js`: policy, bounded metadata/decode helpers, manual preview adapter, conversion checks and resource cleanup.
- `android-app/www/standalone.js`, `docs/standalone.js`, `android-app/android/app/src/main/assets/public/standalone.js`: exact synchronized copies; the last is generated/ignored but updated in the current tree.
- `tests/sec010_image_budget_test.cjs`: deterministic tests against extracted production functions with instrumented resource APIs.
- `tests/sec010_image_browser_test.cjs`: focused real Chrome tests using the existing local server and production bundle.
- `tests/fixtures/sec010-images.json`: small valid raster/orientation fixtures.
- `SECURITY_REMEDIATION_SEC010.md`: this report.
- `PROJECT_MASTER/SECURITY_STATUS.md` and `PROJECT_MASTER/PROJECT_STATUS.md`: SEC-010 status and remaining-work wording.

## Verification executed

| Check | Result and practical coverage |
| --- | --- |
| `node tests/sec010_image_budget_test.cjs` | **17 passed**: valid formats, inclusive geometry boundaries, exact encoded boundary, oversized bytes/axes/pixels before decode, overflow-safe arithmetic, malformed/truncated input, full aspect ratio, decode/render/encoder failures, mismatch cleanup, queue recovery/serialization, manual provenance/cleanup/retry/admission and original repair caps. |
| `node tests/sec010_image_browser_test.cjs` | **Passed on `/` and `/web-app/`**, installed Chrome 152 with CSP enabled. Eight real raster/EXIF fixtures, synthetic oversized header rejected with zero decoder calls, real corrupted-image decode failure/recovery, guarded report submission and preview cleanup, four retained full-frame corners, and existing enhancement fixtures. External requests aborted; report submission mocked for this focused UI check. |
| `python -X utf8 tests/full_frame_invariant_test.py` | **All 18 existing guards passed**, including native acquisition, ordered repair evidence, full-frame downscale/corners and exact source mirrors. The initial invocation encountered Windows CP1251 decoding; rerunning with UTF-8 passed without editing the test. |
| `node --check` on canonical bundle and both new tests | **Passed.** |
| Scoped `git diff --check` and preservation hashes | **Passed**; all four standalone bundles identical. Earlier unrelated source changes, dependency remediation and all four SEC-009 HTML/CSP copies preserved. |

Exact byte-boundary and hostile geometry unit cases use virtual/instrumented inputs; they deliberately do not decode a huge image or allocate attacker-sized pixels. Real browser fixtures are small and harmless. Tests confirm application gates and lifecycle behavior, not a certified codec peak-memory measurement. No paid inference or external report delivery was performed.

## Residual risk and verification limits

This is **partially resolved** because the native camera dependency can fully decode a photo before JavaScript sees it. A reproducible native preflight/sampling fix and device verification remain necessary for that earlier entry point; editing an installed dependency cache would not provide a durable remediation and was not done.

Browser `createImageBitmap` resize bounds the returned bitmap, but its engine may internally decode the permitted source first. A 16 MP RGBA bitmap is about 64 MB, and a canvas may consume another similar backing store; a permitted 64 MP source could require about 256 MB internally, plus codec/encoded/graphics overhead. Serial preparation avoids simultaneous app-owned bitmap/canvas work but does not impose a hard browser process-memory or CPU ceiling. Up to 32 MiB of encoded native response buffering may occur before the handler; limits cannot retroactively prevent that. Header checks and decoder output checks do not establish the absence of codec vulnerabilities or guarantee performance on low-memory hardware.

No Android build, Gradle troubleshooting, emulator, ADB, physical-device or native/WebView memory profiling was performed. Previously recorded build/device limitations and NEW-001/NEW-002 release blockers remain. SEC-010 retains a native source/verification gap, but the original LOW local-resource finding is not recorded as a separate controlled-pilot production blocker; this does not approve public hostile-media exposure or clear existing release blockers.

SEC-001–SEC-009 were **not reworked**. SEC-009 HTML/CSP bytes, SEC-008 dependencies and prior native/security changes were preserved. No framework/dependency changes, architectural rewrite, commit or push occurred. SEC-011 and later findings were not started.
