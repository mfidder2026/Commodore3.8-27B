"""Parametrized versions of the hand-written benchmark tasks (Commodore-Eval v1).

Each family mirrors one task in tasks/c64-basic.json etc. and produces new
instances with their own reference solution, so `c38-eval --references` checks
every generated expectation in VICE. These families are eval-only: the training
families in commodore38/data/families.py are deliberately different.

The generated set is frozen into tasks/generated-v1.json (fixed test set, §5.5):

  python -m commodore38.eval.families > commodore38/eval/tasks/generated-v1.json
"""

from __future__ import annotations

import json
import random
from math import factorial, gcd

WORDS = ["ready player", "game over", "insert coin", "load error", "press play",
         "basic rules", "super cpu", "zero page"]
VOWEL_TEXTS = ["a commodore sixty four", "the kernal rom", "basic version two",
               "sprites and sound", "please press any key"]


def _task(id_, lang, prompt, expect, reference):
    return {"id": id_, "language": lang, "prompt": prompt, "expect": expect, "reference": reference}


def _basic(lines: list[str]) -> str:
    return "".join(f"{10 * (i + 1)} {line}\n" for i, line in enumerate(lines))


def _primes(n):
    return [p for p in range(2, n) if all(p % d for d in range(2, int(p ** 0.5) + 1))]


# --- C64 BASIC -------------------------------------------------------------------

def c64_hello(r, i):
    w = r.choice(WORDS)
    return _task(f"c64b-hello-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that clears the screen and prints {w.upper()}.",
                 {"screen_contains": [w]}, _basic(["print chr$(147)", f'print "{w}"', "end"]))


def c64_sum(r, i):
    a, b = r.randint(1, 50), r.randint(100, 400)
    return _task(f"c64b-sum-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that computes the sum of the integers {a} to {b} with a loop and prints the result.",
                 {"screen_contains": [str(sum(range(a, b + 1)))]},
                 _basic(["s=0", f"for i={a} to {b}", "s=s+i", "next i", "print s", "end"]))


def c64_primes(r, i):
    n = r.randint(30, 90)
    ps = _primes(n)
    return _task(f"c64b-primes-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that prints all prime numbers below {n}.",
                 {"screen_contains": [str(p) for p in ps[-3:]]},
                 _basic([f"for n=2 to {n - 1}", "p=1", "d=2", "if d*d>n then 80", "if n/d=int(n/d) then p=0",
                         "d=d+1", "if p=1 then 40", "if p=1 then print n", "next n", "end"]))


def c64_colors(r, i):
    names = ["black", "white", "red", "cyan", "purple", "green", "blue", "yellow"]
    b, g = r.sample(range(8), 2)
    return _task(f"c64b-colors-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that sets the border color to {names[b]} and the background color to {names[g]}, then ends.",
                 {"memory": [{"addr": 0xD020, "value": b, "mask": 15}, {"addr": 0xD021, "value": g, "mask": 15}]},
                 _basic([f"poke 53280,{b}", f"poke 53281,{g}", "end"]))


def c64_fizzbuzz(r, i):
    n = r.randint(16, 22)
    last = max(k for k in range(1, n + 1) if k % 3 and k % 5)
    return _task(f"c64b-fizzbuzz-v{i}", "c64-basic", f"Write a C64 BASIC V2 FizzBuzz program for the numbers 1 to {n}: print FIZZ for multiples of 3, BUZZ for multiples of 5, FIZZBUZZ for multiples of both, otherwise the number.",
                 {"screen_contains": ["fizzbuzz", str(last)]},
                 _basic([f"for i=1 to {n}", 'if i/15=int(i/15) then print "fizzbuzz":goto 60',
                         'if i/3=int(i/3) then print "fizz":goto 60', 'if i/5=int(i/5) then print "buzz":goto 60',
                         "print i", "next i", "end"]))


def c64_reverse(r, i):
    w = r.choice(["joystick", "datasette", "keyboard", "printer", "monitor", "cassette"])
    return _task(f"c64b-reverse-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that reverses the string {w.upper()} character by character and prints the result.",
                 {"screen_contains": [w[::-1]]},
                 _basic([f'a$="{w}"', 'b$=""', "for i=len(a$) to 1 step -1", "b$=b$+mid$(a$,i,1)", "next i", "print b$", "end"]))


def c64_factorial(r, i):
    n = r.randint(5, 12)
    return _task(f"c64b-factorial-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that computes {n} factorial and prints it.",
                 {"screen_contains": [str(factorial(n))]},
                 _basic(["f=1", f"for i=1 to {n}", "f=f*i", "next i", "print f", "end"]))


