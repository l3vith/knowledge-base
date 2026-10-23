"""Metadata-only generation upgrade: preserve source/vectors, never invoke an LLM."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sqlite3
import time
from contextlib import closing

from kb.ingest.navigation import build_navigation, VERSION
from kb.ingest.parse import read_pdf_info, page_source_metadata
from kb.models import ParsedDoc, PageText
from kb.registry import Registry
from kb.store import Store, DB_NAME


def enrich_collection(collection,settings,source_dir=None):
    registry=Registry(settings);started=time.monotonic()
    with registry.indexing_lock(collection):
        old_generation,old_path=registry.active_dir(collection)
        generation,staging=registry.new_staging(collection)
        source=Store.open(old_path);target=None
        try:
            # SQLite backup includes committed WAL state without mutating the old generation.
            # closing(): sqlite3's own context manager commits but never closes, and an open file blocks the rename on Windows.
            with closing(sqlite3.connect(staging/DB_NAME)) as database:
                source._conn.backup(database)
            for path in old_path.iterdir():
                if path.is_file() and not path.name.startswith(DB_NAME):
                    shutil.copy2(path,staging/path.name)
            target=Store.open(staging);reports={}
            for card in source.docs():
                pages=[PageText(int(n),text,bool(ocr),[],card.navigation.get('pages',{}).get(str(n),{})) for n,text,ocr in source._q(
                    'SELECT page_no,markdown,is_ocr FROM pages WHERE doc_id=? ORDER BY page_no',(card.doc_id,))]
                outline=[(e['level'],e['title'],e['start_page']) for e in card.navigation.get('sections',[])
                         if e.get('origin')=='pdf_outline']
                properties=card.navigation.get('pdf_properties',{})
                source_path=None
                if source_dir is not None:
                    root=Path(source_dir).resolve();candidate=(root/card.file_name).resolve()
                    try:candidate.relative_to(root)
                    except ValueError:raise ValueError('Document source path escapes the supplied source directory')
                    if candidate.is_file():source_path=candidate
                if source_path is not None:
                    import pymupdf
                    doc_id,count,outline,properties=read_pdf_info(source_path)
                    if doc_id!=card.doc_id or count!=card.page_count:
                        raise ValueError('Source PDF identity differs from indexed document; reindex intentionally')
                    by_page={}
                    for level,title,page in outline:by_page.setdefault(page,[]).append(title)
                    with pymupdf.open(source_path) as pdf:
                        for page in pages:
                            page.metadata=page_source_metadata(pdf[page.page_no-1],count,page.markdown)
                            page.toc_titles=by_page.get(page.page_no,[])
                sections={pc.page_no:pc.section for pc in source.page_cards(card.doc_id)}
                elements=source.elements_for_pages(card.doc_id,[p.page_no for p in pages],include_boilerplate=True)
                doc=ParsedDoc(card.doc_id,card.file_name,card.page_count,pages,outline,properties)
                navigation=build_navigation(doc,elements,sections)
                updated=replace(card,navigation=navigation)
                with target._lock,target._conn:
                    target._conn.execute('UPDATE docs SET card_json=? WHERE doc_id=?',
                                         (json.dumps(asdict(updated)),card.doc_id))
                    target._conn.execute('DELETE FROM pages_fts WHERE doc_id=?',(card.doc_id,))
                    cards={pc.page_no:pc for pc in source.page_cards(card.doc_id)}
                    for page in pages:
                        pc=cards.get(page.page_no)
                        extra='\n'.join([pc.section,pc.summary,' '.join(pc.topics),' '.join(pc.entities),' '.join(pc.figures)]) if pc else ''
                        target._conn.execute('INSERT INTO pages_fts(doc_id,page_no,body) VALUES (?,?,?)',
                                             (card.doc_id,page.page_no,page.markdown+'\n'+extra))
                reports[card.doc_id]={**navigation['stats'],'pdf_metadata_loaded':source_path is not None}
            target.close();target=None;source.close();source=None
            report={'collection_name':collection,'generation_id':generation,'source_generation_id':old_generation,
                    'navigation_version':VERSION,'documents':reports,'llm_calls':0,'embedding_calls':0,
                    'cost_usd':0.0,'wall_seconds':round(time.monotonic()-started,3)}
            manifest_path=staging/'manifest.json'
            manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
            manifest.update(generation_id=generation,metadata_enrichment=report)
            manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
            registry.promote(collection,generation,staging)
            return report
        except BaseException:
            if target is not None:target.close()
            if source is not None:source.close()
            registry.discard(staging)
            raise
