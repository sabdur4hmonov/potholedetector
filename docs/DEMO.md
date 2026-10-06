# Before a demo

Do not quote a fixed latency without measuring the current build on the phone and network
used for the demo. Include a cold launch and a warm run.

## Set up, in this order

1. **Install and open it once, before the room is watching.** Measure the cold launch on the
   target phone; do not infer it from an emulator or an older release.
2. **Pick the language** (English or O'zbekcha) and accept the privacy notice.
3. **Paste the OpenAI key** in Settings if you will demonstrate Drive or cloud analysis. Saving
   a Photo report works without it.
4. **Take one report in the area you will demonstrate.** It proves the key works. Delete the
   report afterwards if you want a clean history.

## What to measure

Record cold launch, single-photo detection and Drive Mode processing on the actual demo setup.
Model, network and phone all affect elapsed time. The UI reports Pothole: YES or NO and does
not display an uncalibrated model percentage.

## What needs the network, and what happens without it

- **OpenAI** for pothole detection. Without it, Drive cannot detect damage; Photo reports you
  confirm yourself still save locally.
- **OpenStreetMap Nominatim** for the street name. Without it, the report keeps its coordinates
  and shows them in place of a street name.
- **OpenStreetMap tiles** for the in-app map.

Mount the phone securely before starting Drive and never interact with it while driving.
