# ch05-streaming — Chapter 5

Examples for the **openserverless-streamer** component.

## Files

| File | Description |
|------|-------------|
| `streaming_action.py` | Basic streaming action — streams words via TCP socket |
| `streaming_llm_action.py` | LLM token streaming via Ollama + streamer |

## How the streamer works

```
HTTP Client
    │  POST /action/{ns}/{action}
    ▼
openserverless-streamer (port 8181)
    │  1. Invokes OW action via REST API
    │  2. Opens TCP socket on STREAMER_ADDR
    ▼
OpenWhisk Action Runtime
    │  Connects to STREAMER_ADDR
    │  Writes tokens to socket
    ▼
openserverless-streamer
    │  Reads from socket → writes chunks to HTTP response
    ▼
HTTP Client receives chunked stream
```

## Streamer endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| POST /action/{ns}/{action} | Bearer token | Invoke action (auth required) |
| POST /action/{ns}/{pkg}/{action} | Bearer token | Invoke action in package |
| POST /web/{ns}/{action} | None | Invoke web action (no auth) |
| POST /web/{ns}/{pkg}/{action} | None | Invoke web action in package |

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OW_APIHOST | Yes | — | OpenWhisk API host |
| STREAMER_ADDR | Yes | — | address:port for action TCP socket |
| HTTP_SERVER_PORT | No | 8181 | Streamer HTTP listen port |

## Deploy and test

```bash
# Deploy
ops action create streaming-hello streaming_action.py --kind python:3.11

# Invoke via streamer
TOKEN=$(grep AUTH ~/.wskprops | cut -d= -f2)
curl -X POST http://localhost:8181/action/nuvolaris/streaming-hello \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"prompt": "Hello streaming world"}'
```
