"""Имена и semver прошивок BeePlan (источник для builder).

Синхронизировать с beeplan-api/beeplan/firmware_catalog.py при изменении версий.
"""

from __future__ import annotations

PROJECT_SLUG = "beeplan"

GATEWAY_TYPE = "Gateway"
EDGE_TYPE = "Edge"

# Semver: patch — любая правка прошивки; minor — крупные фичи; major — ломающие изменения.
GATEWAY_VERSION = "0.2.14"
EDGE_VERSION = "0.2.13"


def profile_type(profile: str) -> str:
    if profile == "gateway":
        return GATEWAY_TYPE
    if profile == "edge":
        return EDGE_TYPE
    raise ValueError(f"Unknown profile: {profile}")


def version_for(profile: str) -> str:
    if profile == "gateway":
        return GATEWAY_VERSION
    if profile == "edge":
        return EDGE_VERSION
    raise ValueError(f"Unknown profile: {profile}")


def manifest_name(profile: str) -> str:
    """Имя прошивки для manifest.json (esp-web-tools): beeplan-Gateway."""
    return f"{PROJECT_SLUG}-{profile_type(profile)}"


def serial_tag(profile: str) -> str:
    """Полный идентификатор в Serial и UI: beeplan-Gateway-0.1.2."""
    return f"{manifest_name(profile)}-{version_for(profile)}"


# Обратная совместимость API
FIRMWARE_VERSION = GATEWAY_VERSION
GATEWAY_SERIAL_TAG = serial_tag("gateway")
EDGE_SERIAL_TAG = serial_tag("edge")
