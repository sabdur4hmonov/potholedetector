# Pothole Reporter (Uzbekistan)

An independent Android app that finds potholes on Uzbekistan's roads. Mount the phone on the
dashboard, start **Drive**, and the app watches the road, detects potholes, records where
each one is and keeps a photo as evidence. A pothole you pass twice is kept once. Reports stay
on the phone; nothing is filed or sent to any authority automatically. There is no
project-operated backend or account system.

Languages: **English** and **O&#8216;zbekcha** (Uzbek, Latin script).

<p>
  <a href="docs/example-pothole.jpg"><img src="docs/example-pothole-thumb.jpg" width="280" alt="Pothole detected by Pothole Reporter"></a>
</p>

## How it works

- **Drive** shows a live road view and counters while Maps or a call is open. At a typical
  30 fps it samples about every fifth delivered camera frame into durable three-view windows,
  keeps only one raw burst waiting for live AI and retries unfinished saved windows after the
  drive.
- Every detection, saved-video replay and repair view preserves the complete edge-to-edge
  camera frame. The app may downscale or compress the whole image, but never crops, tiles,
  masks or substitutes a road region for model evidence.
- Detection returns only **Pothole: Yes/No**, never a user-facing confidence score. A Yes
  requires a localized cavity, an eroded edge or material-height transition, visible surface
  loss, usable imagery and consistent Drive views. Flat patches, utility-cover repairs, gravel
  texture, ruts, broad breakup, puddle ambiguity, construction beds and speed breakers are No.
- Each accepted pothole keeps the full-resolution photo, coordinates, time, GPS accuracy and a
  street name (looked up from OpenStreetMap when online).
- Nearby repeat observations are grouped into one report; Debug mode retains each one.
- On a later live drive, **Fixed** requires a separate before/after check that clearly sees the
  same footprint covered by completed, intact repair material. Probable, obstructed,
  mismatched or merely clean-looking views remain open for review.
- **Photo** saves a pothole you confirm yourself as a private, user-reported record. It is never
  shown as AI-confirmed. Optional cloud analysis is a separate, confirmed action.
- **Share evidence** hands a photo and a plain-text note (time, coordinates, map link, GPS
  accuracy) to Android's share sheet. Sharing is always your action.
- A selectable 15/30/60/90-minute active-time battery limit stops Drive automatically.
- Dashcam (RTSP) capture is disabled in this build.

[![Pothole Reporter architecture](docs/architecture.png)](docs/architecture.png)

## Install

1. Build or download a debug APK (see below) and install it on an Android phone.
2. On first launch pick a language and review the privacy notice. Photos can be saved privately
   without an API key. An OpenAI API key is optional for Drive and cloud analysis.
3. Capture while safely stopped, or securely mount the phone before starting **Drive**.

## Important limits

- AI can miss damage or produce false positives. No field-validated accuracy percentage is claimed.
- Android may temporarily take the camera for a video call or another higher-priority app; Drive
  pauses camera sampling and resumes automatically. Device-specific battery managers can still
  stop long-running services.
- Selected pothole images and the user's API key go directly to OpenAI. Exact coordinates go to
  OpenStreetMap Nominatim. See the [privacy policy](docs/privacy.html).
- The project is not affiliated with or endorsed by any government body or data provider.

## Build and test

```bash
python3 tools/sync-web-assets.py   # after editing anything in static/
./tools/build-apk.sh
./tests/run-all.sh
# Explicit live-service checks: RUN_LIVE_TESTS=1 ./tests/run-all.sh
```

`static/` is the source of truth for the web layer; `android-app/www` and `docs/` are
byte-identical mirrors, and the inline script and style hashes in `static/index.html`'s
Content-Security-Policy must be refreshed after every edit (the sync tool does both).

## License

Code is MIT; data retains its source licences and terms. See [LICENSE](LICENSE).
