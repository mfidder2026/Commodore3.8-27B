"""Per-platform facts the pipeline needs: emulator, screen memory, BASIC start."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    emulator: str          # VICE binary name
    emulator_args: tuple[str, ...]
    screen_addr: int       # text screen RAM as seen by the CPU
    columns: int
    rows: int
    basic_start: int       # load address of a tokenized BASIC program
    basic_dialect: str


PLATFORMS: dict[str, Platform] = {
    p.key: p
    for p in [
        Platform("c64", "Commodore 64", "x64sc", (), 0x0400, 40, 25, 0x0801, "basic-v2"),
        # 40-column VIC screen; the 80-column VDC screen is not in CPU memory.
        Platform("c128", "Commodore 128", "x128", ("-40col",), 0x0400, 40, 25, 0x1C01, "basic-7.0"),
        Platform("plus4", "Commodore Plus/4", "xplus4", (), 0x0C00, 40, 25, 0x1001, "basic-3.5"),
        Platform("c16", "Commodore 16", "xplus4", ("-model", "c16"), 0x0C00, 40, 25, 0x1001, "basic-3.5"),
        Platform("pet", "Commodore PET 4032", "xpet", ("-model", "4032"), 0x8000, 40, 25, 0x0401, "basic-4.0"),
    ]
}


def get_platform(key: str) -> Platform:
    try:
        return PLATFORMS[key]
    except KeyError:
        raise ValueError(f"unknown platform {key!r}; known: {', '.join(PLATFORMS)}") from None
