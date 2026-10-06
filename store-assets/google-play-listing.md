# Google Play listing copy (draft)

Prepared 6 October 2026. Paste only the text inside each code block into Play Console.
**Owner decisions still open before any upload:** the Android application ID (currently the
upstream `dev.aiengg.potholereporter`), a public support email, and enabling GitHub Pages for
the privacy URL below. Nothing in this file has been submitted.

## App name

```text
Pothole Reporter
```

## Short description

```text
Mount your phone, drive, and map potholes on Uzbekistan's roads automatically.
```

## Full description

```text
Pothole Reporter is an independent Android app that finds potholes on roads in Uzbekistan. Mount the phone on the dashboard, start Drive, and the app watches the road, detects potholes, records where each one is and keeps a photo as evidence. A pothole you pass twice is kept once.

Reports, photos and drive tracks stay on your phone. Nothing is sent to any authority automatically; you decide whether to share evidence with someone yourself.

How it works
• One-tap Photo while safely stopped, or securely mount the phone and use foreground Drive while Maps or a call is on screen.
• AI looks at complete camera frames (never cropped) and answers only Pothole: Yes or No.
• Nearby repeat sightings are grouped into one report. A later live drive can mark a pothole Fixed only after a clear same-place before/after comparison.
• English and O'zbekcha (Uzbek).

Important limits and data use
• AI can miss damage or produce false positives. Review every result.
• Drive needs camera, location and internet, and uses your own billed OpenAI API key. Photo reports can be saved privately without a key.
• Selected pothole images go to OpenAI. Precise coordinates go to OpenStreetMap Nominatim to look up the street name.
• Raw GPS tracks are deleted automatically after 30 days; you can delete a drive earlier or turn track keeping off.
• Drive recording is optional and off by default. A persistent notification always shows when camera and location are in use.
• Drive stops automatically at the selected 15/30/60/90-minute battery limit (30 by default).
• The app is not a government service and is not affiliated with or endorsed by any government body.

Privacy: https://sabdur4hmonov.github.io/potholedetector/privacy.html
```

## Play Console fields

- Recommended category: **Tools**.
- Ads declaration: **No**, provided no advertising SDK or ad content is added before release.
- Privacy policy URL: `https://sabdur4hmonov.github.io/potholedetector/privacy.html`
- Support website: `https://github.com/sabdur4hmonov/potholedetector/issues`
- Public support email: **to be supplied by the owner**.

Do not use government marks or describe Pothole Reporter as "official," a "government app,"
or affiliated with a civic body. Do not claim guaranteed detection, automatic filing, a
verified pothole, road ownership, or a measured accuracy percentage without independent
evidence.
