#!/usr/bin/env python
"""
Example script demonstrating parser integration with RAGAnything

This example shows how to:
1. Process documents with RAGAnything using configurable parsers
2. Perform pure text queries using aquery() method
3. Perform multimodal queries with specific multimodal content using aquery_with_multimodal() method
4. Handle different types of multimodal content (tables, equations) in queries
"""

import os
import argparse
import asyncio
import logging
import logging.config
from pathlib import Path

# 项目根优先于 site-packages，确保本地 raganything/ 的修改生效（如 MinerU 后端注入）
import sys

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug
from raganything import RAGAnything, RAGAnythingConfig

# ---------- 配置（由 .env 写入代码，可直接修改） ----------
# 注意：若修改过 EMBEDDING 模型或维度，需先删除 rag_storage 目录再运行，否则会报 dimension mismatch
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_API_KEY = "sk-uwuunufhiocggfwbhuxvtnysoanpzwjhdqbzsazneeibydea"
DEFAULT_LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"
DEFAULT_VISION_MODEL = "Pro/moonshotai/Kimi-K2.5"
DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B" 
DEFAULT_EMBEDDING_DIM = 4096
DEFAULT_PARSER = "mineru"
# ----------------------------------------------------


def configure_logging():
    """Configure logging for the application"""
    # Get log directory path from environment variable or use current directory
    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(os.path.join(log_dir, "raganything_example.log"))

    print(f"\nRAGAnything example log file: {log_file_path}\n")
    os.makedirs(os.path.dirname(log_dir), exist_ok=True)

    # Get log file max size and backup count from environment variables
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", 10485760))  # Default 10MB
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", 5))  # Default 5 backups

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s: %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "formatter": "detailed",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file_path,
                    "maxBytes": log_max_bytes,
                    "backupCount": log_backup_count,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "lightrag": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "raganything": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )

    # Set the logger level to INFO
    logger.setLevel(logging.INFO)
    # Enable verbose debug if needed
    set_verbose_debug(os.getenv("VERBOSE", "false").lower() == "true")


