"""Frozen C32/C26 development comparison, reused indexes and shared bounded billing.

Requires original local corpus and the three_unseen_20261024 indexes. Refuses to overwrite
an existing report. Uses CLI credentials only in memory; never writes secrets.
"""
from pathlib import Path
import sys,json,hashlib,subprocess,time,threading,zipfile,logging
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from kb.config import get_settings
from kb.llm import Usage
from kb.model_api import request_spec,response_parts
from kb.query.errors import BudgetExceeded,QueryError
from kb.query.settings import QuerySettings
from kb.query.pipeline import answer_query
from kb.query.observability import LangfuseSink
from kb.embed import get_embedder,get_reranker
from kb.registry import Registry
from kb.store import Store
from scripts.check_langfuse import load_local_env
from evaluation.official import load_notebook_namespace
from evaluation.audit import judge_consistency
OUT=ROOT/'artifacts/task_worksheet_20261024';CORPUS=ROOT.parent/'Train'
CAP=.10;GENERATION_CAP=.07;QUERY_CAP=.035
QWEN='qwen3.8-flash';GLM='glm-5.3-flash'
SPECS=[('fdic','FDIC FAQ.pdf',['C32']),('etf','10.1515_econ-2022-0073 (1).pdf',['C26'])]

def cli(*args):
 r=subprocess.run(['opencode',*args],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError('OpenCode metadata/auth command failed; private output suppressed')
 return json.loads(r.stdout)

class Ledger:
 def __init__(self,token,headers,prices):
  self.token=token;self.headers=headers;self.prices=prices;self.spent=self.computed=self.pending=0.
  self.generation_spent=self.generation_pending=0.;self.by_query={};self.pending_query={}
  self.records=[];self.lock=threading.RLock();self.local=threading.local()
 def save(self):
  (OUT/'cost-ledger.json').write_text(json.dumps({'hard_limit_usd':CAP,'generation_limit_usd':GENERATION_CAP,
   'query_limit_usd':QUERY_CAP,'upper_bound_spent_usd':self.spent,'computed_cost_usd':self.computed,
   'pending_reserved_usd':self.pending,'calls':self.records},indent=2)+'\n', encoding='utf-8')
 def call(self,model,system,user,name,max_tokens,phase,qid):
  self.local.record=None;self.local.response=None;p=self.prices[model];generation=phase!='judge'
  estimate=(len(system.encode())+len(user.encode())+2000)*max(p['input'],p['cache_write'])/1e6+max_tokens*p['output']/1e6
  with self.lock:
   if self.spent+self.pending+estimate>CAP:raise BudgetExceeded('Aggregate $0.10 benchmark admission cap')
   if generation and self.generation_spent+self.generation_pending+estimate>GENERATION_CAP:raise BudgetExceeded('Generation admission cap; judge reserve protected')
   if qid and generation and self.by_query.get(qid,0)+self.pending_query.get(qid,0)+estimate>QUERY_CAP:raise BudgetExceeded('Per-query $0.035 admission cap')
   self.pending+=estimate
   if generation:self.generation_pending+=estimate
   if qid and generation:self.pending_query[qid]=self.pending_query.get(qid,0)+estimate
  start=time.monotonic();known=False;charge=estimate
  rec={'model':model,'phase':phase,'question_id':qid,'stage':name,'status':'failed','output_limit':max_tokens,'input_byte_upper_estimate':len(system.encode())+len(user.encode())+2000}
  try:
   if model==QWEN:
    endpoint,headers,payload=request_spec('https://opencode.ai/inference/openai/v1/chat/completions',model,system,user,max_tokens)
   elif model==GLM and phase=='judge':
    endpoint='https://opencode.ai/inference/openai/v1/chat/completions';headers={}
    payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],
             'max_tokens':max_tokens,'temperature':0,'reasoning_effort':'low'}
   else:raise RuntimeError('Non-allowlisted model/phase')
   with httpx.Client(timeout=120) as client:
    response=client.post(endpoint,headers={**self.headers,**headers,'Authorization':'Bearer '+self.token},json=payload)
    if not response.is_success:
     rec['http_status']=response.status_code
     raise RuntimeError('Provider HTTP '+str(response.status_code)+'; no transport retry')
    body=response.json()
   content,finish,i,o=response_parts(body);usage=body.get('usage') or {}
   if not isinstance(i,int) or not isinstance(o,int):raise RuntimeError('Provider usage missing; conservative reservation charged')
   cache=usage.get('cache_read_input_tokens',(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)) or 0
   written=usage.get('cache_creation_input_tokens',0) or 0
   cost=((i-cache-written)*p['input']+cache*p['cache_read']+written*p['cache_write']+o*p['output'])/1e6
   charge=i*max(p['input'],p['cache_write'])/1e6+o*p['output']/1e6;known=True
   with self.lock:self.computed+=cost
   rec.update(input_tokens=i,output_tokens=o,cached_input_tokens=cache,cache_write_tokens=written,
    cost_usd=cost,cost_upper_bound_usd=charge,finish_reason=finish,
    thinking_block_count=sum(x.get('type')=='thinking' for x in body.get('content',[]) if isinstance(x,dict)),
    reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'))
   self.local.response={'content':content,'finish_reason':finish,'output_limit':max_tokens}
   if finish in ('length','max_tokens'):raise QueryError('MODEL_SCHEMA','Model output limit reached',503)
   text=(content or '').strip()
   if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4]
   try:result=json.loads(text)
   except (ValueError,TypeError) as exc:raise QueryError('MODEL_SCHEMA','Model returned invalid JSON',503) from exc
   if not isinstance(result,dict):raise QueryError('MODEL_SCHEMA','Model returned a non-object',503)
   rec['status']='ok';return result,rec
  except BaseException as exc:
   rec['error']=type(exc).__name__;rec['message']=str(exc)[:200]
   if not known:rec['reserved_cost_usd']=estimate
   raise
  finally:
   rec['latency_seconds']=time.monotonic()-start
   with self.lock:
    self.pending-=estimate;self.spent+=charge
    if generation:self.generation_pending-=estimate;self.generation_spent+=charge
    if qid and generation:
     self.pending_query[qid]-=estimate;self.by_query[qid]=self.by_query.get(qid,0)+charge
    self.records.append(rec);self.local.record=rec;self.save()