def c64_fibonacci(r, i):
    n = r.randint(11, 20)
    fib = [1, 1]
    while len(fib) < n:
        fib.append(fib[-1] + fib[-2])
    return _task(f"c64b-fibonacci-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that prints the first {n} Fibonacci numbers, starting with 1, 1.",
                 {"screen_contains": [str(fib[-2]), str(fib[-1])]},
                 _basic(["a=1", "b=1", f"for i=1 to {n}", "print a", "c=a+b", "a=b", "b=c", "next i", "end"]))


def c64_sprite(r, i):
    n, x, y, blk = r.randint(1, 7), r.randint(40, 250), r.randint(60, 220), r.randint(13, 15)
    return _task(f"c64b-sprite-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that shows sprite {n} as a solid block at X={x}, Y={y}. Put the sprite data in block {blk} (address {blk * 64}), set the sprite pointer accordingly and enable only that sprite.",
                 {"memory": [{"addr": 0x07F8 + n, "value": blk}, {"addr": 0xD000 + 2 * n, "value": x},
                             {"addr": 0xD001 + 2 * n, "value": y}, {"addr": 0xD015, "value": 1 << n}]},
                 _basic(["for i=0 to 62", f"poke {blk * 64}+i,255", "next i", f"poke {2040 + n},{blk}",
                         f"poke {53248 + 2 * n},{x}", f"poke {53249 + 2 * n},{y}", f"poke 53269,{1 << n}", "end"]))


def c64_gcd(r, i):
    g = r.randint(3, 40)
    a, b = g * r.randint(5, 40), g * r.randint(5, 40)
    return _task(f"c64b-gcd-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that computes the greatest common divisor of {a} and {b} with Euclid's algorithm and prints it.",
                 {"screen_contains": [str(gcd(a, b))]},
                 _basic([f"a={a}", f"b={b}", "if b=0 then 80", "t=b", "b=a-int(a/b)*b", "a=t", "goto 30", "print a", "end"]))


def c64_vowels(r, i):
    s = r.choice(VOWEL_TEXTS)
    n = sum(c in "aeiou" for c in s)
    return _task(f"c64b-vowels-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that counts the vowels (a, e, i, o, u) in {s.upper()} and prints the count.",
                 {"screen_contains": [str(n)]},
                 _basic([f'a$="{s}"', "n=0", "for i=1 to len(a$)", "c$=mid$(a$,i,1)",
                         'if c$="a" or c$="e" or c$="i" or c$="o" or c$="u" then n=n+1', "next i", "print n", "end"]))


def c64_poke_char(r, i):
    code, color = r.randint(1, 26), r.randint(1, 15)
    return _task(f"c64b-poke-char-v{i}", "c64-basic", f"Write a C64 BASIC V2 program that clears the screen and then places the letter {chr(64 + code)} in color {color} in the top-left corner by writing directly to screen memory and color memory.",
                 {"memory": [{"addr": 0x0400, "value": code}, {"addr": 0xD800, "value": color, "mask": 15}]},
                 _basic(["print chr$(147)", f"poke 1024,{code}", f"poke 55296,{color}", "end"]))


def c64_countdown_nl(r, i):
    n = r.randint(5, 15)
    w = r.choice(["start", "klaar", "lancering", "go"])
    return _task(f"c64b-countdown-nl-v{i}", "c64-basic", f"Schrijf een C64 BASIC V2-programma dat aftelt van {n} tot en met 1 (elk getal op een eigen regel) en daarna {w.upper()} print.",
                 {"screen_contains": [w, str(n)]},
                 _basic([f"for i={n} to 1 step -1", "print i", "next i", f'print "{w}"', "end"]))


def c64_table_nl(r, i):
    k = r.choice([3, 4, 6, 8, 9, 11, 12])
    return _task(f"c64b-table-nl-v{i}", "c64-basic", f"Schrijf een C64 BASIC V2-programma dat de tafel van {k} print, van 1 x {k} tot en met 10 x {k}, met de uitkomst op elke regel.",
                 {"screen_contains": [str(9 * k), str(10 * k)]},
                 _basic(["for i=1 to 10", f'print i;"x {k} =";i*{k}', "next i", "end"]))


# --- C128 BASIC ------------------------------------------------------------------

def c128_hello(r, i):
    w = r.choice(WORDS)
    return _task(f"c128b-hello-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program for the 40-column screen that clears the screen and prints {w.upper()}.",
                 {"screen_contains": [w]}, _basic(["scnclr", f'print "{w}"', "end"]))


