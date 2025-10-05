from voucher_logic import models
from voucher_logic.highlight import HighlightRenderer


def test_highlight_renderer_embeds_summary():
    renderer = HighlightRenderer()
    original_pdf = b"%PDF-1.4\nOriginal"
    spans = [models.HighlightSpan(page=1, bbox=(0, 0, 1, 1), label="company")]

    output = renderer.render(original_pdf, spans)

    assert output.startswith(b"%PDF")
    assert b"company" in output


def test_highlight_renderer_returns_original_when_no_spans():
    renderer = HighlightRenderer()

    output = renderer.render(b"PDF", [])

    assert output == b"PDF"
