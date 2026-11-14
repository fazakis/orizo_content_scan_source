# Orizo content scan

An open-source, standalone image classification service for content safety. Run it locally or deploy your own HTTP service. It is licensed under the GNU Affero General Public License, version 3 or later.

It takes one image and returns category scores. It makes no decisions and keeps nothing.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
CONTENT_SCAN_TOKEN=$(openssl rand -hex 32) uvicorn app:app --host 127.0.0.1 --port 8099
```

The service refuses to classify without `CONTENT_SCAN_TOKEN`. The first run downloads the detection model.

An optional second stage is off by default. To include it, also install `requirements-second-opinion.txt` (or build the image with `--build-arg CONTENT_SCAN_INCLUDE_SECOND_OPINION=1`) and set `CONTENT_SCAN_SECOND_OPINION=1`.

## Endpoints

- `POST /classify`: raw image bytes, with `Authorization: Bearer <token>`. Returns category scores.
- `GET /health` and `GET /ready`: liveness and readiness.
- `GET /source`: this source offer.

## License

AGPL-3.0-or-later. See `LICENSE`. The unauthenticated `GET /source` endpoint offers the corresponding source. If you deploy a modified version, set `CONTENT_SCAN_SOURCE_URL` to the publicly available corresponding source for that version.
