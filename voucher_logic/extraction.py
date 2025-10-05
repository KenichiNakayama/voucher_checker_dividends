"""Voucher extraction services."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import models
from .llm.clients import DummyLLMClient, LLMClientFactory

TITLE_PATTERN = re.compile(r"^(Dividend\s+Resolution|配当決議.*|Board\s+Resolution.*|配当.*報告書)$", re.IGNORECASE)
COMPANY_LINE_PATTERN = re.compile(
    r"(?:Company\s*(?:Name)?|会社名|社名|Corporate\s+Name)\s*[:：-]\s*(.+)",
    re.IGNORECASE,
)
COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(?:Inc\.?|Corp\.?|Corporation|Company|Co\.?|Holdings|Limited|Ltd\.?|K\.K\.|LLC|GmbH|Kabushiki\s+Kaisha)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
KANJI_DATE_PATTERN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
REIWA_DATE_PATTERN = re.compile(r"令和(\d{1,2})年(\d{1,2})月(\d{1,2})日")
DIVIDEND_LINE_PATTERN = re.compile(
    r"(?:Total\s+(?:Amount\s+of\s+)?Dividends|配当金額|総配当金額|1株当たり配当金|Dividends\s+per\s+Share)\s*[:：-]?\s*(.+)",
    re.IGNORECASE,
)
NUMERIC_AMOUNT_PATTERN = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|\d+(?:\.\d+)?)")


class ExtractionError(RuntimeError):
    """Raised when extraction cannot complete."""


@dataclass
class ExtractionResult:
    data: models.ExtractedVoucherData
    raw_response: Optional[Dict[str, object]] = None


class RuleBasedVoucherExtractor:
    """Fallback extractor based on regex heuristics."""

    def extract(self, parsed: models.ParsedDocument, provider: models.ProviderType) -> models.ExtractedVoucherData:
        highlights: List[models.HighlightSpan] = []

        data = models.ExtractedVoucherData.empty()
        data.title = self._extract_title(parsed)
        if data.title.source_spans:
            highlights.extend(data.title.source_spans)

        company = self._extract_company(parsed)
        if company:
            data.company_name = self._field_with_span(company, parsed, label="company_name", confidence=0.85)
            highlights.extend(data.company_name.source_spans)

        resolution_date = self._extract_resolution_date(parsed)
        if resolution_date:
            data.resolution_date = self._field_with_span(
                resolution_date,
                parsed,
                label="resolution_date",
                confidence=0.8,
            )
            highlights.extend(data.resolution_date.source_spans)

        amount = self._extract_dividend_amount(parsed)
        if amount:
            data.dividend_amount = self._field_with_span(
                amount,
                parsed,
                label="dividend_amount",
                confidence=0.75,
            )
            highlights.extend(data.dividend_amount.source_spans)

        data.source_highlights = highlights
        return data

    def _extract_title(self, parsed: models.ParsedDocument) -> models.FieldValue:
        for token in parsed.tokens:
            if TITLE_PATTERN.match(token.text.strip()):
                span = self._highlight_from_token(token, label="title")
                return models.FieldValue(value=token.text.strip(), confidence=0.9, source_spans=[span])

        if parsed.pages:
            first_page_lines = [line.strip() for line in parsed.pages[0].splitlines() if line.strip()]
            if first_page_lines:
                value = first_page_lines[0]
                span = self._find_span_by_text(parsed, value, label="title")
                if span:
                    return models.FieldValue(value=value, confidence=0.6, source_spans=[span])
                return models.FieldValue(value=value, confidence=0.6)
        return models.FieldValue.empty()

    def _extract_company(self, parsed: models.ParsedDocument) -> Optional[str]:
        lines = list(self._iter_page_lines(parsed))
        for _, _, text in lines:
            match = COMPANY_LINE_PATTERN.search(text)
            if match:
                return match.group(1).strip().strip("・:：")

        candidate = self._find_company_candidate_by_proximity(lines)
        if candidate:
            return candidate
        return None

    def _find_company_candidate_by_proximity(self, lines: Sequence[Tuple[int, int, str]]) -> Optional[str]:
        top_candidates: List[str] = []
        for page, index, text in lines:
            if index > 8:
                break
            if COMPANY_SUFFIX_PATTERN.search(text):
                top_candidates.append(text.strip())

        if top_candidates:
            return top_candidates[0]

        for idx, (_, _, text) in enumerate(lines):
            lower = text.lower()
            if lower.startswith("address") or "corporate number" in lower:
                # Prefer the line immediately before address block.
                for back in range(1, 4):
                    if idx - back < 0:
                        continue
                    candidate = lines[idx - back][2].strip()
                    if candidate and not candidate.lower().startswith("address"):
                        return candidate
        return None

    def _extract_resolution_date(self, parsed: models.ParsedDocument) -> Optional[str]:
        lines = list(self._iter_page_lines(parsed))
        for page_index, _, text in lines:
            normalized = self._match_date(text)
            if not normalized:
                continue
            lower = text.lower()
            if "meeting" in lower or "resolved" in lower or "決議" in lower or "取締役会" in lower:
                return normalized

        for _, _, text in lines:
            normalized = self._match_date(text)
            if normalized:
                return normalized
        return None

    def _extract_dividend_amount(self, parsed: models.ParsedDocument) -> Optional[str]:
        for _, _, text in self._iter_page_lines(parsed):
            match = DIVIDEND_LINE_PATTERN.search(text)
            if match:
                amount_candidate = match.group(1)
                numeric = self._extract_numeric(amount_candidate)
                if numeric:
                    return numeric

        for _, _, text in self._iter_page_lines(parsed):
            lower = text.lower()
            if "dividend" not in lower and "配当" not in lower:
                continue
            numeric = self._extract_numeric(text)
            if numeric:
                return numeric
        return None

    def _extract_numeric(self, text: str) -> Optional[str]:
        normalized = text.replace("JPY", "").replace("¥", "").replace("円", "")
        match = NUMERIC_AMOUNT_PATTERN.search(normalized)
        if match:
            return match.group(1)

        if "億" in text:
            try:
                prefix = text.split("億")[0]
                numeric_match = NUMERIC_AMOUNT_PATTERN.search(prefix.replace(",", ""))
                if not numeric_match:
                    return None
                billions = float(numeric_match.group(1))
                return f"{int(billions * 100000000):,}"
            except Exception:
                return None
        return None

    def _match_date(self, text: str) -> Optional[str]:
        iso_match = DATE_PATTERN.search(text)
        if iso_match:
            year, month, day = iso_match.groups()
            return self._format_date_components(int(year), int(month), int(day))

        kanji_match = KANJI_DATE_PATTERN.search(text)
        if kanji_match:
            year, month, day = kanji_match.groups()
            return self._format_date_components(int(year), int(month), int(day))

        reiwa_match = REIWA_DATE_PATTERN.search(text)
        if reiwa_match:
            era_year, month, day = map(int, reiwa_match.groups())
            year = 2018 + era_year
            return self._format_date_components(year, month, day)
        return None

    def _format_date_components(self, year: int, month: int, day: int) -> str:
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return f"{year:04d}-{month:02d}-{day:02d}"

    def _field_with_span(
        self,
        value: str,
        parsed: models.ParsedDocument,
        *,
        label: str,
        confidence: float,
    ) -> models.FieldValue:
        span = self._find_span_by_text(parsed, value, label=label)
        if span:
            return models.FieldValue(value=value, confidence=confidence, source_spans=[span])
        return models.FieldValue(value=value, confidence=confidence)

    def _find_span_by_text(
        self,
        parsed: models.ParsedDocument,
        needle: str,
        *,
        label: str,
    ) -> Optional[models.HighlightSpan]:
        normalized = needle.lower()
        for token in parsed.tokens:
            if normalized in token.text.lower():
                return self._highlight_from_token(token, label)
        return None

    def _highlight_from_token(self, token: models.TextSpan, label: str) -> models.HighlightSpan:
        if token.bbox is None:
            return models.HighlightSpan(page=token.page, bbox=(0.05, 0.75, 0.95, 0.8), label=label)
        return models.HighlightSpan(page=token.page, bbox=token.bbox, label=label)

    def _iter_page_lines(self, parsed: models.ParsedDocument) -> Iterable[Tuple[int, int, str]]:
        for page_index, page in enumerate(parsed.pages, start=1):
            for line_index, raw_line in enumerate(page.splitlines()):
                line = raw_line.strip()
                if line:
                    yield (page_index, line_index, line)


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
        except NotImplementedError:
            return self._fallback.extract(parsed, provider)
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
