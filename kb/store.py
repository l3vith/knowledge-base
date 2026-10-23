"""One generation's SQLite store: docs, pages, elements, FTS5 indexes and dense vectors (numpy files)."""
import json
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np

from kb.errors import CollectionNotFound
from kb.models import BLANK_PAGE_SUMMARY, DocCard, Element, PageCard, PageText
from kb.textutil import tokens

DB_NAME = "kb.sqlite"
_VEC_FILES = {"page": ("page_vecs.npy", "page_vec_keys.json"), "element": ("el_vecs.npy", "el_vec_keys.json")}

SCHEMA = """
CREATE TABLE docs(doc_id TEXT PRIMARY KEY, file_name TEXT, page_count INT, card_json TEXT);
CREATE TABLE pages(doc_id TEXT, page_no INT, markdown TEXT, is_ocr INT, card_json TEXT, PRIMARY KEY(doc_id, page_no));
CREATE TABLE elements(element_id TEXT PRIMARY KEY, doc_id TEXT, page_no INT, idx INT, kind TEXT, section TEXT, text TEXT, flags TEXT);
CREATE INDEX el_page ON elements(doc_id, page_no, idx);
CREATE VIRTUAL TABLE pages_fts USING fts5(doc_id UNINDEXED, page_no UNINDEXED, body, tokenize='unicode61');
CREATE VIRTUAL TABLE elements_fts USING fts5(element_id UNINDEXED, doc_id UNINDEXED, body, tokenize='unicode61');
"""

_EL_COLS = "element_id, doc_id, page_no, idx, kind, section, text, flags"
_IN = "(SELECT value FROM json_each(?))"  # one bound JSON list instead of N placeholders (no variable limit)


def fts_query(terms: list[str]) -> str:
    """Quoted OR-query over tokens(); every FTS5 operator and punctuation is neutralised."""
    return " OR ".join(f'"{t}"' for t in tokens(" ".join(terms)))


def _element(row) -> Element:
    return Element(row[0], row[1], row[2], row[3], row[4], row[5], row[6], json.loads(row[7] or "[]"))


class _Vectors:
    """Vectors plus a doc_id -> row-indices map, so scoped search touches only eligible rows."""

    def __init__(self, vecs: np.ndarray, keys: list, doc_of, exclude: set = frozenset()):
        self.vecs = np.asarray(vecs, dtype=np.float32)
        self.keys = keys
        rows: dict[str, list[int]] = {}
        for i, k in enumerate(keys):
            if not (isinstance(k, str) and k in exclude):
                rows.setdefault(doc_of(k), []).append(i)
        self.rows = {d: np.asarray(r, dtype=np.int64) for d, r in rows.items()}

    def search(self, query_vecs: np.ndarray, doc_ids: list[str] | None, limit: int) -> list[tuple]:
        groups = self.rows.values() if doc_ids is None else [self.rows[d] for d in dict.fromkeys(doc_ids) if d in self.rows]
        groups = [g for g in groups if len(g)]
        if not groups or limit <= 0:
            return []
        rows = np.concatenate(groups)
        q = np.atleast_2d(np.asarray(query_vecs, dtype=np.float32))
        scores = (self.vecs[rows] @ q.T).max(axis=1)
        top = np.argsort(-scores, kind="stable")[:limit]
        return [(self.keys[rows[i]], float(scores[i])) for i in top]


