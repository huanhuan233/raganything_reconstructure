"""
ParsedDocument 与原生 content_list（List[dict]）之间的转换骨架。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .types import (
    ContentListItem,
    DocumentProcessRequest,
    ParsedChunk,
    ParsedDocument,
    ParsedEquation,
    ParsedImage,
    ParsedTable,
)


class DocumentAdapter:
    """
    文档 DTO 适配：不调用解析器，仅存取结构变换。

    TODO: 与 MinerU 3.x / Docling 输出差异做版本化 schema；与对象存储 URI 对齐。
    """

    @staticmethod
    def from_content_list(
        items: List[Dict[str, Any]],
        *,
        source_file: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> ParsedDocument:
        """将原始 content_list 转为 ParsedDocument（优先填充 raw_content_list + 结构化视图）。"""
        doc = ParsedDocument(
            source_file=source_file,
            doc_id=doc_id,
            raw_content_list=list(items),
        )
        for raw in items:
            if not isinstance(raw, dict):
                continue
            t = raw.get("type", "text")
            if t == "text":
                tx = raw.get("text", "")
                if isinstance(tx, str) and tx.strip():
                    doc.chunks.append(
                        ParsedChunk(
                            text=tx,
                            page_idx=int(raw.get("page_idx", 0)),
                            text_level=int(raw.get("text_level", 0)),
                            metadata={
                                k: v
                                for k, v in raw.items()
                                if k not in ("type", "text", "page_idx", "text_level")
                            },
                        )
                    )
            elif t == "image":
                p = raw.get("img_path", "")
                if p:
                    doc.images.append(
                        ParsedImage(
                            img_path=str(p),
                            page_idx=int(raw.get("page_idx", 0)),
                            captions=list(raw.get("image_caption") or raw.get("img_caption") or []),
                            footnotes=list(raw.get("image_footnote") or raw.get("img_footnote") or []),
                            metadata={k: v for k, v in raw.items() if k not in ("type", "page_idx", "img_path", "image_caption", "img_caption", "image_footnote", "img_footnote")},
                        )
                    )
            elif t == "table":
                body = raw.get("table_body", "")
                if isinstance(body, str):
                    doc.tables.append(
                        ParsedTable(
                            table_body=body,
                            page_idx=int(raw.get("page_idx", 0)),
                            captions=list(raw.get("table_caption") or []),
                            footnotes=list(raw.get("table_footnote") or []),
                            metadata={k: v for k, v in raw.items() if k not in ("type", "page_idx", "table_body", "table_caption", "table_footnote")},
                        )
                    )
            elif t == "equation":
                doc.equations.append(
                    ParsedEquation(
                        latex=str(raw.get("latex", "")),
                        text=raw.get("text"),
                        page_idx=int(raw.get("page_idx", 0)),
                        metadata={k: v for k, v in raw.items() if k not in ("type", "page_idx", "latex", "text")},
                    )
                )
        return doc

    @staticmethod
    def to_content_list(document: ParsedDocument) -> List[Dict[str, Any]]:
        """ParsedDocument → RAGAnything 可用的 List[Dict]。"""
        if document.raw_content_list:
            # 保留解析器原生顺序与字段，避免有损转换。
            return [dict(x) for x in document.raw_content_list]

        out: List[Dict[str, Any]] = []
        for ch in document.chunks:
            item = ContentListItem(
                type="text",
                page_idx=ch.page_idx,
                text=ch.text,
                text_level=ch.text_level,
                metadata=dict(ch.metadata),
            )
            out.append(item.to_dict())
        for im in document.images:
            item = ContentListItem(
                type="image",
                page_idx=im.page_idx,
                img_path=im.img_path,
                image_caption=im.captions,
                image_footnote=im.footnotes,
                metadata=dict(im.metadata),
            )
            out.append(item.to_dict())
        for tb in document.tables:
            item = ContentListItem(
                type="table",
                page_idx=tb.page_idx,
                table_body=tb.table_body,
                table_caption=tb.captions,
                table_footnote=tb.footnotes,
                metadata=dict(tb.metadata),
            )
            out.append(item.to_dict())
        for eq in document.equations:
            item = ContentListItem(
                type="equation",
                page_idx=eq.page_idx,
                latex=eq.latex,
                equation_text=eq.text,
                metadata=dict(eq.metadata),
            )
            out.append(item.to_dict())
        return out

    @staticmethod
    def build_process_request_from_file(path: str, **kwargs: Any) -> DocumentProcessRequest:
        """由文件路径快速构造 DocumentProcessRequest。"""
        return DocumentProcessRequest(source_path=path, extra=dict(kwargs))

    @staticmethod
    def build_process_request_from_document(
        document: ParsedDocument, **kwargs: Any
    ) -> DocumentProcessRequest:
        """由 ParsedDocument 构造入库请求（无文件路径）。"""
        return DocumentProcessRequest(
            parsed_document=document,
            doc_id=document.doc_id,
            extra=dict(kwargs),
        )