class Client:
 def __init__(self,ledger,phase='query',qid=None,model=QWEN):
  self.ledger=ledger;self.phase=phase;self.qid=qid;self.model=model;self.usage=Usage();self.last_usage=None;self.last_response=None
 def scoped(self):return Client(self.ledger,self.phase,self.qid,self.model)
 def complete_json(self,system,user,*,name,model=None,max_tokens=4000):
  if model and model!=self.model:raise RuntimeError('Model override refused')
  self.last_usage=None;self.last_response=None
  try:result,rec=self.ledger.call(self.model,system,user,name,max_tokens,self.phase,self.qid)
  finally:
   rec=getattr(self.ledger.local,'record',None) or {};self.last_response=getattr(self.ledger.local,'response',None)
   if 'input_tokens' in rec:self.last_usage={k:rec[k] for k in ['input_tokens','output_tokens','cost_usd']}
  self.usage.calls+=1;self.usage.input_tokens+=rec['input_tokens'];self.usage.output_tokens+=rec['output_tokens'];self.usage.cost_usd+=rec['cost_usd']
  return result

class Judge:
 def __init__(self,ledger,qid):self.client=Client(ledger,'judge',qid,GLM);self.log=[];self.qid=qid
 def call_structured(self,system_prompt,user_prompt,max_tokens=10000,temperature=0,max_retries=3):
  limit=min(6000,max_tokens);key=hashlib.sha256(json.dumps([GLM,'low',system_prompt,user_prompt,limit]).encode()).hexdigest()
  (OUT/f'{self.qid}_judge_{key}_input.json').write_text(json.dumps({'system':system_prompt,'user':user_prompt,'model':GLM,'reasoning_effort':'low','max_tokens':limit},indent=2)+'\n', encoding='utf-8')
  try:result=self.client.complete_json(system_prompt,user_prompt,name='official_judge',max_tokens=limit)
  finally:
   meta={'request_sha256':key,'finish_reason':(self.client.last_response or {}).get('finish_reason'),'model':GLM,'max_tokens':limit}
   self.log.append(meta)
   (OUT/f'{self.qid}_judge_{key}_transport.json').write_text(json.dumps(meta,indent=2)+'\n', encoding='utf-8')
  (OUT/f'{self.qid}_judge_{key}_output.json').write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
  return result