def c128_border(r, i):
    names = {2: "white", 3: "red", 4: "cyan", 5: "purple", 6: "green", 7: "blue", 8: "yellow"}
    c = r.choice(list(names))
    return _task(f"c128b-border-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that uses the COLOR statement to make the 40-column border {names[c]}, then ends.",
                 {"memory": [{"addr": 0xD020, "value": c - 1, "mask": 15}]}, _basic([f"color 4,{c}", "end"]))


def c128_doloop_sum(r, i):
    n = r.randint(50, 300)
    return _task(f"c128b-doloop-sum-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that uses a DO WHILE ... LOOP (no FOR/NEXT) to sum the integers 1 to {n} and prints the result.",
                 {"screen_contains": [str(n * (n + 1) // 2)]},
                 _basic(["s=0", "i=0", f"do while i<{n}", "i=i+1", "s=s+i", "loop", "print s", "end"]))


def c128_else(r, i):
    n = r.randint(2, 99)
    good, bad = ("odd", "even") if n % 2 else ("even", "odd")
    return _task(f"c128b-else-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that sets N={n} and uses IF ... THEN ... ELSE on a single line to print ODD or EVEN.",
                 {"screen_contains": [good], "screen_excludes": [bad]},
                 _basic([f"n={n}", 'if n and 1 then print "odd":else print "even"', "end"]))


def c128_doubling(r, i):
    start, k = r.randint(1, 5), r.randint(200, 20000)
    x = start
    while x <= k:
        x *= 2
    return _task(f"c128b-doubling-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that starts with X={start} and doubles X in a DO UNTIL loop until X is larger than {k}, then prints X.",
                 {"screen_contains": [str(x)]},
                 _basic([f"x={start}", f"do until x>{k}", "x=x*2", "loop", "print x", "end"]))


def c128_sprite(r, i):
    n = r.randint(1, 8)
    return _task(f"c128b-sprite-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that turns on sprite {n} and moves it to position 150,120 using the BASIC 7.0 sprite commands, then ends.",
                 {"memory": [{"addr": 0xD015, "value": 1 << (n - 1), "mask": 1 << (n - 1)}]},
                 _basic([f"sprite {n},1,2", f"movspr {n},150,120", "end"]))


def c128_instr(r, i):
    w = r.choice(["commodore", "datasette", "joystick", "keyboard", "cartridge"])
    a = r.randint(1, len(w) - 3)
    sub = w[a - 1:a + 2]
    pos = w.find(sub) + 1
    return _task(f"c128b-instr-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that prints the position of the substring {sub.upper()} in the string {w.upper()} using a built-in string function.",
                 {"screen_contains": [f" {pos}"]}, _basic([f'print instr("{w}","{sub}")', "end"]))


def c128_factorial(r, i):
    n = r.randint(5, 12)
    return _task(f"c128b-factorial-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that computes {n} factorial and prints it.",
                 {"screen_contains": [str(factorial(n))]},
                 _basic(["f=1", f"for i=1 to {n}", "f=f*i", "next i", "print f", "end"]))


def c128_poke_char(r, i):
    code, color = r.randint(1, 26), r.randint(1, 15)
    return _task(f"c128b-poke-char-v{i}", "c128-basic", f"Write a C128 BASIC 7.0 program that clears the 40-column screen and puts the letter {chr(64 + code)} in VIC color {color} in the top-left corner by writing directly to screen memory and color memory.",
                 {"memory": [{"addr": 0x0400, "value": code}, {"addr": 0xD800, "value": color, "mask": 15}]},
                 _basic(["scnclr", f"poke 1024,{code}", f"poke 55296,{color}", "end"]))


def c128_vowels_nl(r, i):
    s = r.choice(VOWEL_TEXTS)
    n = sum(c in "aeiou" for c in s)
    return _task(f"c128b-vowels-nl-v{i}", "c128-basic", f"Schrijf een C128 BASIC 7.0-programma dat het aantal klinkers (a, e, i, o, u) telt in {s.upper()} en dat aantal print.",
                 {"screen_contains": [str(n)]},
                 _basic([f'a$="{s}"', "n=0", "for i=1 to len(a$)", 'if instr("aeiou",mid$(a$,i,1)) then n=n+1', "next i", "print n", "end"]))


# --- Kick Assembler ------------------------------------------------------------------

KA = "Write a Kick Assembler program for the C64 with a BASIC upstart that"


def _ka(body: str) -> str:
    return "BasicUpstart2(start)\n\nstart:\n" + body


def ka_colors(r, i):
    b, g = r.sample(range(16), 2)
    return _task(f"c64ka-colors-v{i}", "c64-kickass", f"{KA} sets the border color to {b} and the background color to {g} and returns to BASIC with RTS.",
                 {"memory": [{"addr": 0xD020, "value": b, "mask": 15}, {"addr": 0xD021, "value": g, "mask": 15}]},
                 _ka(f"    lda #{b}\n    sta $d020\n    lda #{g}\n    sta $d021\n    rts\n"))


def ka_text(r, i):
    w = r.choice(["ready", "basic", "sprite", "kernal", "screen"])
    return _task(f"c64ka-text-v{i}", "c64-kickass", f"{KA} writes the word {w.upper()} into the top-left of screen memory ($0400) using screen codes, then returns to BASIC with RTS.",
                 {"memory": [{"addr": 0x0400 + k, "value": ord(c) - 96} for k, c in enumerate(w)]},
                 _ka(f'    ldx #0\nloop:\n    lda msg,x\n    beq done\n    sta $0400,x\n    inx\n    jmp loop\ndone:\n    rts\n\nmsg:\n    .text "{w}"\n    .byte 0\n'))


def ka_add8(r, i):
    a, b = r.randint(10, 150), r.randint(10, 100)
    return _task(f"c64ka-add8-v{i}", "c64-kickass", f"{KA} adds {a} and {b}, stores the 8-bit result at $C000 and returns to BASIC with RTS.",
                 {"memory": [{"addr": 0xC000, "value": a + b}]},
                 _ka(f"    clc\n    lda #{a}\n    adc #{b}\n    sta $c000\n    rts\n"))


def ka_add16(r, i):
    a, b = r.randint(0x0100, 0x7FFF), r.randint(0x0100, 0x7FFF)
    s = a + b
    return _task(f"c64ka-add16-v{i}", "c64-kickass", f"{KA} adds the 16-bit numbers ${a:04X} and ${b:04X}, stores the result little-endian at $C000/$C001 and returns to BASIC with RTS.",
                 {"memory": [{"addr": 0xC000, "value": s & 0xFF}, {"addr": 0xC001, "value": s >> 8}]},
                 _ka(f"    clc\n    lda #${a & 0xFF:02x}\n    adc #${b & 0xFF:02x}\n    sta $c000\n    lda #${a >> 8:02x}\n    adc #${b >> 8:02x}\n    sta $c001\n    rts\n"))


def ka_mul(r, i):
    a, b = r.randint(3, 15), r.randint(3, 15)
    return _task(f"c64ka-mul-v{i}", "c64-kickass", f"{KA} multiplies {a} by {b} using a loop of additions (the 6510 has no multiply instruction), stores the result at $C000 and returns to BASIC with RTS.",
                 {"memory": [{"addr": 0xC000, "value": a * b}]},
                 _ka(f"    lda #0\n    ldx #{b}\nloop:\n    clc\n    adc #{a}\n    dex\n    bne loop\n    sta $c000\n    rts\n"))


def ka_rasterirq(r, i):
    line = r.randint(50, 250)
    return _task(f"c64ka-rasterirq-v{i}", "c64-kickass", f"{KA} installs a raster interrupt on raster line {line} which changes the border color, then returns to BASIC with RTS while the interrupt keeps running.",
                 {"memory": [{"addr": 0xD01A, "value": 1, "mask": 1}]},
                 _ka(f"    sei\n    lda #$7f\n    sta $dc0d\n    lda $dc0d\n    lda #<irq\n    sta $0314\n    lda #>irq\n    sta $0315\n    lda #{line}\n    sta $d012\n"
                     "    lda $d011\n    and #$7f\n    sta $d011\n    lda #1\n    sta $d01a\n    cli\n    rts\n\nirq:\n    asl $d019\n    inc $d020\n    jmp $ea81\n"))


FAMILIES = [
    c64_hello, c64_sum, c64_primes, c64_colors, c64_fizzbuzz, c64_reverse, c64_factorial,
    c64_fibonacci, c64_sprite, c64_gcd, c64_vowels, c64_poke_char, c64_countdown_nl, c64_table_nl,
    c128_hello, c128_border, c128_doloop_sum, c128_else, c128_doubling, c128_sprite, c128_instr,
    c128_factorial, c128_poke_char, c128_vowels_nl,
    ka_colors, ka_text, ka_add8, ka_add16, ka_mul, ka_rasterirq,
]


def generate(instances: int = 3, seed: int = 1038) -> list[dict]:
    r = random.Random(seed)
    return [fam(r, i) for fam in FAMILIES for i in range(1, instances + 1)]


if __name__ == "__main__":
    print(json.dumps(generate(), indent=1, ensure_ascii=False))
