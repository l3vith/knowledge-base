"""Source-derived document navigation. No LLM, gold data, network or factual assertions."""
from collections import Counter, defaultdict
import re

VERSION=1
_WORD=re.compile(r"\w+",re.UNICODE)
_STOP=set('the a an of and or in on to for with by at from is are as this that document page chapter section'.split())
_HEADING=re.compile(r"^\s*(#{1,6})\s+(.+)")
_CAPTION=re.compile(r"^(Table|Figure|Fig\.|Chart|Exhibit|Appendix)\s+([A-Za-z]?\d+(?:\.\d+)*|[A-Z])\b[.:\s–-]*(.*)",re.I)
_REFERENCE=re.compile(r"\b(Table|Figure|Fig\.?|Chart|Exhibit|Section|Appendix)\s+([A-Za-z]?\d+(?:\.\d+)*|[A-Z])\b",re.I)
_TOC=re.compile(r"^\s*(.*?)\s*(?:\.{2,}|(?:\.\s+){2,}|\s{2,})\s*([ivxlcdm]+|\d+)\s*$",re.I)
_INDEX=re.compile(r"^\s*([^|\d].{2,100}?),?\s+(\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-–]\s*\d+)?)*)\s*$")


def words(text):
    return {w for w in _WORD.findall(str(text).casefold()) if len(w)>1 and w not in _STOP}


def locator_key(kind,number):
    kind=kind.lower().rstrip('.')
    return ('figure' if kind=='fig' else kind)+':'+number.lower()


