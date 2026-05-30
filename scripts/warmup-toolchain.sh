#!/bin/sh
# One-time warmup inside a running builder container (when Docker rebuild is unavailable).
set -e
export PIP_DEFAULT_TIMEOUT=120
export PIP_RETRIES=10

apt-get update
apt-get install -y --no-install-recommends python3-dev libffi-dev libssl-dev
pip install --no-cache-dir cryptography ecdsa bitstring reedsolo intelhex

cd /firmware/gateway
cp -f include/config.h.example include/config.h
pio run -e esp32dev

cd /firmware/edge
cp -f include/config.h.example include/config.h
pio run -e esp32dev

echo "Toolchain warmup complete."
