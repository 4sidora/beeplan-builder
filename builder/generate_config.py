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
    uplink_mode: str = "wifi",
    wifi_ssid: str = "",
    wifi_password: str = "",
    api_base_url: str,
    ingest_token: str,
    firmware_version: str,
    firmware_serial_tag: str,
    debug_serial: bool = True,
    gateway_wifi_channel: int = 6,
    cellular_apn: str = "",
    cellular_user: str = "",
    cellular_pass: str = "",
) -> None:
    if uplink_mode not in ("wifi", "cellular"):
        raise ValueError(f"Invalid uplink_mode: {uplink_mode}")
    if uplink_mode == "wifi" and (not wifi_ssid or not wifi_password):
        raise ValueError("wifi_ssid and wifi_password required for wifi uplink")
    if uplink_mode == "cellular" and not cellular_apn:
        raise ValueError("cellular_apn required for cellular uplink")
    if not 1 <= int(gateway_wifi_channel) <= 13:
        raise ValueError("gateway_wifi_channel must be 1–13")

    render_template(
        firmware_dir / "include" / "config.h.in",
        firmware_dir / "include" / "config.h",
        {
            "UPLINK_MODE": "1" if uplink_mode == "cellular" else "0",
            "WIFI_SSID": _escape_c_string(wifi_ssid),
            "WIFI_PASSWORD": _escape_c_string(wifi_password),
            "GATEWAY_WIFI_CHANNEL": str(int(gateway_wifi_channel)),
            "CELLULAR_APN": _escape_c_string(cellular_apn),
            "CELLULAR_USER": _escape_c_string(cellular_user),
            "CELLULAR_PASS": _escape_c_string(cellular_pass),
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
    gateway_wifi_channel: int,
    device_type: str = "multisensor",
    hx711_dout_pin: int = 1,
    hx711_sck_pin: int = 3,
    ds18b20_pin: int = 4,
    weight_mode: str = "full",
    firmware_version: str,
    firmware_serial_tag: str,
    debug_serial: bool = True,
) -> None:
    device_type_code = "1" if device_type == "scales" else "0"
    if device_type == "scales":
        for pin_name, pin in (("hx711_dout_pin", hx711_dout_pin), ("hx711_sck_pin", hx711_sck_pin),
                              ("ds18b20_pin", ds18b20_pin)):
            if not 0 <= int(pin) <= 21:
                raise ValueError(f"{pin_name} must be 0–21")
        if weight_mode not in ("full", "half"):
            raise ValueError("weight_mode must be full or half")
    else:
        hx711_dout_pin = 0
        hx711_sck_pin = 0
        ds18b20_pin = 0
        weight_mode = "full"
    if not 1 <= int(gateway_wifi_channel) <= 13:
        raise ValueError("gateway_wifi_channel must be 1–13")
    render_template(
        firmware_dir / "include" / "config.h.in",
        firmware_dir / "include" / "config.h",
        {
            "GATEWAY_MAC_BYTES": mac_to_byte_list(gateway_mac),
            "DEVICE_PUBLIC_ID": _escape_c_string(device_public_id),
            "WAKE_INTERVAL_SEC": str(int(wake_interval_sec)),
            "GATEWAY_WIFI_CHANNEL": str(int(gateway_wifi_channel)),
            "DEVICE_TYPE": device_type_code,
            "HX711_DOUT_PIN": str(int(hx711_dout_pin)),
            "HX711_SCK_PIN": str(int(hx711_sck_pin)),
            "DS18B20_PIN": str(int(ds18b20_pin)),
            "WEIGHT_MODE_HALF": "1" if weight_mode == "half" else "0",
            "FIRMWARE_VERSION": _escape_c_string(firmware_version),
            "FIRMWARE_SERIAL_TAG": _escape_c_string(firmware_serial_tag),
            "BEEPLAN_DEBUG": "1" if debug_serial else "0",
        },
    )
