"""PlatformIO compile pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from builder.boards import get_board_profile
from builder.firmware_versions import manifest_name, serial_tag, version_for
from builder.generate_config import generate_edge_config, generate_gateway_config


def _platformio_packages_dir() -> Path:
    home = Path(os.environ.get("PLATFORMIO_HOME_DIR", Path.home() / ".platformio"))
    return home / "packages"


def _resolve_flash_part(build_dir: Path, name: str, *, required: bool) -> Path | None:
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
    if not required:
        return None
    raise RuntimeError(f"Missing {name} in {build_dir}")


def _run_pio(project_dir: Path, env: str, flash_parts: tuple[tuple[str, int], ...]) -> Path:
    result = subprocess.run(
        ["pio", "run", "-e", env, "-d", str(project_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pio run failed:\n{result.stdout}\n{result.stderr}")
    build_dir = project_dir / ".pio" / "build" / env
    required = {name for name, _ in flash_parts}
    for name in required:
        _resolve_flash_part(build_dir, name, required=True)
    return build_dir


def _write_manifest(
    out_dir: Path,
    *,
    name: str,
    version: str,
    chip_family: str,
    flash_parts: tuple[tuple[str, int], ...],
) -> None:
    manifest = {
        "name": name,
        "version": version,
        "new_install_prompt_erase": True,
        "builds": [
            {
                "chipFamily": chip_family,
                "parts": [{"path": fname, "offset": offset} for fname, offset in flash_parts],
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
    board_profile = get_board_profile(board)

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
                firmware_version=gateway_config.get("firmware_version", version_for("gateway")),
                firmware_serial_tag=gateway_config.get("firmware_serial_tag", serial_tag("gateway")),
            )
        elif profile == "edge":
            if edge_config is None:
                raise ValueError("edge_config required")
            generate_edge_config(
                work,
                gateway_mac=edge_config["gateway_mac"],
                device_public_id=edge_config["device_public_id"],
                wake_interval_sec=int(edge_config.get("wake_interval_sec", 600)),
                firmware_version=edge_config.get("firmware_version", version_for("edge")),
                firmware_serial_tag=edge_config.get("firmware_serial_tag", serial_tag("edge")),
            )
        else:
            raise ValueError(f"Unknown profile: {profile}")

        build_dir = _run_pio(work, board_profile.env, board_profile.flash_parts)
        for fname, _offset in board_profile.flash_parts:
            src = _resolve_flash_part(build_dir, fname, required=True)
            assert src is not None
            shutil.copy2(src, artifact_dir / fname)

    _write_manifest(
        artifact_dir,
        name=manifest_name(profile),
        version=version_for(profile),
        chip_family=board_profile.chip_family,
        flash_parts=board_profile.flash_parts,
    )
