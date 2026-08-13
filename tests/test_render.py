from polyforge import render


def test_render_uses_defaults():
    source, merged = render.render("box", {})
    assert merged["width"] == 60
    assert "width = 60" in source


def test_render_applies_overrides():
    source, merged = render.render("box", {"width": 100})
    assert merged["width"] == 100
    assert merged["depth"] == 40  # untouched default
    assert "width = 100" in source
