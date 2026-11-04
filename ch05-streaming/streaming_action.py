#--kind python:3.11
"""
streaming_action.py -- OpenWhisk action that streams output via the streamer socket.
Chapter 5 -- Mastering Apache OpenServerless

The openserverless-streamer opens a TCP socket per request and passes its
address to the action as the STREAM_HOST and STREAM_PORT parameters.
The action connects to that socket and writes incremental output.
The streamer relays each chunk immediately to the HTTP client.

Deploy:
    ops action create streaming-hello streaming_action.py --kind python:3.11

Invoke via streamer endpoint:
    curl -N -X POST https://stream.<openserverless-domain>/action/devel/streaming-hello \
         -H "Authorization: Bearer <token>" \
         -d '{"prompt": "Hello"}'
"""
import socket
import time

def main(args: dict) -> dict:
    prompt = args.get("prompt", "Hello OpenServerless")
    stream_host = args.get("STREAM_HOST", None)
    stream_port = args.get("STREAM_PORT", None)

    if not stream_host or not stream_port:
        # Fallback: direct invocation without streamer
        return {"body": f"Echo: {prompt}"}

    with socket.create_connection((stream_host, int(stream_port)), timeout=30) as sock:
        words = prompt.split()
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "\n")
            sock.sendall(chunk.encode("utf-8"))
            time.sleep(0.05)  # Simulate token generation delay
        sock.sendall(b"[DONE]\n")

    return {"status": "ok", "tokens_sent": len(words)}
