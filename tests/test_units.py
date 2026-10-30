from commodore38.eval.runner import extract_code, load_tasks
from commodore38.petscii import screen_to_lines
from commodore38.verify import LANGUAGES, MemoryCheck
from commodore38.vice import RunResult, classify_screen

BOOT = ["    **** commodore 64 basic v2 ****", "", " 64k ram system  38911 basic bytes free", "", "ready."]


def test_screen_codes_to_text():
    assert screen_to_lines(bytes([8, 5, 12, 12, 15, 0x20, 0x31]), 40) == ["hello 1"]
    assert screen_to_lines(bytes([0x88]), 40) == ["h"]  # reverse video


def test_classify_waits_for_autostart():
    assert classify_screen(BOOT) is None


def test_classify_finished_and_error():
    assert classify_screen(BOOT + ["run", "hello", "", "ready."]) == "finished"
    assert classify_screen(BOOT + ["run", "?syntax  error in 20", "ready."]) == "basic_error"
    assert classify_screen(BOOT + ["run", "still going"]) is None


def test_classify_finished_with_poked_rows_below_cursor():
    # a program that pokes screen rows below the cursor, then ends: 'ready.' is not the last line
    assert classify_screen(BOOT + ["run", "done", "ready.", "", "", "llllllll"]) == "finished"


def test_classify_after_clear_screen():
    # chr$(147) wipes both the banner and the 'run' line
    assert classify_screen(["", "hello", "ready.", ""]) == "finished"


def test_output_lines_skip_banner():
    r = RunResult("finished", BOOT + ["run", " 6", "", "ready.", ""])
    assert r.output_lines() == [" 6"]


def test_memory_check_parsing():
    m = MemoryCheck.from_dict({"addr": "$d020", "value": 2, "mask": 15})
    assert (m.addr, m.value, m.mask) == (0xD020, 2, 15)


def test_extract_code_prefers_program_and_strips_thinking():
    answer = "<think>```basic\n10 rem draft\n```</think>Run it with `run`:\n```basic\n10 print \"hi\"\n20 end\n```\n```\nrun\n```"
    assert extract_code(answer) == "10 print \"hi\"\n20 end\n"
    assert extract_code("no code here") is None


def test_tasks_are_well_formed():
    tasks = load_tasks()
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids))
    for t in tasks:
        assert t["language"] in LANGUAGES
        assert t["reference"].strip()
        assert t["expect"].get("screen_contains") or t["expect"].get("memory")


def test_output_lines_keep_printed_run():
    # a program that prints RUN itself: only the autostart's 'run' line is skipped
    r = RunResult("finished", BOOT + ["run", "choice", "run", "ready.", ""])
    assert r.output_lines() == ["choice", "run"]
