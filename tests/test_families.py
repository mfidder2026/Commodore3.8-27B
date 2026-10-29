from collections import Counter

from commodore38.data.families import FAMILIES, generate_tasks
from commodore38.eval.runner import load_tasks
from commodore38.verify import Expectation

COUNTS = {"c64-basic": 80, "c128-basic": 70, "c64-kickass": 50}


def test_generation_is_deterministic():
    a = [t.prompt for t in generate_tasks(COUNTS, seed=1)]
    b = [t.prompt for t in generate_tasks(COUNTS, seed=1)]
    assert a == b


def test_every_family_is_used_and_counts_match():
    tasks = generate_tasks(COUNTS)
    assert Counter(t.language for t in tasks) == Counter(COUNTS)
    for lang, fams in FAMILIES.items():
        used = {t.family for t in tasks if t.language == lang}
        assert len(used) == len(fams), lang


def test_no_overlap_with_benchmark():
    eval_prompts = {t["prompt"] for t in load_tasks()}
    eval_ids = {t["id"].split("-", 1)[1] for t in load_tasks()}
    tasks = generate_tasks(COUNTS)
    assert not eval_prompts & {t.prompt for t in tasks}
    assert not eval_ids & {t.family for t in tasks}


def test_expectations_parse():
    for t in generate_tasks(COUNTS):
        exp = Expectation.from_dict(t.expect)
        assert exp.screen_contains or exp.memory
        for m in exp.memory:
            assert 0 <= m.value <= 255 and 0 <= m.addr <= 0xFFFF


def test_only_restricts_families():
    tasks = generate_tasks({"c64-basic": 6, "c128-basic": 4}, only={"clear_print", "dec"})
    assert {t.family for t in tasks} == {"clear_print", "dec"}
    assert all(t.language == "c64-basic" for t in tasks if t.family == "clear_print")


def test_strip_c128_boilerplate():
    from commodore38.data.assemble import strip_boilerplate
    code = "10 rem demo\n20 graphic 0\n30 scnclr 0\n40 color 0,1:color 4,1:color 5,2\n50 print \"hi\"\n"
    assert strip_boilerplate(code) == "10 rem demo\n50 print \"hi\"\n"
    keep = "10 color 0,1:print \"x\"\n"
    assert strip_boilerplate(keep) == keep
