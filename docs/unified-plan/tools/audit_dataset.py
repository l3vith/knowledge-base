#!/usr/bin/env python3
"""Read-only source audit. Writes only derived files beneath --out."""
import argparse, collections, concurrent.futures, hashlib, json, re, statistics, subprocess
from pathlib import Path

def quantiles(xs):
    s=sorted(xs)
    return {"min":s[0],"median":statistics.median(s),"p90":s[min(len(s)-1,int((len(s)-1)*.9))],"max":s[-1],"total":sum(s)} if s else {}

def inspect_pdf(p):
    info=subprocess.run(['pdfinfo',str(p)],capture_output=True,text=True,check=True).stdout
    match=re.search(r'^Pages:\s+(\d+)',info,re.M)
    raw=subprocess.run(['pdftotext','-layout',str(p),'-'],capture_output=True,check=True)
    text=raw.stdout.decode('utf-8',errors='replace')
    pages=text.split('\f')
    if pages and not pages[-1].strip():pages.pop()
    return {'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pages':int(match.group(1)),'extracted_pages':len(pages),'text_chars':sum(len(x.strip()) for x in pages),'low_text_pages':[i+1 for i,t in enumerate(pages) if len(re.sub(r'\s','',t))<80],'first_page_excerpt':pages[0][:1000] if pages else ''},pages

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='Train');ap.add_argument('--out',default='knowledge-base-plan/audit');a=ap.parse_args()
    root=Path(a.root).resolve();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    bpath=root/'Benchmarks/benchmark_100.jsonl';rows=[json.loads(x) for x in bpath.read_text().splitlines() if x.strip()]
    paths=sorted((root/'Documents').glob('*.pdf'));pdfs=[];texts={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for p,(stat,pages) in zip(paths,pool.map(inspect_pdf,paths)):
            pdfs.append(stat);texts[p.name]=pages
    refs=collections.Counter();questions=[];all_lens=[];page_outliers=[];missing=[]
    for r in rows:
        chunks=r['benchmark_chunks_w_metadata'];flat=[c for cs in chunks.values() for c in cs]
        docs=list(chunks);refs.update(docs);pages_by={};mismatch=[]
        for d,cs in chunks.items():
            pages_by[d]=sorted({p for c in cs for p in c.get('metadata',{}).get('page_numbers',[])})
            if d not in texts:missing.append({'question':r['id'],'document':d})
            for c in cs:
                all_lens.append(len(c.get('content','').split()))
                if c.get('metadata',{}).get('document')!=d:mismatch.append(c.get('metadata',{}).get('document'))
                for p in c.get('metadata',{}).get('page_numbers',[]):
                    if d in texts and (not isinstance(p,int) or p<1 or p>len(texts[d])):page_outliers.append({'question':r['id'],'document':d,'page':p})
        questions.append({'id':r['id'],'question':r['question'],'answer_words':len(r['benchmark_answer'].split()),'documents':docs,'document_count':len(docs),'gold_chunk_count':len(flat),'gold_pages':pages_by,'distinct_gold_page_count':sum(len(x) for x in pages_by.values()),'metadata_document_mismatches':mismatch})
    report={'root':str(root),'benchmark_sha256':hashlib.sha256(bpath.read_bytes()).hexdigest(),'evaluation_sha256':hashlib.sha256((root/'Evaluation/Evaluation.ipynb').read_bytes()).hexdigest(),'pdf_count':len(pdfs),'total_pages':sum(p['pages'] for p in pdfs),'total_bytes':sum(p['bytes'] for p in pdfs),'question_count':len(rows),'question_id_prefixes':dict(collections.Counter(re.sub(r'\d.*$','',r['id']) for r in rows)),'gold_chunks_per_question':quantiles([q['gold_chunk_count'] for q in questions]),'gold_pages_per_question':quantiles([q['distinct_gold_page_count'] for q in questions]),'gold_chunk_words':quantiles(all_lens),'answer_words':quantiles([q['answer_words'] for q in questions]),'documents_per_question':dict(collections.Counter(q['document_count'] for q in questions)),'document_question_frequency':dict(refs.most_common()),'missing_document_references':missing,'out_of_range_gold_pages':page_outliers,'low_text_page_count':sum(len(p['low_text_pages']) for p in pdfs),'unreferenced_documents':sorted(set(texts)-set(refs))}
    (out/'dataset-audit.json').write_text(json.dumps(report,indent=2));(out/'document-manifest.json').write_text(json.dumps(pdfs,indent=2));(out/'question-inventory.json').write_text(json.dumps(questions,indent=2))
    # Selected page text for reproducible citation-offset inspection; no benchmark answers copied.
    probes={}
    for d,pages in texts.items():
        probes[d]={'first_pages':[{'pdf_page':i+1,'text':t[:2200]} for i,t in enumerate(pages[:3])]}
    (out/'page-probes.json').write_text(json.dumps(probes,indent=2))
    print(json.dumps(report,indent=2))
    print('\nQuestion inventory:')
    for q in questions:print(q['id'],q['gold_chunk_count'],q['distinct_gold_page_count'],q['document_count'],q['question'])
if __name__=='__main__':main()
