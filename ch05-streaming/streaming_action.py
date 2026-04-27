"""
streaming_action.py — OpenWhisk action that streams output via the streamer socket.
Chapter 5 — Mastering Apache OpenServerless

The openserverless-streamer opens a TCP socket per request.
The action connects to STREAMER_ADDR and writes incremental output.
The streamer relays each chunk immediately to the HTTP client.

Deploy:
    ops action create streaming-hello streaming_action.py --kind python:3.11

Invoke via streamer endpoint:
    curl -X POST http://<streamer-host>/action/nuvolaris/streaming-hello \
         -H "Authorization: Bearer <token>" \
         -d '{"prompt": "Hello"}'
"""
import socket
import os
import time


def main(args: dict) -> dict:
    """
    Streams tokens word by word to the caller via the streamer TCP socket.
    Falls back to normal return if no STREAMER_ADDR (direct invocation).
    """
    prompt = args.get("prompt", "Hello OpenServerless")
    streamer_addr = args.get("__ow_streamer_addr") or os.environ.get("STREAMER_ADDR", "")

    if not streamer_addr:
        return {"body": f"Echo: {prompt}"}

    host, port = streamer_addr.rsplit(":", 1)

    with socket.create_connection((host, int(port)), timeout=30) as sock:
        words = prompt.split()
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "\n")
            sock.sendall(chunk.encode("utf-8"))
            time.sleep(0.05)  # Simulate token generation delay
        sock.sendall(b"[DONE]\n")

    return {"status": "ok", "tokens_sent": len(words)}
