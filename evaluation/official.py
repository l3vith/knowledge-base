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
         "OPENCODE_MODEL":os.getenv("OPENCODE_MODEL",os.getenv("LLM_MODEL","deepseek-v4.1-flash")),
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
        raise ValueError("OpenCode key required for real official judging")
    ns=load_notebook_namespace(notebook,expected_hash,{"OPENCODE_API_KEY":key})
    client=ns["OpenCodeClient"](api_key=key,model=ns["OPENCODE_MODEL"],base_url=ns["OPENCODE_BASE_URL"])
    evaluator=ns["RAGMetricsEvaluator"](client)
    rows=[json.loads(s) for s in Path(run_path).read_text().splitlines() if s.strip()]
    scored=[];errors=[]
    for row in rows:
        if row.get("error"):
            errors.append({"id":row["id"],"stage":"query","error":row["error"]});continue
        try:
            metrics=evaluator.evaluate_single(query=row["query"],ai_answer=row["ai_answer"],benchmark_answer=row["benchmark_answer"],
                                               retrieved_chunks=row["retrieved_chunks"],benchmark_chunks=row["benchmark_chunks"])
            scored.append({"id":row["id"],**metrics})
        except Exception as exc:
            errors.append({"id":row["id"],"stage":"judge","error":type(exc).__name__})
    n=len(rows)
    summary={"total_rows":n,"scored_rows":len(scored),"failed_rows":len(errors),
             "scored_row_means":{m:sum(r[m] for r in scored)/len(scored) if scored else None for m in METRICS},
             "failure_as_zero_means_diagnostic":{m:sum(r[m] for r in scored)/n if n else None for m in METRICS},
             "warning":"Failure-as-zero aggregate is separately labeled; official formulas are unchanged.",
             "evaluator_sha256":expected_hash,"executed_definition_cells":ns["_executed_cells"]}
    result={"summary":summary,"per_question":scored,"errors":errors}
    Path(str(run_path)+".scores.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    return result