class Store:
    def __init__(self, gen_dir: Path, conn: sqlite3.Connection):
        self.gen_dir = Path(gen_dir)
        self._conn = conn
        self._lock = threading.Lock()
        self._vecs: dict[str, _Vectors | None] = {"page": None, "element": None}

    @classmethod
    def create(cls, gen_dir: Path) -> "Store":
        gen_dir = Path(gen_dir)
        gen_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(gen_dir / DB_NAME), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.commit()
        return cls(gen_dir, conn)

    @classmethod
    def open(cls, gen_dir: Path) -> "Store":
        gen_dir = Path(gen_dir)
        if not (gen_dir / DB_NAME).is_file():
            raise CollectionNotFound(gen_dir.parent.parent.name or str(gen_dir))
        store = cls(gen_dir, sqlite3.connect(str(gen_dir / DB_NAME), check_same_thread=False))
        # Eager load: once in memory, vectors survive a later cleanup of this generation's files.
        for kind in _VEC_FILES:
            store._load_vectors(kind)
        return store

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _q(self, sql: str, params=()) -> list:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---------- writing ----------
    def add_document(self, card: DocCard, pages: list[PageText], page_cards: list[PageCard], elements: list[Element]) -> None:
        cards = {pc.page_no: pc for pc in page_cards}
        page_rows, page_fts = [], []
        for p in pages:
            pc = cards.get(p.page_no)
            page_rows.append((card.doc_id, p.page_no, p.markdown, int(p.is_ocr), json.dumps(asdict(pc)) if pc else None))
            extra = "\n".join([pc.summary, " ".join(pc.topics), " ".join(pc.entities), " ".join(pc.figures)]) if pc else ""
            page_fts.append((card.doc_id, p.page_no, f"{p.markdown}\n{extra}"))
        el_rows = [(e.element_id, e.doc_id, e.page_no, e.idx, e.kind, e.section, e.text, json.dumps(e.flags))
                   for e in elements]
        el_fts = [(e.element_id, e.doc_id, f"{e.section}\n{e.text}") for e in elements if "boilerplate" not in e.flags]
        with self._lock, self._conn:
            c = self._conn
            c.execute("INSERT INTO docs VALUES (?,?,?,?)",
                      (card.doc_id, card.file_name, card.page_count, json.dumps(asdict(card))))
            c.executemany("INSERT INTO pages VALUES (?,?,?,?,?)", page_rows)
            c.executemany("INSERT INTO pages_fts(doc_id, page_no, body) VALUES (?,?,?)", page_fts)
            c.executemany(f"INSERT INTO elements({_EL_COLS}) VALUES (?,?,?,?,?,?,?,?)", el_rows)
            c.executemany("INSERT INTO elements_fts(element_id, doc_id, body) VALUES (?,?,?)", el_fts)

    def set_vectors(self, kind: str, keys: list, vecs: np.ndarray) -> None:
        if kind not in _VEC_FILES:
            raise ValueError(f"unknown vector kind {kind!r}")
        vecs = np.asarray(vecs, dtype=np.float32)
        if len(keys) != len(vecs):
            raise ValueError("keys and vecs differ in length")
        vec_file, key_file = _VEC_FILES[kind]
        np.save(self.gen_dir / vec_file, vecs)
        (self.gen_dir / key_file).write_text(json.dumps([list(k) if kind == "page" else k for k in keys]), encoding="utf-8")
        self._load_vectors(kind)

    def _load_vectors(self, kind: str) -> None:
        vec_file, key_file = _VEC_FILES[kind]
        if not (self.gen_dir / vec_file).is_file():
            return
        vecs = np.load(self.gen_dir / vec_file)
        keys = json.loads((self.gen_dir / key_file).read_text(encoding="utf-8"))
        if kind == "page":
            self._vecs[kind] = _Vectors(vecs, [(d, int(p)) for d, p in keys], lambda k: k[0])
        else:
            boiler = {r[0] for r in self._q("SELECT element_id FROM elements WHERE flags LIKE '%\"boilerplate\"%'")}
            self._vecs[kind] = _Vectors(vecs, keys, lambda k: k.split(":", 1)[0], exclude=boiler)

    # ---------- StoreProtocol ----------
    def docs(self) -> list[DocCard]:
        return [DocCard(**json.loads(r[0])) for r in self._q("SELECT card_json FROM docs ORDER BY rowid")]

    def doc(self, doc_id: str) -> DocCard:
        rows = self._q("SELECT card_json FROM docs WHERE doc_id = ?", (doc_id,))
        if not rows:
            raise KeyError(doc_id)
        return DocCard(**json.loads(rows[0][0]))

    def page_cards(self, doc_id: str, page_nos: list[int] | None = None) -> list[PageCard]:
        sql = "SELECT card_json FROM pages WHERE doc_id = ? AND card_json IS NOT NULL"
        params: tuple = (doc_id,)
        if page_nos is not None:
            sql += f" AND page_no IN {_IN}"
            params += (json.dumps([int(p) for p in page_nos]),)
        return [PageCard(**json.loads(r[0])) for r in self._q(sql + " ORDER BY page_no", params)]

    def nonblank_pages(self, doc_id: str) -> list[int]:
        return [pc.page_no for pc in self.page_cards(doc_id) if pc.summary != BLANK_PAGE_SUMMARY]

    def elements_for_pages(self, doc_id: str, page_nos: list[int], include_boilerplate: bool = False) -> list[Element]:
        rows = self._q(f"SELECT {_EL_COLS} FROM elements WHERE doc_id = ? AND page_no IN {_IN} ORDER BY page_no, idx",
                       (doc_id, json.dumps([int(p) for p in page_nos])))
        els = [_element(r) for r in rows]
        return els if include_boilerplate else [e for e in els if "boilerplate" not in e.flags]

    def elements_by_ids(self, element_ids: list[str]) -> list[Element]:
        rows = self._q(f"SELECT {_EL_COLS} FROM elements WHERE element_id IN {_IN}", (json.dumps(list(element_ids)),))
        by_id = {r[0]: _element(r) for r in rows}
        return [by_id[i] for i in element_ids if i in by_id]

    def _fts(self, table: str, cols: str, terms: list[str], doc_ids: list[str] | None, limit: int) -> list:
        match = fts_query(terms)
        if not match or limit <= 0 or doc_ids == []:
            return []
        sql = f"SELECT {cols}, -bm25({table}) FROM {table} WHERE {table} MATCH ?"
        params: tuple = (match,)
        if doc_ids is not None:
            sql += f" AND doc_id IN {_IN}"
            params += (json.dumps(list(doc_ids)),)
        return self._q(sql + f" ORDER BY bm25({table}) LIMIT ?", params + (int(limit),))

    def search_pages(self, terms: list[str], doc_ids: list[str] | None, limit: int) -> list[tuple[str, int, float]]:
        return [(d, int(p), float(s)) for d, p, s in self._fts("pages_fts", "doc_id, page_no", terms, doc_ids, limit)]

    def search_elements(self, terms: list[str], doc_ids: list[str] | None, limit: int) -> list[tuple[str, float]]:
        return [(e, float(s)) for e, s in self._fts("elements_fts", "element_id", terms, doc_ids, limit)]

    def dense_pages(self, query_vecs: np.ndarray, doc_ids: list[str] | None, limit: int) -> list[tuple[str, int, float]]:
        v = self._vecs["page"]
        return [(k[0], k[1], s) for k, s in v.search(query_vecs, doc_ids, limit)] if v else []

    def dense_elements(self, query_vecs: np.ndarray, doc_ids: list[str] | None, limit: int) -> list[tuple[str, float]]:
        v = self._vecs["element"]
        return v.search(query_vecs, doc_ids, limit) if v else []
