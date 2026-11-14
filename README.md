# Orizo content scan

The image classifier behind Orizo's content safety checks. This repository is the corresponding source of the running service, offered under section 13 of the GNU Affero General Public License. The service points here from `GET /source`.

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

AGPL-3.0-or-later. See `LICENSE`.
