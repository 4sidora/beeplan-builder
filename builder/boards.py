"""Supported firmware target boards (PlatformIO env + esp-web-tools manifest)."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_BOARDS = frozenset({"esp32dev", "esp32c3", "esp32c3-usb"})


@dataclass(frozen=True)
class BoardProfile:
    env: str
    chip_family: str
    flash_parts: tuple[tuple[str, int], ...]


BOARD_PROFILES: dict[str, BoardProfile] = {
    "esp32dev": BoardProfile(
        env="esp32dev",
        chip_family="ESP32",
        flash_parts=(
            ("bootloader.bin", 0x1000),
            ("partitions.bin", 0x8000),
            ("boot_app0.bin", 0xE000),
            ("firmware.bin", 0x10000),
        ),
    ),
    "esp32c3": BoardProfile(
        env="esp32c3",
        chip_family="ESP32-C3",
        flash_parts=(
            ("bootloader.bin", 0x0),
            ("partitions.bin", 0x8000),
            ("firmware.bin", 0x10000),
        ),
    ),
    "esp32c3-usb": BoardProfile(
        env="esp32c3-usb",
        chip_family="ESP32-C3",
        flash_parts=(
            ("bootloader.bin", 0x0),
            ("partitions.bin", 0x8000),
            ("firmware.bin", 0x10000),
        ),
    ),
}


def get_board_profile(board: str) -> BoardProfile:
    profile = BOARD_PROFILES.get(board)
    if profile is None:
        supported = ", ".join(sorted(SUPPORTED_BOARDS))
        raise ValueError(f"Unsupported board: {board} (supported: {supported})")
    return profile
