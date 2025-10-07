"""Voucher extraction services."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Set

from . import models
from .llm.clients import DummyLLMClient, LLMClientFactory

TITLE_PATTERN = re.compile(r"^(Dividend\s+Resolution|配当決議.*|Board\s+Resolution.*|配当.*報告書)$", re.IGNORECASE)
COMPANY_LINE_PATTERN = re.compile(
    r"(?:Company\s*(?:Name)?|会社名|社名|Corporate\s+Name)\s*[:：-]\s*(.+)",
    re.IGNORECASE,
)
COMPANY_SUFFIX_PATTERN = re.compile(
    r"(?:Inc\.?|Corp\.?|Corporation|Company|Co\.?|Holdings|Limited|Ltd\.?|K\.K\.|LLC|GmbH|Kabushiki\s+Kaisha|株式会社|有限会社|合同会社|\(株\)|（株）|㈱)",
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

JP_COMPANY_KEYWORDS = (
    "株式会社",
    "有限会社",
    "合同会社",
    "学校法人",
    "医療法人",
    "(株)",
    "（株）",
    "㈱",
    "(有)",
    "（有）",
)

EN_COMPANY_KEYWORDS = (
    "co.",
    "co",
    "co., ltd",
    "co., ltd.",
    "co ltd",
    "company",
    "corp",
    "corp.",
    "corporation",
    "inc",
    "inc.",
    "limited",
    "ltd",
    "ltd.",
    "holdings",
    "group",
    "llc",
    "plc",
    "gmbh",
    "s.a.",
    "s.p.a.",
    "pte ltd",
    "pty ltd",
    "ag",
    "bv",
    "nv",
)

COMPANY_INVALID_TERMS = (
    "resolved",
    "resolve",
    "resolves",
    "approved",
    "approve",
    "approves",
    "decided",
    "decide",
    "distribute",
    "distributing",
    "distributed",
    "dividend",
    "meeting",
    "board",
    "directors",
    "shareholders",
    "agenda",
    "決議",
    "開催",
    "実施",
    "分配",
    "配当",
    "支払",
)

JAPANESE_COMPANY_PATTERN = re.compile(
    r"(?:株式会社|有限会社|合同会社|学校法人|医療法人)[^\s　、，()（）]{1,40}|[^\s　、，()（）]{1,40}(?:株式会社|有限会社|合同会社|学校法人|医療法人)",
)

ENGLISH_COMPANY_PATTERN = re.compile(
    r"(?:[A-Z&][A-Za-z&'.-]*\s+){0,4}[A-Z&][A-Za-z&'.-]*\s+(?:Co\.?|Company|Corporation|Corp\.?|Inc\.?|Ltd\.?|Limited|Holdings|Group|LLC|PLC|GmbH|S\.A\.?|S\.P\.A\.?|Pte\.?\s+Ltd\.?|Pty\.?\s+Ltd\.?|AG|BV|NV)(?:\s+[A-Z][A-Za-z&'.-]*)*",
    re.IGNORECASE,
)

COMPANY_LABEL_KEYWORDS = (
    "会社名",
    "社名",
    "法人名",
    "商号",
    "株式会社",
    "(株)",
    "Company Name",
    "Corporate Name",
    "Company",
)

COMPANY_EXCLUDE_KEYWORDS = (
    "所在地",
    "住所",
    "address",
)

DATE_LABEL_PRIORITY = [
    ("配当決議日", "決議日", "取締役会決議日", "Board Resolution Date", "Resolution Date"),
]

DATE_EXCLUDE_KEYWORDS = (
    "基準日",
    "record date",
    "効力",
    "支払",
    "payment",
    "株主確定日",
)

AMOUNT_LABEL_KEYWORDS = (
    "総配当金額",
    "配当金総額",
    "配当金額",
    "支払配当金額",
    "Total Amount of Dividends",
    "Total Dividends",
)


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
            company_value, company_raw = company
            data.company_name = self._field_with_span(
                company_value,
                parsed,
                label="company_name",
                confidence=0.88,
                raw_text=company_raw,
            )
            highlights.extend(data.company_name.source_spans)

        resolution_date = self._extract_resolution_date(parsed)
        if resolution_date:
            resolution_value, resolution_raw = resolution_date
            data.resolution_date = self._field_with_span(
                resolution_value,
                parsed,
                label="resolution_date",
                confidence=0.82,
                raw_text=resolution_raw,
            )
            highlights.extend(data.resolution_date.source_spans)

        amount = self._extract_dividend_amount(parsed)
        if amount:
            amount_value, amount_raw = amount
            data.dividend_amount = self._field_with_span(
                amount_value,
                parsed,
                label="dividend_amount",
                confidence=0.78,
                raw_text=amount_raw,
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

    def _extract_company(self, parsed: models.ParsedDocument) -> Optional[Tuple[str, str]]:
        lines = self._collect_lines(parsed)

        labeled = self._find_labeled_value(
            lines,
            COMPANY_LABEL_KEYWORDS,
            exclude_keywords=COMPANY_EXCLUDE_KEYWORDS,
            allow_next_line=True,
        )
        candidates: List[Tuple[float, str, str]] = []

        def register_candidate(raw_text: str, context_weight: float) -> None:
            for normalized, raw in self._generate_company_segments(raw_text):
                score = self._score_company_candidate(normalized)
                if score <= 0:
                    continue
                candidates.append((score - context_weight, normalized, raw))

        if labeled:
            value, raw = labeled
            register_candidate(value, 0.0)
            register_candidate(raw, 0.05)

        for page_index, line_index, text in lines:
            if line_index > 10:
                break
            context_penalty = line_index * 0.1 + (page_index - 1) * 0.5
            register_candidate(text, context_penalty)

        candidate = self._find_company_candidate_by_proximity(lines)
        if candidate:
            register_candidate(candidate, 0.2)

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
        _, best_value, best_raw = candidates[0]
        return best_value, best_raw

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
            if "所在地" in text or "住所" in text:
                for back in range(1, 4):
                    if idx - back < 0:
                        continue
                    candidate = lines[idx - back][2].strip()
                    if candidate and "所在地" not in candidate and "住所" not in candidate:
                        return candidate
        return None

    def _extract_resolution_date(self, parsed: models.ParsedDocument) -> Optional[Tuple[str, str]]:
        lines = self._collect_lines(parsed)

        def _has_valid_date(text: str) -> bool:
            return self._match_date(text) is not None

        for keyword_group in DATE_LABEL_PRIORITY:
            labeled = self._find_labeled_value(
                lines,
                keyword_group,
                exclude_keywords=DATE_EXCLUDE_KEYWORDS,
                allow_next_line=True,
                value_predicate=_has_valid_date,
            )
            if labeled:
                candidate, raw = labeled
                normalized = self._match_date(candidate) or self._match_date(raw)
                if normalized:
                    return normalized, raw

        for _, _, text in lines:
            if self._line_contains_keyword(text, DATE_EXCLUDE_KEYWORDS):
                continue
            normalized = self._match_date(text)
            if not normalized:
                continue
            if self._line_contains_keyword(text, ("決議", "取締役会", "meeting", "resolved")):
                return normalized, text

        for _, _, text in lines:
            if self._line_contains_keyword(text, DATE_EXCLUDE_KEYWORDS):
                continue
            normalized = self._match_date(text)
            if normalized:
                return normalized, text
        return None

    def _extract_dividend_amount(self, parsed: models.ParsedDocument) -> Optional[Tuple[str, str]]:
        lines = self._collect_lines(parsed)

        labeled = self._find_labeled_value(
            lines,
            AMOUNT_LABEL_KEYWORDS,
            allow_next_line=True,
            exclude_keywords=("per share", "per-share", "1株当たり", "１株当たり"),
            value_predicate=lambda text: self._extract_numeric(text) is not None,
        )
        if labeled:
            candidate, raw = labeled
            numeric = self._extract_numeric(candidate) or self._extract_numeric(raw)
            if numeric:
                return numeric, raw

        for _, _, text in lines:
            if not self._line_contains_keyword(text, ("配当", "dividend")):
                continue
            if self._line_contains_keyword(text, ("per share", "1株当たり", "１株当たり")):
                continue
            numeric = self._extract_numeric(text)
            if numeric:
                return numeric, text
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
        raw_text: Optional[str] = None,
    ) -> models.FieldValue:
        span = self._find_span_by_text(parsed, raw_text or value, label=label)
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
        if not needle:
            return None
        normalized = needle.lower()
        for token in parsed.tokens:
            token_text = token.text.lower()
            if normalized in token_text:
                return self._highlight_from_token(token, label)
            if normalized.replace(" ", "") and normalized.replace(" ", "") in token_text.replace(" ", ""):
                return self._highlight_from_token(token, label)
        return None

    def _highlight_from_token(self, token: models.TextSpan, label: str) -> models.HighlightSpan:
        if token.bbox is None:
            return models.HighlightSpan(page=token.page, bbox=(0.05, 0.75, 0.95, 0.8), label=label)
        return models.HighlightSpan(page=token.page, bbox=token.bbox, label=label)

    def _collect_lines(self, parsed: models.ParsedDocument) -> List[Tuple[int, int, str]]:
        return list(self._iter_page_lines(parsed))

    def _normalize_delimiters(self, text: str) -> str:
        normalized = text.replace("：", ":").replace("　", " ").replace("\t", " ")
        normalized = normalized.replace("‐", "-").replace("―", "-")
        return re.sub(r"\s+", " ", normalized).strip()

    def _line_contains_keyword(self, text: str, keywords: Sequence[str]) -> bool:
        if not keywords:
            return False
        normalized = self._normalize_delimiters(text).lower()
        for keyword in keywords:
            keyword_normalized = self._normalize_delimiters(keyword).lower()
            if keyword_normalized and keyword_normalized in normalized:
                return True
        return False

    def _extract_segment_after_keyword(
        self,
        normalized_text: str,
        lowered_text: str,
        keywords: Sequence[str],
    ) -> str:
        for keyword in keywords:
            keyword_normalized = self._normalize_delimiters(keyword)
            keyword_lower = keyword_normalized.lower()
            index = lowered_text.find(keyword_lower)
            if index == -1:
                continue
            segment = normalized_text[index + len(keyword_lower) :]
            segment = segment.lstrip(":：-‐― 　 ")
            segment = segment.strip()
            if segment:
                return segment
        return ""

    def _find_labeled_value(
        self,
        lines: Sequence[Tuple[int, int, str]],
        keywords: Sequence[str],
        *,
        exclude_keywords: Sequence[str] = (),
        allow_next_line: bool,
        value_predicate: Optional[Callable[[str], bool]] = None,
    ) -> Optional[Tuple[str, str]]:
        if not keywords:
            return None

        for index, (page, _, text) in enumerate(lines):
            normalized = self._normalize_delimiters(text)
            lowered = normalized.lower()
            if not self._line_contains_keyword(text, keywords):
                continue
            if self._line_contains_keyword(text, exclude_keywords):
                continue

            candidate = self._extract_segment_after_keyword(normalized, lowered, keywords)
            if candidate:
                candidate = candidate.strip()
                if not value_predicate or value_predicate(candidate):
                    return candidate, text

            if allow_next_line and index + 1 < len(lines):
                next_page, _, next_text = lines[index + 1]
                if next_page != page:
                    continue
                if self._line_contains_keyword(next_text, keywords):
                    continue
                candidate_next = next_text.strip()
                if not candidate_next:
                    continue
                if value_predicate and not value_predicate(candidate_next):
                    continue
                if self._line_contains_keyword(candidate_next, exclude_keywords):
                    continue
                return candidate_next, next_text

        return None

    def _generate_company_segments(self, text: str) -> List[Tuple[str, str]]:
        candidates: List[Tuple[str, str]] = []
        seen: Set[Tuple[str, str]] = set()

        def add(raw_segment: str) -> None:
            raw_segment = raw_segment.strip()
            if not raw_segment:
                return
            normalized = self._normalize_company_value(raw_segment)
            if not normalized:
                return
            key = (normalized.lower(), raw_segment)
            if key in seen:
                return
            seen.add(key)
            candidates.append((normalized, raw_segment))

        add(text)
        for delimiter in ("／", "/", "|", "｜", "\n"):
            for part in text.split(delimiter):
                add(part)
        for match in JAPANESE_COMPANY_PATTERN.finditer(text):
            add(match.group())
        for match in ENGLISH_COMPANY_PATTERN.finditer(text):
            add(match.group())
        return candidates

    def _normalize_company_value(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = normalized.replace("（株）", "株式会社").replace("(株)", "株式会社").replace("㈱", "株式会社")
        normalized = normalized.replace("（有）", "有限会社").replace("(有)", "有限会社")
        normalized = normalized.strip(" ,.;:・")
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"(株式会社)+", "株式会社", normalized)
        normalized = re.sub(r"(有限会社)+", "有限会社", normalized)
        normalized = re.sub(r"(合同会社)+", "合同会社", normalized)
        return normalized.strip()

    def _score_company_candidate(self, candidate: str) -> float:
        candidate = candidate.strip()
        if not candidate:
            return 0.0
        if len(candidate) < 2 or len(candidate) > 80:
            return 0.0
        text_lower = candidate.lower()
        if any(term in text_lower for term in COMPANY_INVALID_TERMS):
            return 0.0

        has_jp_keyword = any(keyword in candidate for keyword in JP_COMPANY_KEYWORDS)
        has_en_keyword = any(keyword in text_lower for keyword in EN_COMPANY_KEYWORDS)
        if not (has_jp_keyword or has_en_keyword):
            return 0.0

        score = 1.0
        if has_jp_keyword:
            score += 5.0
        if has_en_keyword:
            tokens = re.findall(r"[A-Za-z][\w&'.-]*", candidate)
            uppercase_tokens = [token for token in tokens if token[0].isupper()]
            if len(uppercase_tokens) < 2:
                return 0.0
            score += 4.0

        if len(candidate) <= 30:
            score += 1.0
        if candidate.count(" ") <= 5:
            score += 0.5
        return score

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
