"""
streaming_llm_action.py -- Action that streams LLM tokens via the streamer.
Chapter 5 -- Mastering Apache OpenServerless

Real-world pattern for LLM inference with token streaming.
Assumes Ollama or compatible LLM backend reachable from the cluster.

Deploy:
    ops action create streaming-llm streaming_llm_action.py \
        --kind python:3.11 --timeout 120000 --memory 256 --web true

Invoke via streamer /web/ endpoint (no auth required):
    curl -N https://stream.<openserverless-domain>/web/devel/streaming-llm \
         -d '{"prompt": "Explain Kubernetes in 3 sentences"}'
"""
import socket, os, json, urllib.request

LLM_ENDPOINT = os.environ.get(
    "LLM_ENDPOINT",
    "http://ollama.openserverless.svc.cluster.local:11434"
)

def stream_from_llm(prompt: str):
    """Call Ollama streaming API and yield tokens one by one."""
    payload = json.dumps({
        "model": "mistral", "prompt": prompt, "stream": True
    }).encode()
    req = urllib.request.Request(
        f"{LLM_ENDPOINT}/api/generate", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        for line in resp:
            chunk = json.loads(line.decode())
            token = chunk.get("response", "")
            if token:
                yield token
            if chunk.get("done"):
                break

def main(args: dict) -> dict:
    prompt = args.get("prompt", "Hello")
    stream_host = args.get("STREAM_HOST", None)
    stream_port = args.get("STREAM_PORT", None)

    if not stream_host or not stream_port:
        return {"body": f"[no streamer] prompt={prompt}"}

    with socket.create_connection((stream_host, int(stream_port)), timeout=120) as sock:
        for token in stream_from_llm(prompt):
            sock.sendall(token.encode("utf-8"))
        sock.sendall(b"\n[DONE]\n")

    return {"status": "ok"}
