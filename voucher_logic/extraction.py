"""Voucher extraction services."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from . import models
from .llm.clients import DummyLLMClient, LLMClientFactory

COMPANY_PATTERN = re.compile(r"Company\s*[:：]\s*(.+)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"Date\s*[:：]\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"Amount\s*[:：]\s*([\d,\.]+)", re.IGNORECASE)
TITLE_PATTERN = re.compile(r"^(Dividend Resolution|配当決議.*)$", re.IGNORECASE)


class ExtractionError(RuntimeError):
    """Raised when extraction cannot complete."""


@dataclass
class ExtractionResult:
    data: models.ExtractedVoucherData
    raw_response: Optional[Dict[str, object]] = None


class RuleBasedVoucherExtractor:
    """Fallback extractor based on regex heuristics."""

    def extract(self, parsed: models.ParsedDocument, provider: models.ProviderType) -> models.ExtractedVoucherData:
        text = "\n".join(parsed.pages)
        highlights: List[models.HighlightSpan] = []

        title_value = self._match_title(parsed)
        company_match = COMPANY_PATTERN.search(text)
        date_match = DATE_PATTERN.search(text)
        amount_match = AMOUNT_PATTERN.search(text)

        data = models.ExtractedVoucherData.empty()
        data.title = models.FieldValue(value=title_value, confidence=0.4)
        if company_match:
            value = company_match.group(1).strip()
            span = self._make_span(parsed, value, label="company")
            data.company_name = models.FieldValue(value=value, confidence=0.5, source_spans=[span])
            highlights.append(span)
        if date_match:
            value = date_match.group(1).strip()
            span = self._make_span(parsed, value, label="resolution_date")
            data.resolution_date = models.FieldValue(value=value, confidence=0.5, source_spans=[span])
            highlights.append(span)
        if amount_match:
            value = amount_match.group(1).strip()
            span = self._make_span(parsed, value, label="dividend_amount")
            data.dividend_amount = models.FieldValue(value=value, confidence=0.4, source_spans=[span])
            highlights.append(span)

        data.source_highlights = highlights
        return data

    def _make_span(self, parsed: models.ParsedDocument, needle: str, label: str) -> models.HighlightSpan:
        for token in parsed.tokens:
            if needle.lower() in token.text.lower():
                return models.HighlightSpan(page=token.page, bbox=(0.0, 0.0, 1.0, 0.2), label=label)
        return models.HighlightSpan(page=1, bbox=(0.0, 0.0, 1.0, 0.2), label=label)

    def _match_title(self, parsed: models.ParsedDocument) -> Optional[str]:
        for token in parsed.tokens:
            if TITLE_PATTERN.match(token.text.strip()):
                return token.text.strip()
        return parsed.pages[0].splitlines()[0].strip() if parsed.pages and parsed.pages[0] else None


class VoucherExtractor:
    """High-level extractor that can leverage LLM providers."""

    def __init__(
        self,
        llm_factory: Optional[LLMClientFactory] = None,
        fallback: Optional[RuleBasedVoucherExtractor] = None,
    ) -> None:
        self._llm_factory = llm_factory or LLMClientFactory.build_default()
        self._fallback = fallback or RuleBasedVoucherExtractor()

    def extract(self, parsed: models.ParsedDocument, provider: models.ProviderType) -> models.ExtractedVoucherData:
        try:
            client = self._llm_factory.create(provider)
        except KeyError:
            return self._fallback.extract(parsed, provider)

        if isinstance(client, DummyLLMClient):
            return client.extract_structured(parsed)

        try:
            response = client.extract(parsed)
        except Exception as exc:  # pragma: no cover - network path not used in tests
            raise ExtractionError(str(exc)) from exc

        return self._from_llm_response(parsed, response)

    def _from_llm_response(self, parsed: models.ParsedDocument, response: Dict[str, object]) -> models.ExtractedVoucherData:
        data = models.ExtractedVoucherData.empty()
        highlights: List[models.HighlightSpan] = []

        def value_for(key: str) -> Optional[str]:
            value = response.get(key)
            if isinstance(value, str):
                return value
            return None

        data.title = models.FieldValue(value=value_for("title"))
        data.company_name = models.FieldValue(value=value_for("company_name"))
        data.resolution_date = models.FieldValue(value=value_for("resolution_date"))
        amount = value_for("dividend_amount")
        if amount is not None and isinstance(amount, str):
            data.dividend_amount = models.FieldValue(value=amount)

        highlight_entries = response.get("highlights")
        if isinstance(highlight_entries, Iterable):
            for entry in highlight_entries:
                if not isinstance(entry, dict):
                    continue
                page = int(entry.get("page", 1))
                bbox = entry.get("bbox", (0.0, 0.0, 1.0, 0.2))
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    span = models.HighlightSpan(page=page, bbox=tuple(float(x) for x in bbox), label=entry.get("label"))
                    highlights.append(span)
        data.source_highlights = highlights
        return data
