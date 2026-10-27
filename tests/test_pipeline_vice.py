"""End-to-end tests through the real checkers, bas2prg and VICE. Run with: pytest -m vice"""

import pytest

from commodore38.config import load_toolchain
from commodore38.verify import Expectation, MemoryCheck, verify_source

pytestmark = [
    pytest.mark.vice,
    pytest.mark.skipif(not load_toolchain().vice("x64sc"), reason="VICE not installed"),
]

HELLO = '10 print chr$(147)\n20 print "hello"\n30 end\n'


def stage(res, name):
    return next(s for s in res.stages if s.name == name)


def test_hello_verifies():
    res = verify_source(HELLO, "c64-basic", expect=Expectation(["hello"]))
    assert res.status == "verified", res.to_dict()


def test_wrong_expected_text_fails():
    res = verify_source(HELLO, "c64-basic", expect=Expectation(["goodbye"]))
    assert res.status == "failed"
    assert stage(res, "expect").detail["missing"] == ["goodbye"]


def test_wrong_memory_value_fails():
    res = verify_source("10 poke 53280,2\n20 end\n", "c64-basic",
                        expect=Expectation(memory=[MemoryCheck(0xD020, 5, 0x0F)]))
    assert res.status == "failed"
    assert stage(res, "expect").detail["memory"] == [{"addr": "$D020", "expected": 5, "actual": 2}]


def test_checker_error_stops_pipeline():
    res = verify_source('10 print "a"\n10 print "b"\n', "c64-basic")  # duplicate line number
    assert res.status == "failed"
    assert [s.name for s in res.stages] == ["check"]


def test_runtime_error_detected():
    res = verify_source("10 dim a(5)\n20 a(9)=1\n30 end\n", "c64-basic")
    assert res.status == "failed"
    assert stage(res, "run").detail["run_status"] == "basic_error"


def test_endless_loop_needs_allow_timeout():
    loop = "10 poke 53280,i and 15\n20 i=i+1\n30 goto 10\n"
    assert verify_source(loop, "c64-basic", timeout=3).status == "failed"
    assert verify_source(loop, "c64-basic", timeout=3, expect=Expectation(allow_timeout=True)).status == "verified"


KICKASS_ADD = "BasicUpstart2(start)\n\nstart:\n    clc\n    lda #100\n    adc #55\n    sta $c000\n    rts\n"


@pytest.mark.skipif(not (load_toolchain().java and load_toolchain().kickass_jar), reason="KickAss not configured")
def test_kickass_memory_result():
    ok = verify_source(KICKASS_ADD, "c64-kickass", expect=Expectation(memory=[MemoryCheck(0xC000, 155)]))
    assert ok.status == "verified", ok.to_dict()
    bad = verify_source(KICKASS_ADD.replace("#55", "#56"), "c64-kickass",
                        expect=Expectation(memory=[MemoryCheck(0xC000, 155)]))
    assert bad.status == "failed"


@pytest.mark.skipif(not (load_toolchain().java and load_toolchain().kickass_jar), reason="KickAss not configured")
def test_kickass_file_directive_output_is_found():
    # .file makes KickAss pick its own output name and ignore -o
    src = KICKASS_ADD.replace("BasicUpstart2(start)\n",
                              '.file [name="custom.prg", segments="Default"]\nBasicUpstart2(start)\n')
    res = verify_source(src, "c64-kickass", expect=Expectation(memory=[MemoryCheck(0xC000, 155)]))
    assert res.status == "verified", res.to_dict()


def test_c128_else():
    src = '10 n=7\n20 if n and 1 then print "odd":else print "even"\n30 end\n'
    res = verify_source(src, "c128-basic", expect=Expectation(["odd"], screen_excludes=["even"]))
    assert res.status == "verified", res.to_dict()
