# -*- coding: utf-8 -*-
"""What the app tells the user must be true in every supported language and render.

Two bugs this guards against, both of which shipped once:
  - HTML entities inside strings applied with textContent, which render literally.
  - Translated strings drifting behind the English ones and describing an older build.

Supported languages: English and Uzbek (every key must exist in both).
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []
LANGS = ("English", "Uzbek")

for name in ("static/index.html", "android-app/www/index.html", "docs/index.html"):
    s = (ROOT / name).read_text(encoding="utf-8")

    # The mirrors must be byte-identical; a partial patch is how the recording
    # toggle silently went missing once.
    if name != "static/index.html":
        if s != (ROOT / "static/index.html").read_text(encoding="utf-8"):
            fails.append(f"{name} has drifted from static/index.html")

    # Disclosure: the user must be told the photo leaves the device in every language.
    notes = re.findall(r'settings_note: "([^"]+)"', s)
    if len(notes) != 2:
        fails.append(f"{name}: expected 2 settings_note strings, found {len(notes)}")
    else:
        for language, note in zip(LANGS, notes):
            if "OpenAI" not in note:
                fails.append(f"{name}: {language} settings note does not mention OpenAI")
            if "Nominatim" not in note:
                fails.append(f"{name}: {language} settings note does not disclose the geocoder")

    # No leftover India-specific strings, languages or selector options.
    for banned in ('value="kn"', 'value="mr"', 'value="bn"', "BMC", "Bengaluru", "Mumbai",
                   "grievance", "India", "GBA", "Gaurav Sen"):
        if banned in s:
            fails.append(f"{name}: leftover India-specific text {banned!r}")
    for language, value in (("English", "en"), ("Uzbek", "uz")):
        if f'<option value="{value}">' not in s:
            fails.append(f"{name}: {language} is missing from the language selector")

    # Both dictionaries must define exactly the same keys.
    blocks = re.findall(r"^  (en|uz): \{(.*?)^  \},?\s*$", s, re.S | re.M)
    keysets = {lang: set(re.findall(r"^    ([A-Za-z0-9_]+):", body, re.M)) for lang, body in blocks}
    if set(keysets) != {"en", "uz"}:
        fails.append(f"{name}: could not find both the en and uz dictionaries")
    else:
        for lang, other in (("uz", "en"), ("en", "uz")):
            missing = sorted(keysets[other] - keysets[lang])
            if missing:
                fails.append(f"{name}: {lang} dictionary lacks {len(missing)} keys, e.g. {missing[:5]}")

    # New detections have one public decision only. Do not let confidence, subtype,
    # or clear/probable wording creep back into the visible result or labelling UI.
    detected = re.findall(r'^\s{4}verdict_detected: "([^"]+)"', s, re.MULTILINE)
    rejected = re.findall(r'^\s{4}verdict_rejected: "([^"]+)"', s, re.MULTILINE)
    if len(detected) != 2 or len(rejected) != 2:
        fails.append(f"{name}: expected two localized binary pothole verdict pairs")
    elif detected[0] != "Pothole: YES" or rejected[0] != "Pothole: NO":
        fails.append(f"{name}: English detection verdict is not binary YES/NO")
    if re.search(r'^\s{4}confidence:', s, re.MULTILINE):
        fails.append(f"{name}: visible confidence wording returned")
    if any(button in s for button in ('id="lblPatch"', 'id="lblSurface"', 'id="lblRut"')):
        fails.append(f"{name}: human detector labels are not binary")

    # Entities are fine inside innerHTML, fatal inside textContent.
    for m in re.finditer(r'\$\("(\w+)"\)\.textContent = t\("(\w+)"\)', s):
        val = re.search(rf'\n    {m.group(2)}: "([^"]*)"', s)
        if val and re.search(r"&[a-z]+;|&#\d+;", val.group(1)):
            fails.append(f"{name}: {m.group(2)} holds an HTML entity but is set via textContent")

for mirror in ("android-app/www/standalone.js", "docs/standalone.js"):
    if (ROOT / mirror).read_bytes() != (ROOT / "static/standalone.js").read_bytes():
        fails.append(f"{mirror} has drifted from static/standalone.js")

if fails:
    print("FAIL"); [print("  -", f) for f in fails]; sys.exit(1)
print("UI TEXT TEST PASS")
