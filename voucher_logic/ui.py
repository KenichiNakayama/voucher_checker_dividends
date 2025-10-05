"""Helpers for presenting voucher analysis results."""
from __future__ import annotations

from typing import Dict, List

from . import models

STATUS_ICON = {
    models.RequirementState.PASS: "✅",
    models.RequirementState.FAIL: "❌",
    models.RequirementState.UNKNOWN: "⚠️",
}


def build_validation_rows(report: models.ValidationReport) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for key, status in report.requirements.items():
        icon = STATUS_ICON.get(status.status, "")
        rows.append(
            {
                "label": key,
                "status": status.status.name,
                "icon": icon,
                "message": status.message,
            }
        )
    return rows


def format_extracted_fields(data: models.ExtractedVoucherData) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for label, field_value in data.iter_required_fields():
        entries.append(
            {
                "label": label,
                "value": "" if field_value.value is None else str(field_value.value),
                "confidence": _format_confidence(field_value.confidence),
            }
        )
    for key, field_value in data.others.items():
        entries.append(
            {
                "label": key,
                "value": "" if field_value.value is None else str(field_value.value),
                "confidence": _format_confidence(field_value.confidence),
            }
        )
    return entries


def _format_confidence(confidence) -> str:
    if confidence is None:
        return "-"
    return f"{confidence:.2f}"


__all__ = ["build_validation_rows", "format_extracted_fields"]
