import datetime as dt
from decimal import Decimal

import pytest

from voucher_logic import models


def test_field_value_supports_metadata():
    span = models.HighlightSpan(page=1, bbox=(0.1, 0.2, 0.3, 0.4), label="company")
    field = models.FieldValue(value="ACME Corp", confidence=0.9, source_spans=[span])

    assert field.value == "ACME Corp"
    assert pytest.approx(field.confidence, rel=1e-3) == 0.9
    assert field.source_spans[0].label == "company"


def test_voucher_analysis_result_collects_components():
    parsed = models.ParsedDocument(pages=["Sample"], tokens=[], metadata={})
    extracted = models.ExtractedVoucherData(
        title=models.FieldValue(value="Dividend Resolution", confidence=0.8),
        company_name=models.FieldValue(value="ACME Holdings", confidence=0.95),
        resolution_date=models.FieldValue(value=dt.date(2024, 1, 1)),
        dividend_amount=models.FieldValue(value=Decimal("1000000")),
        others={},
        source_highlights=[],
    )
    validation = models.ValidationReport(
        requirements={
            "title": models.RequirementStatus(status=models.RequirementState.PASS, message="ok"),
        },
        overall_status=models.ValidationOutcome.PASS,
    )
    result = models.VoucherAnalysisResult(
        parsed_document=parsed,
        extracted=extracted,
        validation=validation,
        highlight_pdf=b"%PDF-1.4 placeholder",
        errors=[],
        warnings=["No highlights"],
    )

    assert result.validation.overall_status is models.ValidationOutcome.PASS
    assert result.extracted.company_name.value == "ACME Holdings"
    assert result.highlight_pdf.startswith(b"%PDF")
    assert result.warnings == ["No highlights"]


def test_provider_type_from_string_handles_case():
    assert models.ProviderType.from_string("openai") is models.ProviderType.OPENAI
    assert models.ProviderType.from_string("CLAUDE") is models.ProviderType.CLAUDE
    with pytest.raises(ValueError):
        models.ProviderType.from_string("azure")
