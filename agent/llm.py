"""Calls a local model through the Ollama chat API."""

import json
import time
import urllib.request


def load(cfg):
    """Loads the model into the GPU, so the first decision is not slowed by it."""
    body = {"model": cfg["model"], "keep_alive": "30m"}
    request = urllib.request.Request(
        cfg["url"] + "/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        response.read()
    return round(time.perf_counter() - start, 1)


def chat(cfg, system, user, schema):
    """Returns (answer dict or None, raw text, timing dict)."""
    body = {
        "model": cfg["model"],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": cfg["temperature"],
            "seed": cfg["seed"],
            "num_ctx": cfg["num_ctx"],
        },
    }
    request = urllib.request.Request(
        cfg["url"] + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read())
    timing = {
        "wall_s": round(time.perf_counter() - start, 3),
        "load_s": round(result.get("load_duration", 0) / 1e9, 3),
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "prompt_s": round(result.get("prompt_eval_duration", 0) / 1e9, 3),
        "output_tokens": result.get("eval_count", 0),
        "output_s": round(result.get("eval_duration", 0) / 1e9, 3),
    }
    text = result["message"]["content"]
    try:
        answer = json.loads(text)
    except ValueError:
        answer = None
    return answer, text, timing
