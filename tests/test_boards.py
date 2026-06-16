"""Board profile tests."""

from builder.boards import BOARD_PROFILES, get_board_profile


def test_ttgo_t_call_profile() -> None:
    p = get_board_profile("ttgo-t-call-v14")
    assert p.chip_family == "ESP32"
    assert p.env == "ttgo-t-call-v14"
    names = [n for n, _ in p.flash_parts]
    assert "boot_app0.bin" in names
    assert p.flash_parts[0] == ("bootloader.bin", 0x1000)


def test_ttgo_t_energy_profile() -> None:
    p = get_board_profile("ttgo-t-energy")
    assert p.chip_family == "ESP32"
    assert p.env == "ttgo-t-energy"


def test_all_boards_registered() -> None:
    assert set(BOARD_PROFILES) == {"ttgo-t-energy", "ttgo-t-call-v14"}
