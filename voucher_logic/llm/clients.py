"""LLM client abstractions for voucher extraction."""
from __future__ import annotations

from typing import Callable, Dict

from .. import models
from ..settings import get_provider_key


class LLMClient:
    """Base interface for LLM-backed extractors."""

    def extract(self, parsed: models.ParsedDocument) -> Dict[str, object]:  # pragma: no cover - interface method
        raise NotImplementedError


class OpenAIClient(LLMClient):  # pragma: no cover - network path not used in tests
    def __init__(self, api_key: str):
        self.api_key = api_key

    def extract(self, parsed: models.ParsedDocument) -> Dict[str, object]:
        raise NotImplementedError("OpenAI client integration is pending implementation.")


class ClaudeClient(LLMClient):  # pragma: no cover - network path not used in tests
    def __init__(self, api_key: str):
        self.api_key = api_key

    def extract(self, parsed: models.ParsedDocument) -> Dict[str, object]:
        raise NotImplementedError("Claude client integration is pending implementation.")


class DummyLLMClient:
    """Fallback client that defers to the rule-based extractor."""

    def __init__(self, provider: models.ProviderType) -> None:
        self.provider = provider

    def extract(self, parsed: models.ParsedDocument) -> Dict[str, object]:
        structured = self.extract_structured(parsed)
        highlights = [
            {
                "page": span.page,
                "bbox": span.bbox,
                "label": span.label,
            }
            for span in structured.source_highlights
        ]
        return {
            "title": structured.title.value,
            "company_name": structured.company_name.value,
            "resolution_date": structured.resolution_date.value,
            "dividend_amount": structured.dividend_amount.value,
            "highlights": highlights,
        }

    def extract_structured(self, parsed: models.ParsedDocument) -> models.ExtractedVoucherData:
        from ..extraction import RuleBasedVoucherExtractor

        extractor = RuleBasedVoucherExtractor()
        return extractor.extract(parsed, self.provider)


class LLMClientFactory:
    """Factory that provides LLM clients for a given provider."""

    def __init__(self) -> None:
        self._registry: Dict[models.ProviderType, Callable[[], object]] = {}

    def register(self, provider: models.ProviderType, builder: Callable[[], object]) -> None:
        self._registry[provider] = builder

    def create(self, provider: models.ProviderType):
        builder = self._registry.get(provider)
        if builder is None:
            raise KeyError(provider.value)
        return builder()

    @classmethod
    def build_default(cls) -> "LLMClientFactory":
        factory = cls()
        openai_key = get_provider_key(models.ProviderType.OPENAI)
        anthropic_key = get_provider_key(models.ProviderType.CLAUDE)

        if openai_key:
            factory.register(models.ProviderType.OPENAI, lambda: OpenAIClient(openai_key))
        else:
            factory.register(models.ProviderType.OPENAI, lambda: DummyLLMClient(models.ProviderType.OPENAI))

        if anthropic_key:
            factory.register(models.ProviderType.CLAUDE, lambda: ClaudeClient(anthropic_key))
        else:
            factory.register(models.ProviderType.CLAUDE, lambda: DummyLLMClient(models.ProviderType.CLAUDE))

        return factory


__all__ = [
    "LLMClient",
    "OpenAIClient",
    "ClaudeClient",
    "DummyLLMClient",
    "LLMClientFactory",
]
