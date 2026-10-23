"""Load unchanged official definition cells; sample invocation never executes."""
import ast
import hashlib
import json
import os
from pathlib import Path

EXPECTED_EVALUATOR_SHA256="f75493648896a79fc28499f04bb4909baea9bf717c1b040d0c3fb3974aa5f583"
METRICS=("answer_precision","answer_recall","context_precision","context_recall")


def load_notebook_namespace(ipynb,expected_hash=EXPECTED_EVALUATOR_SHA256,config=None):
    path=Path(ipynb);original=path.read_bytes()
    if hashlib.sha256(original).hexdigest()!=expected_hash:
        raise ValueError("official evaluator hash differs; inspect and explicitly pin the provided original")
    notebook=json.loads(original)
    cfg={"OPENCODE_API_KEY":os.getenv("OPENCODE_API_KEY",""),
         "OPENCODE_MODEL":os.getenv("OPENCODE_MODEL",os.getenv("LLM_MODEL","qwen3.8-flash")),
         "OPENCODE_BASE_URL":os.getenv("OPENCODE_BASE_URL","https://opencode.ai/inference/openai/v1/chat/completions")}
    if config:
        cfg.update(config)
    ns={"__name__":"official_evaluator_isolated",**cfg};executed=[]
    wanted={"OpenCodeClient","RAGMetricsEvaluator","evaluate_dataset"}
    for index,cell in enumerate(notebook["cells"]):
        if cell["cell_type"]!="code":
            continue
        source="".join(cell.get("source",[]))
        tree=ast.parse(source)
        definitions={n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        only_imports=bool(tree.body) and all(isinstance(n,(ast.Import,ast.ImportFrom)) for n in tree.body)
        if only_imports or definitions & wanted:
            # Entire source cell is executed verbatim; unexpected top-level calls fail review.
            if any(not isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.Import,ast.ImportFrom)) for n in tree.body):
                raise ValueError("definition cell has unexpected top-level side effects")
            exec(compile(source,f"{path.name}:cell{index}","exec"),ns)
            executed.append(index)
    if not wanted.issubset(ns):
        raise ValueError("missing official evaluator definitions")
    if path.read_bytes()!=original:
        raise RuntimeError("protected evaluator changed during load")
    ns["_executed_cells"]=executed
    return ns


