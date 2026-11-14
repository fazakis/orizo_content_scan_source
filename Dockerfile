FROM python:3.12-slim

RUN useradd --system --uid 10001 --create-home --home-dir /home/scanner scanner

WORKDIR /app
COPY requirements.txt requirements-second-opinion.txt ./

ARG CONTENT_SCAN_INCLUDE_SECOND_OPINION=0
RUN set -eu; \
    pip install --no-cache-dir -r requirements.txt; \
    case "$CONTENT_SCAN_INCLUDE_SECOND_OPINION" in \
      0) ;; \
      1) pip install --no-cache-dir -r requirements-second-opinion.txt ;; \
      *) echo 'CONTENT_SCAN_INCLUDE_SECOND_OPINION must be 0 or 1' >&2; exit 2 ;; \
    esac

ENV HF_HOME=/home/scanner/.cache/huggingface

ARG CONTENT_SCAN_MODEL=nudenet
ARG CONTENT_SCAN_CLIP_MODEL=openai/clip-vit-base-patch32
ENV CONTENT_SCAN_MODEL=${CONTENT_SCAN_MODEL}
ENV CONTENT_SCAN_CLIP_MODEL=${CONTENT_SCAN_CLIP_MODEL}

USER scanner
RUN set -eu; \
    python -c "from nudenet import NudeDetector; NudeDetector()"; \
    if [ "$CONTENT_SCAN_INCLUDE_SECOND_OPINION" = 1 ]; then \
      python -c "from transformers import CLIPModel, CLIPProcessor; CLIPModel.from_pretrained('${CONTENT_SCAN_CLIP_MODEL}'); CLIPProcessor.from_pretrained('${CONTENT_SCAN_CLIP_MODEL}')"; \
    fi

# LICENSE ships with the image (AGPL-3.0).
COPY --chown=scanner:scanner LICENSE labels.py prompts.py app.py ./

EXPOSE 8099
ENV CONTENT_SCAN_WORKERS=1
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port 8099 --workers ${CONTENT_SCAN_WORKERS} --limit-concurrency 4 --backlog 32 --timeout-keep-alive 5"]
