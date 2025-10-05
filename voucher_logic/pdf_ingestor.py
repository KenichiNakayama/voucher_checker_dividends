"""Utilities for converting uploaded PDFs into parsed documents."""
from __future__ import annotations

import io
import re
import zlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from . import models

_STREAM_RE = re.compile(rb"stream\s*(.*?)\s*endstream", re.DOTALL)
_OBJECT_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.DOTALL)
_CONTENTS_REF_RE = re.compile(rb"/Contents\s+(\d+)\s+\d+\s+R")
_CONTENTS_ARRAY_RE = re.compile(rb"/Contents\s+\[(.*?)\]", re.DOTALL)
_INDIRECT_REF_RE = re.compile(rb"(\d+)\s+\d+\s+R")


@dataclass
class _PageExtraction:
    text: str
    spans: List[models.TextSpan]


class PdfIngestor:
    """Parses PDF bytes into the internal ParsedDocument representation."""

    def parse(self, file_bytes: bytes) -> models.ParsedDocument:
        if not file_bytes:
            raise ValueError("Empty file provided")

        if not file_bytes.lstrip().startswith(b"%PDF"):
            text = file_bytes.decode("utf-8", errors="ignore")
            return models.ParsedDocument(pages=[text], tokens=[], metadata={"page_count": 1})

        extraction = self._extract_with_pymupdf(file_bytes)
        if extraction is None:
            extraction = self._extract_with_pdfplumber(file_bytes)

        if extraction is None:
            extraction = self._extract_with_fallback(file_bytes)

        pages = [page.text for page in extraction]
        tokens: List[models.TextSpan] = []
        for page in extraction:
            tokens.extend(page.spans)

        if not pages:
            raise ValueError("PDF parsing produced no pages")

        metadata = {"page_count": len(pages)}
        return models.ParsedDocument(pages=pages, tokens=tokens, metadata=metadata)

    def _extract_with_pymupdf(self, file_bytes: bytes) -> Optional[List[_PageExtraction]]:
        try:
            import fitz  # type: ignore
        except Exception:  # pragma: no cover - dependency optional during tests
            return None

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:
            return None

        pages: List[_PageExtraction] = []
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            spans: List[models.TextSpan] = []
            words = page.get_text("words") or []
            if words:
                spans.extend(self._words_to_spans(words, page, page_index))
            else:
                blocks = page.get_text("blocks") or []
                spans.extend(self._blocks_to_spans(blocks, page, page_index))
            pages.append(_PageExtraction(text=text, spans=spans))
        return pages

    def _extract_with_pdfplumber(self, file_bytes: bytes) -> Optional[List[_PageExtraction]]:
        try:
            import pdfplumber  # type: ignore
        except Exception:  # pragma: no cover - dependency optional during tests
            return None

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages: List[_PageExtraction] = []
                for page_index, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    spans: List[models.TextSpan] = []
                    for block in page.extract_words():
                        spans.append(
                            models.TextSpan(
                                page=page_index,
                                text=block.get("text", ""),
                                bbox=self._normalize_bbox(
                                    float(block["x0"]),
                                    float(block["top"]),
                                    float(block["x1"]),
                                    float(block["bottom"]),
                                    float(page.width),
                                    float(page.height),
                                ),
                            )
                        )
                    pages.append(_PageExtraction(text=text, spans=spans))
        except Exception:
            return None

        if not pages:
            return None
        return pages

    def _extract_with_fallback(self, file_bytes: bytes) -> List[_PageExtraction]:
        pages = self._extract_pdf_pages(file_bytes)
        spans: List[_PageExtraction] = []
        for page_index, text in enumerate(pages, start=1):
            line_spans: List[models.TextSpan] = []
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            visible_count = len(lines) or 1
            step = 1.0 / (visible_count + 1)
            for line_index, line in enumerate(lines, start=1):
                top = 1.0 - line_index * step
                bottom = max(top - step * 0.85, 0.0)
                line_spans.append(
                    models.TextSpan(
                        page=page_index,
                        text=line,
                        bbox=(0.08, bottom, 0.92, max(top, bottom + 0.02)),
                    )
                )
            spans.append(_PageExtraction(text=text, spans=line_spans))
        return spans

    def _words_to_spans(
        self,
        words: Iterable[Tuple[float, ...]],
        page,
        page_index: int,
    ) -> List[models.TextSpan]:
        spans: List[models.TextSpan] = []
        grouped: Dict[Tuple[int, int], List[Tuple[float, ...]]] = {}
        for word in words:
            if len(word) < 8:
                continue
            key = (int(word[5]), int(word[6]))
            grouped.setdefault(key, []).append(word)

        for entries in grouped.values():
            entries.sort(key=lambda item: item[7] if len(item) > 7 else 0)
            text = " ".join(str(entry[4]) for entry in entries if len(entry) > 4 and entry[4])
            if not text:
                continue
            x0 = min(float(entry[0]) for entry in entries)
            y0 = min(float(entry[1]) for entry in entries)
            x1 = max(float(entry[2]) for entry in entries)
            y1 = max(float(entry[3]) for entry in entries)
            spans.append(
                models.TextSpan(
                    page=page_index,
                    text=text,
                    bbox=self._normalize_bbox(x0, y0, x1, y1, page.rect.width, page.rect.height),
                )
            )
        return spans

    def _blocks_to_spans(self, blocks: Iterable[Tuple[float, float, float, float, str]], page, page_index: int) -> List[models.TextSpan]:
        spans: List[models.TextSpan] = []
        for block in blocks:
            if len(block) < 5:
                continue
            text = block[4].strip()
            if not text:
                continue
            spans.append(
                models.TextSpan(
                    page=page_index,
                    text=text,
                    bbox=self._normalize_bbox(block[0], block[1], block[2], block[3], page.rect.width, page.rect.height),
                )
            )
        return spans

    def _normalize_bbox(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        width: float,
        height: float,
    ) -> Tuple[float, float, float, float]:
        if width <= 0 or height <= 0:
            return (0.05, 0.05, 0.95, 0.15)

        def clamp(value: float) -> float:
            return max(0.0, min(1.0, value))

        nx0 = clamp(x0 / width)
        nx1 = clamp(x1 / width)
        # Convert top-origin coordinates to bottom-origin for consistency
        ny0 = clamp(1.0 - (y1 / height))
        ny1 = clamp(1.0 - (y0 / height))
        if ny1 <= ny0:
            ny1 = clamp(ny0 + 0.02)
        if nx1 <= nx0:
            nx1 = clamp(nx0 + 0.02)
        return (nx0, ny0, nx1, ny1)

    def _extract_pdf_pages(self, file_bytes: bytes) -> List[str]:
        pages = self._extract_with_pypdf(file_bytes)
        if pages:
            return pages

        return self._extract_with_naive_parser(file_bytes)

    def _extract_with_pypdf(self, file_bytes: bytes) -> List[str]:
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:  # pragma: no cover - optional dependency
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except Exception:
                return []

        reader = PdfReader(io.BytesIO(file_bytes))
        output: List[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:  # pragma: no cover - defensive
                text = ""
            output.append(text)
        return output

    def _extract_with_naive_parser(self, file_bytes: bytes) -> List[str]:
        objects = self._build_object_table(file_bytes)
        if not objects:
            decoded = self._decode_text(file_bytes)
            return [decoded]

        pages: List[str] = []
        for raw in objects.values():
            if b"/Type" not in raw or b"/Page" not in raw:
                continue
            content_object_ids = self._resolve_contents_ids(raw)
            text_fragments: List[str] = []
            for content_id in content_object_ids:
                stream_bytes = self._extract_stream(objects.get(content_id, b""))
                if not stream_bytes:
                    continue
                text_fragments.append(self._extract_text_from_stream(stream_bytes))
            page_text = "\n".join(fragment for fragment in text_fragments if fragment)
            pages.append(page_text)

        if pages:
            return pages

        decoded = self._decode_text(file_bytes)
        return [decoded]

    def _build_object_table(self, file_bytes: bytes) -> Dict[int, bytes]:
        objects: Dict[int, bytes] = {}
        for match in _OBJECT_RE.finditer(file_bytes):
            obj_id = int(match.group(1))
            objects[obj_id] = match.group(3)
        return objects

    def _resolve_contents_ids(self, page_object: bytes) -> List[int]:
        direct_match = _CONTENTS_REF_RE.search(page_object)
        if direct_match:
            return [int(direct_match.group(1))]

        array_match = _CONTENTS_ARRAY_RE.search(page_object)
        if not array_match:
            return []

        return [int(ref) for ref in _INDIRECT_REF_RE.findall(array_match.group(1))]

    def _extract_stream(self, raw_object: bytes) -> bytes:
        if not raw_object:
            return b""

        match = _STREAM_RE.search(raw_object)
        if not match:
            return b""

        stream = match.group(1)
        stream = stream.strip(b"\r\n")

        if b"FlateDecode" in raw_object:
            try:
                return zlib.decompress(stream)
            except zlib.error:
                return b""
        return stream

    def _extract_text_from_stream(self, stream_bytes: bytes) -> str:
        chunks: List[str] = []
        buffer: List[str] = []
        i = 0
        length = len(stream_bytes)
        while i < length:
            byte = stream_bytes[i]
            if byte == 0x28:  # '('
                text, advance = self._read_pdf_string(stream_bytes, i + 1)
                if text:
                    buffer.append(text)
                i = advance
                continue
            if stream_bytes.startswith(b"Tj", i) or stream_bytes.startswith(b"TJ", i):
                if buffer:
                    chunks.append("".join(buffer))
                    buffer = []
                i += 2
                continue
            if stream_bytes.startswith(b"T*", i) or stream_bytes.startswith(b"'", i):
                if buffer:
                    chunks.append("".join(buffer))
                    buffer = []
                chunks.append("\n")
                i += 2 if stream_bytes.startswith(b"T*", i) else 1
                continue
            i += 1

        if buffer:
            chunks.append("".join(buffer))

        lines: List[str] = []
        current: List[str] = []
        for chunk in chunks:
            if chunk == "\n":
                if current:
                    lines.append("".join(current))
                    current = []
                else:
                    lines.append("")
            else:
                current.append(chunk)
        if current:
            lines.append("".join(current))
        return "\n".join(line.strip() for line in lines if line.strip())

    def _read_pdf_string(self, data: bytes, start: int) -> Tuple[str, int]:
        result = bytearray()
        depth = 1
        i = start
        while i < len(data) and depth > 0:
            char = data[i]
            if char == 0x5c:  # '\\'
                i += 1
                if i >= len(data):
                    break
                escape = data[i]
                if 0x30 <= escape <= 0x37:  # octal sequence
                    octal_digits = [escape]
                    for _ in range(2):
                        if i + 1 < len(data) and 0x30 <= data[i + 1] <= 0x37:
                            i += 1
                            octal_digits.append(data[i])
                        else:
                            break
                    value = int(bytes(octal_digits), 8)
                    result.append(value)
                elif escape in (0x6e, 0x72, 0x74, 0x62, 0x66):  # n r t b f
                    mapping = {
                        0x6e: 0x0a,
                        0x72: 0x0d,
                        0x74: 0x09,
                        0x62: 0x08,
                        0x66: 0x0c,
                    }
                    result.append(mapping[escape])
                else:
                    result.append(escape)
            elif char == 0x28:  # '('
                depth += 1
                result.append(char)
            elif char == 0x29:  # ')'
                depth -= 1
                if depth == 0:
                    i += 1
                    break
                result.append(char)
            else:
                result.append(char)
            i += 1

        raw_bytes = bytes(result)
        if raw_bytes.startswith(b"\xfe\xff"):
            return raw_bytes[2:].decode("utf-16-be", errors="ignore"), i
        try:
            return raw_bytes.decode("utf-8"), i
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="ignore"), i

    def _decode_text(self, file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="ignore")