def evaluate_file(run_path,api_key=None,notebook=None,expected_hash=EXPECTED_EVALUATOR_SHA256):
    if notebook is None:
        raise ValueError("pass the provided official notebook path")
    key=api_key or os.getenv("OPENCODE_API_KEY","")
    if not key:
        from kb.opencode_auth import cli_headers
        cli_headers()  # no key: the judge uses the logged-in opencode CLI (fails here, before any spend)
    ns=load_notebook_namespace(notebook,expected_hash,{"OPENCODE_API_KEY":key})
    # Keep official metric definitions unchanged; adapt only the provider transport.
    client=OfficialJudgeTransport(key,ns["OPENCODE_MODEL"],ns["OPENCODE_BASE_URL"])
    evaluator=ns["RAGMetricsEvaluator"](client)
    rows=[json.loads(s) for s in Path(run_path).read_text(encoding="utf-8").splitlines() if s.strip()]
    scored=[];errors=[]
    for row in rows:
        if row.get("error"):
            errors.append({"id":row["id"],"stage":"query","error":row["error"]});continue
        try:
            client.log=[]
            metrics=evaluator.evaluate_single(query=row["query"],ai_answer=row["ai_answer"],benchmark_answer=row["benchmark_answer"],
                                               retrieved_chunks=row["retrieved_chunks"],benchmark_chunks=row["benchmark_chunks"])
            # Official metrics untouched; alongside them, every judge request/response this score came from
            # (data/judge_cache/<request_sha256>.json) and zero-call consistency flags. Flagged rows are never re-judged.
            from evaluation.audit import judge_consistency, checklist
            scored.append({"id":row["id"],**metrics,"judge_calls":client.log,
                           "consistency":judge_consistency(metrics,row["ai_answer"],client.log),
                           "dev_checklist":checklist(row["id"],row["ai_answer"])})
        except Exception as exc:
            errors.append({"id":row["id"],"stage":"judge","error":f"{type(exc).__name__}: {exc}"[:300]})
    n=len(rows)
    summary={"total_rows":n,"scored_rows":len(scored),"failed_rows":len(errors),
             "scored_row_means":{m:sum(r[m] for r in scored)/len(scored) if scored else None for m in METRICS},
             "failure_as_zero_means_diagnostic":{m:sum(r[m] for r in scored)/n if n else None for m in METRICS},
             "warning":"Failure-as-zero aggregate is separately labeled; official formulas are unchanged.",
             "evaluator_sha256":expected_hash,"executed_definition_cells":ns["_executed_cells"],
             "judge_model":client.model,"judge_reasoning_effort":getattr(client,"effort",None),
             "judge_calls_over_notebook_limit":getattr(client,"over_notebook_limit",0),
             "rows_with_consistency_flags":[r["id"] for r in scored if r["consistency"]["flags"]]}
    result={"summary":summary,"per_question":scored,"errors":errors}
    Path(str(run_path)+".scores.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result


class OfficialJudgeTransport:
    """Use the shared Messages/OpenAI transport without changing official metric logic.

    A non-Qwen judge (OPENCODE_MODEL=deepseek-v4.1-flash, the notebook default) never goes through the
    system's Qwen-only client: it is sent exactly like the notebook's OpenCodeClient payload, plus CLI auth."""
    def __init__(self,key,model,base_url):
        from kb.config import get_settings
        from kb.model_api import REQUIRED_MODEL
        self.key,self.model,self.base_url,self.effort=key,model,base_url,None
        self.log=[]
        self.cache=get_settings().ledger_path().parent/"judge_cache"
        if model==REQUIRED_MODEL:
            from kb.llm import OpenCodeLLM
            self.client=OpenCodeLLM(get_settings(opencode_api_key=key,llm_model=model,
                                                opencode_base_url=base_url,llm_max_retries=1))
        else:
            self.client=None
            self.settings=get_settings()
            self.prices=(float(os.getenv("JUDGE_PRICE_INPUT_PER_M","0.30")),float(os.getenv("JUDGE_PRICE_OUTPUT_PER_M","1.20")))
            # DeepSeek thinks by default and can spend the notebook's whole 10,000-token limit before answering.
            # Our runs use "low" to save credit; JUDGE_REASONING_EFFORT=default sends the notebook's exact payload.
            self.effort=os.getenv("JUDGE_REASONING_EFFORT","low")
            self.over_notebook_limit=0

    def call_structured(self,system_prompt,user_prompt,max_tokens=10000,temperature=0,max_retries=3):
        if self.client:
            key=hashlib.sha256(json.dumps([self.model,system_prompt,user_prompt,max_tokens],sort_keys=True).encode()).hexdigest()
            result=self.client.complete_json(system_prompt,user_prompt,name="official_judge",max_tokens=max_tokens)
            self._keep(key,result,{"finish_reason":getattr(self.client,"last_finish_reason",None)})
            return result
        import time
        import requests
        from kb.llm import spent_usd,_record_spend
        s=self.settings
        if s.budget_usd is not None and spent_usd(s)>=s.budget_usd:
            raise RuntimeError(f"spend cap KB_BUDGET_USD={s.budget_usd} reached")
        if self.key:
            auth={"Authorization":f"Bearer {self.key}"}
        else:
            from kb.opencode_auth import cli_headers
            auth=cli_headers()
        payload={"model":self.model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
                 "temperature":temperature,"max_tokens":max_tokens,"response_format":{"type":"json_object"}}
        if self.effort!="default":
            payload["reasoning_effort"]=self.effort
        # Temperature 0: the same judge call gives the same verdict, so a rerun reads it from disk for $0.
        key=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        cached=self.cache/(key+".json")
        if cached.is_file():
            self.log.append({"request_sha256":key,"cached":True,"max_tokens":max_tokens})
            return json.loads(cached.read_text(encoding="utf-8"))
        last=None
        for attempt in range(max_retries):
            try:
                resp=requests.post(self.base_url,headers={**auth,"Content-Type":"application/json"},json=payload,timeout=120)
                resp.raise_for_status();data=resp.json()
            except requests.RequestException as exc:
                last=exc;time.sleep(1.5*(attempt+1));continue
            usage=data.get("usage") or {};i,o=usage.get("prompt_tokens") or 0,usage.get("completion_tokens") or 0
            _record_spend(s,"official_judge",self.model,i,o,(i*self.prices[0]+o*self.prices[1])/1e6)
            choice=(data.get("choices") or [{}])[0];content=(choice.get("message") or {}).get("content")
            if not content:
                # The same request fails the same way at temperature 0, so one retry with a larger limit, never a repeat.
                # Counted: the official notebook (10,000 tokens) would have errored on this call.
                big=int(os.getenv("JUDGE_MAX_TOKENS_ESCALATED","32000"))
                if choice.get("finish_reason")=="length" and max_tokens<big:
                    self.over_notebook_limit+=1
                    self.log.append({"request_sha256":key,"finish_reason":"length","output_tokens":o,"max_tokens":max_tokens,"escalated":True})
                    return self.call_structured(system_prompt,user_prompt,big,temperature,max_retries)
                raise RuntimeError(f"judge returned no content (finish_reason={choice.get('finish_reason')}, output_tokens={o})")
            text=content.strip()
            if text.startswith("```"):
                text=text.strip("`");text=text[4:] if text.lower().startswith("json") else text
            result=json.loads(text)
            self._keep(key,result,{"finish_reason":choice.get("finish_reason"),"output_tokens":o,"max_tokens":max_tokens})
            return result
        raise RuntimeError(f"judge call failed after {max_retries} attempts: {type(last).__name__}")

    def _keep(self,key,result,info):
        # The parsed response is the cache entry (same request at temperature 0 = same verdict) and the audit trail.
        path=self.cache/(key+".json");path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
        self.log.append({"request_sha256":key,**info})