async def process_with_rag(
    file_path: str,
    output_dir: str,
    api_key: str,
    base_url: str = None,
    working_dir: str = None,
    parser: str = None,
    custom_query: str = None,
):
    """
    Process document with RAGAnything

    Args:
        file_path: Path to the document
        output_dir: Output directory for RAG results
        api_key: OpenAI API key
        base_url: Optional base URL for API
        working_dir: Working directory for RAG storage
    """
    rag = None
    try:
        # Model names from 上方配置
        llm_model = DEFAULT_LLM_MODEL
        vision_model = DEFAULT_VISION_MODEL

        # Create RAGAnything configuration
        config = RAGAnythingConfig(
            working_dir=working_dir or "./rag_storage",
            parser=parser,  # Parser selection: mineru, docling, or paddleocr
            parse_method="auto",  # Parse method: auto, ocr, or txt
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )

        # Define LLM model function
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        # Define vision model function for image processing
        def vision_model_func(
            prompt,
            system_prompt=None,
            history_messages=[],
            image_data=None,
            messages=None,
            **kwargs,
        ):
            # If messages format is provided (for multimodal VLM enhanced query), use it directly
            if messages:
                return openai_complete_if_cache(
                    vision_model,
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            # Traditional single image format
            elif image_data:
                return openai_complete_if_cache(
                    vision_model,
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=[
                        {"role": "system", "content": system_prompt}
                        if system_prompt
                        else None,
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    },
                                },
                            ],
                        }
                        if image_data
                        else {"role": "user", "content": prompt},
                    ],
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            # Pure text format
            else:
                return llm_model_func(prompt, system_prompt, history_messages, **kwargs)

        # Define embedding function - 使用上方配置
        # 注意：lightrag 的 openai_embed 被 @wrap_embedding_func_with_attrs(embedding_dim=1536) 装饰，
        # 若直接用 openai_embed() 会按 1536 校验导致 dimension mismatch。改用 .func 调用底层实现，
        # 仅由本处 EmbeddingFunc(embedding_dim=4096) 做维度校验。
        embedding_dim = DEFAULT_EMBEDDING_DIM
        embedding_model = DEFAULT_EMBEDDING_MODEL
        _raw_openai_embed = getattr(openai_embed, "func", openai_embed)

        embedding_func = EmbeddingFunc(
            embedding_dim=embedding_dim,
            max_token_size=8192,
            func=lambda texts: _raw_openai_embed(
                texts,
                model=embedding_model,
                api_key=api_key,
                base_url=base_url,
            ),
        )

        # Initialize RAGAnything with new dataclass structure
        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
        )

        # Process document（MinerU 需显式 -d：环境变量 MINERU_DEVICE / PARSER_DEVICE，如 cuda:0）
        _mineru_device = os.getenv("MINERU_DEVICE") or os.getenv("PARSER_DEVICE")
        _parse_kw = {"device": _mineru_device} if _mineru_device else {}
        await rag.process_document_complete(
            file_path=file_path,
            output_dir=output_dir,
            parse_method="auto",
            **_parse_kw,
        )

        # Example queries - demonstrating different query approaches
        logger.info("\nQuerying processed document:")

        # 0. Custom query from command line (if provided)
        if custom_query:
            logger.info(f"\n[Custom Query]: {custom_query}")
            result = await rag.aquery(custom_query, mode="hybrid")
            logger.info(f"Answer: {result}")
            print("\n" + "=" * 50)
            print("【你的问题】", custom_query)
            print("【回答】", result)
            print("=" * 50 + "\n")

        # 1. Pure text queries using aquery()
        text_queries = [
            "What is the main content of the document?",
            "What are the key topics discussed?",
        ]

        for query in text_queries:
            logger.info(f"\n[Text Query]: {query}")
            result = await rag.aquery(query, mode="hybrid")
            logger.info(f"Answer: {result}")

        # 2. Multimodal query with specific multimodal content using aquery_with_multimodal()
        logger.info(
            "\n[Multimodal Query]: Analyzing performance data in context of document"
        )
        multimodal_result = await rag.aquery_with_multimodal(
            "Compare this performance data with any similar results mentioned in the document",
            multimodal_content=[
                {
                    "type": "table",
                    "table_data": """Method,Accuracy,Processing_Time
                                RAGAnything,95.2%,120ms
                                Traditional_RAG,87.3%,180ms
                                Baseline,82.1%,200ms""",
                    "table_caption": "Performance comparison results",
                }
            ],
            mode="hybrid",
        )
        logger.info(f"Answer: {multimodal_result}")

        # 3. Another multimodal query with equation content
        logger.info("\n[Multimodal Query]: Mathematical formula analysis")
        equation_result = await rag.aquery_with_multimodal(
            "Explain this formula and relate it to any mathematical concepts in the document",
            multimodal_content=[
                {
                    "type": "equation",
                    "latex": "F1 = 2 \\cdot \\frac{precision \\cdot recall}{precision + recall}",
                    "equation_caption": "F1-score calculation formula",
                }
            ],
            mode="hybrid",
        )
        logger.info(f"Answer: {equation_result}")

    except Exception as e:
        logger.error(f"Error processing with RAG: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
    finally:
        # 必须在当前 asyncio 事件循环内关闭 Neo4j 等异步存储；否则进程退出时
        # atexit 会另起新循环收尾，易触发「Event loop is closed」。
        if rag is not None:
            try:
                await rag.finalize_storages()
            except Exception as fin_err:
                logger.warning("finalize_storages in finally: %s", fin_err)


def main():
    """Main function to run the example"""
    parser = argparse.ArgumentParser(description="MinerU RAG Example")
    parser.add_argument("file_path", help="Path to the document to process")
    parser.add_argument(
        "--working_dir",
        "-w",
        default=str(Path(__file__).parent.parent / "rag_storage"),
        help="Working directory path (默认: 项目根/rag_storage)",
    )
    parser.add_argument(
        "--output", "-o", default="./output", help="Output directory path"
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="OpenAI API key (默认使用代码内配置)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="API base URL (默认使用代码内配置)",
    )
    parser.add_argument(
        "--parser",
        default=DEFAULT_PARSER,
        choices=["mineru", "docling", "paddleocr", "deepseek_ocr2"],
        help="Parser selection (deepseek_ocr2: set DEEPSEEK_OCR2_PYTHON to OCR2 conda python if deps are in another env)",
    )
    parser.add_argument(
        "--query", "-q",
        default=None,
        help="Optional: ask a question about the document after processing (e.g. 这个讲了什么？)",
    )

    args = parser.parse_args()

    # Check if API key is provided
    if not args.api_key:
        logger.error("Error: OpenAI API key is required")
        logger.error("Set api key environment variable or use --api-key option")
        return

    # Create output directory if specified
    if args.output:
        os.makedirs(args.output, exist_ok=True)

    # Process with RAG
    asyncio.run(
        process_with_rag(
            args.file_path,
            args.output,
            args.api_key,
            args.base_url,
            args.working_dir,
            args.parser,
            args.query,
        )
    )


if __name__ == "__main__":
    # Configure logging first
    configure_logging()

    print("RAGAnything Example")
    print("=" * 30)
    print("Processing document with multimodal RAG pipeline")
    print("=" * 30)

    main()
