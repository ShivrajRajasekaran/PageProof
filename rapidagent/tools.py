"""Document store, the four allowed tools, and the budgeted/logged tool wrapper.

The agent can only touch document content through DocTools:
    list_documents() / list_headings(doc_id) / get_page(doc_id, page_number) / search_keyword(doc_id, keyword)
Every call goes through BudgetedToolbox, which logs it and refuses to execute past the budget.
"""
from __future__ import annotations

import collections
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

TOOL_BUDGET = 6

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_PRIVATE_USE = re.compile("[-]")


def clean_text(text: str) -> str:
    """Fix extraction artifacts that would break reading and keyword search."""
    for k, v in _LIGATURES.items():
        text = text.replace(k, v)
    text = unicodedata.normalize("NFKC", text)
    text = _PRIVATE_USE.sub("", text)
    text = text.replace("∗", "*").replace("’", "'").replace("‘", "'")
    text = re.sub(r"\*(?=[A-Za-z])", "* ", text)  # "A*search" -> "A* search" (kerning ate the space)
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join end-of-line hyphenation
    return text


def norm_for_search(text: str) -> str:
    return re.sub(r"\s+", " ", clean_text(text).lower()).strip()


# ----------------------------------------------------------------------------- headings
def _span_text(span: dict) -> str:
    """Rebuild span text from glyphs, inserting a space where the gap is word-sized (TeX bold fonts have no space glyph)."""
    out, prev = [], None
    for ch in span["chars"]:
        if prev is not None and ch["c"] != " " and prev["c"] != " ":
            if ch["bbox"][0] - prev["bbox"][2] > span["size"] * 0.18:
                out.append(" ")
        out.append(ch["c"])
        prev = ch
    return "".join(out)


_NUMBERED = re.compile(r"^(\d+(\.\d+){0,3}|[A-Z]\.|[IVX]+\.|Chapter \d+|Section \d+|Part [IVX\d]+|Appendix [A-Z\d]*)\s*\S", re.I)
_BARE_NUMBER = re.compile(r"^[\dIVXivx.]+$")


