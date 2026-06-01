"""Board profile tests."""

from builder.boards import BOARD_PROFILES, get_board_profile


def test_esp32dev_profile() -> None:
    p = get_board_profile("esp32dev")
    assert p.chip_family == "ESP32"
    assert p.env == "esp32dev"
    names = [n for n, _ in p.flash_parts]
    assert "boot_app0.bin" in names
    assert p.flash_parts[0] == ("bootloader.bin", 0x1000)


def test_esp32c3_profile() -> None:
    p = get_board_profile("esp32c3")
    assert p.chip_family == "ESP32-C3"
    assert p.env == "esp32c3"
    names = [n for n, _ in p.flash_parts]
    assert "boot_app0.bin" not in names
    assert p.flash_parts[0] == ("bootloader.bin", 0x0)


def test_all_boards_registered() -> None:
    assert set(BOARD_PROFILES) == {"esp32dev", "esp32c3", "esp32c3-usb"}


def test_esp32c3_usb_profile() -> None:
    p = get_board_profile("esp32c3-usb")
    assert p.env == "esp32c3-usb"
    assert p.chip_family == "ESP32-C3"
