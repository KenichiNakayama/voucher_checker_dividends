"""Utilities for converting uploaded PDFs into parsed documents."""
from __future__ import annotations

import io
from typing import List

from . import models


class PdfIngestor:
    """Parses PDF bytes into the internal ParsedDocument representation."""

    def parse(self, file_bytes: bytes) -> models.ParsedDocument:
        if not file_bytes:
            raise ValueError("Empty file provided")

        if file_bytes.lstrip().startswith(b"%PDF"):
            text = self._extract_pdf_text(file_bytes)
        else:
            text = self._decode_text(file_bytes)

        pages = text.split("\f") if "\f" in text else [text]
        tokens: List[models.TextSpan] = []
        for page_index, content in enumerate(pages, start=1):
            for line in content.splitlines():
                tokens.append(
                    models.TextSpan(
                        page=page_index,
                        text=line.strip(),
                        bbox=None,
                    )
                )

        metadata = {"page_count": len(pages)}
        return models.ParsedDocument(pages=pages, tokens=tokens, metadata=metadata)

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return self._decode_text(file_bytes)

        reader = PdfReader(io.BytesIO(file_bytes))
        pages: List[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - PyPDF2 fallback
                pages.append(f"[unextractable page: {exc}]")
        return "\f".join(pages)

    def _decode_text(self, file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="ignore")
