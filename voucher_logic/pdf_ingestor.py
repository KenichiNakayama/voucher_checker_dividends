"""Utilities for converting uploaded PDFs into parsed documents."""
from __future__ import annotations

import io
import re
import zlib
from typing import Dict, Iterable, List, Tuple

from . import models

_STREAM_RE = re.compile(rb"stream\s*(.*?)\s*endstream", re.DOTALL)
_OBJECT_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.DOTALL)
_CONTENTS_REF_RE = re.compile(rb"/Contents\s+(\d+)\s+\d+\s+R")
_CONTENTS_ARRAY_RE = re.compile(rb"/Contents\s+\[(.*?)\]", re.DOTALL)
_INDIRECT_REF_RE = re.compile(rb"(\d+)\s+\d+\s+R")


class PdfIngestor:
    """Parses PDF bytes into the internal ParsedDocument representation."""

    def parse(self, file_bytes: bytes) -> models.ParsedDocument:
        if not file_bytes:
            raise ValueError("Empty file provided")

        if file_bytes.lstrip().startswith(b"%PDF"):
            pages = self._extract_pdf_pages(file_bytes)
        else:
            pages = [self._decode_text(file_bytes)]

        if not pages:
            raise ValueError("PDF parsing produced no pages")

        tokens: List[models.TextSpan] = []
        metadata = {"page_count": len(pages)}
        for page_index, content in enumerate(pages, start=1):
            lines = content.splitlines()
            visible_lines = [line for line in lines if line.strip()]
            visible_count = len(visible_lines) or 1
            step = 1.0 / (visible_count + 1)
            visible_index = 0
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                visible_index += 1
                top = 1.0 - visible_index * step
                bottom = max(top - step * 0.9, 0.0)
                tokens.append(
                    models.TextSpan(
                        page=page_index,
                        text=line,
                        bbox=(0.08, bottom, 0.92, max(top, bottom + 0.02)),
                    )
                )

        return models.ParsedDocument(pages=pages, tokens=tokens, metadata=metadata)

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
        for object_id, raw in objects.items():
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
