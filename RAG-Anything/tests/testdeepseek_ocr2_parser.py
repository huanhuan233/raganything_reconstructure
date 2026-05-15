import pytest

from third_party.raganything.parser import DeepseekOCR2Parser, SUPPORTED_PARSERS, get_parser


def test_supported_parsers_include_deepseek_ocr2():
    assert "deepseek_ocr2" in SUPPORTED_PARSERS


def test_get_parser_returns_deepseek_ocr2_parser():
    parser = get_parser("deepseek_ocr2")
    assert isinstance(parser, DeepseekOCR2Parser)


def test_deepseek_check_installation_false_when_dependency_missing(monkeypatch):
    parser = DeepseekOCR2Parser()

    def missing_dependency():
        raise ImportError("missing transformers")

    monkeypatch.setattr(parser, "_require_transformers", missing_dependency)
    assert parser.check_installation() is False


def test_deepseek_parse_image_returns_content_list_schema(monkeypatch, tmp_path):
    parser = DeepseekOCR2Parser()
    fake_image = tmp_path / "sample.png"
    fake_image.write_bytes(b"image-bytes")

    monkeypatch.setattr(
        parser,
        "_infer_image_markdown",
        lambda **kwargs: "# title\n\nsome parsed markdown",
    )

    content_list = parser.parse_image(fake_image, page_idx=3)
    assert content_list == [
        {"type": "text", "text": "# title\n\nsome parsed markdown", "page_idx": 3}
    ]


def test_deepseek_parse_pdf_assigns_page_index(monkeypatch, tmp_path):
    parser = DeepseekOCR2Parser()
    fake_pdf = tmp_path / "sample.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n")

    class DummyPageImage:
        def save(self, path):
            with open(path, "wb") as f:
                f.write(b"dummy")

    monkeypatch.setattr(
        parser,
        "_extract_pdf_page_inputs",
        lambda pdf_path: [(0, DummyPageImage()), (1, DummyPageImage())],
    )
    monkeypatch.setattr(
        parser,
        "_infer_image_markdown",
        lambda **kwargs: "page markdown",
    )

    content_list = parser.parse_pdf(fake_pdf)
    assert content_list == [
        {"type": "text", "text": "page markdown", "page_idx": 0},
        {"type": "text", "text": "page markdown", "page_idx": 1},
    ]
