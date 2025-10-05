from voucher_logic import models
from voucher_logic.validators import VoucherValidator


def make_field(value, label):
    return models.FieldValue(value=value, source_spans=[models.HighlightSpan(page=1, bbox=(0, 0, 1, 1), label=label)])


def test_validator_passes_when_all_required_fields_present():
    data = models.ExtractedVoucherData(
        title=make_field("Dividend Resolution", "title"),
        company_name=make_field("ACME", "company"),
        resolution_date=make_field("2024-01-01", "date"),
        dividend_amount=make_field("1000000", "amount"),
    )
    validator = VoucherValidator()

    report = validator.validate(data)

    assert report.overall_status is models.ValidationOutcome.PASS
    assert all(status.status is models.RequirementState.PASS for status in report.requirements.values())


def test_validator_flags_missing_fields():
    data = models.ExtractedVoucherData(
        title=models.FieldValue.empty("Missing"),
        company_name=make_field("ACME", "company"),
        resolution_date=models.FieldValue.empty("No date"),
        dividend_amount=models.FieldValue.empty(),
    )
    validator = VoucherValidator()

    report = validator.validate(data)

    assert report.requirements["title"].status is models.RequirementState.FAIL
    assert report.requirements["resolution_date"].status is models.RequirementState.FAIL
    assert report.requirements["dividend_amount"].status is models.RequirementState.FAIL
    assert report.overall_status is models.ValidationOutcome.FAIL