def main(prior_ledger=None):
 OUT.mkdir(parents=True,exist_ok=True);load_local_env(ROOT/'.env');logging.basicConfig(level=logging.WARNING)
 if (OUT/'report.json').exists():raise RuntimeError('Refusing to overwrite/repeat a frozen run')
 rows=[json.loads(s) for s in (CORPUS/'Benchmarks/benchmark_100.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
 selected=[]
 for slug,doc,ids in SPECS:
  for qid in ids:
   row=next(x for x in rows if x['id']==qid)
   if set(row['benchmark_chunks_w_metadata'])!={doc}:raise RuntimeError('Query is not self-contained for selected document')
   selected.append({'document':doc,'id':qid,'query':row['question']})
 protected=[CORPUS/'Benchmarks/benchmark_100.jsonl',CORPUS/'Evaluation/Evaluation.ipynb']+[CORPUS/'Documents'/d for _,d,_ in SPECS]
 hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
 report={'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'scope':'One fresh development pass on C32 and C26 after task worksheet changes; existing source indexes reused; no score-driven retries',
  'selection_frozen_before_scoring':selected,'excluded_prior_documents':['2012.07440v3.pdf','Heston.pdf','BCBS-Basel-Endgame.pdf'],
  'answer_model':QWEN,'answer_thinking':'disabled','judge_model':GLM,'judge_reasoning_effort':'low',
  'query_deadline_setting_s':30,'generation_cap_usd':GENERATION_CAP,'total_cap_usd':CAP,
  'protected_sha256':hashes,'status':'running','indexing':[],'results':[]}
 def save():
  (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
 save()
 models=cli('api','GET','/api/model')['data'];prices={}
 for mid in [QWEN,GLM]:
  m=next(x for x in models if x.get('providerID')=='opencode' and x['id']==mid);p=m['cost'][0]
  prices[mid]={'input':p['input'],'output':p['output'],'cache_read':p.get('cache',{}).get('read',p['input']),'cache_write':p.get('cache',{}).get('write',p['input'])}
  if prices[mid]['input']>.15 or prices[mid]['output']>(.47 if mid==QWEN else .5):raise RuntimeError('Model price exceeds cheap-model bounds')
 provider=next(x for x in cli('api','GET','/api/provider')['data'] if x['id']=='opencode')
 credentials=cli('auth','export','opencode');credentials=[credentials] if isinstance(credentials,dict) else credentials
 credential=next(x for x in credentials if x.get('active'))['value'];token=credential.get('access') if credential.get('type')=='oauth' else credential.get('key')
 if not token:raise RuntimeError('No active OpenCode authentication')
 ledger=Ledger(token,provider.get('headers',{}),prices)
 if prior_ledger:
  previous=json.loads(Path(prior_ledger).read_text(encoding='utf-8'))
  if previous.get('pending_reserved_usd',0)>1e-9:raise RuntimeError('Cannot carry forward an in-flight ledger')
  ledger.spent=previous['upper_bound_spent_usd'];ledger.computed=previous['computed_cost_usd']
  ledger.records=[{**r,'carried_from_prior_attempt':True} for r in previous['calls']]
  for r in ledger.records:
   charge=r.get('cost_upper_bound_usd',r.get('reserved_cost_usd',0))
   if r['phase']!='judge':
    ledger.generation_spent+=charge
    if r.get('question_id'):ledger.by_query[r['question_id']]=ledger.by_query.get(r['question_id'],0)+charge
  report['prior_attempt']={'ledger_path':str(prior_ledger),'computed_cost_usd':ledger.computed,'charged_upper_bound_usd':ledger.spent}
  ledger.save()
 report['pricing_per_million']=prices;save()
 settings=get_settings(data_dir=ROOT/'artifacts/three_unseen_20261024/data',llm_model=QWEN,answer_model=QWEN,llm_concurrency=2,parse_workers=1,use_cache=False,
  page_cards_mode='extractive',llm_max_retries=1,mongodb_uri='')
 emb=get_embedder(settings);ranker=get_reranker(settings);ns=load_notebook_namespace(protected[1])
 for slug,doc,ids in SPECS:
  coll='unseen_'+slug
  generation,directory=Registry(settings).active_dir(coll);store=Store.open(directory)
  report['indexing'].append({'document':doc,'reused_generation_id':generation,'new_indexing_cost_usd':0})
  save()
  try:
   for qid in ids:
    row=next(x for x in rows if x['id']==qid);print('Query',qid,doc,flush=True)
    item={'id':qid,'document':doc,'query':row['question'],'generation_id':generation};start=time.monotonic();cost=ledger.computed;at=len(ledger.records)
    try:
     response=answer_query(coll,row['question'],store=store,generation_id=generation,
      settings=QuerySettings(analytical_writer_mode='synthesis',artifact_dir=OUT/'query_runs',strict_observability=True),
      llm=Client(ledger,'query',qid),embedder=emb,reranker=ranker,sink=LangfuseSink())
     (OUT/(qid+'-response.json')).write_text(json.dumps(response,indent=2)+'\n', encoding='utf-8')
     item.update(status=response['status'],answer=response['answer'],query_seconds=time.monotonic()-start,
      returned_chunks=len(response['chunks']),answer_characters=len(response['answer']),coverage=response['coverage'],
      trace_steps=len(response['trace']),langfuse_trace_id=response['langfuse_trace_id'],query_calls=len(ledger.records)-at,query_cost_usd=ledger.computed-cost)
     print('Judging',qid,'query_seconds',round(item['query_seconds'],2),'chunks',item['returned_chunks'],flush=True)
     judge=Judge(ledger,qid);start=time.monotonic();cost=ledger.computed;gold=row['benchmark_chunks_w_metadata'][doc]
     try:
      metrics=ns['RAGMetricsEvaluator'](judge).evaluate_single(query=row['question'],ai_answer=response['answer'],benchmark_answer=row['benchmark_answer'],
       retrieved_chunks=[c['content'] for c in response['chunks']],benchmark_chunks=[c['content'] for c in gold])
      item.update(official_metrics=metrics,judge_audit=judge_consistency(metrics,response['answer'],judge.log))
      print(qid,'metrics',json.dumps({k:v for k,v in metrics.items() if k!='answer_detail'}),flush=True)
     except Exception as exc:
      item['judge_error']={'type':type(exc).__name__,'message':str(exc)[:300]};print(qid,'judge error',type(exc).__name__,flush=True)
     item.update(judge_seconds=time.monotonic()-start,judge_cost_usd=ledger.computed-cost,judge_calls=judge.log)
    except Exception as exc:
     item['query_error']={'type':type(exc).__name__,'message':str(exc)[:300]};print(qid,'query error',type(exc).__name__,flush=True)
    report['results'].append(item);report['computed_cost_usd']=ledger.computed;report['cost_upper_bound_usd']=ledger.spent;save()
  finally:store.close()
 report['protected_inputs_unchanged']=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
 report['document_metrics']={}
 for _,doc,ids in SPECS:
  done=[x for x in report['results'] if x['document']==doc and 'official_metrics' in x]
  report['document_metrics'][doc]={'expected_queries':len(ids),'scored_queries':len(done),'aggregation':'arithmetic mean across this document\'s selected self-contained queries',
   'metrics':{m:sum(x['official_metrics'][m] for x in done)/len(done) if done else None for m in ['answer_precision','answer_recall','context_precision','context_recall']}}
 report['status']='completed' if all('official_metrics' in x for x in report['results']) and len(report['results'])==len(selected) else 'completed_with_failures'
 report['computed_cost_usd']=ledger.computed;report['cost_upper_bound_usd']=ledger.spent;save()
 print('DONE',report['status'],'known cost',ledger.computed,'upper',ledger.spent,flush=True)

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--out',type=Path,default=OUT)
 parser.add_argument('--prior-ledger',type=Path)
 args=parser.parse_args();OUT=args.out.resolve()
 main(args.prior_ledger)
