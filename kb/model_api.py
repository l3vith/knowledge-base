"""Provider wire formats. Qwen Flash uses OpenCode's Messages endpoint without thinking."""
from urllib.parse import urlsplit, urlunsplit


def is_qwen_no_thinking(model):
    return model == "qwen3.8-flash"


def request_spec(base_url, model, system, user, max_tokens, json_mode=True):
    headers={}
    if is_qwen_no_thinking(model):
        parts=urlsplit(base_url)
        if parts.hostname == "opencode.ai":
            base_url=urlunsplit((parts.scheme,parts.netloc,"/inference/anthropic/v1/messages","",""))
        headers["anthropic-version"]="2023-06-01"
        payload={"model":model,"system":system+("\nReturn only a valid JSON object." if json_mode else ""),
                 "messages":[{"role":"user","content":user}],"temperature":0,
                 "max_tokens":max_tokens,"thinking":{"type":"disabled"}}
    else:
        payload={"model":model,"temperature":0,"max_tokens":max_tokens,
                 "messages":[{"role":"system","content":system},{"role":"user","content":user}]}
        if json_mode:
            payload["response_format"]={"type":"json_object"}
        if model.startswith("deepseek-"):
            payload["reasoning_effort"]="low"
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
