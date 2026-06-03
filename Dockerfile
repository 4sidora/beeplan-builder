# Build from workspace root:
#   docker build -f beeplan-builder/Dockerfile .

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

COPY beeplan-builder/builder/ ./builder/
COPY beeplan-edge/ /firmware/edge/
COPY beeplan-gateway/ /firmware/gateway/

# Pre-fetch ESP32 / ESP32-C3 toolchains (avoids PyPI timeouts during user builds)
RUN cd /firmware/gateway && cp include/config.h.example include/config.h \
    && pio run -e esp32dev && pio run -e esp32c3 \
    && cd /firmware/edge && cp include/config.h.example include/config.h \
    && pio run -e esp32dev && pio run -e esp32c3

ENV BEEPLAN_ARTIFACTS_DIR=/artifacts
ENV BEEPLAN_WORKDIR=/workdir
ENV BEEPLAN_FIRMWARE_EDGE=/firmware/edge
ENV BEEPLAN_FIRMWARE_GATEWAY=/firmware/gateway
ENV BEEPLAN_BUILDER_SECRET=dev-builder-secret

RUN mkdir -p /artifacts /workdir

EXPOSE 9000

CMD ["uvicorn", "builder.main:app", "--host", "0.0.0.0", "--port", "9000"]
