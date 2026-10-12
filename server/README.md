# Community server (rankings, shared pothole map, traffic-aware routing)

A single Python file (`community_server.py`, standard library only) plus OSRM for routing.
The app works fully without it; these features appear only in a build pointed at a server.

## What it stores

| Data | What exactly | Who can see it |
| --- | --- | --- |
| Profile | random device token (only its SHA-256 hash), chosen display name, region, district, village | name appears in rankings |
| Trips | per-trip totals: day, distance, moving time, score, event counts. **No GPS track.** | aggregated in rankings |
| Potholes | latitude, longitude, kind (`pothole`/`road_shock`), how many distinct drivers confirmed it. **No photos.** | everyone (confirmed by ≥ 2 drivers) |
| Speeds | ~110 m cell, 8 heading sectors, 15-minute bin, average speed. **No device id.** Kept 7 days. | used only for routing |

`DELETE /v1/devices/me` removes a profile with its trips and pothole confirmations.
Limits per device per day: 50 trips, 2 000 pothole points, 20 000 speed samples; 10 new
profiles per address per day. No request logs are written.

## Run it on a VPS (≈ 2 vCPU, 4 GB RAM, Ubuntu, Docker)

1. Point a domain (for example `api.yourdomain.uz`) at the VPS and put it in `Caddyfile`.
2. Build the Uzbekistan road graph once (and weekly for map updates): `./osrm-prepare.sh`
3. Start everything: `docker compose up -d`. Caddy obtains the HTTPS certificate.
4. Check: `curl https://api.yourdomain.uz/v1/health` → `{"ok": true, ...}`.
5. Point the app at it and rebuild the APK:
   `python3 tools/set-community-server.py https://api.yourdomain.uz`
   (this sets the constant **and** the CSP `connect-src` together; `--clear` undoes it).

Back up `community-data/community.db` (SQLite in WAL mode) regularly. For many thousands of
active drivers move to PostgreSQL/PostGIS; the API stays the same.

## Endpoints

`GET /v1/health`, `GET /v1/regions`, `POST /v1/devices`, `GET|PATCH|DELETE /v1/devices/me`,
`POST /v1/trips`, `GET /v1/rankings?level=village|district|region|country`,
`POST|GET /v1/potholes`, `POST /v1/speeds`, `GET /v1/route?from=lat,lng&to=lat,lng`.

Rankings: distance-weighted average safe-driving score over 30 days; at least 20 km to
appear. The score rewards smooth driving and never speed. Routing asks OSRM for up to three
alternatives and re-times each segment with live speeds reported in the last 30 minutes
(at least 3 samples per cell), then recommends the fastest; where nobody has reported,
OSRM's typical speed is used. Live traffic is only as good as the number of drivers who
opt in to sharing speeds.

## Names in rankings

Display names, districts and villages are checked when they are saved. Insults (Uzbek,
Russian, English, also in Cyrillic and with look-alike digits or dots between letters),
names posing as officials (YHXX, GAI, police, admin, prezident…) and links or phone numbers
are refused, and the app explains why. A name that a later version of the list catches is
shown as "Haydovchi" without anything else to do.

Anything the list misses can be hidden by hand on the VPS:

    docker compose exec community python3 /app/community_server.py --list-names
    docker compose exec community python3 /app/community_server.py --hide-name "Bad name"
    docker compose exec community python3 /app/community_server.py --unhide-name "Bad name"

A hidden name shows as "Haydovchi" until its owner renames the profile; the new name is
checked again.

## Not done yet

* A dispute flow for wrong potholes, and an in-app "report this name" button.
* Phone-number accounts or other anti-cheat beyond plausibility checks and daily limits.