def _extract_headings(doc: pymupdf.Document) -> tuple[list[dict], str]:
    """Return (headings, source). Uses the embedded outline when present, else font-size/bold detection."""
    toc = doc.get_toc()
    if len(toc) >= 3:
        return ([{"level": lvl, "title": clean_text(t).strip(), "page": max(p, 1)} for lvl, t, p in toc], "embedded outline")

    # pass 1: find body font size and collect every line with its dominant font props
    size_chars: collections.Counter = collections.Counter()
    lines: list[dict] = []
    for pno, page in enumerate(doc, start=1):
        for block in page.get_text("rawdict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [s for s in ln["spans"] if any(c["c"].strip() for c in s["chars"])]
                if not spans:
                    continue
                for s in spans:
                    s["text"] = _span_text(s)
                text = re.sub(r"\s+", " ", " ".join(s["text"] for s in spans)).strip()
                size = round(max(s["size"] for s in spans), 1)
                bold = all(("bold" in s["font"].lower() or "bx" in s["font"].lower() or s["flags"] & 16) for s in spans)
                for s in spans:
                    size_chars[round(s["size"], 1)] += len(s["text"])
                lines.append({"page": pno, "y": ln["bbox"][1], "x": ln["bbox"][0], "size": size, "bold": bold, "text": text})
    if not size_chars:
        return [], "none"
    body = size_chars.most_common(1)[0][0]

    bare_num_pos: dict[int, list[float]] = {}  # (page -> y) of bold bare section numbers
    for ln in lines:
        if ln["bold"] and re.fullmatch(r"\d+(\.\d+){0,3}\.?", ln["text"].strip()):
            bare_num_pos.setdefault(ln["page"], []).append(ln["y"])
    cands = []
    for ln in lines:
        t = clean_text(ln["text"]).strip()
        if not t or len(t) > 110:
            continue
        bigger = ln["size"] >= body * 1.15
        bold_ok = ln["bold"] and ln["size"] >= body * 0.95
        numbered_bold = bold_ok and _NUMBERED.match(t) and len(t) < 80
        bare_num_bold = bold_ok and re.fullmatch(r"\d+(\.\d+){0,3}\.?", t)  # "1" / "3.1" printed apart from its title
        slightly_bigger_bold = bold_ok and ln["size"] >= body * 1.05 and len(t) < 80  # e.g. 12pt bold headings, 10.9pt body
        if bigger or numbered_bold or bare_num_bold or slightly_bigger_bold:
            cands.append({**ln, "text": t})
        elif bold_ok and len(t) < 70 and bare_num_pos.get(ln["page"]) and any(abs(y - ln["y"]) < 5 for y in bare_num_pos[ln["page"]]):
            cands.append({**ln, "text": t})  # title on the same baseline as a bold section number

    # merge pieces of one heading: same baseline (number + title) or consecutive same-size lines (wrapped titles)
    merged: list[dict] = []
    for c in cands:
        prev = merged[-1] if merged else None
        if prev and prev["page"] == c["page"] and (
            abs(prev["y"] - c["y"]) < 5
            or (abs(prev["size"] - c["size"]) < 0.3 and 0 < c["y"] - prev["y"] < c["size"] * 1.6 and not _NUMBERED.match(c["text"]))
        ):
            prev["text"] = (prev["text"] + " " + c["text"]).strip()
            prev["y"] = max(prev["y"], c["y"])
        else:
            merged.append(dict(c))

    # drop noise: bare numbers, mostly digits/symbols, repeated running headers
    def alpha_ratio(s: str) -> float:
        return sum(ch.isalpha() for ch in s) / max(len(s), 1)

    merged = [m for m in merged if not _BARE_NUMBER.match(m["text"]) and alpha_ratio(m["text"]) > 0.5 and len(m["text"]) >= 3]
    freq = collections.Counter(re.sub(r"\d+", "#", m["text"].lower()) for m in merged)
    npages = len(doc)
    merged = [m for m in merged if freq[re.sub(r"\d+", "#", m["text"].lower())] <= max(3, npages // 10)]

    if len(merged) < 3:
        return [], "none"
    sizes = sorted({m["size"] for m in merged}, reverse=True)
    out = []
    for m in merged:
        out.append({"level": sizes.index(m["size"]) + 1, "title": m["text"], "page": m["page"]})
    return out, "font-size/bold detection"


# ----------------------------------------------------------------------------- store
MAX_HEADINGS = 300  # keep list_headings inside the model's context on huge books


@dataclass
class Document:
    """An opened PDF. Page text is NOT cached: it is extracted from the PDF only when a tool is called.
    Upload-time processing only builds the outline that list_headings returns."""
    doc_id: str
    title: str
    filename: str
    pdf: pymupdf.Document
    headings: list[dict]
    heading_source: str
    meta: dict = field(default_factory=dict)

    def page_text(self, n: int) -> str:  # n is 1-based
        return clean_text(self.pdf[n - 1].get_text()).strip()


class DocStore:
    def __init__(self) -> None:
        self.docs: dict[str, Document] = {}

    def add_pdf(self, path: str | Path, original_name: str | None = None) -> Document:
        path = Path(path)
        pdf = pymupdf.open(str(path))
        headings, source = _extract_headings(pdf)
        md = pdf.metadata or {}
        name = original_name or path.name
        title = (md.get("title") or "").strip() or Path(name).stem
        doc_id = f"doc{len(self.docs) + 1}"
        has_text = any(pdf[i].get_text().strip() for i in range(min(len(pdf), 5)))
        doc = Document(doc_id=doc_id, title=title[:120], filename=name, pdf=pdf, headings=headings, heading_source=source,
                       meta={"num_pages": len(pdf), "author": ((md.get("author") or "").strip() or None), "has_text_layer": has_text})
        self.docs[doc_id] = doc
        return doc


# ----------------------------------------------------------------------------- the four tools
class DocTools:
    """Exactly the four permitted tools. Nothing else reads document content."""

    def __init__(self, store: DocStore) -> None:
        self.store = store

    def _doc(self, doc_id: str) -> Document:
        if doc_id not in self.store.docs:
            raise ValueError(f"unknown doc_id '{doc_id}'. Valid ids: {list(self.store.docs)}")
        return self.store.docs[doc_id]

    def list_documents(self) -> list[dict]:
        return [{"doc_id": d.doc_id, "title": d.title, "filename": d.filename, **d.meta} for d in self.store.docs.values()]

    def list_headings(self, doc_id: str) -> list[dict]:
        d = self._doc(doc_id)
        out = [{"level": h["level"], "title": h["title"][:120], "page": h["page"]} for h in d.headings[:MAX_HEADINGS]]
        if len(d.headings) > MAX_HEADINGS:
            out.append({"level": 0, "title": f"[outline truncated: {len(d.headings) - MAX_HEADINGS} more headings; use search_keyword]", "page": 0})
        return out

    def get_page(self, doc_id: str, page_number: int) -> str:
        d = self._doc(doc_id)
        if isinstance(page_number, float) and not page_number.is_integer():
            raise ValueError(f"page_number must be an integer, got {page_number}")
        n = int(page_number)
        if not 1 <= n <= d.meta["num_pages"]:
            raise ValueError(f"page_number {n} out of range 1..{d.meta['num_pages']}")
        return d.page_text(n)

    def search_keyword(self, doc_id: str, keyword: str) -> list[int]:
        d = self._doc(doc_id)
        kw = norm_for_search(str(keyword))
        if not kw:
            raise ValueError("empty keyword")
        pages = [norm_for_search(d.page_text(i)) for i in range(1, d.meta["num_pages"] + 1)]  # scanned per call, not cached
        hits = [i + 1 for i, p in enumerate(pages) if kw in p]
        if not hits and len(kw) >= 5:  # extraction drops spaces / hyphenation varies; retry ignoring both
            k2 = re.sub(r"[\s-]+", "", kw)
            hits = [i + 1 for i, p in enumerate(pages) if k2 in re.sub(r"[\s-]+", "", p)]
        if not hits and " " in kw:  # multi-word keyword with no exact phrase: pages containing every word (plain lexical AND, not semantic)
            words = [w for w in re.findall(r"[\w*+#.-]+", kw) if len(w) > 1]
            if len(words) > 1:
                hits = [i + 1 for i, p in enumerate(pages) if all(w in p for w in words)]
                if not hits and len(words) > 2:  # still nothing: pages containing the most of the words (>= 2), lexical only
                    counts = [sum(w in p for w in words) for p in pages]
                    best = max(counts)
                    if best >= 2:
                        hits = [i + 1 for i, c in enumerate(counts) if c == best]
        return hits


# ----------------------------------------------------------------------------- budget + log wrapper
class BudgetedToolbox:
    """Logs every tool call and refuses to execute once the per-question budget is spent."""

    NAMES = ("list_documents", "list_headings", "get_page", "search_keyword")

    def __init__(self, tools: DocTools, budget: int = TOOL_BUDGET, log_path: str | Path | None = None, question: str = "") -> None:
        self.tools = tools
        self.budget = budget
        self.used = 0
        self.question = question
        self.trace: list[dict] = []
        self.pages_read: dict[tuple[str, int], str] = {}  # for answer-grounding checks only
        self.log_path = Path(log_path) if log_path else None

    @property
    def remaining(self) -> int:
        return self.budget - self.used

    def call(self, name: str, args: dict) -> dict:
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "question": self.question, "tool": name, "args": args}
        if name not in self.NAMES:
            entry.update(status="rejected", counted=False, result=f"unknown tool '{name}'")
        elif self.used >= self.budget:
            entry.update(status="rejected", counted=False, result=f"BUDGET EXHAUSTED: {self.budget} tool calls already used. Not executed. Give your final answer now.")
        else:
            self.used += 1  # failed calls count too
            entry["call_no"] = self.used
            entry["counted"] = True
            try:
                result = getattr(self.tools, name)(**args)
                entry.update(status="ok", result=result)
                if name == "get_page":
                    self.pages_read[(args["doc_id"], int(args["page_number"]))] = result
            except Exception as e:  # noqa: BLE001 - surfaced to the agent so it can adapt
                entry.update(status="error", result=f"{type(e).__name__}: {e}")
        self._write(entry)
        self.trace.append(entry)
        return entry

    def note(self, kind: str, data: dict) -> None:
        """Log non-tool events (dropped calls, the final answer) so the trace hides nothing."""
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "question": self.question, "tool": kind, "args": {}, "status": "info",
                 "counted": False, "result": data}
        self._write(entry)
        self.trace.append(entry)

    def _write(self, entry: dict) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        slim = dict(entry)  # full, unabridged results: the trace must hide nothing
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(slim, ensure_ascii=False, default=str) + "\n")
