"""Image classifier service: one image in, category scores out."""
from __future__ import annotations

import logging
import os
import secrets

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from labels import categories_from_detections
from prompts import ALL_PROMPTS, merge_second_opinion, unsafe_confidence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('content_scan_service')

TOKEN = os.environ.get('CONTENT_SCAN_TOKEN', '')
MAX_BYTES = int(os.environ.get('CONTENT_SCAN_MAX_BYTES', str(12 * 1024 * 1024)))
if MAX_BYTES < 1:
    raise RuntimeError('CONTENT_SCAN_MAX_BYTES must be a positive integer')

app = FastAPI(title='content scan', docs_url=None, redoc_url=None)

_detector = None
_clip = None

# Optional second stage, off by default.
SECOND_OPINION = os.environ.get('CONTENT_SCAN_SECOND_OPINION', '') == '1'
SECOND_OPINION_LOW = float(os.environ.get('CONTENT_SCAN_SECOND_OPINION_LOW', '0.30'))
SECOND_OPINION_HIGH = float(os.environ.get('CONTENT_SCAN_SECOND_OPINION_HIGH', '0.97'))
SECOND_OPINION_RAISE_CAP = float(
    os.environ.get('CONTENT_SCAN_SECOND_OPINION_RAISE_CAP', '0.75')
)
CLIP_MODEL = os.environ.get('CONTENT_SCAN_CLIP_MODEL', 'openai/clip-vit-base-patch32')

if not 0 <= SECOND_OPINION_RAISE_CAP < 0.90:
    raise RuntimeError(
        'CONTENT_SCAN_SECOND_OPINION_RAISE_CAP must be between 0 and 0.90'
    )


MODEL_ID = os.environ.get('CONTENT_SCAN_MODEL', 'nudenet')

# Source offer (AGPL-3.0 section 13), served from GET /source.
SOURCE_URL = os.environ.get(
    'CONTENT_SCAN_SOURCE_URL',
    'https://github.com/fazakis/orizo_content_scan_source',
)


def detector():
    """The detector, loaded once on first use."""
    global _detector
    if _detector is None:
        from nudenet import NudeDetector

        _detector = NudeDetector()
        logger.info('detector loaded: part-level (AGPL-3.0)')
    return _detector


def clip():
    """The optional second-stage model, loaded on first use."""
    global _clip
    if _clip is None:
        from transformers import CLIPModel, CLIPProcessor

        model = CLIPModel.from_pretrained(CLIP_MODEL)
        model.eval()
        _clip = (model, CLIPProcessor.from_pretrained(CLIP_MODEL))
        logger.info('clip loaded: %s', CLIP_MODEL)
    return _clip


def second_opinion(image) -> float | None:
    """Second-stage score for the image, or None if it could not be computed."""
    try:
        import torch

        model, processor = clip()
        inputs = processor(text=list(ALL_PROMPTS), images=image, return_tensors='pt', padding=True)
        with torch.no_grad():
            probs = model(**inputs).logits_per_image.softmax(dim=1)[0].tolist()
    except Exception as exc:
        logger.warning('second opinion failed: %s', exc)
        return None
    score = unsafe_confidence(probs)
    return None if score < 0 else score


@app.get('/source')
def source():
    """Where to get this service's source (AGPL-3.0 section 13)."""
    return {'source': SOURCE_URL, 'license': 'AGPL-3.0-or-later'}


@app.get('/health')
def health():
    """Liveness. Does not load the model."""
    return {'ok': True}


@app.get('/ready')
def ready():
    """Loads every configured model; fails if one cannot be loaded."""
    try:
        detector()
        if SECOND_OPINION:
            clip()
    except Exception as exc:
        return JSONResponse({'ok': False, 'detail': str(exc)}, status_code=503)
    return {'ok': True}


def credentials_match(authorization: str, token: str) -> bool:
    """Compare bytes so malformed non-ASCII headers fail authentication safely."""
    return bool(token) and secrets.compare_digest(
        authorization.encode('utf-8'), f'Bearer {token}'.encode('utf-8'))


@app.post('/classify')
async def classify(request: Request, authorization: str = Header(default='')):
    if TOKEN:
        if not credentials_match(authorization, TOKEN):
            raise HTTPException(status_code=401, detail='bad token')
    else:
        raise HTTPException(status_code=503, detail='CONTENT_SCAN_TOKEN is not set')

    chunks = []
    body_size = 0
    async for chunk in request.stream():
        body_size += len(chunk)
        if body_size > MAX_BYTES:
            raise HTTPException(status_code=413, detail='too large')
        chunks.append(chunk)
    body = b''.join(chunks)
    if not body:
        raise HTTPException(status_code=400, detail='empty body')

    import io
    import tempfile

    from PIL import Image

    # Only these formats are parsed.
    try:
        image = Image.open(io.BytesIO(body), formats=['JPEG', 'PNG', 'WEBP', 'GIF'])
        if image.width <= 0 or image.height <= 0 or image.width * image.height > 40_000_000:
            raise ValueError('Image dimensions exceed the decoding limit.')
        image.load()
        image = image.convert('RGB')
    except Exception as exc:
        logger.warning('undecodable image: %s', exc)
        raise HTTPException(status_code=400, detail='could not decode image') from exc

    # The detector reads from a path: a temporary file, removed on exit.
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg') as handle:
            image.save(handle, format='JPEG')
            handle.flush()
            predictions = detector().detect(handle.name)
    except Exception as exc:
        logger.warning('detection failed: %s', exc)
        raise HTTPException(status_code=502, detail='detector failed') from exc

    categories = categories_from_detections(predictions)

    first = categories.get('explicit', 0.0)
    if SECOND_OPINION and SECOND_OPINION_LOW <= first < SECOND_OPINION_HIGH:
        refined = second_opinion(image)
        if refined is not None:
            categories['explicit'] = merge_second_opinion(
                first,
                refined,
                raise_cap=SECOND_OPINION_RAISE_CAP,
            )
            logger.info('second opinion: %.2f -> %.2f', first, categories['explicit'])
    logger.info('classified: %d predictions, %d actionable', len(predictions or []), len(categories))
    return {'categories': categories}
