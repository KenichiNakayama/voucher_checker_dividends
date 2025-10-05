from voucher_logic import models
from voucher_logic.highlight import HighlightRenderer


def test_highlight_renderer_creates_visual_pdf():
    renderer = HighlightRenderer()
    original_pdf = b"%PDF-1.4\nOriginal"
    parsed = models.ParsedDocument(
        pages=["Line one\nHighlighted line"],
        tokens=[
            models.TextSpan(page=1, text="Highlighted line", bbox=(0.1, 0.3, 0.9, 0.4)),
        ],
    )
    spans = [models.HighlightSpan(page=1, bbox=(0.1, 0.3, 0.9, 0.4), label="company")]

    output = renderer.render(original_pdf, spans, parsed_document=parsed)

    assert output.startswith(b"%PDF")
    assert b"Span" not in output  # ensure we no longer emit textual summary


def test_highlight_renderer_returns_original_when_no_spans():
    renderer = HighlightRenderer()
    parsed = models.ParsedDocument(pages=["Line"], tokens=[])

    output = renderer.render(b"PDF", [], parsed_document=parsed)

    assert output == b"PDF"
