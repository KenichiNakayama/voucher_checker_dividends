"""Simple analysis result storage abstractions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Optional

from .models import VoucherAnalysisResult


class AnalysisStore(ABC):
    """Abstract interface for storing analysis results."""

    @abstractmethod
    def save(self, key: str, result: VoucherAnalysisResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def load(self, key: str) -> Optional[VoucherAnalysisResult]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def keys(self) -> List[str]:
        raise NotImplementedError


class InMemoryAnalysisStore(AnalysisStore):
    """Stores analysis results in memory for the session lifetime."""

    def __init__(self) -> None:
        self._store: Dict[str, VoucherAnalysisResult] = {}

    def save(self, key: str, result: VoucherAnalysisResult) -> None:
        self._store[key] = result

    def load(self, key: str) -> Optional[VoucherAnalysisResult]:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> List[str]:
        return list(self._store.keys())


__all__ = ["AnalysisStore", "InMemoryAnalysisStore"]
