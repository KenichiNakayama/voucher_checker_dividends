"""Highlight rendering utilities."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import models


class _SimplePDFBuilder:
    """Builds a lightweight PDF with highlighted text rows."""

    def __init__(self, *, width: float = 595.0, height: float = 842.0, margin: float = 48.0, font_size: float = 12.0) -> None:
        self._width = width
        self._height = height
        self._margin = margin
        self._font_size = font_size
        self._leading = font_size + 4.0
        self._pages: List[Tuple[List[str], List[Tuple[float, float, float, float]]]] = []

    def add_page(self, lines: List[str], highlights: List[Tuple[float, float, float, float]]) -> None:
        self._pages.append((lines, highlights))

    def build(self) -> bytes:
        objects: List[Tuple[int, str]] = []
        obj_index = 1

        catalog_id = obj_index
        objects.append((catalog_id, "<< /Type /Catalog /Pages 2 0 R >>"))
        obj_index += 1

        pages_id = obj_index
        obj_index += 1

        font_id = obj_index
        objects.append((font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        obj_index += 1

        page_object_ids: List[int] = []
        page_contents: List[Tuple[int, str]] = []

        for page_number, (lines, highlights) in enumerate(self._pages, start=1):
            content = self._build_page_content(lines, highlights)
            content_id = obj_index
            obj_index += 1
            page_contents.append((content_id, f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}\nendstream"))

            page_id = obj_index
            obj_index += 1
            page_object_ids.append(page_id)
            page_dict = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self._width:.0f} {self._height:.0f}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            )
            objects.append((page_id, page_dict))

        pages_dict = (
            f"<< /Type /Pages /Count {len(page_object_ids)} /Kids [{' '.join(f'{pid} 0 R' for pid in page_object_ids)}] >>"
        )
        objects.insert(1, (pages_id, pages_dict))

        # Append stream objects after structural ones
        for content_id, payload in page_contents:
            objects.append((content_id, payload))

        # Assemble PDF with xref
        body_parts: List[str] = ["%PDF-1.4"]
        offsets: Dict[int, int] = {}
        current_offset = len("%PDF-1.4\n")
        for obj_id, body in objects:
            obj_header = f"{obj_id} 0 obj\n{body}\nendobj"
            offsets[obj_id] = current_offset
            encoded = obj_header.encode("utf-8")
            body_parts.append(obj_header)
            current_offset += len(encoded) + 1  # account for newline join

        xref_start = current_offset
        max_obj = max(offsets)
        xref_lines = ["xref", f"0 {max_obj + 1}"]
        xref_lines.append("0000000000 65535 f ")
        for obj_id in range(1, max_obj + 1):
            offset = offsets.get(obj_id, 0)
            xref_lines.append(f"{offset:010d} 00000 n ")

        trailer = (
            "trailer\n"
            f"<< /Size {max_obj + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        )

        pdf_content = "\n".join(body_parts + xref_lines + [trailer])
        return pdf_content.encode("utf-8")

    def _build_page_content(
        self,
        lines: List[str],
        highlights: List[Tuple[float, float, float, float]],
    ) -> str:
        commands: List[str] = []
        usable_width = self._width - 2 * self._margin
        usable_height = self._height - 2 * self._margin

        # Draw highlight rectangles first so text stays on top
        for x0, y0, x1, y1 in highlights:
            absolute_x0 = self._margin + usable_width * max(min(x0, 1.0), 0.0)
            absolute_x1 = self._margin + usable_width * max(min(x1, 1.0), 0.0)
            absolute_y0 = self._margin + usable_height * max(min(y0, 1.0), 0.0)
            absolute_y1 = self._margin + usable_height * max(min(y1, 1.0), 0.0)
            width = max(absolute_x1 - absolute_x0, 2.0)
            height = max(absolute_y1 - absolute_y0, self._leading * 0.8)
            commands.extend(
                [
                    "q",
                    "1 1 0 rg",  # Yellow fill
                    f"{absolute_x0:.2f} {absolute_y0:.2f} {width:.2f} {height:.2f} re f",
                    "Q",
                ]
            )

        cursor_y = self._height - self._margin - self._font_size
        for line in lines:
            safe_text = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.extend(
                [
                    "BT",
                    f"/F1 {self._font_size:.1f} Tf",
                    f"1 0 0 1 {self._margin:.2f} {cursor_y:.2f} Tm",
                    f"({safe_text}) Tj",
                    "ET",
                ]
            )
            cursor_y -= self._leading

        return "\n".join(commands)


class HighlightRenderer:
    """Produces a downloadable PDF containing visual highlight cues."""

    def render(
        self,
        original_pdf: bytes,
        spans: Sequence[models.HighlightSpan],
        parsed_document: Optional[models.ParsedDocument] = None,
    ) -> bytes:
        if not spans:
            return original_pdf

        if parsed_document is None or not parsed_document.pages:
            return original_pdf

        builder = _SimplePDFBuilder()

        span_map: Dict[int, List[models.HighlightSpan]] = {}
        for span in spans:
            span_map.setdefault(span.page, []).append(span)

        page_count = len(parsed_document.pages)
        for page_number in range(1, page_count + 1):
            page_text = parsed_document.pages[page_number - 1]
            lines = [line for line in page_text.splitlines()]
            highlight_rects = [span.bbox for span in span_map.get(page_number, []) if span.bbox]
            builder.add_page(lines, highlight_rects)

        return builder.build()


__all__ = ["HighlightRenderer"]
