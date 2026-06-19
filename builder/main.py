"""BeePlan firmware builder service."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from builder.compile import DEFAULT_WORKDIR, BuildPhase, BuildProgressUpdate, compile_firmware

ARTIFACTS_DIR = Path(os.environ.get("BEEPLAN_ARTIFACTS_DIR", "/artifacts"))
FIRMWARE_EDGE_DIR = Path(os.environ.get("BEEPLAN_FIRMWARE_EDGE", "/firmware/edge"))
FIRMWARE_GATEWAY_DIR = Path(os.environ.get("BEEPLAN_FIRMWARE_GATEWAY", "/firmware/gateway"))
BUILDER_SECRET = os.environ.get("BEEPLAN_BUILDER_SECRET", "dev-builder-secret")
WORKDIR_ROOT = Path(os.environ.get("BEEPLAN_WORKDIR", str(DEFAULT_WORKDIR)))

app = FastAPI(title="BeePlan Builder", version="0.1.0")

_build_lock = threading.Lock()
_compile_lock = threading.Lock()
_builds: dict[str, dict[str, Any]] = {}


class BuildStatus(str, Enum):
    queued = "queued"
    building = "building"
    ready = "ready"
    failed = "failed"


class GatewayBuildConfig(BaseModel):
    uplink_mode: str = Field(default="wifi", pattern="^(wifi|cellular)$")
    wifi_ssid: str = Field(default="", max_length=64)
    wifi_password: str = Field(default="", max_length=128)
    api_base_url: str = Field(min_length=1, max_length=256)
    ingest_token: str = Field(min_length=1, max_length=64)
    firmware_version: str = Field(default="0.1.0", max_length=32)
    firmware_serial_tag: str = Field(default="", max_length=64)
    debug_serial: bool = True
    gateway_wifi_channel: int = Field(default=6, ge=1, le=13)
    cellular_apn: str = Field(default="", max_length=64)
    cellular_user: str = Field(default="", max_length=64)
    cellular_pass: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def validate_uplink_fields(self) -> "GatewayBuildConfig":
        if self.uplink_mode == "wifi":
            if not self.wifi_ssid or not self.wifi_password:
                raise ValueError("wifi_ssid and wifi_password required for wifi uplink")
        elif not self.cellular_apn:
            raise ValueError("cellular_apn required for cellular uplink")
        return self


class EdgeBuildConfig(BaseModel):
    gateway_mac: str = Field(min_length=11, max_length=17)
    device_public_id: str = Field(min_length=1, max_length=64)
    wake_interval_sec: int = Field(default=3600, ge=10, le=86400)
    gateway_wifi_channel: int = Field(ge=1, le=13)
    device_type: str = Field(default="multisensor", pattern="^(multisensor|scales)$")


class BuildRequest(BaseModel):
    build_id: str = Field(min_length=1, max_length=64)
    profile: str = Field(pattern="^(gateway|edge)$")
    board: str = Field(
        default="ttgo-t-energy",
        pattern="^(ttgo-t-energy|ttgo-t-call-v14)$",
    )
    gateway_config: GatewayBuildConfig | None = None
    edge_config: EdgeBuildConfig | None = None


class BuildStatusOut(BaseModel):
    build_id: str
    status: BuildStatus
    error: str | None = None
    created_at: str
    finished_at: str | None = None
    updated_at: str | None = None
    phase: BuildPhase | None = None
    log_tail: list[str] | None = None
    progress_pct: int | None = None


def _verify_secret(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing builder token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != BUILDER_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid builder token")


def _apply_progress(build_id: str, update: BuildProgressUpdate) -> None:
    with _build_lock:
        row = _builds.get(build_id)
        if row is None:
            return
        row["phase"] = update.phase.value
        row["log_tail"] = update.log_tail
        row["progress_pct"] = update.progress_pct
        row["updated_at"] = update.updated_at


def _run_build(build_id: str, body: BuildRequest) -> None:
    artifact_dir = ARTIFACTS_DIR / build_id
    try:
        with _build_lock:
            _builds[build_id]["status"] = BuildStatus.building
            _builds[build_id]["phase"] = BuildPhase.preparing.value
            _builds[build_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

        with _compile_lock:
            compile_firmware(
                profile=body.profile,
                board=body.board,
                artifact_dir=artifact_dir,
                firmware_roots={"edge": FIRMWARE_EDGE_DIR, "gateway": FIRMWARE_GATEWAY_DIR},
                gateway_config=body.gateway_config.model_dump() if body.gateway_config else None,
                edge_config=body.edge_config.model_dump() if body.edge_config else None,
                workdir_root=WORKDIR_ROOT,
                on_progress=lambda u: _apply_progress(build_id, u),
            )
        with _build_lock:
            _builds[build_id]["status"] = BuildStatus.ready
            _builds[build_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            _builds[build_id]["phase"] = BuildPhase.packaging.value
            _builds[build_id]["progress_pct"] = 100
            _builds[build_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:  # noqa: BLE001 — surface builder error to API
        log_tail: list[str] = []
        log_path = artifact_dir / "build.log"
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = lines[-40:]
        with _build_lock:
            _builds[build_id]["status"] = BuildStatus.failed
            _builds[build_id]["error"] = str(exc)
            _builds[build_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            _builds[build_id]["log_tail"] = log_tail
            _builds[build_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def _row_to_out(build_id: str, row: dict[str, Any]) -> BuildStatusOut:
    phase_raw = row.get("phase")
    phase = BuildPhase(phase_raw) if phase_raw in BuildPhase._value2member_map_ else None
    return BuildStatusOut(
        build_id=build_id,
        status=row["status"],
        error=row.get("error"),
        created_at=row["created_at"],
        finished_at=row.get("finished_at"),
        updated_at=row.get("updated_at"),
        phase=phase,
        log_tail=row.get("log_tail"),
        progress_pct=row.get("progress_pct"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/releases")
def firmware_releases() -> dict[str, str]:
    from builder.firmware_versions import (
        EDGE_SERIAL_TAG,
        EDGE_VERSION,
        FIRMWARE_VERSION,
        GATEWAY_SERIAL_TAG,
        GATEWAY_VERSION,
    )

    return {
        "firmware_version": FIRMWARE_VERSION,
        "gateway_version": GATEWAY_VERSION,
        "edge_version": EDGE_VERSION,
        "gateway_serial_tag": GATEWAY_SERIAL_TAG,
        "edge_serial_tag": EDGE_SERIAL_TAG,
    }


@app.post("/v1/builds", response_model=BuildStatusOut, status_code=status.HTTP_202_ACCEPTED)
def create_build(
    body: BuildRequest,
    authorization: str | None = Header(default=None),
) -> BuildStatusOut:
    _verify_secret(authorization)
    build_id = body.build_id
    if body.profile == "gateway" and body.gateway_config is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "gateway_config required")
    if body.profile == "edge" and body.edge_config is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "edge_config required")

    with _build_lock:
        if build_id in _builds and _builds[build_id]["status"] in (BuildStatus.queued, BuildStatus.building):
            raise HTTPException(status.HTTP_409_CONFLICT, "Build already in progress")
        _builds[build_id] = {
            "status": BuildStatus.queued,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "phase": None,
            "log_tail": None,
            "progress_pct": None,
        }

    thread = threading.Thread(target=_run_build, args=(build_id, body), daemon=True)
    thread.start()
    return _row_to_out(build_id, _builds[build_id])


@app.get("/v1/builds/{build_id}", response_model=BuildStatusOut)
def get_build(build_id: str, authorization: str | None = Header(default=None)) -> BuildStatusOut:
    _verify_secret(authorization)
    with _build_lock:
        row = _builds.get(build_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")
    return _row_to_out(build_id, row)


ALLOWED_ARTIFACTS = frozenset(
    {"bootloader.bin", "partitions.bin", "boot_app0.bin", "firmware.bin", "manifest.json"}
)


@app.get("/v1/builds/{build_id}/{artifact_name}")
def download_artifact(build_id: str, artifact_name: str, authorization: str | None = Header(default=None)):
    _verify_secret(authorization)
    if artifact_name not in ALLOWED_ARTIFACTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    path = ARTIFACTS_DIR / build_id / artifact_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    from fastapi.responses import FileResponse

    media = "application/json" if artifact_name.endswith(".json") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=artifact_name)


@app.get("/v1/builds/{build_id}/firmware.bin")
def download_firmware(build_id: str, authorization: str | None = Header(default=None)):
    return download_artifact(build_id, "firmware.bin", authorization)


@app.get("/v1/builds/{build_id}/manifest.json")
def download_manifest(build_id: str, authorization: str | None = Header(default=None)):
    return download_artifact(build_id, "manifest.json", authorization)
