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
