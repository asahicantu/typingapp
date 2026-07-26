import zipfile
from typingapp.engine.epub_source import scan_epub_folder, parse_epub, epub_to_flat_text, epub_book_id, DocNode

CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Sample Book</dc:title>
    <dc:creator>A. Writer</dc:creator>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>
"""

CH1 = """<html><body>
<h1>Chapter One</h1>
<p>This is the first paragraph of chapter one.</p>
<p>This is the second paragraph.</p>
<script>ignored_var = 1;</script>
</body></html>
"""

CH2 = """<html><body>
<h1>Chapter Two</h1>
<p>Chapter two begins here.</p>
</body></html>
"""


def _write_epub(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", OPF)
        zf.writestr("OEBPS/ch1.xhtml", CH1)
        zf.writestr("OEBPS/ch2.xhtml", CH2)


def test_scan_missing_folder_returns_empty(tmp_path):
    assert scan_epub_folder(str(tmp_path / "does-not-exist")) == []


def test_scan_finds_valid_epub_with_metadata(tmp_path):
    _write_epub(tmp_path / "book.epub")
    results = scan_epub_folder(str(tmp_path))
    assert len(results) == 1
    assert results[0].title == "Sample Book"
    assert results[0].author == "A. Writer"
    assert results[0].path.endswith("book.epub")


def test_parse_epub_extracts_headings_and_paragraphs_in_order(tmp_path):
    epub_path = tmp_path / "book.epub"
    _write_epub(epub_path)
    nodes = parse_epub(str(epub_path))
    assert nodes == [
        DocNode("heading", "Chapter One"),
        DocNode("paragraph", "This is the first paragraph of chapter one."),
        DocNode("paragraph", "This is the second paragraph."),
        DocNode("heading", "Chapter Two"),
        DocNode("paragraph", "Chapter two begins here."),
    ]


def test_parse_epub_skips_script_content():
    pass  # covered implicitly above: "ignored_var" never appears in extracted nodes


def test_parse_epub_returns_none_on_corrupt_zip(tmp_path):
    bad_path = tmp_path / "bad.epub"
    bad_path.write_bytes(b"not a zip file")
    assert parse_epub(str(bad_path)) is None


def test_parse_epub_returns_none_on_missing_container(tmp_path):
    path = tmp_path / "no_container.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
    assert parse_epub(str(path)) is None


def test_epub_to_flat_text_matches_markup_convention():
    nodes = [DocNode("heading", "Title"), DocNode("paragraph", "Body text.")]
    flat = epub_to_flat_text(nodes)
    assert flat == "# Title\n\nBody text."


def test_epub_book_id_stable_across_calls_for_same_path(tmp_path):
    path = str(tmp_path / "book.epub")
    assert epub_book_id(path) == epub_book_id(path)
    assert epub_book_id(path).startswith("epub:")


def test_epub_book_id_differs_for_different_paths(tmp_path):
    assert epub_book_id(str(tmp_path / "a.epub")) != epub_book_id(str(tmp_path / "b.epub"))
