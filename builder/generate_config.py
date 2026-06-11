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
    debug_serial: bool = True,
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
            "BEEPLAN_DEBUG": "1" if debug_serial else "0",
        },
    )


def generate_edge_config(
    firmware_dir: Path,
    *,
    gateway_mac: str,
    device_public_id: str,
    wake_interval_sec: int,
    telemetry_slot_sec: int,
    gateway_wifi_channel: int,
    device_type: str = "multisensor",
    firmware_version: str,
    firmware_serial_tag: str,
    debug_serial: bool = True,
) -> None:
    device_type_code = "1" if device_type == "scales" else "0"
    if not 1 <= int(gateway_wifi_channel) <= 13:
        raise ValueError("gateway_wifi_channel must be 1–13")
    if not 0 <= int(telemetry_slot_sec) <= 3599:
        raise ValueError("telemetry_slot_sec must be 0–3599")
    render_template(
        firmware_dir / "include" / "config.h.in",
        firmware_dir / "include" / "config.h",
        {
            "GATEWAY_MAC_BYTES": mac_to_byte_list(gateway_mac),
            "DEVICE_PUBLIC_ID": _escape_c_string(device_public_id),
            "WAKE_INTERVAL_SEC": str(int(wake_interval_sec)),
            "TELEMETRY_SLOT_SEC": str(int(telemetry_slot_sec)),
            "GATEWAY_WIFI_CHANNEL": str(int(gateway_wifi_channel)),
            "DEVICE_TYPE": device_type_code,
            "FIRMWARE_VERSION": _escape_c_string(firmware_version),
            "FIRMWARE_SERIAL_TAG": _escape_c_string(firmware_serial_tag),
            "BEEPLAN_DEBUG": "1" if debug_serial else "0",
        },
    )
