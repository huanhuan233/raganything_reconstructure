"""
解析器统一门面：MinerU / Docling / PaddleOCR / DeepSeek-OCR2 等由后续实现注入。

当前不接 `raganything.parser`，避免在本层启动重依赖子进程。

**与惰性 Parser 的关系**：在真正实现 ``parse_file`` / ``parse_pdf`` 等之前，请由编排层先调用
``RAGAnythingEngineAdapter.ensure_parser_ready_for_document_parsing()``，
或统一走引擎的 ``process_document``（带 ``source_path``）— 后者会自动 ``mark_parser_required``。
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Union

from .document_adapter import DocumentAdapter
from .types import ParsedDocument


class ParserAdapter(ABC):
    """解析器抽象基类。"""

    @abstractmethod
    async def parse_file(
        self,
        file_path: Union[str, Path],
        *,
        output_dir: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """按扩展名或配置选择解析链路。"""
        raise NotImplementedError

    async def parse_pdf(
        self, pdf_path: Union[str, Path], *, output_dir: Optional[str] = None, **kwargs: Any
    ) -> ParsedDocument:
        raise NotImplementedError

    async def parse_image(
        self, image_path: Union[str, Path], *, output_dir: Optional[str] = None, **kwargs: Any
    ) -> ParsedDocument:
        raise NotImplementedError

    async def parse_office(
        self, doc_path: Union[str, Path], *, output_dir: Optional[str] = None, **kwargs: Any
    ) -> ParsedDocument:
        raise NotImplementedError


class MinerUParserAdapter(ParserAdapter):
    """
    MinerU 解析占位。

    TODO: 委托 `raganything.parser.MineruParser` 或 HTTP API；对齐 MINERU_BACKEND、设备与安全目录。
    """

    @staticmethod
    def _as_positive_int(value: Any, default: int) -> int:
        try:
            n = int(value)
            return n if n > 0 else default
        except Exception:  # noqa: BLE001
            return default

    @staticmethod
    def _resolve_output_dir(output_dir: Optional[str]) -> Optional[str]:
        """
        统一解析输出目录：
        - 节点显式传入 output_dir：优先使用
        - 未传时默认当前项目根目录下 ``output``（复制项目后自动跟随）
        - 可通过 .env 暴露策略：
          - ``OUTPUT_DIR_POLICY=project``（默认）：OUTPUT_DIR 仅允许项目内路径；项目外绝对路径会被忽略
          - ``OUTPUT_DIR_POLICY=env``：严格使用 OUTPUT_DIR（即便是项目外绝对路径）
        - 若 OUTPUT_DIR 是相对路径，则按当前项目根目录解析
        """
        project_root = Path(__file__).resolve().parents[2]
        project_output = (project_root / "output").resolve()
        output_policy = str(os.getenv("OUTPUT_DIR_POLICY") or "project").strip().lower()
        allow_external_env_output = output_policy in {"env", "absolute", "external"}

        candidate = str(output_dir or "").strip()
        if candidate:
            p = Path(candidate).expanduser()
            return str((p if p.is_absolute() else (project_root / p)).resolve())

        env_out = str(os.getenv("OUTPUT_DIR") or "").strip()
        if env_out:
            p = Path(env_out).expanduser()
            resolved = (p if p.is_absolute() else (project_root / p)).resolve()
            if p.is_absolute():
                if allow_external_env_output:
                    return str(resolved)
                try:
                    resolved.relative_to(project_root)
                    return str(resolved)
                except Exception:  # noqa: BLE001
                    # 默认 project 策略下，旧工程绝对路径会被忽略，避免复制项目后继续写旧目录。
                    return str(project_output)
            return str(resolved)

        return str(project_output)

    @staticmethod
    def _checkpoint_path(base_output_dir: Path) -> Path:
        return base_output_dir / "_mineru_parse_checkpoint.json"

    @staticmethod
    def _load_checkpoint(base_output_dir: Path) -> dict[str, Any]:
        ckpt = MinerUParserAdapter._checkpoint_path(base_output_dir)
        if not ckpt.is_file():
            return {}
        try:
            raw = json.loads(ckpt.read_text(encoding="utf-8"))
            return dict(raw) if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _save_checkpoint(base_output_dir: Path, payload: dict[str, Any]) -> None:
        ckpt = MinerUParserAdapter._checkpoint_path(base_output_dir)
        try:
            ckpt.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _build_parse_signature(
        *,
        src_path: Path,
        parse_method: str,
        pages_per_split: int,
        parse_kwargs: dict[str, Any],
    ) -> str:
        safe_kwargs = {
            str(k): str(v)
            for k, v in sorted(parse_kwargs.items(), key=lambda x: str(x[0]))
            if str(k) not in {"doc_id"}
        }
        sig = {
            "src": str(src_path),
            "method": parse_method,
            "pages_per_split": int(pages_per_split),
            "kwargs": safe_kwargs,
        }
        return json.dumps(sig, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _has_batch_parse_artifacts(page_output_dir: Path, file_stem: str, method: str) -> bool:
        direct_json = page_output_dir / f"{file_stem}_content_list.json"
        if direct_json.is_file():
            return True
        file_stem_subdir = page_output_dir / file_stem
        nested = file_stem_subdir / method / f"{file_stem}_content_list.json"
        if nested.is_file():
            return True
        for subdir in page_output_dir.iterdir():
            if not subdir.is_dir():
                continue
            candidate_json = subdir / f"{file_stem}_content_list.json"
            if candidate_json.is_file():
                return True
        return False

    @staticmethod
    def _patch_page_index(item: dict[str, Any], *, offset: int) -> dict[str, Any]:
        if offset <= 0:
            return item
        patched = dict(item)
        for key in ("page_idx", "page_num", "page_number", "page_id"):
            if key not in patched:
                continue
            v = patched.get(key)
            if isinstance(v, int):
                patched[key] = v + offset
            elif isinstance(v, float) and float(v).is_integer():
                patched[key] = int(v) + offset
            elif isinstance(v, str) and v.strip().isdigit():
                patched[key] = int(v.strip()) + offset
        return patched

    @staticmethod
    def _resolve_mineru_method(parse_method: str, parse_kwargs: dict[str, Any]) -> str:
        """
        对齐 ``raganything.parser.MineruParser.parse_pdf`` 的 backend -> method 目录映射。
        """
        backend = str(parse_kwargs.get("backend") or "").strip()
        if backend.startswith("vlm-"):
            return "vlm"
        if backend.startswith("hybrid-"):
            return "hybrid_auto"
        return parse_method

    @staticmethod
    def _resolve_page_value(v: Any, *, batch_start: int, batch_page_count: int) -> Any:
        """
        将 batch 内局部页号提升为全局页号。
        仅在 ``batch_start > 0`` 且值落在 ``[0, batch_page_count)`` 时偏移，避免误改本就全局的页号。
        """
        if batch_start <= 0:
            return v
        if batch_page_count <= 0:
            return v
        if isinstance(v, int):
            if 0 <= v < batch_page_count:
                return v + batch_start
            return v
        if isinstance(v, float) and float(v).is_integer():
            iv = int(v)
            if 0 <= iv < batch_page_count:
                return iv + batch_start
            return iv
        if isinstance(v, str) and v.strip().isdigit():
            iv = int(v.strip())
            if 0 <= iv < batch_page_count:
                return iv + batch_start
            return iv
        return v

    @classmethod
    def _patch_page_refs_recursive(
        cls,
        obj: Any,
        *,
        batch_start: int,
        batch_page_count: int,
    ) -> Any:
        """
        递归修复解析结果中的页号引用：
        - 顶层与嵌套 dict/list 中的 page_idx/page_number/page_num/page_id/page
        - 同时保留非页号字段原值
        """
        page_keys = {"page_idx", "page_num", "page_number", "page_id", "page"}
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if k in page_keys:
                    out[k] = cls._resolve_page_value(
                        v,
                        batch_start=batch_start,
                        batch_page_count=batch_page_count,
                    )
                else:
                    out[k] = cls._patch_page_refs_recursive(
                        v,
                        batch_start=batch_start,
                        batch_page_count=batch_page_count,
                    )
            return out
        if isinstance(obj, list):
            return [
                cls._patch_page_refs_recursive(
                    x,
                    batch_start=batch_start,
                    batch_page_count=batch_page_count,
                )
                for x in obj
            ]
        if isinstance(obj, tuple):
            return tuple(
                cls._patch_page_refs_recursive(
                    x,
                    batch_start=batch_start,
                    batch_page_count=batch_page_count,
                )
                for x in obj
            )
        return obj

    @staticmethod
    def _infer_item_page(item: dict[str, Any], default_page: int) -> int:
        for key in ("page_idx", "page_number", "page_num", "page_id", "page"):
            v = item.get(key)
            if isinstance(v, int):
                return v
            if isinstance(v, float) and float(v).is_integer():
                return int(v)
            if isinstance(v, str) and v.strip().isdigit():
                return int(v.strip())
        return default_page

    @classmethod
    def merge_paginated_parse_results(
        cls,
        batches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        合并分页解析结果为单一完整 content_list（保持全局页号与文档顺序）。
        每个 batch 形如：
            {
              "start": int,
              "end": int,
              "batch_index": int,
              "content_list": list[dict]
            }
        """
        flattened: list[tuple[int, int, int, dict[str, Any]]] = []
        for b in batches:
            start = int(b.get("start") or 0)
            end = int(b.get("end") or start)
            batch_index = int(b.get("batch_index") or 0)
            batch_page_count = max(1, end - start + 1)
            raw_items = b.get("content_list")
            if not isinstance(raw_items, list):
                continue
            for local_idx, one in enumerate(raw_items):
                if not isinstance(one, dict):
                    continue
                patched = cls._patch_page_refs_recursive(
                    one,
                    batch_start=start,
                    batch_page_count=batch_page_count,
                )
                page_order = cls._infer_item_page(patched, default_page=start)
                flattened.append((page_order, batch_index, local_idx, patched))
        flattened.sort(key=lambda x: (x[0], x[1], x[2]))
        return [x[3] for x in flattened]

    def _parse_paginated_pdf_with_mineru(
        self,
        mineru: Any,
        *,
        src_path: Path,
        parse_method: str,
        output_dir: Optional[str],
        pages_per_split: int,
        parse_kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        复用 MinerU 原生分页执行与输出读取逻辑（按原始 PDF 的起止页范围调用），
        再合并为单一完整 content_list。
        """
        from pypdf import PdfReader  # pyright: ignore[reportMissingImports]

        reader = PdfReader(str(src_path))
        total_pages = len(reader.pages)
        if total_pages <= 0:
            return [], {
                "paginated_parse": False,
                "page_batches": 0,
                "merged_back": True,
                "total_pages": 0,
            }

        if output_dir:
            base_output_dir = Path(mineru._unique_output_dir(output_dir, src_path))  # type: ignore[attr-defined]
        else:
            base_output_dir = src_path.parent / "mineru_output"
        base_output_dir.mkdir(parents=True, exist_ok=True)

        read_method = self._resolve_mineru_method(parse_method, parse_kwargs)
        file_stem = src_path.stem

        parse_signature = self._build_parse_signature(
            src_path=src_path,
            parse_method=parse_method,
            pages_per_split=pages_per_split,
            parse_kwargs=parse_kwargs,
        )
        checkpoint = self._load_checkpoint(base_output_dir)
        ckpt_signature = str(checkpoint.get("parse_signature") or "")
        if ckpt_signature != parse_signature:
            checkpoint = {
                "version": 1,
                "source_file": str(src_path),
                "source_mtime_ns": int(src_path.stat().st_mtime_ns),
                "source_size": int(src_path.stat().st_size),
                "parse_signature": parse_signature,
                "updated_at": int(time.time()),
                "batches": {},
            }
        batches_state = checkpoint.get("batches")
        if not isinstance(batches_state, dict):
            batches_state = {}
            checkpoint["batches"] = batches_state

        resumed_batches = 0
        executed_batches = 0
        batches: list[dict[str, Any]] = []
        for batch_index, start in enumerate(range(0, total_pages, pages_per_split)):
            end = min(start + pages_per_split - 1, total_pages - 1)
            page_output_dir = base_output_dir / f"pages_{start}_{end}"
            page_output_dir.mkdir(parents=True, exist_ok=True)
            batch_key = f"{start}_{end}"
            has_artifact = self._has_batch_parse_artifacts(page_output_dir, file_stem, read_method)
            batch_state = batches_state.get(batch_key) if isinstance(batches_state, dict) else None
            state_done = isinstance(batch_state, dict) and str(batch_state.get("status") or "") == "done"

            if state_done or has_artifact:
                content_list, _ = mineru._read_output_files(  # type: ignore[attr-defined]
                    page_output_dir,
                    file_stem,
                    method=read_method,
                )
                resumed_batches += 1
            else:
                mineru._run_mineru_command(  # type: ignore[attr-defined]
                    input_path=src_path,
                    output_dir=page_output_dir,
                    method=read_method,
                    start_page=start,
                    end_page=end,
                    **parse_kwargs,
                )
                content_list, _ = mineru._read_output_files(  # type: ignore[attr-defined]
                    page_output_dir,
                    file_stem,
                    method=read_method,
                )
                executed_batches += 1

            batches_state[batch_key] = {
                "status": "done",
                "batch_index": int(batch_index),
                "start": int(start),
                "end": int(end),
                "block_count": int(len(content_list) if isinstance(content_list, list) else 0),
                "updated_at": int(time.time()),
            }
            checkpoint["updated_at"] = int(time.time())
            self._save_checkpoint(base_output_dir, checkpoint)
            batches.append(
                {
                    "start": start,
                    "end": end,
                    "batch_index": batch_index,
                    "content_list": content_list if isinstance(content_list, list) else [],
                }
            )

        merged = self.merge_paginated_parse_results(batches)
        return merged, {
            "paginated_parse": True,
            "page_batches": len(batches),
            "merged_back": True,
            "total_pages": total_pages,
            "resumed_batches": resumed_batches,
            "executed_batches": executed_batches,
        }

    def _build_page_split_source_pdf(
        self,
        *,
        mineru: Any,
        src_path: Path,
        output_dir: Optional[str],
    ) -> tuple[Path | None, list[Path]]:
        """
        为分页切分准备 PDF 源：
        - pdf: 直接返回原文件
        - office/text: 先转成 pdf 再返回
        - 其他（如图片）: 返回 None（回退原 parse_document）
        """
        cleanup_paths: list[Path] = []
        ext = src_path.suffix.lower()

        if ext == ".pdf":
            return src_path, cleanup_paths

        if ext in getattr(mineru, "OFFICE_FORMATS", set()):
            conv_dir = tempfile.mkdtemp(prefix="mineru_office_to_pdf_")
            pdf_path = Path(mineru.convert_office_to_pdf(src_path, conv_dir))
            cleanup_paths.extend([pdf_path, Path(conv_dir)])
            return pdf_path, cleanup_paths

        if ext in getattr(mineru, "TEXT_FORMATS", set()):
            conv_dir = tempfile.mkdtemp(prefix="mineru_text_to_pdf_")
            pdf_path = Path(mineru.convert_text_to_pdf(src_path, conv_dir))
            cleanup_paths.extend([pdf_path, Path(conv_dir)])
            return pdf_path, cleanup_paths

        return None, cleanup_paths

    async def parse_file(
        self,
        file_path: Union[str, Path],
        *,
        output_dir: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        # 最小封装：复用 raganything.parser 既有解析逻辑，不重复实现 MinerU 命令细节。
        from third_party.raganything.parser import get_parser

        src = str(Path(file_path).expanduser().resolve())
        src_path = Path(src)
        effective_output_dir = self._resolve_output_dir(output_dir)
        mineru = get_parser("mineru")
        parse_method = str(method or "auto")
        parse_kwargs = dict(kwargs)
        raw_doc_id = parse_kwargs.pop("doc_id", None)
        doc_id = str(raw_doc_id) if raw_doc_id else None
        pages_per_split = self._as_positive_int(parse_kwargs.pop("pages_per_split", 2), 2)
        backend_env = os.getenv("MINERU_BACKEND", "").strip()
        if backend_env and parse_kwargs.get("backend") is None:
            parse_kwargs["backend"] = backend_env
        source_env = os.getenv("MINERU_MODEL_SOURCE", "").strip()
        if source_env and parse_kwargs.get("source") is None:
            parse_kwargs["source"] = source_env
        parse_meta: dict[str, Any] = {
            "paginated_parse": False,
            "page_batches": 0,
            "merged_back": True,
        }
        split_src_pdf, cleanup_files = self._build_page_split_source_pdf(
            mineru=mineru,
            src_path=src_path,
            output_dir=effective_output_dir,
        )
        try:
            if split_src_pdf is not None:
                content_list, parse_meta = self._parse_paginated_pdf_with_mineru(
                    mineru,
                    src_path=split_src_pdf,
                    parse_method=parse_method,
                    output_dir=effective_output_dir,
                    pages_per_split=pages_per_split,
                    parse_kwargs=parse_kwargs,
                )
            else:
                # 图片等非可分页格式：仍走原始解析流程
                content_list = mineru.parse_document(
                    src,
                    method=parse_method,
                    output_dir=effective_output_dir,
                    **parse_kwargs,
                )
                parse_meta = {
                    "paginated_parse": False,
                    "page_batches": 0,
                    "merged_back": True,
                }
        finally:
            for f in cleanup_files:
                try:
                    if f.exists():
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            for p in sorted(f.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                                if p.is_file():
                                    p.unlink(missing_ok=True)
                                elif p.is_dir():
                                    p.rmdir()
                            f.rmdir()
                except Exception:  # noqa: BLE001
                    pass
        doc = DocumentAdapter.from_content_list(
            content_list if isinstance(content_list, list) else [],
            source_file=src,
            doc_id=doc_id,
        )
        doc.metadata.update(
            {
                "parser": "mineru",
                "parse_method": parse_method,
                "output_dir": effective_output_dir,
                "pages_per_split": pages_per_split,
                "paginated_parse": bool(parse_meta.get("paginated_parse", False)),
                "page_batches": int(parse_meta.get("page_batches", 0) or 0),
                "merged_back": bool(parse_meta.get("merged_back", True)),
            }
        )
        return doc


class GenericParserAdapter(ParserAdapter):
    """
    通用回退占位（如仅 Markdown/纯文本直读）。

    TODO: 与 `raganything.parser` 中非 MinerU 分支对齐。
    """

    async def parse_file(
        self,
        file_path: Union[str, Path],
        *,
        output_dir: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        raise NotImplementedError(
            "TODO: 小文件直连读取或由 Docling CLI 封装。"
        )
