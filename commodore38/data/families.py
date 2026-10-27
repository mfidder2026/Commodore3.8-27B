"""Parametrized task families for synthetic training data.

Each family turns a random generator into one task: a prompt plus an expectation
that the pipeline can check (computed here, so every kept sample is verified
against a known answer). The families deliberately differ from the
Commodore-Eval tasks (commodore38/eval/tasks) so the benchmark does not leak.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

DIALECT = {
    "c64-basic": "C64 BASIC V2",
    "c128-basic": "C128 BASIC 7.0",
}

WORDS = ["commodore", "joystick", "datasette", "petscii", "sprite", "raster",
         "kernal", "cartridge", "floppy", "monitor", "level", "radar", "rotor"]
SENTENCES = ["load the game from disk", "press fire to start", "the quick brown fox",
             "insert the next tape", "high score table", "ready for the next level"]


@dataclass
class Task:
    family: str
    language: str
    prompt: str
    expect: dict


Family = Callable[[random.Random, str], Task]


def _t(family: str, language: str, prompt: str, **expect) -> Task:
    return Task(family, language, prompt, expect)


# --- BASIC families shared by C64 and C128 -------------------------------------

def even_sum(r, lang):
    a, b = r.randint(2, 40), r.randint(60, 300)
    total = sum(n for n in range(a, b + 1) if n % 2 == 0)
    return _t("even_sum", lang, f"Write a {DIALECT[lang]} program that adds up all even numbers from {a} to {b} and prints the total.",
              screen_contains=[str(total)])


def power_loop(r, lang):
    b, e = r.randint(2, 7), r.randint(3, 9)
    while b ** e > 10 ** 8:
        e -= 1
    return _t("power_loop", lang, f"Write a {DIALECT[lang]} program that computes {b} to the power {e} with a multiplication loop (do not use the ^ operator) and prints the result.",
              screen_contains=[str(b ** e)])


def count_letter(r, lang):
    w = r.choice(SENTENCES)
    ch = r.choice(sorted(set(w.replace(" ", ""))))
    return _t("count_letter", lang, f'Write a {DIALECT[lang]} program that counts how often the letter "{ch}" occurs in the string "{w}" and prints the count.',
              screen_contains=[str(w.count(ch))])


def data_max(r, lang):
    nums = r.sample(range(3, 250), 8)
    return _t("data_max", lang, f"Write a {DIALECT[lang]} program that reads these numbers from DATA statements: {', '.join(map(str, nums))}. Print the largest one.",
              screen_contains=[str(max(nums))])


def data_min(r, lang):
    nums = r.sample(range(3, 250), 7)
    return _t("data_min", lang, f"Schrijf een {DIALECT[lang]}-programma dat deze getallen uit DATA-regels leest: {', '.join(map(str, nums))}. Print het kleinste getal.",
              screen_contains=[str(min(nums))])


def count_greater(r, lang):
    nums = r.sample(range(1, 100), 9)
    k = r.randint(20, 80)
    return _t("count_greater", lang, f"Write a {DIALECT[lang]} program that reads the numbers {', '.join(map(str, nums))} from DATA statements and prints how many of them are greater than {k}.",
              screen_contains=[str(sum(n > k for n in nums))])


def digit_sum(r, lang):
    n = r.randint(1000, 99999)
    return _t("digit_sum", lang, f"Write a {DIALECT[lang]} program that computes the sum of the digits of {n} using arithmetic (not string functions) and prints it.",
              screen_contains=[str(sum(map(int, str(n))))])


def collatz(r, lang):
    n = r.randint(6, 60)
    steps, x = 0, n
    while x != 1:
        x = x // 2 if x % 2 == 0 else 3 * x + 1
        steps += 1
    return _t("collatz", lang, f"Write a {DIALECT[lang]} program that counts the steps of the Collatz sequence starting at {n} until it reaches 1 (halve even numbers, otherwise 3n+1) and prints the number of steps.",
              screen_contains=[str(steps)])


def squares_sum(r, lang):
    n = r.randint(5, 30)
    return _t("squares_sum", lang, f"Write a {DIALECT[lang]} program that prints the sum of the squares of 1 to {n}.",
              screen_contains=[str(sum(i * i for i in range(1, n + 1)))])


def stars(r, lang):
    n = r.randint(5, 30)
    return _t("stars", lang, f"Write a {DIALECT[lang]} program that builds a string of {n} asterisks in a loop, prints it, and then prints its length.",
              screen_contains=["*" * n, str(n)])


def celsius(r, lang):
    c = r.choice(range(-20, 105, 5))
    return _t("celsius", lang, f"Write a {DIALECT[lang]} program that converts {c} degrees Celsius to Fahrenheit and prints the result.",
              screen_contains=[str(c * 9 // 5 + 32)])


def leap_year(r, lang):
    y = r.choice([1900, 1984, 1982, 2000, 2024, 2100, 1964, 1977, 2023, 1600])
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    if leap:
        exp = dict(screen_contains=["leap"], screen_excludes=["not"])
    else:
        exp = dict(screen_contains=["not a leap year"])
    return _t("leap_year", lang, f"Write a {DIALECT[lang]} program that checks whether {y} is a leap year and prints LEAP YEAR or NOT A LEAP YEAR.", **exp)


def palindrome(r, lang):
    w = r.choice(["level", "radar", "rotor", "kayak", "sprite", "basic", "civic", "kernal"])
    if w == w[::-1]:
        exp = dict(screen_contains=["palindrome"], screen_excludes=["not"])
    else:
        exp = dict(screen_contains=["not a palindrome"])
    return _t("palindrome", lang, f'Write a {DIALECT[lang]} program that checks whether "{w}" is a palindrome and prints PALINDROME or NOT A PALINDROME.', **exp)


def to_binary(r, lang):
    n = r.randint(1, 255)
    return _t("to_binary", lang, f"Write a {DIALECT[lang]} program that converts the number {n} to an 8-digit binary string (with leading zeros) and prints it.",
              screen_contains=[format(n, "08b")])


def lcm(r, lang):
    a, b = r.randint(4, 40), r.randint(4, 40)
    from math import gcd
    return _t("lcm", lang, f"Write a {DIALECT[lang]} program that computes the least common multiple of {a} and {b} and prints it.",
              screen_contains=[str(a * b // gcd(a, b))])


def reverse_number(r, lang):
    n = r.randint(1000, 98765)
    while n % 10 == 0:
        n += 1
    return _t("reverse_number", lang, f"Write a {DIALECT[lang]} program that reverses the digits of the number {n} using arithmetic and prints the reversed number.",
              screen_contains=[str(n)[::-1]])


def word_count(r, lang):
    s = r.choice(SENTENCES)
    return _t("word_count", lang, f'Schrijf een {DIALECT[lang]}-programma dat telt hoeveel woorden de zin "{s}" bevat (woorden worden gescheiden door één spatie) en het aantal print.',
              screen_contains=[str(len(s.split()))])


def countdown_step(r, lang):
    a, s = r.randint(40, 99), r.randint(3, 9)
    last = a
    while last - s >= 0:
        last -= s
    return _t("countdown_step", lang, f"Write a {DIALECT[lang]} program that counts down from {a} in steps of {s}, printing each number, and stops before going below zero.",
              screen_contains=[f" {last}"])


BASIC_FAMILIES: list[Family] = [
    even_sum, power_loop, count_letter, data_max, data_min, count_greater, digit_sum,
    collatz, squares_sum, stars, celsius, leap_year, palindrome, to_binary, lcm,
    reverse_number, word_count, countdown_step,
]

# --- C64-specific (hardware via poke) ---------------------------------------------

def c64_char_at(r, lang):
    row, col, code = r.randint(12, 22), r.randint(0, 39), r.randint(1, 26)
    letter = chr(ord("a") + code - 1)
    return _t("char_at", lang, f'Write a C64 BASIC V2 program that clears the screen and then puts the letter {letter.upper()} at row {row}, column {col} (both counted from 0) by poking screen memory.',
              memory=[{"addr": 0x0400 + 40 * row + col, "value": code}])


def c64_char_color(r, lang):
    row, col, color = r.randint(12, 22), r.randint(0, 39), r.randint(1, 15)
    return _t("char_color", lang, f"Write a C64 BASIC V2 program that sets the color of the character cell at row {row}, column {col} (counted from 0) to color {color} by poking color memory.",
              memory=[{"addr": 0xD800 + 40 * row + col, "value": color, "mask": 15}])


def c64_text_color(r, lang):
    bg, fg = r.randint(0, 15), r.randint(0, 15)
    return _t("text_color", lang, f"Write a C64 BASIC V2 program that sets the background color to {bg} and the cursor (text) color to {fg} using poke.",
              memory=[{"addr": 0xD021, "value": bg, "mask": 15}, {"addr": 0x0286, "value": fg}])


def c64_sprite_color(r, lang):
    n, color = r.randint(1, 7), r.randint(1, 15)
    return _t("sprite_color", lang, f"Write a C64 BASIC V2 program that turns on sprite {n} (and no other sprites) and gives it color {color}.",
              memory=[{"addr": 0xD015, "value": 1 << n}, {"addr": 0xD027 + n, "value": color, "mask": 15}])


def c64_fill_row(r, lang):
    row, code = r.randint(12, 23), r.randint(1, 26)
    letter = chr(ord("a") + code - 1)
    base = 0x0400 + 40 * row
    return _t("fill_row", lang, f"Schrijf een C64 BASIC V2-programma dat rij {row} van het scherm (geteld vanaf 0) helemaal vult met de letter {letter.upper()} door rechtstreeks in het schermgeheugen te poken.",
              memory=[{"addr": base, "value": code}, {"addr": base + 39, "value": code}])


C64_FAMILIES: list[Family] = [c64_char_at, c64_char_color, c64_text_color, c64_sprite_color, c64_fill_row]

# --- C128-specific (BASIC 7.0 statements) -------------------------------------------

def c128_do_until(r, lang):
    k = r.randint(50, 5000)
    n = 1
    while n * n <= k:
        n += 1
    return _t("do_until", lang, f"Write a C128 BASIC 7.0 program that uses DO ... LOOP UNTIL to find the smallest whole number n for which n*n is larger than {k}, and prints n.",
              screen_contains=[str(n)])


def c128_else_max(r, lang):
    a, b = r.sample(range(1, 999), 2)
    return _t("else_max", lang, f"Write a C128 BASIC 7.0 program that sets A={a} and B={b} and uses a single-line IF ... THEN ... ELSE to print the larger value.",
              screen_contains=[str(max(a, b))], screen_excludes=[str(min(a, b))] if str(min(a, b)) not in str(max(a, b)) else [])


def c128_hex(r, lang):
    n = r.randint(16, 65535)
    return _t("hex", lang, f"Write a C128 BASIC 7.0 program that prints the number {n} in hexadecimal using the built-in function for that.",
              screen_contains=[format(n, "04x")])


def c128_while_digits(r, lang):
    n = r.randint(10, 9999999)
    return _t("while_digits", lang, f"Write a C128 BASIC 7.0 program that counts the digits of {n} with a DO WHILE loop that divides by 10, and prints the count.",
              screen_contains=[str(len(str(n)))])


def c128_char_cmd(r, lang):
    row, col = r.randint(12, 22), r.randint(0, 30)
    word = r.choice(WORDS)
    return _t("char_cmd", lang, f'Write a C128 BASIC 7.0 program for the 40-column screen that clears the screen and uses the CHAR statement to print "{word}" at column {col}, row {row}.',
              memory=[{"addr": 0x0400 + 40 * row + col, "value": ord(word[0]) - ord("a") + 1}])


def c128_background(r, lang):
    color = r.randint(1, 16)  # BASIC 7.0 color numbers are 1-16, VIC registers 0-15
    return _t("background", lang, f"Write a C128 BASIC 7.0 program that uses COLOR to set the 40-column background to BASIC color number {color}, then ends.",
              memory=[{"addr": 0xD021, "value": color - 1, "mask": 15}])


C128_FAMILIES: list[Family] = [c128_do_until, c128_else_max, c128_hex, c128_while_digits, c128_char_cmd, c128_background]

# --- Kick Assembler (C64) ----------------------------------------------------------

KA = "Write a Kick Assembler program for the C64 with a BASIC upstart that"


def ka_sub8(r, lang):
    a, b = r.randint(100, 255), r.randint(1, 99)
    return _t("sub8", lang, f"{KA} subtracts {b} from {a}, stores the 8-bit result at $C010 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC010, "value": a - b}])


def ka_sub16(r, lang):
    a, b = r.randint(0x4000, 0xFFFF), r.randint(0x0100, 0x3FFF)
    d = a - b
    return _t("sub16", lang, f"{KA} subtracts the 16-bit number ${b:04X} from ${a:04X} and stores the result little-endian at $C020/$C021, then returns to BASIC with RTS.",
              memory=[{"addr": 0xC020, "value": d & 0xFF}, {"addr": 0xC021, "value": d >> 8}])


def ka_fill(r, lang):
    n, v = r.randint(10, 200), r.randint(1, 255)
    return _t("fill", lang, f"{KA} fills {n} bytes starting at $C100 with the value ${v:02X} using a loop, then returns to BASIC with RTS.",
              memory=[{"addr": 0xC100, "value": v}, {"addr": 0xC100 + n - 1, "value": v}])


def ka_popcount(r, lang):
    v = r.randint(1, 255)
    return _t("popcount", lang, f"{KA} counts the number of 1-bits in the value ${v:02X} with a shift loop, stores the count at $C000 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": bin(v).count("1")}])


def ka_table_max(r, lang):
    nums = r.sample(range(1, 255), 8)
    return _t("table_max", lang, f"{KA} finds the largest value in a table defined with .byte {', '.join(map(str, nums))}, stores it at $C000 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": max(nums)}])


def ka_table_sum(r, lang):
    nums = r.sample(range(50, 255), 6)
    s = sum(nums)
    return _t("table_sum", lang, f"{KA} adds up the bytes of a table defined with .byte {', '.join(map(str, nums))} into a 16-bit sum, stores it little-endian at $C000/$C001 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": s & 0xFF}, {"addr": 0xC001, "value": s >> 8}])


def ka_shift_mul(r, lang):
    a = r.randint(20, 255)
    k = r.choice([2, 4, 8, 16])
    p = a * k
    return _t("shift_mul", lang, f"{KA} multiplies {a} by {k} using only shift and rotate instructions, stores the 16-bit result little-endian at $C000/$C001 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": p & 0xFF}, {"addr": 0xC001, "value": p >> 8}])


def ka_color_ram(r, lang):
    row, color = r.randint(12, 24), r.randint(1, 15)
    base = 0xD800 + 40 * row
    return _t("color_row", lang, f"{KA} sets the color of all 40 characters in screen row {row} (counted from 0) to color {color} by writing to color RAM, then returns to BASIC with RTS.",
              memory=[{"addr": base, "value": color, "mask": 15}, {"addr": base + 39, "value": color, "mask": 15}])


def ka_screen_text(r, lang):
    row = r.randint(12, 22)
    word = r.choice(WORDS)
    base = 0x0400 + 40 * row
    return _t("screen_text", lang, f'{KA} writes the word "{word}" at the start of screen row {row} (counted from 0) using screen codes, then returns to BASIC with RTS.',
              memory=[{"addr": base, "value": ord(word[0]) - 96}, {"addr": base + len(word) - 1, "value": ord(word[-1]) - 96}])


def ka_xor_checksum(r, lang):
    nums = r.sample(range(0, 256), 6)
    x = 0
    for n in nums:
        x ^= n
    return _t("xor_checksum", lang, f"{KA} computes the XOR of all bytes in a table defined with .byte {', '.join(map(str, nums))}, stores it at $C000 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": x}])


KICKASS_FAMILIES: list[Family] = [ka_sub8, ka_sub16, ka_fill, ka_popcount, ka_table_max,
                                  ka_table_sum, ka_shift_mul, ka_color_ram, ka_screen_text, ka_xor_checksum]

FAMILIES: dict[str, list[Family]] = {
    "c64-basic": BASIC_FAMILIES + C64_FAMILIES,
    "c128-basic": BASIC_FAMILIES + C128_FAMILIES,
    "c64-kickass": KICKASS_FAMILIES,
}


def generate_tasks(per_language: dict[str, int], seed: int = 38) -> list[Task]:
    """Round-robin over each language's families so every family is represented."""
    r = random.Random(seed)
    tasks, seen = [], set()
    for lang, count in per_language.items():
        fams = FAMILIES[lang]
        i = attempts = 0
        while sum(t.language == lang for t in tasks) < count and attempts < count * 10:
            task = fams[i % len(fams)](r, lang)
            i += 1
            attempts += 1
            if task.prompt not in seen:
                seen.add(task.prompt)
                tasks.append(task)
    return tasks
