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
    │  POST https://stream.<openserverless-domain>/action/{ns}/{action}
    ▼
openserverless-streamer (StatefulSet openserverless-streamer-api, port 8080)
    │  1. Opens a TCP socket on a free port of its pod (STREAMER_ADDR)
    │  2. Invokes the action via the OpenWhisk REST API, passing
    │     the socket address as the STREAM_HOST and STREAM_PORT parameters
    ▼
OpenWhisk Action Runtime
    │  Connects to STREAM_HOST:STREAM_PORT
    │  Writes tokens to socket
    ▼
openserverless-streamer
    │  Reads from socket → writes chunks to HTTP response
    ▼
HTTP Client receives chunked stream
```

The streamer is installed by `ops setup openserverless streamer deploy` in the
`openserverless` namespace and is exposed through the ingress at
`stream.<openserverless-domain>`.

## Streamer endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| POST /action/{ns}/{action} | Bearer token | Invoke action (auth required) |
| POST /action/{ns}/{pkg}/{action} | Bearer token | Invoke action in package |
| POST /web/{ns}/{action} | None | Invoke web action (no auth) |
| POST /web/{ns}/{pkg}/{action} | None | Invoke web action in package |

## Streamer environment variables

| Variable | Description |
|----------|-------------|
| OW_APIHOST | OpenWhisk API host |
| STREAMER_ADDR | IP address of the streamer pod (from `status.podIP`), used for the action sockets |
| HTTP_SERVER_PORT | Streamer HTTP listen port (8080 in the deployment; 80 is the default in the code) |
| CORS_ENABLED | Enables CORS headers on the HTTP responses |

The action does not read these variables: it receives `STREAM_HOST` and
`STREAM_PORT` as invocation parameters.

## Deploy and test

```bash
# Deploy
ops action create streaming-hello streaming_action.py --kind python:3.11

# Invoke via streamer (example user: devel)
TOKEN=$(grep AUTH ~/.wskprops | cut -d= -f2)
curl -N -X POST https://stream.<openserverless-domain>/action/devel/streaming-hello \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"prompt": "Hello streaming world"}'
```
