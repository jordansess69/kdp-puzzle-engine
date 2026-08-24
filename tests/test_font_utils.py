"""Targeted tests for the shared font resolver (font_utils)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import font_utils


def test_search_dirs_prefers_windows_system_then_user_fonts(monkeypatch):
    monkeypatch.setenv("WINDIR", r"D:\FakeWin")
    monkeypatch.setenv("LOCALAPPDATA", r"D:\FakeUser")
    dirs = font_utils.font_search_dirs()
    assert dirs[0] == Path(r"D:\FakeWin\Fonts")
    assert Path(r"D:\FakeUser\Microsoft\Windows\Fonts") == dirs[1]


def test_resolve_font_file_finds_bare_name_in_search_dirs(tmp_path, monkeypatch):
    fake = tmp_path / "fakefont.ttf"
    fake.write_bytes(b"not a real font")
    monkeypatch.setattr(font_utils, "font_search_dirs", lambda: [tmp_path])
    assert font_utils.resolve_font_file(["missing.ttf", "fakefont.ttf"]) == fake


def test_resolve_font_file_tries_absolute_paths_directly(tmp_path):
    real = tmp_path / "abs.ttf"
    real.write_bytes(b"x")
    assert font_utils.resolve_font_file([str(real)]) == real
    assert font_utils.resolve_font_file(["definitely_missing_xyz.ttf"]) is None
    assert font_utils.resolve_font_file([""]) is None


class _FakePdfMetrics:
    def __init__(self, registered=()):
        self.registered = list(registered)
        self.calls = []

    def getRegisteredFontNames(self):
        return list(self.registered)

    def registerFont(self, font):
        self.calls.append(font)


def _patch_reportlab(monkeypatch, metrics):
    # The submodules must be imported before they can be patched by name.
    import reportlab.pdfbase.pdfmetrics  # noqa: F401
    import reportlab.pdfbase.ttfonts  # noqa: F401
    monkeypatch.setattr("reportlab.pdfbase.pdfmetrics", metrics)
    monkeypatch.setattr(
        "reportlab.pdfbase.ttfonts.TTFont", lambda alias, path: (alias, path)
    )


def test_register_pdf_font_registers_first_resolvable_candidate(tmp_path, monkeypatch):
    bold = tmp_path / "arialbd.ttf"
    bold.write_bytes(b"x")
    monkeypatch.setattr(font_utils, "font_search_dirs", lambda: [tmp_path])
    metrics = _FakePdfMetrics()
    _patch_reportlab(monkeypatch, metrics)
    assert font_utils.register_pdf_font("SansB", ["nope.ttf", "arialbd.ttf"]) is True
    assert metrics.calls == [("SansB", str(bold))]


def test_register_pdf_font_skips_already_registered_alias(monkeypatch):
    metrics = _FakePdfMetrics(registered=["BookSans"])
    _patch_reportlab(monkeypatch, metrics)
    assert font_utils.register_pdf_font("BookSans", []) is True
    assert metrics.calls == []


def test_register_pdf_font_returns_false_when_nothing_resolves(monkeypatch):
    monkeypatch.setattr(font_utils, "font_search_dirs", lambda: [])
    metrics = _FakePdfMetrics()
    _patch_reportlab(monkeypatch, metrics)
    assert font_utils.register_pdf_font("Sans", ["ghost.ttf"]) is False
    assert metrics.calls == []


def test_load_image_font_falls_back_to_pillow_default():
    from PIL import ImageFont

    fallback = font_utils.load_image_font(["definitely_missing_xyz.ttf"], 10)
    assert type(fallback) is type(ImageFont.load_default())


def test_load_image_font_loads_a_real_font_when_present():
    from PIL import ImageFont

    candidates = font_utils.image_font_candidates("sans-bold")
    if font_utils.resolve_font_file(candidates) is None:
        pytest.skip("No sans-bold system font available on this machine.")
    loaded = font_utils.load_image_font(candidates, 12)
    assert isinstance(loaded, ImageFont.FreeTypeFont)
    assert loaded.size == 12


def test_wordsearch_aliases_register_with_real_fonts():
    import wordsearch

    families = [font_utils.pdf_font_candidates(f) for f in wordsearch.PDF_FONT_FAMILIES.values()]
    if any(font_utils.resolve_font_file(candidates) is None for candidates in families):
        pytest.skip("Standard system fonts are unavailable on this machine.")
    wordsearch.register_fonts()
    for alias in wordsearch.PDF_FONT_FAMILIES:
        assert alias in __import__("reportlab.pdfbase.pdfmetrics", fromlist=["x"]).getRegisteredFontNames()


def test_family_candidate_order_keeps_legacy_fallbacks():
    # The first two sans-bold hits must stay the historical macOS path then the
    # classic Windows file, so existing machines keep rendering identically.
    assert font_utils.image_font_candidates("sans-bold")[:2] == (
        ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "arialbd.ttf"])
    mono = font_utils.pdf_font_candidates("mono-bold")
    assert mono.index("courbd.ttf") < mono.index("DejaVuSansMono-Bold.ttf")
    # cover.py's display-mono chain intentionally falls back to Arial Bold.
    assert font_utils.image_font_candidates("display-mono")[1] == "arialbd.ttf"
