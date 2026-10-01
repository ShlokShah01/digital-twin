"""File loaders: plain text, markdown, JSON (chat logs, any nested dicts) and
CSV. Every document is normalized into a Document object with a title, source
path and raw text. JSON chat logs use a heuristic to find the user's own
utterances vs. the counterparty."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from .models import Chunk, Document
from .text_utils import chunk_text, clean, token_count

EXT_TEXT = {".txt", ".md", ".markdown", ".rst", ".org"}
EXT_JSON = {".json", ".jsonl", ".ndjson"}
EXT_CSV = {".csv", ".tsv"}


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# plain text / markdown
# ---------------------------------------------------------------------------
def _strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)  # code blocks
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)  # headings
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links
    text = re.sub(r"[*_~`>|>\-]{1,}", " ", text)  # bold/italic/list markers
    return text


def _load_text(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return Document(
        doc_id=f"{path.stem}-{_hash(raw)}",
        title=path.stem,
        source=str(path),
        kind="markdown" if path.suffix in {".md", ".markdown"} else "text",
        text=clean(_strip_markdown(raw)),
    )


# ---------------------------------------------------------------------------
# json / chat logs
# ---------------------------------------------------------------------------
_NARRATIVE_FIELDS = {"text", "message", "content", "body", "note", "thought", "entry", "reply"}


def _walk_strings(node, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, (list, tuple)):
        for x in node:
            _walk_strings(x, out)
    elif isinstance(node, dict):
        for v in node.values():
            _walk_strings(v, out)


def _messages_from(node):
    """Best-effort extraction of message records from arbitrary JSON."""
    if isinstance(node, dict):
        if any(k in node for k in ("text", "message", "body", "content")) and "name" in node:
            return [node]
        out = []
        for v in node.values():
            out.extend(_messages_from(v))
        return out
    if isinstance(node, list):
        out = []
        for x in node:
            out.extend(_messages_from(x))
        return out
    return []


def _load_json(path: Path) -> list[Document]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    parsed = json.loads(raw)
    docs: list[Document] = []
    msgs = _messages_from(parsed)
    if msgs:
        # Try to treat it as a chat log: prefer the person's own voice.
        self_names = {m.get("name") for m in msgs if m.get("name")}
        likely_self = _pick_self_name(msgs)
        self_msgs = [
            m.get("text", m.get("message", m.get("body", "")))
            for m in msgs
            if (m.get("name") or m.get("from") or m.get("author")) == likely_self
            and m.get("text", m.get("message", m.get("body", "")))
        ]
        body = "\n\n".join(str(x) for x in self_msgs) if self_msgs else "\n\n".join(str(x) for x in _walk_json_str(msgs))
        docs.append(Document(doc_id=f"{path.stem}-{_hash(raw)}", title=f"{path.stem} (self voice)",
                             source=str(path), kind="json-chat", text=clean(body)))
        other_msgs = [
            m.get("text", m.get("message", m.get("body", "")))
            for m in msgs
            if (m.get("name") or m.get("from") or m.get("author")) not in (None, likely_self)
            and m.get("text", m.get("message", m.get("body", "")))
        ]
        if other_msgs and self_msgs:
            combined = []
            for m in msgs:
                sender = m.get("name") or m.get("from") or m.get("author")
                content = m.get("text", m.get("message", m.get("body", "")))
                if content and sender is not None:
                    combined.append(f"{sender}: {content}")
            docs.append(Document(doc_id=f"{path.stem}-full-{_hash(raw)}", title=f"{path.stem} (conversation)",
                                 source=str(path), kind="json-chat", text=clean("\n\n".join(combined))))
    else:
        chunks = []
        _walk_strings(parsed, chunks)
        body = "\n\n".join(c for c in chunks if c.strip())
        docs.append(Document(doc_id=f"{path.stem}-{_hash(raw)}", title=path.stem,
                             source=str(path), kind="json", text=clean(body)))
    return docs


def _walk_json_str(node):
    out = []
    _walk_strings(node, out)
    return out


def _pick_self_name(msgs):
    """The person of interest is usually the dominant speaker in their own log."""
    from collections import Counter
    counts = Counter()
    for m in msgs:
        name = m.get("name") or m.get("from") or m.get("author")
        if name:
            counts[name] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# csv
# ---------------------------------------------------------------------------
def _load_csv(path: Path) -> Document:
    charset = path.read_text(encoding="utf-8", errors="ignore")
    dialect = csv.Sniffer().sniff(charset[:4096]) if charset.strip() else csv.excel
    rows = list(csv.reader(charset.splitlines(), dialect))
    if not rows:
        return Document(doc_id=f"{path.stem}-0", title=path.stem, source=str(path), kind="csv", text="")
    header = rows[0]
    lines = []
    if len(header) >= 2:
        body_rows = rows[1:]
        for row in body_rows:
            if len(row) >= 2:
                lines.append(f"{row[0]}: {row[1]}")
        text = "\n".join(lines)
    else:
        text = "\n".join(", ".join(r) for r in rows)
    return Document(doc_id=f"{path.stem}-{_hash(text)}", title=path.stem,
                    source=str(path), kind="csv", text=clean(text))


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def load_file(path: Path) -> list[Document]:
    path = Path(path)
    if not path.is_file():
        return []
    if path.suffix.lower() in EXT_TEXT:
        return [_load_text(path)]
    if path.suffix.lower() in EXT_JSON:
        return _load_json(path)
    if path.suffix.lower() in EXT_CSV:
        return [_load_csv(path)]
    return []


def load_directory(src: str | Path) -> list[Document]:
    src = Path(src)
    docs: list[Document] = []
    if src.is_file():
        return load_file(src)
    if not src.is_dir():
        return docs
    for p in sorted(src.rglob("*")):
        if p.is_file() and p.suffix.lower() in EXT_TEXT | EXT_JSON | EXT_CSV:
            docs.extend(load_file(p))
    return docs


def chunk_documents(docs: list[Document], chunk_words: int = 220, overlap: int = 40,
                    index: dict[str, Chunk] | None = None) -> list[Chunk]:
    """Split documents into overlap-aware chunks. `index` optionally maps
    existing chunk ids -> Chunk to keep ids stable across rebuilds."""
    chunks: list[Chunk] = []
    seen: set[str] = set()
    chunk_id = 0
    for doc in docs:
        if not doc.text:
            continue
        for piece in chunk_text(doc.text, chunk_words, overlap):
            cid = f"c{chunk_id:06d}"
            chunk_id += 1
            if index is not None and piece in {c.text for c in index.values()}:
                continue  # dedupe against existing index
            if piece in seen:
                continue
            seen.add(piece)
            chunks.append(Chunk(id=cid, doc_id=doc.doc_id, source=doc.source,
                                title=doc.title, text=piece, n_tokens=token_count(piece)))
    return chunks