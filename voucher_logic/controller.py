"""Orchestrates the voucher analysis workflow."""
from __future__ import annotations

from typing import Optional

from . import models
from .extraction import RuleBasedVoucherExtractor, VoucherExtractor
from .highlight import HighlightRenderer
from .pdf_ingestor import PdfIngestor
from .persistence import AnalysisStore, InMemoryAnalysisStore
from .validators import VoucherValidator


def analyze_voucher(
    file_bytes: bytes,
    provider: models.ProviderType,
    *,
    pdf_ingestor: Optional[PdfIngestor] = None,
    extractor: Optional[RuleBasedVoucherExtractor] = None,
    validator: Optional[VoucherValidator] = None,
    highlight_renderer: Optional[HighlightRenderer] = None,
    store: Optional[AnalysisStore] = None,
    session_key: Optional[str] = None,
) -> models.VoucherAnalysisResult:
    pdf_ingestor = pdf_ingestor or PdfIngestor()
    validator = validator or VoucherValidator()
    highlight_renderer = highlight_renderer or HighlightRenderer()

    if extractor is None:
        extractor_instance = VoucherExtractor()
        def _extract(parsed: models.ParsedDocument, provider: models.ProviderType) -> models.ExtractedVoucherData:
            return extractor_instance.extract(parsed, provider)
    else:
        def _extract(parsed: models.ParsedDocument, provider: models.ProviderType) -> models.ExtractedVoucherData:
            return extractor.extract(parsed, provider)

    try:
        parsed = pdf_ingestor.parse(file_bytes)
    except Exception as exc:
        result = models.VoucherAnalysisResult.empty()
        result.errors.append(f"PDF parsing failed: {exc}")
        result.highlight_pdf = file_bytes
        return result

    try:
        extracted = _extract(parsed, provider)
    except Exception as exc:
        result = models.VoucherAnalysisResult(parsed_document=parsed)
        result.errors.append(f"Extraction failed: {exc}")
        return result

    validation = validator.validate(extracted)

    try:
        highlight_pdf = highlight_renderer.render(
            file_bytes,
            extracted.source_highlights,
            parsed_document=parsed,
        )
        warnings = []
    except Exception as exc:
        highlight_pdf = file_bytes
        warnings = [f"highlight rendering skipped: {exc}"]

    result = models.VoucherAnalysisResult(
        parsed_document=parsed,
        extracted=extracted,
        validation=validation,
        highlight_pdf=highlight_pdf,
        warnings=warnings,
    )

    if store and session_key:
        store.save(session_key, result)

    return result
