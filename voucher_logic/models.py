"""Core data models for voucher analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

BBox = Tuple[float, float, float, float]


@dataclass(frozen=True)
class HighlightSpan:
    """Represents a highlighted region within the source PDF."""

    page: int
    bbox: BBox
    label: Optional[str] = None


@dataclass
class FieldValue:
    """Holds an extracted field along with provenance metadata."""

    value: Any = None
    confidence: Optional[float] = None
    source_spans: List[HighlightSpan] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def is_set(self) -> bool:
        return self.value not in (None, "")

    @classmethod
    def empty(cls, notes: Optional[str] = None) -> "FieldValue":
        return cls(value=None, confidence=None, source_spans=[], notes=notes)


@dataclass(frozen=True)
class TextSpan:
    page: int
    text: str
    bbox: Optional[BBox] = None


@dataclass
class ParsedDocument:
    """Raw PDF content broken down for downstream processing."""

    pages: List[str] = field(default_factory=list)
    tokens: List[TextSpan] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ParsedDocument":
        return cls()


@dataclass
class ExtractedVoucherData:
    """Structured data extracted from the voucher."""

    title: FieldValue = field(default_factory=FieldValue.empty)
    company_name: FieldValue = field(default_factory=FieldValue.empty)
    resolution_date: FieldValue = field(default_factory=FieldValue.empty)
    dividend_amount: FieldValue = field(default_factory=FieldValue.empty)
    others: Dict[str, FieldValue] = field(default_factory=dict)
    source_highlights: List[HighlightSpan] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ExtractedVoucherData":
        return cls()

    def iter_required_fields(self) -> Iterable[Tuple[str, FieldValue]]:
        yield "title", self.title
        yield "company_name", self.company_name
        yield "resolution_date", self.resolution_date
        yield "dividend_amount", self.dividend_amount


class RequirementState(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass
class RequirementStatus:
    status: RequirementState
    message: str = ""


class ValidationOutcome(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"

    @classmethod
    def from_requirements(cls, statuses: Sequence[RequirementStatus]) -> "ValidationOutcome":
        if not statuses:
            return cls.UNKNOWN
        outcome = cls.PASS
        for status in statuses:
            if status.status is RequirementState.FAIL:
                return cls.FAIL
            if status.status is RequirementState.UNKNOWN:
                outcome = cls.WARNING
        return outcome


@dataclass
class ValidationReport:
    requirements: Dict[str, RequirementStatus] = field(default_factory=dict)
    overall_status: ValidationOutcome = ValidationOutcome.UNKNOWN

    @classmethod
    def empty(cls) -> "ValidationReport":
        return cls()

    def register(self, key: str, status: RequirementStatus) -> None:
        self.requirements[key] = status
        self.overall_status = ValidationOutcome.from_requirements(list(self.requirements.values()))


class ProviderType(Enum):
    OPENAI = "openai"
    CLAUDE = "claude"

    @classmethod
    def from_string(cls, value: str) -> "ProviderType":
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown provider: {value}")


@dataclass
class VoucherAnalysisResult:
    parsed_document: ParsedDocument = field(default_factory=ParsedDocument.empty)
    extracted: ExtractedVoucherData = field(default_factory=ExtractedVoucherData.empty)
    validation: ValidationReport = field(default_factory=ValidationReport.empty)
    highlight_pdf: bytes = b""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_filename: str = ""

    @classmethod
    def empty(cls) -> "VoucherAnalysisResult":
        return cls()


__all__ = [
    "BBox",
    "HighlightSpan",
    "FieldValue",
    "TextSpan",
    "ParsedDocument",
    "ExtractedVoucherData",
    "RequirementState",
    "RequirementStatus",
    "ValidationOutcome",
    "ValidationReport",
    "ProviderType",
    "VoucherAnalysisResult",
]
