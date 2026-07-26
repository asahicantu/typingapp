from __future__ import annotations
import hashlib
import os
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser

CONTAINER_PATH = "META-INF/container.xml"
CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "nav"}


@dataclass(frozen=True)
class EpubMeta:
    path: str
    title: str
    author: str


@dataclass(frozen=True)
class DocNode:
    kind: str  # "heading" | "paragraph"
    text: str


class _BodyTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[DocNode] = []
        self._tag_stack: list[str] = []
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in HEADING_TAGS or tag == "p":
            self._buffer = []

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in HEADING_TAGS:
            text = " ".join("".join(self._buffer).split())
            if text:
                self.nodes.append(DocNode("heading", text))
            self._buffer = []
        elif tag == "p":
            text = " ".join("".join(self._buffer).split())
            if text:
                self.nodes.append(DocNode("paragraph", text))
            self._buffer = []

    def handle_data(self, data):
        if self._tag_stack and self._tag_stack[-1] in SKIP_TAGS:
            return
        if any(t in SKIP_TAGS for t in self._tag_stack):
            return
        self._buffer.append(data)


def epub_book_id(path: str) -> str:
    """Stable book_id for an EPUB file, derived from its absolute path."""
    return f"epub:{hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:16]}"


def scan_epub_folder(folder: str) -> list[EpubMeta]:
    if not folder:
        return []
    try:
        entries = os.listdir(folder)
    except OSError:
        return []

    results: list[EpubMeta] = []
    for name in sorted(entries):
        if not name.lower().endswith(".epub"):
            continue
        path = os.path.join(folder, name)
        meta = _read_epub_meta(path)
        if meta is not None:
            results.append(meta)
    return results


def _read_epub_meta(path: str) -> EpubMeta | None:
    try:
        title, author = _read_opf_metadata(path)
    except Exception:
        return None
    if title is None:
        return None
    return EpubMeta(path=path, title=title, author=author or "Unknown")


def _read_opf_metadata(path: str) -> tuple[str | None, str | None]:
    with zipfile.ZipFile(path) as zf:
        opf_path = _resolve_opf_path(zf)
        opf_root = ET.fromstring(zf.read(opf_path))
        title_el = opf_root.find(".//{http://purl.org/dc/elements/1.1/}title")
        creator_el = opf_root.find(".//{http://purl.org/dc/elements/1.1/}creator")
        title = title_el.text.strip() if title_el is not None and title_el.text else None
        author = creator_el.text.strip() if creator_el is not None and creator_el.text else None
        return title, author


def _resolve_opf_path(zf: zipfile.ZipFile) -> str:
    container_xml = zf.read(CONTAINER_PATH)
    root = ET.fromstring(container_xml)
    rootfile = root.find(".//c:rootfile", CONTAINER_NS)
    if rootfile is None or "full-path" not in rootfile.attrib:
        raise ValueError("no rootfile in container.xml")
    return rootfile.attrib["full-path"]


def parse_epub(path: str) -> list[DocNode] | None:
    try:
        with zipfile.ZipFile(path) as zf:
            opf_path = _resolve_opf_path(zf)
            opf_dir = posixpath.dirname(opf_path)
            opf_root = ET.fromstring(zf.read(opf_path))

            manifest = {
                item.attrib["id"]: item.attrib["href"]
                for item in opf_root.findall(".//opf:manifest/opf:item", OPF_NS)
            }
            spine_ids = [
                itemref.attrib["idref"]
                for itemref in opf_root.findall(".//opf:spine/opf:itemref", OPF_NS)
            ]

            nodes: list[DocNode] = []
            for idref in spine_ids:
                href = manifest.get(idref)
                if not href:
                    continue
                doc_path = posixpath.normpath(posixpath.join(opf_dir, href))
                try:
                    raw = zf.read(doc_path).decode("utf-8", errors="ignore")
                except KeyError:
                    continue
                parser = _BodyTextParser()
                parser.feed(raw)
                nodes.extend(parser.nodes)
            return nodes
    except Exception:
        return None


def epub_to_flat_text(nodes: list[DocNode]) -> str:
    blocks = []
    for node in nodes:
        if node.kind == "heading":
            blocks.append(f"# {node.text}")
        else:
            blocks.append(node.text)
    return "\n\n".join(blocks)
