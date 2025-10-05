"""Validation routines for extracted voucher data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict

from . import models


class VoucherValidator:
    """Validates extracted voucher fields against business rules."""

    def __init__(self) -> None:
        self._requirements: Dict[str, str] = {
            "title": "配当決議書のタイトルが確認できません",
            "company_name": "配当決議の会社名が確認できません",
            "resolution_date": "配当決議日が確認できません",
            "dividend_amount": "配当金額が確認できません",
        }

    def validate(self, data: models.ExtractedVoucherData) -> models.ValidationReport:
        report = models.ValidationReport.empty()
        for field_name, message in self._requirements.items():
            field_value = getattr(data, field_name)
            status = self._evaluate_field(field_name, field_value, message)
            report.register(field_name, status)
        return report

    def _evaluate_field(
        self,
        field_name: str,
        field_value: models.FieldValue,
        missing_message: str,
    ) -> models.RequirementStatus:
        if not field_value or not field_value.is_set:
            return models.RequirementStatus(models.RequirementState.FAIL, missing_message)

        if field_name == "resolution_date":
            if not self._is_valid_date(field_value.value):
                return models.RequirementStatus(
                    models.RequirementState.FAIL,
                    "日付形式が不正です (YYYY-MM-DD)",
                )
        if field_name == "dividend_amount":
            if not self._is_valid_amount(field_value.value):
                return models.RequirementStatus(
                    models.RequirementState.FAIL,
                    "金額の形式が不正です",
                )

        return models.RequirementStatus(models.RequirementState.PASS, "")

    def _is_valid_date(self, value) -> bool:
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.strptime(value.strip(), "%Y-%m-%d")
                return True
            except ValueError:
                return False
        return False

    def _is_valid_amount(self, value) -> bool:
        if isinstance(value, (int, float, Decimal)):
            return True
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            try:
                Decimal(cleaned)
                return True
            except (InvalidOperation, ValueError):
                return False
        return False


__all__ = ["VoucherValidator"]
