"""Template-solved training samples for hardware tasks the teacher cannot solve.

v0.4 still fails sprites (C64 VIC registers, C128 SPRITE/MOVSPR), the C128 COLOR
sources (border = 4, numbers 1-16) and raster interrupts in every release format,
and the teacher (same base model) fails them too. These families come with a
generated solution in a few styles; every solution goes through the normal
pipeline (checker -> build -> VICE -> expected memory/screen) via
`handwritten verify`, so only verified programs become samples.

The task shapes differ from the Commodore-Eval variants (commodore38/eval/families.py):
other sprite blocks, X above 255, expansion, DATA shapes, background IRQs.

  python -m commodore38.data.templated --out data/v0.5-templates
  python -m commodore38.data.handwritten verify --out data/v0.5-templates
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from .families import C64_COLORS

# Sprite blocks outside the eval range (13-15); 12 overlaps the vectors at $0300.
BLOCKS = [11, 200, 201, 202, 203, 204, 205]
# BASIC 7.0 color numbers are 1-16: VIC color + 1
C128_COLORS = {i + 1: name for i, name in enumerate(C64_COLORS)}


def _basic(lines: list[str], step: int = 10) -> str:
    return "".join(f"{step * (i + 1)} {line}\n" for i, line in enumerate(lines))


def _rem(r, text: str) -> list[str]:
    return [f"rem {text}"] if r.random() < 0.5 else []


def _fill(r, blk: int) -> list[str]:
    a = blk * 64
    return r.choice([
        [f"for i=0 to 62:poke {a}+i,255:next"],
        [f"for i={a} to {a + 62}", "poke i,255", "next i"],
    ])


# --- C64 BASIC sprites ------------------------------------------------------------

def _sprite_regs(r, n, blk, x, y, extra=()):
    """Sprite n at x,y from block blk, plus extra (VIC offset, value) pokes; returns (lines, memory)."""
    msb = x > 255
    regs = [(2 * n, x & 255), (2 * n + 1, y)] + list(extra)
    if r.random() < 0.5:
        lines = ["v=53248", f"poke 2040+{n},{blk}"] + [f"poke v+{o},{val}" for o, val in regs]
        if msb:
            lines.append(f"poke v+16,peek(v+16) or {1 << n}")
        lines.append(f"poke v+21,{1 << n}")
    else:
        lines = [f"poke {2040 + n},{blk}"] + [f"poke {53248 + o},{val}" for o, val in regs]
        if msb:
            lines.append(f"poke 53264,peek(53264) or {1 << n}")
        lines.append(f"poke 53269,{1 << n}")
    mem = [{"addr": 0x07F8 + n, "value": blk}, {"addr": 0xD000 + 2 * n, "value": x & 255},
           {"addr": 0xD001 + 2 * n, "value": y}, {"addr": 0xD015, "value": 1 << n}]
    if msb:
        mem.append({"addr": 0xD010, "value": 1 << n, "mask": 1 << n})
    return lines, mem


def c64_sprite_msb(r):
    n, blk, x, y = r.randint(0, 7), r.choice(BLOCKS), r.randint(256, 330), r.randint(60, 220)
    lines, mem = _sprite_regs(r, n, blk, x, y)
    prompt = r.choice([
        f"Write a C64 BASIC V2 program that shows sprite {n} as a filled square at X={x}, Y={y}. The X position is above 255, so use the MSB register. Use sprite block {blk} (address {blk * 64}).",
        f"Schrijf een C64 BASIC V2-programma dat sprite {n} als gevuld blok toont op X={x}, Y={y} (X groter dan 255, dus met het MSB-register). Zet de spritedata in blok {blk} (adres {blk * 64}).",
    ])
    return "sprite_msb", "c64-basic", prompt, {"memory": mem}, _basic(_rem(r, f"sprite {n} at x={x}") + _fill(r, blk) + lines + ["end"])


def c64_sprite_expand_color(r):
    n, blk, x, y, c = r.randint(0, 7), r.choice(BLOCKS), r.randint(30, 250), r.randint(60, 200), r.randint(1, 15)
    extra = [(39 + n, c), (23, 1 << n), (29, 1 << n)]
    lines, mem = _sprite_regs(r, n, blk, x, y, extra)
    mem += [{"addr": 0xD027 + n, "value": c, "mask": 15}, {"addr": 0xD017, "value": 1 << n}, {"addr": 0xD01D, "value": 1 << n}]
    prompt = f"Write a C64 BASIC V2 program that shows sprite {n} as a solid block in {C64_COLORS[c]}, double width and double height, at X={x}, Y={y}. Store the sprite data in block {blk} (address {blk * 64})."
    return "sprite_expand_color", "c64-basic", prompt, {"memory": mem}, _basic(_rem(r, "expanded sprite") + _fill(r, blk) + lines + ["end"])


def c64_sprite_data_shape(r):
    n, blk, x, y = r.randint(0, 7), r.choice(BLOCKS), r.randint(30, 250), r.randint(60, 200)
    a = blk * 64
    rows = ["255,255,255"] + ["128,0,1"] * 19 + ["255,255,255"]
    data = [f"data {','.join(rows[i:i + 3])}" for i in range(0, 21, 3)]
    lines, mem = _sprite_regs(r, n, blk, x, y)
    mem += [{"addr": a, "value": 255}, {"addr": a + 3, "value": 128}, {"addr": a + 5, "value": 1}]
    prompt = f"Write a C64 BASIC V2 program that reads the shape of a hollow square (a 24x21 outline) from DATA statements into sprite block {blk} (address {a}) and shows it as sprite {n} at X={x}, Y={y}."
    body = [f"for i=0 to 62:read b:poke {a}+i,b:next"] + lines + ["end"] + data
    return "sprite_data_shape", "c64-basic", prompt, {"memory": mem}, _basic(_rem(r, "hollow square sprite") + body)


def c64_two_sprites(r):
    a, b = sorted(r.sample(range(8), 2))
    blk = r.choice(BLOCKS)
    (xa, ya), (xb, yb) = [(r.randint(30, 250), r.randint(60, 200)) for _ in range(2)]
    lines = _fill(r, blk) + [f"poke {2040 + a},{blk}", f"poke {2040 + b},{blk}",
                             f"poke {53248 + 2 * a},{xa}", f"poke {53249 + 2 * a},{ya}",
                             f"poke {53248 + 2 * b},{xb}", f"poke {53249 + 2 * b},{yb}",
                             f"poke 53269,{(1 << a) | (1 << b)}", "end"]
    mem = [{"addr": 0x07F8 + a, "value": blk}, {"addr": 0x07F8 + b, "value": blk},
           {"addr": 0xD000 + 2 * a, "value": xa}, {"addr": 0xD001 + 2 * b, "value": yb},
           {"addr": 0xD015, "value": (1 << a) | (1 << b)}]
    prompt = f"Write a C64 BASIC V2 program that shows sprites {a} and {b} (both a solid block from sprite block {blk}) at {xa},{ya} and {xb},{yb}, with only those two sprites enabled."
    return "two_sprites", "c64-basic", prompt, {"memory": mem}, _basic(lines)


# --- C128 BASIC 7.0 sprites and COLOR ------------------------------------------------

def c128_sprite_color(r):
    n, c = r.randint(1, 8), r.randint(1, 16)
    x, y = r.randint(30, 300), r.randint(60, 200)
    prompt = r.choice([
        f"Write a C128 BASIC 7.0 program that turns on sprite {n} in {C128_COLORS[c]} with the SPRITE statement and places it at {x},{y} with MOVSPR, then ends.",
        f"Schrijf een C128 BASIC 7.0-programma dat sprite {n} aanzet in de kleur {C128_COLORS[c]} en hem met MOVSPR naar {x},{y} verplaatst.",
    ])
    mem = [{"addr": 0xD015, "value": 1 << (n - 1), "mask": 1 << (n - 1)}, {"addr": 0xD026 + n, "value": c - 1, "mask": 15}]
    lines = _rem(r, f"sprite {n}: on, color {c} = {C128_COLORS[c]}") + [f"sprite {n},1,{c}", f"movspr {n},{x},{y}", "end"]
    return "c128_sprite_color", "c128-basic", prompt, {"memory": mem}, _basic(lines)


def c128_sprite_expand(r):
    n, c = r.randint(1, 8), r.randint(2, 16)
    xe, ye = r.choice([(1, 0), (0, 1), (1, 1)])
    what = {(1, 0): "expanded horizontally", (0, 1): "expanded vertically", (1, 1): "expanded in both directions"}[(xe, ye)]
    x, y = r.randint(30, 300), r.randint(60, 200)
    prompt = f"Write a C128 BASIC 7.0 program that shows sprite {n} in {C128_COLORS[c]}, {what}, at position {x},{y}, using the BASIC 7.0 sprite statements."
    bit = 1 << (n - 1)
    mem = [{"addr": 0xD015, "value": bit, "mask": bit}, {"addr": 0xD026 + n, "value": c - 1, "mask": 15},
           {"addr": 0xD01D, "value": bit * xe, "mask": bit}, {"addr": 0xD017, "value": bit * ye, "mask": bit}]
    lines = _rem(r, "sprite n,on,color,priority,x-expand,y-expand") + [f"sprite {n},1,{c},0,{xe},{ye}", f"movspr {n},{x},{y}", "end"]
    return "c128_sprite_expand", "c128-basic", prompt, {"memory": mem}, _basic(lines)


def c128_border_background(r):
    b, g = r.sample(list(C128_COLORS), 2)
    prompt = r.choice([
        f"Write a C128 BASIC 7.0 program that uses COLOR to make the 40-column border {C128_COLORS[b]} and the background {C128_COLORS[g]}, then ends.",
        f"Schrijf een C128 BASIC 7.0-programma dat met COLOR de rand {C128_COLORS[b]} en de achtergrond {C128_COLORS[g]} maakt (40 kolommen).",
    ])
    mem = [{"addr": 0xD020, "value": b - 1, "mask": 15}, {"addr": 0xD021, "value": g - 1, "mask": 15}]
    lines = _rem(r, "color 4 = border, color 0 = background, colors 1-16") + r.choice([
        [f"color 4,{b}", f"color 0,{g}"], [f"color 0,{g}", f"color 4,{b}"], [f"color 4,{b}:color 0,{g}"]]) + ["end"]
    return "c128_border_background", "c128-basic", prompt, {"memory": mem}, _basic(lines)


def c128_text_color(r):
    c = r.choice([k for k in C128_COLORS if k not in (1, 7)])
    w = r.choice(["commodore", "joystick", "datasette", "sprite", "monitor"])
    prompt = f'Write a C128 BASIC 7.0 program that uses COLOR to set the 40-column text color to {C128_COLORS[c]} and then prints "{w}".'
    lines = [f"color 5,{c}", f'print "{w}"', "end"]
    return "c128_text_color", "c128-basic", prompt, {"screen_contains": [w], "memory": [{"addr": 0xF1, "value": c - 1, "mask": 15}]}, _basic(lines)


# --- Kick Assembler raster interrupts ------------------------------------------------

KA = "Write a Kick Assembler program for the C64 with a BASIC upstart that"


def _irq_setup(r, line: int) -> str:
    ack = r.choice(["    asl $d019\n", "    lda #$ff\n    sta $d019\n"])
    setup = (f"    sei\n    lda #$7f\n    sta $dc0d       // CIA timer IRQs off\n    lda $dc0d\n"
             f"    lda #<irq\n    sta $0314\n    lda #>irq\n    sta $0315\n"
             f"    lda #{line & 255}\n    sta $d012       // raster compare, low 8 bits\n"
             f"    lda $d011\n    {'ora #$80' if line > 255 else 'and #$7f'}\n    sta $d011       // bit 7 = raster bit 8\n"
             f"    lda #1\n    sta $d01a       // enable raster IRQ\n    cli\n    rts\n")
    return setup, ack


def ka_raster_background(r):
    line, c = r.randint(40, 300), r.randint(0, 15)
    setup, ack = _irq_setup(r, line)
    src = (f"BasicUpstart2(start)\n\nstart:\n{setup}\nirq:\n{ack}    lda #{c}\n    sta $d021\n    jmp $ea31\n")
    prompt = r.choice([
        f"{KA} installs a raster interrupt on raster line {line} that sets the background color to {c}, then returns to BASIC with RTS while the interrupt keeps running.",
        f"Schrijf een Kick Assembler-programma voor de C64 met BASIC upstart dat een raster-interrupt op lijn {line} installeert die de achtergrondkleur op {c} zet, en daarna met RTS terugkeert naar BASIC.",
    ])
    return "raster_background", "c64-kickass", prompt, {"memory": [{"addr": 0xD01A, "value": 1, "mask": 1}, {"addr": 0xD021, "value": c, "mask": 15}]}, src


def ka_raster_split(r):
    top, split = r.randint(0, 40), r.randint(100, 240)
    a, b = r.sample(range(16), 2)
    setup, ack = _irq_setup(r, top)
    src = (f"BasicUpstart2(start)\n\n.const TOP = {top}\n.const SPLIT = {split}\n\nstart:\n"
           + setup.replace(f"lda #{top}\n", "lda #TOP\n") +
           f"\nirq:\n{ack}    lda $d012\n    cmp #SPLIT\n    bcs lower\n"
           f"    lda #{a}\n    sta $d020\n    lda #SPLIT\n    sta $d012\n    jmp $ea81\n"
           f"lower:\n    lda #{b}\n    sta $d020\n    lda #TOP\n    sta $d012\n    jmp $ea81\n")
    prompt = f"{KA} splits the border color with a raster interrupt: color {a} from raster line {top} and color {b} from line {split}, by moving the raster compare between the two lines. Return to BASIC with RTS while the split keeps running."
    return "raster_split", "c64-kickass", prompt, {"memory": [{"addr": 0xD01A, "value": 1, "mask": 1}]}, src


FAMILIES = {
    "c64-basic": [c64_sprite_msb, c64_sprite_expand_color, c64_sprite_data_shape, c64_two_sprites],
    "c128-basic": [c128_sprite_color, c128_sprite_expand, c128_border_background, c128_text_color],
    "c64-kickass": [ka_raster_background, ka_raster_split],
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write template-solved tasks for `handwritten verify`.")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-family", type=int, default=24)
    p.add_argument("--seed", type=int, default=505)
    args = p.parse_args(argv)
    r = random.Random(args.seed)
    (args.out / "solutions").mkdir(parents=True, exist_ok=True)
    seen, n = set(), 0
    with (args.out / "tasks.jsonl").open("w", encoding="utf-8") as f:
        for lang, fams in FAMILIES.items():
            for fam in fams:
                for _ in range(args.per_family):
                    family, language, prompt, expect, code = fam(r)
                    if prompt in seen:
                        continue
                    seen.add(prompt)
                    task_id = f"{language}-{family}-{hashlib.sha256(prompt.encode()).hexdigest()[:6]}"
                    f.write(json.dumps({"id": task_id, "language": language, "family": family,
                                        "prompt": prompt, "expect": expect}, ensure_ascii=False) + "\n")
                    ext = ".asm" if language.endswith("kickass") else ".bas"
                    (args.out / "solutions" / (task_id + ext)).write_text(code, encoding="utf-8")
                    n += 1
    print(f"{n} tasks with solutions -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
