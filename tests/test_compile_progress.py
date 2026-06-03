"""Unit tests for PlatformIO log phase/progress parsing."""

from builder.compile import BuildPhase, _phase_from_line, _progress_pct_from_line


def test_phase_compiling() -> None:
    assert _phase_from_line("Compiling .pio/src/main.cpp.o", BuildPhase.preparing) == BuildPhase.compiling


def test_phase_linking() -> None:
    assert _phase_from_line("Linking .pio/build/esp32dev/firmware.elf", BuildPhase.compiling) == BuildPhase.linking


def test_phase_packaging() -> None:
    assert _phase_from_line("Building .pio/build/esp32dev/firmware.bin", BuildPhase.linking) == BuildPhase.packaging


def test_progress_pct_bracket() -> None:
    assert _progress_pct_from_line("[========  ]  42%", None) == 42


def test_progress_pct_unchanged() -> None:
    assert _progress_pct_from_line("Verbose line", 10) == 10
