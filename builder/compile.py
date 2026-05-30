"""PlatformIO compile pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from builder.generate_config import generate_edge_config, generate_gateway_config

FIRMWARE_VERSION = "0.1.0"
BOARD_ENV = {"esp32dev": "esp32dev"}

# PlatformIO / Arduino-ESP32 layout for esp32dev (see .pio/build/esp32dev/)
ESP32_FLASH_PARTS: tuple[tuple[str, int], ...] = (
    ("bootloader.bin", 0x1000),
    ("partitions.bin", 0x8000),
    ("boot_app0.bin", 0xE000),
    ("firmware.bin", 0x10000),
)

ARTIFACT_NAMES = frozenset(name for name, _ in ESP32_FLASH_PARTS)


def _platformio_packages_dir() -> Path:
    home = Path(os.environ.get("PLATFORMIO_HOME_DIR", Path.home() / ".platformio"))
    return home / "packages"


def _resolve_flash_part(build_dir: Path, name: str) -> Path:
    candidate = build_dir / name
    if candidate.is_file():
        return candidate
    if name == "boot_app0.bin":
        fw_root = _platformio_packages_dir() / "framework-arduinoespressif32"
        for fallback in (
            fw_root / "tools" / "partitions" / "boot_app0.bin",
            fw_root / "tools" / "partitions" / "boot_app0" / "boot_app0.bin",
        ):
            if fallback.is_file():
                return fallback
    raise RuntimeError(f"Missing {name} in {build_dir}")


def _run_pio(project_dir: Path, env: str) -> Path:
    result = subprocess.run(
        ["pio", "run", "-e", env, "-d", str(project_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pio run failed:\n{result.stdout}\n{result.stderr}")
    build_dir = project_dir / ".pio" / "build" / env
    for name, _offset in ESP32_FLASH_PARTS:
        _resolve_flash_part(build_dir, name)
    return build_dir


def _write_manifest(out_dir: Path, *, name: str, version: str) -> None:
    manifest = {
        "name": name,
        "version": version,
        "new_install_prompt_erase": True,
        "builds": [
            {
                "chipFamily": "ESP32",
                "parts": [{"path": fname, "offset": offset} for fname, offset in ESP32_FLASH_PARTS],
            }
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def compile_firmware(
    *,
    profile: str,
    board: str,
    artifact_dir: Path,
    firmware_roots: dict[str, Path],
    gateway_config: dict | None = None,
    edge_config: dict | None = None,
) -> None:
    if profile not in firmware_roots:
        raise ValueError(f"Unknown profile: {profile}")
    env = BOARD_ENV.get(board)
    if env is None:
        raise ValueError(f"Unsupported board: {board}")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    src_root = firmware_roots[profile]

    with tempfile.TemporaryDirectory(prefix="beeplan-build-") as tmp:
        work = Path(tmp) / profile
        shutil.copytree(src_root, work, dirs_exist_ok=True)

        if profile == "gateway":
            if gateway_config is None:
                raise ValueError("gateway_config required")
            generate_gateway_config(
                work,
                wifi_ssid=gateway_config["wifi_ssid"],
                wifi_password=gateway_config["wifi_password"],
                api_base_url=gateway_config["api_base_url"],
                ingest_token=gateway_config["ingest_token"],
                firmware_version=gateway_config.get("firmware_version", FIRMWARE_VERSION),
            )
        elif profile == "edge":
            if edge_config is None:
                raise ValueError("edge_config required")
            generate_edge_config(
                work,
                gateway_mac=edge_config["gateway_mac"],
                device_public_id=edge_config["device_public_id"],
                wake_interval_sec=int(edge_config.get("wake_interval_sec", 600)),
            )
        else:
            raise ValueError(f"Unknown profile: {profile}")

        build_dir = _run_pio(work, env)
        for fname, _offset in ESP32_FLASH_PARTS:
            shutil.copy2(_resolve_flash_part(build_dir, fname), artifact_dir / fname)

    title = "BeePlan Gateway" if profile == "gateway" else "BeePlan Edge"
    _write_manifest(artifact_dir, name=title, version=FIRMWARE_VERSION)
