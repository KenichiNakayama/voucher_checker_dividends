from voucher_logic import models
from voucher_logic.ui import build_validation_rows, format_extracted_fields


def test_build_validation_rows_maps_status():
    report = models.ValidationReport.empty()
    report.register("title", models.RequirementStatus(models.RequirementState.PASS, "ok"))
    report.register("company_name", models.RequirementStatus(models.RequirementState.FAIL, "missing"))

    rows = build_validation_rows(report)

    assert rows[0]["status"] == "PASS"
    assert rows[1]["status"] == "FAIL"
    assert rows[1]["message"] == "missing"


def test_format_extracted_fields_outputs_display_data():
    data = models.ExtractedVoucherData.empty()
    data.company_name = models.FieldValue(value="ACME", notes=None)
    data.dividend_amount = models.FieldValue(value="1000")

    formatted = format_extracted_fields(data)

    assert any(entry["label"] == "company_name" for entry in formatted)
    amount_entry = next(entry for entry in formatted if entry["label"] == "dividend_amount")
    assert amount_entry["value"] == "1000"
    assert amount_entry["confidence"] == "-"
