"""Generate include/config.h from config.h.in templates."""

from __future__ import annotations

import re
from pathlib import Path


def _escape_c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def mac_to_byte_list(mac: str) -> str:
    cleaned = mac.strip().replace("-", ":").upper()
    parts = cleaned.split(":")
    if len(parts) != 6 or not all(re.fullmatch(r"[0-9A-F]{2}", p) for p in parts):
        raise ValueError(f"Invalid MAC address: {mac}")
    return ", ".join(f"0x{p}" for p in parts)


def render_template(template_path: Path, output_path: Path, values: dict[str, str]) -> None:
    content = template_path.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    if "{{" in content:
        raise ValueError(f"Unresolved placeholders in {template_path.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def generate_gateway_config(
    firmware_dir: Path,
    *,
    wifi_ssid: str,
    wifi_password: str,
    api_base_url: str,
    ingest_token: str,
    firmware_version: str,
    firmware_serial_tag: str,
) -> None:
    render_template(
        firmware_dir / "include" / "config.h.in",
        firmware_dir / "include" / "config.h",
        {
            "WIFI_SSID": _escape_c_string(wifi_ssid),
            "WIFI_PASSWORD": _escape_c_string(wifi_password),
            "API_BASE_URL": _escape_c_string(api_base_url.rstrip("/")),
            "INGEST_TOKEN": _escape_c_string(ingest_token),
            "FIRMWARE_VERSION": _escape_c_string(firmware_version),
            "FIRMWARE_SERIAL_TAG": _escape_c_string(firmware_serial_tag),
        },
    )


def generate_edge_config(
    firmware_dir: Path,
    *,
    gateway_mac: str,
    device_public_id: str,
    wake_interval_sec: int,
    firmware_version: str,
    firmware_serial_tag: str,
) -> None:
    render_template(
        firmware_dir / "include" / "config.h.in",
        firmware_dir / "include" / "config.h",
        {
            "GATEWAY_MAC_BYTES": mac_to_byte_list(gateway_mac),
            "DEVICE_PUBLIC_ID": _escape_c_string(device_public_id),
            "WAKE_INTERVAL_SEC": str(int(wake_interval_sec)),
            "FIRMWARE_VERSION": _escape_c_string(firmware_version),
            "FIRMWARE_SERIAL_TAG": _escape_c_string(firmware_serial_tag),
        },
    )
