"""Query-owned operations and source bindings. Labels are hypotheses, never evidence.

No corpus-specific answers, external data, or persistent second knowledge base.
"""
import re
from .utils import get

OPERATIONS = {'lookup', 'compare', 'reconcile', 'assess', 'inspect', 'absence'}
SCOPE_FIELDS = ('entity', 'metric', 'period', 'unit', 'basis')
STATUSES = {'supported', 'corroborated', 'contradicted', 'incomparable', 'unresolved',
            'not_established_in_inspected_evidence'}


def compile_tasks(query, aspects, proposed):
    """An operation must point back to a literal query phrase and a real obligation."""
    aids = {a.aspect_id for a in aspects}
    tasks = []
    for row in proposed if isinstance(proposed, list) else []:
        if not isinstance(row, dict):
            continue
        anchor = row.get('query_anchor')
        if not isinstance(anchor, str) or not anchor.strip() or anchor.casefold() not in query.casefold():
            continue
        op = row.get('operation')
        raw_ids=row.get('obligation_ids', [])
        ids = [a for a in raw_ids if isinstance(a, str) and a in aids] if isinstance(raw_ids,list) else []
        roles = row.get('source_roles', [])
        roles = [r[:160] for r in roles if isinstance(r, str) and r.strip()] if isinstance(roles, list) else []
        if op not in OPERATIONS or not ids or not roles:
            continue
        tasks.append({'id': f'T{len(tasks)+1}', 'text': str(row.get('description', anchor))[:600],
                      'query_anchor': anchor, 'operation': op, 'obligation_ids': ids,
                      'source_roles': roles[:4], 'required_fields': list(SCOPE_FIELDS) if op in ('compare', 'reconcile') else []})
        if len(tasks) >= 12:
            break
    if not tasks:
        op = 'compare' if re.search(r'\b(compare|consisten\w*|reconcil\w*)\b', query, re.I) else (
            'assess' if re.search(r'\b(validat\w*|robust\w*|generaliz\w*|generalis\w*|critique)\b', query, re.I) else 'lookup')
        for a in aspects[:12]:
            tasks.append({'id': f'T{len(tasks)+1}', 'text': a.text, 'query_anchor': query,
                          'operation': op, 'obligation_ids': [a.aspect_id], 'source_roles': [a.text],
                          'required_fields': list(SCOPE_FIELDS) if op == 'compare' else []})
    return tasks


def bind_results(tasks, raw, numbered, spans):
    """Resolve IDs to source offsets; comparisons fail closed on unknown/mismatched scopes.

    A model's scope value must occur in the cited span or its original section. Cross-year
    comparisons explicitly mark period as a varying field; all other required fields agree.
    Final semantic verification still checks the relationship, not just these labels.
    """
    by_task = {}
    duplicates = set()
    for row in raw if isinstance(raw, list) else []:
        if isinstance(row, dict) and isinstance(row.get('task_id'), str):
            if row['task_id'] in by_task:
                duplicates.add(row['task_id'])
            by_task[row['task_id']] = row
    out = []
    for task in tasks:
        row = by_task.get(task['id'], {})
        bindings = []
        for source in row.get('inputs', []) if isinstance(row.get('inputs'), list) else []:
            if not isinstance(source, dict):
                continue
            eid, sid = source.get('evidence_id'), source.get('span_id')
            if not isinstance(eid, str) or eid not in numbered or not isinstance(sid, str) or sid not in spans[eid]:
                continue
            ev = numbered[eid]; el = ev.element; text = spans[eid][sid]
            original = text + ' ' + str(get(el, 'section', ''))
            scope = source.get('scope') if isinstance(source.get('scope'), dict) else {}
            scope = {k: v if isinstance(v, str) and v.strip() and v.casefold() in original.casefold() else None
                     for k in SCOPE_FIELDS for v in [scope.get(k)]}
            full = get(el, 'text', '')
            offset = full.find(text)
            bindings.append({'evidence_id': eid, 'span_id': sid, 'doc_id': get(el, 'doc_id'),
                             'page': get(el, 'page_no'), 'section': get(el, 'section', ''),
                             'char_start': get(el, 'char_start', 0) + offset if offset >= 0 else None,
                             'char_end': get(el, 'char_start', 0) + offset + len(text) if offset >= 0 else None,
                             'quote': text, 'role': source.get('role') if source.get('role') in
                             ('assertion', 'result', 'policy', 'qualification', 'counterevidence', 'explanation') else 'assertion',
                             'scope': scope})
        status = row.get('status') if row.get('status') in STATUSES else 'unresolved'
        missing = []
        scope_status = 'not_required'
        if task['operation'] in ('compare', 'reconcile'):
            varying = row.get('varying_field')
            # Variation must be requested in the literal query anchor, not invented by a writer.
            allowed = {'period': r'year|period|over time', 'entity': r'entit|compan|bank|between',
                       'metric': r'metric|ratio|reconcil'}
            varying = varying if varying in allowed and re.search(allowed[varying], task['query_anchor'], re.I) else None
            missing = [k for k in task['required_fields'] if len(bindings) < 2 or any(not b['scope'][k] for b in bindings)]
            mismatched = [k for k in task['required_fields'] if k != varying and
                          len({b['scope'][k].casefold() for b in bindings if b['scope'][k]}) > 1]
            scope_status = 'unresolved' if missing else 'incomparable' if mismatched else 'comparable'
            if scope_status != 'comparable':
                status = 'incomparable' if mismatched else 'unresolved'
        if not bindings or task['id'] in duplicates:
            status = 'unresolved'
        out.append({**task, 'inputs': bindings, 'scope_status': scope_status, 'status': status,
                    'missing_inputs': missing, 'result': None, 'completion': 'unchecked'})
    return out


TASK_SYSTEM = """
TASK WORKSHEET CONTRACT (takes precedence over role/findings inventory instructions):
Perform the requested operations, not a descriptive summary of the paper. All supplied source spans are eligible;
the facts list is advisory and neither exhaustive nor mandatory. Do not restore every fact or repeat background.
Use one coherent answer, organized around the literal query tasks, with cited findings and labelled assessments.
Link each reported result to its method/data split, conditions and qualifications. Explain implications only from
those cited premises. Retain definitions/otherwise branches when needed to evaluate the target, timing or scope.
For comparison/reconciliation, inspect each requested section independently, bring the related sources together,
check entity/metric/period/unit/basis before concluding agreement or discrepancy. Audit assurances alone do not
complete a reconciliation. Unknown or mismatched scopes mean unresolved/incomparable, never a contradiction.
Do not infer images from captions. Distinguish no direct requested answer from no useful explanatory evidence.
For an unsupported-premise lookup, cite relevant explanations/qualifications and distinguish illustrative cases
from aggregate claims. Never manufacture a requested numeric value or infer whole-document absence.
Return the usual sections/statements plus task_results:[{task_id,status:supported|corroborated|contradicted|
incomparable|unresolved|not_established_in_inspected_evidence,varying_field:null|string,
inputs:[{evidence_id,span_id,role:assertion|result|policy|qualification|counterevidence|explanation,
scope:{entity:null|string,metric:null|string,period:null|string,unit:null|string,basis:null|string}}]}].
Scope values are exact substrings of their source span or section; leave unknown fields null. Task labels and
scope strings are hypotheses checked by code and a separate final verifier. No free-text numeric worksheet result.
Each statement must answer a task, preserve source qualifications and carry valid obligation_ids. Max statements
is a ceiling, not a target. Write enough distinct supported points to complete the tasks, without filler.
"""
