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


def data_average(r, lang):
    n = r.randint(4, 8)
    nums = [r.randint(1, 60) for _ in range(n - 1)]
    nums.append(n * r.randint(10, 40) - sum(nums))  # make the average a whole number
    while nums[-1] < 0:
        nums = [r.randint(1, 60) for _ in range(n - 1)]
        nums.append(n * r.randint(30, 60) - sum(nums))
    return _t("data_average", lang, f"Write a {DIALECT[lang]} program that reads the numbers {', '.join(map(str, nums))} from DATA statements and prints their average.",
              screen_contains=[str(sum(nums) // n)])


def count_multiples(r, lang):
    a, b, k = r.randint(1, 50), r.randint(100, 500), r.randint(3, 13)
    return _t("count_multiples", lang, f"Write a {DIALECT[lang]} program that counts how many numbers from {a} to {b} are divisible by {k} and prints the count.",
              screen_contains=[str(sum(1 for n in range(a, b + 1) if n % k == 0))])


def first_common_multiple(r, lang):
    a, p, q = r.randint(10, 200), r.randint(3, 9), r.randint(4, 11)
    n = a + 1
    while n % p or n % q:
        n += 1
    return _t("first_common_multiple", lang, f"Write a {DIALECT[lang]} program that finds the first number greater than {a} that is divisible by both {p} and {q}, and prints it.",
              screen_contains=[str(n)])


def minutes_to_hours(r, lang):
    m = r.randint(61, 1439)
    return _t("minutes_to_hours", lang, f"Schrijf een {DIALECT[lang]}-programma dat {m} minuten omrekent naar uren en minuten en beide getallen print.",
              screen_contains=[str(m // 60), str(m % 60)])


def table_product_sum(r, lang):
    n = r.randint(3, 12)
    return _t("table_product_sum", lang, f"Write a {DIALECT[lang]} program that uses two nested FOR loops to add up i*j for all i and j from 1 to {n}, and prints the total.",
              screen_contains=[str((n * (n + 1) // 2) ** 2)])


def double_letters(r, lang):
    w = r.choice(WORDS)
    return _t("double_letters", lang, f'Write a {DIALECT[lang]} program that builds a new string in which every character of "{w}" appears twice, and prints it.',
              screen_contains=["".join(c * 2 for c in w)])


def asc_sum(r, lang):
    w = r.choice(WORDS)
    # Lowercase source + bas2prg -i: the letters are stored as unshifted PETSCII 65-90.
    return _t("asc_sum", lang, f'Write a {DIALECT[lang]} program that prints the sum of the ASC values of all characters in the string "{w}".',
              screen_contains=[str(sum(ord(c.upper()) for c in w))])


def gosub_square(r, lang):
    n = r.randint(11, 300)
    return _t("gosub_square", lang, f"Write a {DIALECT[lang]} program that sets N={n}, calls a subroutine with GOSUB that computes the square of N into S, and prints S after the RETURN.",
              screen_contains=[str(n * n)])


def on_goto_menu(r, lang):
    words = r.sample(["load", "save", "list", "run", "help", "quit"], 4)
    k = r.randint(1, 4)
    return _t("on_goto_menu", lang, f"Write a {DIALECT[lang]} program that sets K={k} and uses ON K GOTO to jump to one of four lines that print {', '.join(w.upper() for w in words)} respectively.",
              screen_contains=[words[k - 1]], screen_excludes=[w for w in words if w != words[k - 1] and w not in words[k - 1]])


def binary_search(r, lang):
    secret = r.randint(1, 100)
    lo, hi, guesses = 1, 100, 0
    while True:
        guesses += 1
        mid = (lo + hi) // 2
        if mid == secret:
            break
        lo, hi = (mid + 1, hi) if mid < secret else (lo, mid - 1)
    return _t("binary_search", lang, f"Write a {DIALECT[lang]} program that finds the secret number {secret} between 1 and 100 by binary search (guess = INT((LO+HI)/2), starting with LO=1 and HI=100) and prints how many guesses it took.",
              screen_contains=[str(guesses)])


BASIC_FAMILIES: list[Family] = [
    even_sum, power_loop, count_letter, data_max, data_min, count_greater, digit_sum,
    collatz, squares_sum, stars, celsius, leap_year, palindrome, to_binary, lcm,
    reverse_number, word_count, countdown_step,
    data_average, count_multiples, first_common_multiple, minutes_to_hours, table_product_sum,
    double_letters, asc_sum, gosub_square, on_goto_menu, binary_search,
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


def c64_peek_border(r, lang):
    color = r.randint(1, 15)
    return _t("peek_border", lang, f"Write a C64 BASIC V2 program that sets the border color to {color} with poke, then reads it back with peek (keep only the lower 4 bits) and prints the value.",
              screen_contains=[str(color)], memory=[{"addr": 0xD020, "value": color, "mask": 15}])


def c64_reverse_line(r, lang):
    row = r.randint(12, 23)
    base = 0x0400 + 40 * row
    return _t("reverse_line", lang, f"Write a C64 BASIC V2 program that draws a solid bar across the whole of screen row {row} (counted from 0) by poking the reverse-space character (screen code 160) into screen memory.",
              memory=[{"addr": base, "value": 160}, {"addr": base + 39, "value": 160}])


def c64_sprite_expand(r, lang):
    n = r.randint(0, 7)
    return _t("sprite_expand", lang, f"Write a C64 BASIC V2 program that turns on sprite {n} and makes it double width and double height (and no other sprite expanded).",
              memory=[{"addr": 0xD015, "value": 1 << n, "mask": 1 << n}, {"addr": 0xD017, "value": 1 << n}, {"addr": 0xD01D, "value": 1 << n}])


def c64_lowercase(r, lang):
    return _t("lowercase_charset", lang, r.choice([
        "Write a C64 BASIC V2 program that switches the screen to the upper/lowercase character set by poking the VIC memory setup register.",
        "Schrijf een C64 BASIC V2-programma dat het scherm omschakelt naar de tekenset met kleine en hoofdletters via een poke in het VIC-geheugenregister.",
    ]), memory=[{"addr": 0xD018, "value": 23}])


C64_FAMILIES: list[Family] = [c64_char_at, c64_char_color, c64_text_color, c64_sprite_color, c64_fill_row,
                              c64_peek_border, c64_reverse_line, c64_sprite_expand, c64_lowercase]

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


def c128_fast(r, lang):
    return _t("fast_mode", lang, r.choice([
        "Write a C128 BASIC 7.0 program that switches the CPU to 2 MHz mode with the BASIC 7.0 statement for that, then ends.",
        "Schrijf een C128 BASIC 7.0-programma dat de processor met het BASIC 7.0-commando daarvoor naar 2 MHz zet en daarna eindigt.",
    ]), memory=[{"addr": 0xD030, "value": 1, "mask": 1}])


def c128_dec(r, lang):
    n = r.randint(16, 65535)
    return _t("dec", lang, f'Write a C128 BASIC 7.0 program that converts the hexadecimal string "{n:X}" to decimal with the built-in function for that and prints the result.',
              screen_contains=[str(n)])


def c128_begin_bend(r, lang):
    x, k = r.randint(1, 20), r.randint(5, 15)
    if x > k:
        exp = dict(screen_contains=["big", str(x * 2)])
    else:
        exp = dict(screen_contains=["done"], screen_excludes=["big"])
    return _t("begin_bend", lang, f"Write a C128 BASIC 7.0 program that sets X={x} and, if X is greater than {k}, uses a BEGIN ... BEND block to print BIG and then X*2. Finally print DONE.",
              **exp)


C128_FAMILIES: list[Family] = [c128_do_until, c128_else_max, c128_hex, c128_while_digits, c128_char_cmd, c128_background,
                               c128_fast, c128_dec, c128_begin_bend]

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


def ka_countdown_table(r, lang):
    n = r.randint(5, 60)
    return _t("countdown_table", lang, f"{KA} stores the numbers {n} down to 0 in consecutive bytes starting at $C000 (so $C000 holds {n}), then returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": n}, {"addr": 0xC000 + n // 2, "value": n - n // 2}, {"addr": 0xC000 + n, "value": 0}])


def ka_copy_table(r, lang):
    data = r.sample(range(1, 256), 16)
    return _t("copy_table", lang, f"{KA} copies a 16-byte table defined with .byte {', '.join(map(str, data))} to $C100 with an indexed loop, then returns to BASIC with RTS.",
              memory=[{"addr": 0xC100, "value": data[0]}, {"addr": 0xC107, "value": data[7]}, {"addr": 0xC10F, "value": data[15]}])


def ka_max2(r, lang):
    a, b = r.sample(range(0, 256), 2)
    return _t("max2", lang, f"{KA} compares the unsigned numbers {a} and {b}, stores the larger one at $C000 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": max(a, b)}])


def ka_nibbles(r, lang):
    v = r.randint(0x11, 0xFE)
    return _t("nibbles", lang, f"{KA} splits the byte ${v:02X} into its high nibble (stored at $C000) and low nibble (stored at $C001), then returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": v >> 4}, {"addr": 0xC001, "value": v & 15}])


def ka_macro_colors(r, lang):
    b, g = r.sample(range(16), 2)
    return _t("macro_colors", lang, f"{KA} defines a Kick Assembler .macro that sets the border and background color from two parameters, calls it with border {b} and background {g}, and returns to BASIC with RTS.",
              memory=[{"addr": 0xD020, "value": b, "mask": 15}, {"addr": 0xD021, "value": g, "mask": 15}])


def ka_for_squares(r, lang):
    k = r.randint(2, 15)
    return _t("for_squares", lang, f"{KA} uses a Kick Assembler .for loop to generate a table of the squares of 0 to 15, copies the entry for {k} to $C000 and returns to BASIC with RTS.",
              memory=[{"addr": 0xC000, "value": k * k}])


def ka_clear_screen(r, lang):
    return _t("clear_screen", lang, r.choice([
        f"{KA} fills all 1000 bytes of screen memory with the space character (screen code 32) using a loop, then returns to BASIC with RTS.",
        f"{KA} clears the screen by writing screen code 32 to all of $0400-$07E7 with a loop over four pages, then returns to BASIC with RTS.",
    ]), memory=[{"addr": 0x0400 + 40 * 2, "value": 32}, {"addr": 0x0600, "value": 32}, {"addr": 0x07E7, "value": 32}])


KICKASS_FAMILIES: list[Family] = [ka_sub8, ka_sub16, ka_fill, ka_popcount, ka_table_max,
                                  ka_table_sum, ka_shift_mul, ka_color_ram, ka_screen_text, ka_xor_checksum,
                                  ka_countdown_table, ka_copy_table, ka_max2, ka_nibbles, ka_macro_colors,
                                  ka_for_squares, ka_clear_screen]

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
