"""Provider wire format. Every paid call is qwen3.8-flash on OpenCode's Messages endpoint, thinking disabled."""
from urllib.parse import urlsplit, urlunsplit

# Team rule: one model, never with thinking. Any other model is refused here, the single wire-format door
# shared by ingestion, queries and the evaluator judge.
REQUIRED_MODEL = "qwen3.8-flash"


def is_qwen_no_thinking(model):
    return model == REQUIRED_MODEL


def request_spec(base_url, model, system, user, max_tokens, json_mode=True):
    if model != REQUIRED_MODEL:
        raise ValueError(f"model {model!r} refused: only {REQUIRED_MODEL} (thinking disabled) may be called")
    parts=urlsplit(base_url)
    if parts.hostname == "opencode.ai":
        base_url=urlunsplit((parts.scheme,parts.netloc,"/inference/anthropic/v1/messages","",""))
    headers={"anthropic-version":"2023-06-01"}
    payload={"model":model,"system":system+("\nReturn only a valid JSON object." if json_mode else ""),
             "messages":[{"role":"user","content":user}],"temperature":0,
             "max_tokens":max_tokens,"thinking":{"type":"disabled"}}
    return base_url,headers,payload


def response_parts(body):
    usage=body.get("usage") or {}
    if "choices" in body:
        choice=body["choices"][0]
        return (choice.get("message",{}).get("content"),choice.get("finish_reason"),
                usage.get("prompt_tokens"),usage.get("completion_tokens"))
    content="".join(b.get("text","") for b in body.get("content",[]) if b.get("type")=="text")
    # Messages input_tokens excludes cache reads/writes; count all input conservatively.
    inputs=usage.get("input_tokens")
    if isinstance(inputs,int):
        inputs+=int(usage.get("cache_read_input_tokens") or 0)+int(usage.get("cache_creation_input_tokens") or 0)
    return content,body.get("stop_reason"),inputs,usage.get("output_tokens")