def _number(label):
    if label.isdigit():return int(label)
    label=label.upper()
    if not label or not re.fullmatch(r'M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})',label):return None
    values={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    return sum(-values[c] if i+1<len(label) and values[c]<values[label[i+1]] else values[c] for i,c in enumerate(label))


def _level(title):
    match=re.match(r'^(\d+(?:\.\d+)*)\b',title)
    return min(6,match.group(1).count('.')+1) if match else 1


def _matches(title,text):
    needle=words(re.sub(r'^\d+(?:\.\d+)*[.\s]*','',title))
    return bool(needle) and len(needle & words(text))/len(needle)>=0.75


def _finish_ranges(entries,count):
    entries.sort(key=lambda e:(e['start_page'],e['level']))
    for i,e in enumerate(entries):
        end=count
        for nxt in entries[i+1:]:
            if nxt['level']<=e['level']:
                end=max(e['start_page'],nxt['start_page']-1);break
        e['end_page']=min(count,end)
    return entries


def build_navigation(doc,elements,sections):
    """Build explicit ranges, validated printed references, locators and page features."""
    bypage={p.page_no:p for p in doc.pages}
    els=defaultdict(list)
    for e in elements:els[e.page_no].append(e)
    pages={};ranges=[];seen=set();locators=defaultdict(list);printed=[];toc_pages=set()
    labelmap=defaultdict(list)
    def add_range(title,page,level,origin,anchor_page=None):
        if not 1<=page<=doc.page_count or not title.strip():return
        key=(page,' '.join(sorted(words(title))))
        if key in seen:return
        seen.add(key)
        ranges.append({'title':title[:240],'start_page':page,'level':level,'origin':origin,
                       'confidence':(1.0 if _matches(title,bypage[page].markdown[:4000]) else .6) if origin=='pdf_outline' else .9,
                       'anchor_page':anchor_page or page})
    for level,title,page in doc.outline:add_range(title,page,max(1,level),'pdf_outline')
    outline_by_page=defaultdict(list)
    for level,title,page in doc.outline:outline_by_page[page].append((level,title))
    outline_stack=[]
    for p in doc.pages:
        for level,title in outline_by_page.get(p.page_no,[]):
            while outline_stack and outline_stack[-1][0]>=level:outline_stack.pop()
            outline_stack.append((level,title))
        base=outline_stack[-1][0] if outline_stack else 0
        raw=getattr(p,'metadata',{}) or {};label=str(raw.get('page_label') or '')
        if label:labelmap[label.casefold()].append(p.page_no)
        lines=p.markdown.splitlines();headings=[];captions=[]
        for ln in lines:
            hm=_HEADING.match(ln)
            if hm:
                title=hm.group(2).strip('*_ ');headings.append(title[:240])
                add_range(title,p.page_no,base+len(hm.group(1)),'source_heading')
            cm=_CAPTION.match(ln.lstrip('#*_ '))
            if cm:
                key=locator_key(cm.group(1),cm.group(2))
                locators[key].append(p.page_no)
                captions.append({'id':key,'title':cm.group(0)[:240]})
        # Section numbers are source-local navigation references, not legal identifiers.
        for title in headings:
            m=re.match(r'^(\d+(?:\.\d+)*)\s',title)
            if m:locators['section:'+m.group(1)].append(p.page_no)
        is_index=bool(re.search(r'^\s*#*\s*(?:subject\s+)?index\s*$',p.markdown[:1000],re.I|re.M))
        is_toc=bool(re.search(r'^\s*#*\s*(?:table of contents|contents|list of tables|list of figures)\b',p.markdown[:800],re.I|re.M))
        dotted=[_TOC.match(ln) for ln in lines if '|' not in ln]
        dotted=[m for m in dotted if m and words(m.group(1))]
        if is_toc or len(dotted)>=3 or is_index:
            toc_pages.add(p.page_no)
            for m in dotted:
                printed.append({'title':m.group(1).strip('*_ .'),'printed_label':m.group(2),
                                'anchor_page':p.page_no,'kind':'contents','level':_level(m.group(1))})
            if is_index:
                for ln in lines:
                    m=_INDEX.match(ln)
                    if not m:continue
                    for item in m.group(2).split(',')[:8]:
                        bounds=re.split(r'[-–]',item.strip())
                        printed.append({'title':m.group(1).strip(' ,.'),'printed_label':bounds[0].strip(),
                                        'printed_end_label':bounds[-1].strip(),'anchor_page':p.page_no,'kind':'index','level':1})
        table_headers=[]
        for e in els[p.page_no]:
            if e.kind=='table':
                rows=[ln.strip() for ln in e.text.splitlines() if ln.strip().startswith('|')]
                if rows:table_headers.append(rows[0][:400])
        tokens=_WORD.findall(p.markdown)
        pages[str(p.page_no)]={**raw,'physical_page':p.page_no,'section':sections.get(p.page_no,''),
            'headings':headings[:16],'captions':captions[:24],'table_headers':table_headers[:16],
            'table_count':sum(e.kind=='table' for e in els[p.page_no]),
            'years':sorted(set(re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)',p.markdown)))[:24],
            'units':sorted(set(re.findall(r'\b(?:USD|EUR|GBP|INR|million|billion|percent|basis points|milliseconds|seconds|minutes)\b|%',p.markdown,re.I)))[:24],
            'numeric_density':round(sum(any(c.isdigit() for c in t) for t in tokens)/max(1,len(tokens)),4),
            'ocr':bool(p.is_ocr),'navigation_page':False,
            'references':list(dict.fromkeys(locator_key(m.group(1),m.group(2)) for m in _REFERENCE.finditer(p.markdown)))[:40]}
    # Validate printed-to-physical mapping using unique source heading matches.
    # Never blindly assume printed page N is physical page N.
    targets={};offsets=[]
    heading_index=defaultdict(set)
    heading_words={n:[words(h) for h in pages[str(n)]['headings']] for n in bypage if n not in toc_pages}
    for n,headings in heading_words.items():
        for heading in headings:
            for token in heading:heading_index[token].add(n)
    for i,entry in enumerate(printed):
        if entry['kind']=='index':continue
        needle=words(re.sub(r'^\d+(?:\.\d+)*[.\s]*','',entry['title']))
        possible=set().union(*(heading_index[t] for t in needle)) if needle else set()
        matches=[n for n in possible if any(len(needle & h)/len(needle)>=.75 for h in heading_words[n])]
        linked=set(pages[str(entry['anchor_page'])].get('internal_link_pages',[]))
        if len(matches)!=1 and linked:
            checked=[n for n in linked if n in bypage and n not in toc_pages and
                     _matches(entry['title'],bypage[n].markdown[:4000])]
            if len(checked)==1:matches=checked
        if len(matches)==1:
            targets[i]=matches[0]
            number=_number(entry['printed_label'])
            if number is not None:offsets.append((matches[0]-number,entry['title']))
    votes=defaultdict(set)
    for offset,title in offsets:votes[offset].add(title.casefold())
    offset=max(votes,key=lambda o:len(votes[o])) if votes else None
    if offset is not None and len(votes[offset])<2:offset=None
    resolved=[];unresolved=[]
    for i,entry in enumerate(printed):
        target=targets.get(i);origin='printed_heading_match'
        if target is None:
            labels=labelmap.get(entry['printed_label'].casefold(),[])
            number=_number(entry['printed_label'])
            proposed=labels[0] if len(labels)==1 else number+offset if number is not None and offset is not None else None
            if proposed in bypage and proposed not in toc_pages and _matches(entry['title'],bypage[proposed].markdown[:4000]):
                target=proposed;origin='printed_label_or_offset_verified'
        if target is None:
            unresolved.append(entry);continue
        row={**entry,'start_page':target,'end_page':target,'origin':origin,'confidence':.9}
        if entry['kind']=='index':
            endlabel=entry.get('printed_end_label',entry['printed_label'])
            endpoints=labelmap.get(endlabel.casefold(),[]);num=_number(endlabel)
            end=endpoints[0] if len(endpoints)==1 else num+offset if num is not None and offset is not None else target
            if target<=end<=min(doc.page_count,target+100):row['end_page']=end
            resolved.append(row)
        else:
            add_range(entry['title'],target,entry['level'],origin,entry['anchor_page'])
            resolved.append(row)
    for n in toc_pages:pages[str(n)]['navigation_page']=True
    ranges=_finish_ranges(ranges,doc.page_count)
    return {'version':VERSION,'source':'source_navigation_only','pdf_properties':dict(doc.pdf_metadata),
            'sections':ranges,'printed_references':resolved,'unresolved_references':unresolved[:500],
            'printed_page_offset':offset,'label_map':dict(labelmap),'locators':{k:sorted(set(v)) for k,v in locators.items()},
            'pages':pages,'stats':{'sections':len(ranges),'resolved_printed_references':len(resolved),
                                 'unresolved_printed_references':len(unresolved),'locator_count':len(locators)}}
