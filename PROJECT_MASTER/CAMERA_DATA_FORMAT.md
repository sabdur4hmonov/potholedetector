# Road camera data for the antiradar (what to request from the authorities)

The app warns about fixed road cameras from a list stored on the phone. Warnings are only as
good as this list, so it should come from the official source and carry the fields below.
One row per camera **and per direction it watches** (a camera covering both directions is
either two rows or one row with an empty heading).

| Column | Required | Meaning | Example |
| --- | --- | --- | --- |
| `id` | recommended | Stable official identifier, so updates replace the right camera | `TSH-0412` |
| `lat` | yes | Latitude, WGS84 decimal degrees (6 decimals ≈ 10 cm) | `41.311081` |
| `lng` | yes | Longitude, WGS84 decimal degrees | `69.279737` |
| `type` | yes | `speed`, `seatbelt`, `red_light`, `lane`, `phone` or `speed_bump` | `speed` |
| `heading` | recommended | Direction of travel the camera checks, degrees from north (0 = north, 90 = east). Empty = both directions | `90` |
| `limit` | for `speed` | Posted speed limit in km/h at that camera | `60` |
| `name` | optional | Street or place, shown to the driver | `Amir Temur ko'chasi` |

Accepted file formats: CSV (comma, semicolon or tab; header row required; UTF-8) or the
JSON pack below. Uzbek/Russian type spellings such as `tezlik`, `remen`, `kamar`,
`svetofor` are also accepted.

```json
{"schema": "uz-road-cameras-v1", "source": "Official list", "updated": "2026-10-07",
 "cameras": [{"id": "TSH-0412", "lat": 41.311081, "lng": 69.279737, "type": "speed",
              "heading": 90, "limit": 60, "name": "Amir Temur ko'chasi"}]}
```

How to use it:

* **On a phone:** Settings → Road cameras → Import camera list, choose the CSV/JSON file.
* **For a release:** `python3 tools/build-camera-pack.py cameras.csv --source "..." --updated YYYY-MM-DD --out cameras-uz.json`
  validates every row and prints the rejected ones.

Warning timing: about 22 seconds before the camera at the current speed, at least 300 m and
at most 1 km ahead; only for a camera ahead on the current course and, when `heading` is
given, only in the direction it watches. Over the limit (+3 km/h tolerance) the warning adds
"Tezlikni kamaytiring".

Limits (tell users plainly): mobile/tripod cameras and entries missing from or outdated in
the list are not covered; GPS can drift in tunnels, under bridges and near parallel roads.
The list must be updated whenever cameras are added, moved or removed.

The repository contains only a **synthetic** test file (`tests/fixtures/cameras-synthetic.csv`);
no real camera data is shipped until the official list is supplied.
