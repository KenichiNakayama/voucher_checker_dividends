import importlib.util

import pytest

from voucher_logic import models
from voucher_logic.highlight import HighlightRenderer


def test_highlight_renderer_creates_visual_pdf():
    if importlib.util.find_spec("fitz") is None:
        pytest.skip("PyMuPDF not available")

    import fitz  # type: ignore

    renderer = HighlightRenderer()
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((80, 550), "Highlighted line")
    original_pdf = doc.tobytes(deflate=True)
    doc.close()
    parsed = models.ParsedDocument(
        pages=["Line one\nHighlighted line"],
        tokens=[
            models.TextSpan(page=1, text="Highlighted line", bbox=(0.1, 0.3, 0.9, 0.4)),
        ],
    )
    spans = [models.HighlightSpan(page=1, bbox=(0.1, 0.3, 0.9, 0.4), label="company")]

    output = renderer.render(original_pdf, spans, parsed_document=parsed)

    assert output.startswith(b"%PDF")
    assert b"Annots" in output
    assert output != original_pdf


def test_highlight_renderer_returns_original_when_no_spans():
    renderer = HighlightRenderer()
    parsed = models.ParsedDocument(pages=["Line"], tokens=[])

    output = renderer.render(b"PDF", [], parsed_document=parsed)

    assert output == b"PDF"
