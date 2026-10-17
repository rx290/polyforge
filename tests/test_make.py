"""make: the checker loop, with a scripted fake LLM (no network)."""
import pytest

pytest.importorskip("build123d")
from polyforge.make import make, requested_sizes

GOOD = """```python
from build123d import *
outer = Box(120, 80, 50, align=(Align.MIN, Align.MIN, Align.MIN))
inner = Pos(2, 2, 2) * Box(116, 76, 48, align=(Align.MIN, Align.MIN, Align.MIN))
result = outer - inner
```"""
WRONG_SIZE = GOOD.replace("Box(120, 80, 50", "Box(110, 80, 50").replace("Box(116, 76, 48", "Box(106, 76, 48")
BROKEN = "```python\nresult = Box(1, 2)\n```"


def fake(replies):
    seen = []
    def chat(messages):
        seen.append(messages[-1]["content"]); return replies[len(seen) - 1]
    chat.seen = seen
    return chat


def test_sizes_are_parsed_from_the_request():
    assert requested_sizes("a box 120x80x50 mm with lid") == [50.0, 80.0, 120.0]
    assert requested_sizes("plate 60 x 40 mm") == [40.0, 60.0]
    assert requested_sizes("a hook") == []


def test_errors_and_wrong_sizes_are_fed_back_until_it_is_right(tmp_path):
    chat = fake([BROKEN, WRONG_SIZE, GOOD])
    res = make("a storage box 120x80x50 mm, 2 mm walls, open top", tmp_path, chat=chat, lang="build123d")
    assert res.ok and res.rounds == 3 and res.stl.exists() and res.step.exists()
    assert "Error" in chat.seen[1] or "error" in chat.seen[1].lower()
    assert "requested overall size 120.0" in chat.seen[2]


def test_gives_up_after_the_round_limit_and_keeps_the_script(tmp_path):
    res = make("a box 10x10x10 mm", tmp_path, rounds=2, chat=fake([BROKEN, BROKEN]), lang="build123d")
    assert not res.ok and res.script.exists()


SCAD_GOOD = "```openscad\ndifference(){cube([120,80,50]); translate([2,2,2]) cube([116,76,49]);}\n```"
SCAD_BAD = "```openscad\ncube([120,80,50]\n```"


def test_openscad_loop_fixes_a_syntax_error(tmp_path):
    res = make("a storage box 120x80x50 mm, open top", tmp_path, chat=fake([SCAD_BAD, SCAD_GOOD]))
    assert res.ok and res.rounds == 2 and res.stl.exists() and res.step is None
