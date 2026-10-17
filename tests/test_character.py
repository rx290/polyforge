"""Character mode runs an external pipeline; these tests use a fake pipeline script so no GPU is needed."""
import sys
import textwrap

import pytest

from polyforge import character, cli

FAKE = textwrap.dedent('''
    import sys, os
    name, out, height, steps, tokens, depth = sys.argv[1:7]
    slug = "".join(ch if ch.isalnum() else "_" for ch in name)[:40].strip("_")
    if "boom" in name:
        print("RuntimeError: HIP out of memory"); sys.exit(1)
    print("prompt: a figure of", name)
    print("anatomy scores:", [7.0, 9.0] if os.environ.get("CHAR_CANDIDATES") == "2" else [0.0])
    print("printable check: watertight=True")
    open(os.path.join(out, slug + ".stl"), "w").write("solid x\\nendsolid x\\n")
    open(os.path.join(out, slug + "_image.png"), "wb").write(b"png")
    print(f"CHARACTER_OK {slug}: 1s, 10 faces, watertight=True, [{height}] mm, steps={steps} tokens={tokens} depth={depth}")
''')


@pytest.fixture
def fake_pipeline(tmp_path, monkeypatch):
    script = tmp_path / "fake_character.py"
    script.write_text(FAKE)
    monkeypatch.setenv("POLYFORGE_CHARACTER_PIPELINE", str(script))
    monkeypatch.setenv("POLYFORGE_CHARACTER_PYTHON", sys.executable)
    monkeypatch.setenv("POLYFORGE_CHARACTER_CWD", str(tmp_path))
    return tmp_path


def test_generate_returns_stl_image_and_scores(fake_pipeline):
    stages = []
    res = character.generate("three Spider-Man figures pointing", fake_pipeline / "out", height_mm=120, candidates=2,
                             on_progress=lambda d, t, label: stages.append(label))
    assert res.stl.name == "three_Spider_Man_figures_pointing.stl" and res.stl.exists()
    assert res.image.exists()
    assert "[120] mm" in res.summary and "tokens=2048" in res.summary   # full quality by default
    assert res.anatomy_scores == "[7.0, 9.0]"
    assert stages[-1] == "done"


def test_fast_quality_passes_smaller_triposg_settings(fake_pipeline):
    res = character.generate("a cute owl", fake_pipeline / "out", quality="fast", candidates=1)
    assert "steps=30 tokens=1024 depth=8" in res.summary


def test_pipeline_failure_is_reported_with_its_error(fake_pipeline):
    with pytest.raises(character.CharacterError, match="HIP out of memory"):
        character.generate("boom", fake_pipeline / "out")


def test_missing_pipeline_explains_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("POLYFORGE_CHARACTER_PIPELINE", str(tmp_path / "nope.py"))
    ok, why = character.available()
    assert not ok and "nope.py" in why
    with pytest.raises(character.CharacterError, match="not set up"):
        character.generate("goku", tmp_path)


def test_empty_text_and_bad_options_are_rejected(fake_pipeline):
    with pytest.raises(character.CharacterError):
        character.generate("  ", fake_pipeline)
    with pytest.raises(character.CharacterError):
        character.generate("goku", fake_pipeline, quality="ultra")
    with pytest.raises(character.CharacterError):
        character.generate("goku", fake_pipeline, image_model="dalle")


def test_cli_character_command(fake_pipeline, capsys):
    rc = cli.main(["character", "Goku in a fighting stance", "--out", str(fake_pipeline / "cli"), "--candidates", "1"])
    out = capsys.readouterr().out
    assert rc == 0 and "STL:" in out and "Goku_in_a_fighting_stance.stl" in out


def test_gui_character_json_paths_are_workdir_relative(fake_pipeline):
    from polyforge.gui import app
    data = app.character_json({"text": "a duck", "candidates": 1}, fake_pipeline)
    assert data["stl"] == "characters/a_duck.stl" and data["image"] == "characters/a_duck_image.png"
    assert app.character_status_json()["available"] is True


def test_gpu_fault_is_retried_once(fake_pipeline):
    flag = fake_pipeline / "faulted"
    script = fake_pipeline / "fake_character.py"
    script.write_text(f"import os, sys\nif not os.path.exists({str(flag)!r}):\n    open({str(flag)!r}, 'w').close()\n"
                      "    print('Memory access fault by GPU node-1'); sys.exit(134)\n" + FAKE)
    res = character.generate("a cute owl", fake_pipeline / "out", candidates=1)
    assert res.stl.exists() and flag.exists()
