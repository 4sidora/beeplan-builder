# Build from workspace root:
#   docker build -f beeplan-builder/Dockerfile .
#
# Firmware source is NOT baked in — production mounts /firmware/* from the host
# (see beeplan-api/docker-compose.prod.yml). Image build only prefetches PIO toolchains.

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    python3-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

RUN pip install --no-cache-dir platformio \
    cryptography ecdsa bitstring reedsolo intelhex

WORKDIR /app

COPY beeplan-builder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Toolchain prefetch (cached layers; stubs in beeplan-builder/docker/prefetch/) ---
COPY beeplan-builder/docker/prefetch/gateway/ /prefetch/gateway/
COPY beeplan-builder/docker/prefetch/edge/ /prefetch/edge/

ARG PREFETCH_GATEWAY=1
ARG PREFETCH_EDGE=1

RUN if [ "$PREFETCH_GATEWAY" = "1" ]; then \
      cd /prefetch/gateway && pio run -e ttgo-t-call-v14; \
    fi

RUN if [ "$PREFETCH_EDGE" = "1" ]; then \
      cd /prefetch/edge && pio run -e ttgo-t-energy; \
    fi

COPY beeplan-builder/builder/ ./builder/

ENV BEEPLAN_ARTIFACTS_DIR=/artifacts
ENV BEEPLAN_WORKDIR=/workdir
ENV BEEPLAN_FIRMWARE_EDGE=/firmware/edge
ENV BEEPLAN_FIRMWARE_GATEWAY=/firmware/gateway
ENV BEEPLAN_BUILDER_SECRET=dev-builder-secret

RUN mkdir -p /artifacts /workdir /firmware/edge /firmware/gateway

EXPOSE 9000

CMD ["uvicorn", "builder.main:app", "--host", "0.0.0.0", "--port", "9000"]
