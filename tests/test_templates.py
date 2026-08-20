import shutil
import subprocess

import pytest

from polyforge import templates

EXPECTED_KEYS = {"box", "shelf_bracket", "l_bracket", "cable_comb", "standoff_mount", "vase"}


def test_all_expected_templates_registered():
    assert {t.key for t in templates.all_templates()} == EXPECTED_KEYS


def test_generate_with_defaults_produces_scad_text():
    for template in templates.all_templates():
        source = template.generate(template.defaults())
        assert "module" in source
        assert "difference()" in source or "union()" in source
        for param in template.params:
            assert param.name in source


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_generated_scad_compiles(tmp_path):
    for template in templates.all_templates():
        scad_path = tmp_path / f"{template.key}.scad"
        scad_path.write_text(template.generate(template.defaults()))
        stl_path = tmp_path / f"{template.key}.stl"
        result = subprocess.run(
            ["openscad", "--render", "-o", str(stl_path), str(scad_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert stl_path.exists() and stl_path.stat().st_size > 0
