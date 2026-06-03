"""PlatformIO compile pipeline."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from builder.boards import get_board_profile
from builder.firmware_versions import manifest_name, serial_tag, version_for
from builder.generate_config import generate_edge_config, generate_gateway_config

LOG_TAIL_LINES = 40
DEFAULT_WORKDIR = Path(os.environ.get("BEEPLAN_WORKDIR", "/workdir"))


class BuildPhase(str, Enum):
    preparing = "preparing"
    compiling = "compiling"
    linking = "linking"
    packaging = "packaging"


@dataclass
class BuildProgressUpdate:
    phase: BuildPhase
    log_tail: list[str]
    progress_pct: int | None
    updated_at: str


ProgressCallback = Callable[[BuildProgressUpdate], None]


def _platformio_packages_dir() -> Path:
    home = Path(os.environ.get("PLATFORMIO_HOME_DIR", Path.home() / ".platformio"))
    return home / "packages"


def _pio_jobs() -> int:
    count = os.cpu_count() or 1
    return max(1, count)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _phase_from_line(line: str, current: BuildPhase) -> BuildPhase:
    lower = line.lower()
    if "linking" in lower or "linking ." in lower:
        return BuildPhase.linking
    if "compiling" in lower or "archiving" in lower:
        return BuildPhase.compiling
    if "building" in lower or "checking size" in lower or "creating image" in lower:
        return BuildPhase.packaging
    if "retrieving" in lower or "installing" in lower or "unpacking" in lower:
        return BuildPhase.preparing
    return current


def _progress_pct_from_line(line: str, current: int | None) -> int | None:
    for pattern in (r"\]\s*(\d+)%", r"(\d+)%"):
        m = re.search(pattern, line)
        if m:
            pct = int(m.group(1))
            if 0 <= pct <= 100:
                return min(99, pct) if pct < 100 else 100
            break
    if "success" in line.lower() and "pio" in line.lower():
        return 100
    return current


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


def _should_skip_sync(rel: Path) -> bool:
    return ".pio" in rel.parts or rel.name in {".git", "__pycache__"}


def _sync_firmware_sources(src_root: Path, work: Path) -> None:
    """Sync firmware tree into persistent workdir, preserving .pio build cache."""
    if not work.exists():
        shutil.copytree(
            src_root,
            work,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".pio", ".git", "__pycache__"),
        )
        return
    for src_path in src_root.rglob("*"):
        rel = src_path.relative_to(src_root)
        if _should_skip_sync(rel):
            continue
        dest = work / rel
        if src_path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        if not dest.exists() or src_path.stat().st_mtime > dest.stat().st_mtime:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)


def _persistent_project_dir(workdir_root: Path, profile: str, board: str) -> Path:
    return workdir_root / profile / board


def _append_log(
    log_path: Path,
    line: str,
    tail: deque[str],
    on_progress: ProgressCallback | None,
    phase: BuildPhase,
    progress_pct: int | None,
) -> tuple[BuildPhase, int | None]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        if not line.endswith("\n"):
            fh.write("\n")
    stripped = line.rstrip("\n\r")
    if stripped:
        tail.append(stripped)
    phase = _phase_from_line(stripped, phase)
    progress_pct = _progress_pct_from_line(stripped, progress_pct)
    if on_progress is not None:
        on_progress(
            BuildProgressUpdate(
                phase=phase,
                log_tail=list(tail),
                progress_pct=progress_pct,
                updated_at=_utc_now(),
            )
        )
    return phase, progress_pct


def _run_pio(
    project_dir: Path,
    env: str,
    flash_parts: tuple[tuple[str, int], ...],
    *,
    log_path: Path,
    on_progress: ProgressCallback | None,
) -> Path:
    jobs = _pio_jobs()
    cmd = ["pio", "run", "-e", env, "-d", str(project_dir), "-j", str(jobs)]
    tail: deque[str] = deque(maxlen=LOG_TAIL_LINES)
    phase = BuildPhase.preparing
    progress_pct: int | None = None

    if on_progress is not None:
        on_progress(
            BuildProgressUpdate(
                phase=phase,
                log_tail=[],
                progress_pct=None,
                updated_at=_utc_now(),
            )
        )

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        phase, progress_pct = _append_log(log_path, line, tail, on_progress, phase, progress_pct)
    code = proc.wait()
    if code != 0:
        log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        raise RuntimeError(f"pio run failed (exit {code}):\n{log_text[-8000:]}")
    build_dir = project_dir / ".pio" / "build" / env
    required = {name for name, _ in flash_parts}
    for name in required:
        _resolve_flash_part(build_dir, name, required=True)
    if on_progress is not None:
        on_progress(
            BuildProgressUpdate(
                phase=BuildPhase.packaging,
                log_tail=list(tail),
                progress_pct=100,
                updated_at=_utc_now(),
            )
        )
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
    workdir_root: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    if profile not in firmware_roots:
        raise ValueError(f"Unknown profile: {profile}")
    board_profile = get_board_profile(board)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / "build.log"
    log_path.write_text("", encoding="utf-8")

    src_root = firmware_roots[profile]
    work_root = workdir_root or DEFAULT_WORKDIR
    work = _persistent_project_dir(work_root, profile, board)

    if on_progress is not None:
        on_progress(
            BuildProgressUpdate(
                phase=BuildPhase.preparing,
                log_tail=[],
                progress_pct=None,
                updated_at=_utc_now(),
            )
        )

    _sync_firmware_sources(src_root, work)

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

    build_dir = _run_pio(
        work,
        board_profile.env,
        board_profile.flash_parts,
        log_path=log_path,
        on_progress=on_progress,
    )
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
