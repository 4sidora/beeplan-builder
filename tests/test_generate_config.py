"""Tests for config generation."""

from pathlib import Path

import pytest

from builder.generate_config import generate_edge_config, generate_gateway_config, mac_to_byte_list


def test_mac_to_byte_list() -> None:
    assert mac_to_byte_list("AA:BB:CC:DD:EE:FF") == "0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF"


def test_mac_invalid() -> None:
    with pytest.raises(ValueError):
        mac_to_byte_list("not-a-mac")


def test_generate_gateway_config(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "config.h.in").write_text(
        '#define WIFI_SSID "{{WIFI_SSID}}"\n#define INGEST_TOKEN "{{INGEST_TOKEN}}"\n',
        encoding="utf-8",
    )
    generate_gateway_config(
        tmp_path,
        wifi_ssid="net",
        wifi_password="pass",
        api_base_url="http://api.test",
        ingest_token="tok",
        firmware_version="0.1.0",
        firmware_serial_tag="beeplan-Gateway-0.1.0",
    )
    out = (include / "config.h").read_text(encoding="utf-8")
    assert 'WIFI_SSID "net"' in out
    assert 'INGEST_TOKEN "tok"' in out


def test_generate_edge_config(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "config.h.in").write_text(
        "MAC={ {{GATEWAY_MAC_BYTES}} }\nID={{DEVICE_PUBLIC_ID}}\nSEC={{WAKE_INTERVAL_SEC}}\n"
        "CH={{GATEWAY_WIFI_CHANNEL}}\nDT={{DEVICE_TYPE}}\n",
        encoding="utf-8",
    )
    generate_edge_config(
        tmp_path,
        gateway_mac="11:22:33:44:55:66",
        device_public_id="edge-abc",
        wake_interval_sec=3600,
        gateway_wifi_channel=6,
        device_type="multisensor",
        firmware_version="0.2.0",
        firmware_serial_tag="beeplan-Edge-0.2.0",
    )
    out = (include / "config.h").read_text(encoding="utf-8")
    assert "0x11, 0x22" in out
    assert "edge-abc" in out
    assert "3600" in out
    assert "6" in out
    assert "DT=0" in out


def test_generate_edge_config_scales(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "config.h.in").write_text(
        "DT={{DEVICE_TYPE}}\nDOUT={{HX711_DOUT_PIN}}\nSCK={{HX711_SCK_PIN}}\n"
        "T={{DS18B20_PIN}}\nWM={{WEIGHT_MODE_HALF}}\n",
        encoding="utf-8",
    )
    generate_edge_config(
        tmp_path,
        gateway_mac="11:22:33:44:55:66",
        device_public_id="edge-scale",
        wake_interval_sec=1800,
        gateway_wifi_channel=2,
        device_type="scales",
        hx711_dout_pin=1,
        hx711_sck_pin=3,
        ds18b20_pin=4,
        weight_mode="half",
        firmware_version="0.3.0",
        firmware_serial_tag="beeplan-Edge-0.3.0",
    )
    out = (include / "config.h").read_text(encoding="utf-8")
    assert "DT=1" in out
    assert "DOUT=1" in out
    assert "SCK=3" in out
    assert "T=4" in out
    assert "WM=1" in out
