import io

import pytest

from voucher_logic import models
from voucher_logic.controller import analyze_voucher
from voucher_logic.persistence import InMemoryAnalysisStore
from voucher_logic.pdf_ingestor import PdfIngestor
from voucher_logic.extraction import RuleBasedVoucherExtractor
from voucher_logic.validators import VoucherValidator
from voucher_logic.highlight import HighlightRenderer


class FailingPdfIngestor(PdfIngestor):
    def parse(self, file_bytes: bytes) -> models.ParsedDocument:
        raise ValueError("bad pdf")


class DummyHighlightRenderer(HighlightRenderer):
    def render(self, original_pdf: bytes, spans, parsed_document=None):
        raise RuntimeError("highlight failure")


SAMPLE_DOC = b"Dividend Resolution\nCompany: ACME Holdings\nDate: 2024-01-01\nAmount: 1000000"


def test_analyze_voucher_success_round_trip():
    store = InMemoryAnalysisStore()
    result = analyze_voucher(
        SAMPLE_DOC,
        provider=models.ProviderType.OPENAI,
        pdf_ingestor=PdfIngestor(),
        extractor=RuleBasedVoucherExtractor(),
        validator=VoucherValidator(),
        highlight_renderer=HighlightRenderer(),
        store=store,
        session_key="sess-1",
    )

    assert result.validation.overall_status is models.ValidationOutcome.PASS
    assert result.extracted.company_name.value == "ACME Holdings"
    assert store.load("sess-1") is result


def test_analyze_voucher_handles_ingest_error():
    result = analyze_voucher(
        SAMPLE_DOC,
        provider=models.ProviderType.CLAUDE,
        pdf_ingestor=FailingPdfIngestor(),
        extractor=RuleBasedVoucherExtractor(),
        validator=VoucherValidator(),
        highlight_renderer=HighlightRenderer(),
    )

    assert result.errors
    assert result.validation.overall_status is models.ValidationOutcome.UNKNOWN


def test_analyze_voucher_handles_highlight_failure():
    result = analyze_voucher(
        SAMPLE_DOC,
        provider=models.ProviderType.OPENAI,
        pdf_ingestor=PdfIngestor(),
        extractor=RuleBasedVoucherExtractor(),
        validator=VoucherValidator(),
        highlight_renderer=DummyHighlightRenderer(),
    )

    assert "highlight" in result.warnings[0]
    assert result.highlight_pdf == SAMPLE_DOC
