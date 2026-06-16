"""Supported firmware target boards (PlatformIO env + esp-web-tools manifest)."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_BOARDS = frozenset({"ttgo-t-energy", "ttgo-t-call-v14"})

_ESP32_FLASH_PARTS: tuple[tuple[str, int], ...] = (
    ("bootloader.bin", 0x1000),
    ("partitions.bin", 0x8000),
    ("boot_app0.bin", 0xE000),
    ("firmware.bin", 0x10000),
)


@dataclass(frozen=True)
class BoardProfile:
    env: str
    chip_family: str
    flash_parts: tuple[tuple[str, int], ...]


BOARD_PROFILES: dict[str, BoardProfile] = {
    "ttgo-t-call-v14": BoardProfile(
        env="ttgo-t-call-v14",
        chip_family="ESP32",
        flash_parts=_ESP32_FLASH_PARTS,
    ),
    "ttgo-t-energy": BoardProfile(
        env="ttgo-t-energy",
        chip_family="ESP32",
        flash_parts=_ESP32_FLASH_PARTS,
    ),
}


def get_board_profile(board: str) -> BoardProfile:
    profile = BOARD_PROFILES.get(board)
    if profile is None:
        supported = ", ".join(sorted(SUPPORTED_BOARDS))
        raise ValueError(f"Unsupported board: {board} (supported: {supported})")
    return profile
