"""
web_action.py — Web Action accessible via HTTP without authentication.
Chapter 10 — Mastering Apache OpenServerless

Web Actions are enabled with --web true.
They receive the full HTTP request and can return structured HTTP responses.

Deploy:
    ops action create web-hello web_action.py --kind python:3.11 --web true

Access via HTTP (no auth required; <apihost> is the API host you logged in to,
and devel is the example user and namespace used in the book):
    curl "<apihost>/api/v1/web/devel/default/web-hello?name=Alessio"
    curl "<apihost>/api/v1/web/devel/default/web-hello" \
         -X POST -H "Content-Type: application/json" \
         -d '{"name": "Alessio"}'

URL pattern:
    /api/v1/web/<namespace>/default/<action-name>
    /api/v1/web/<namespace>/<package>/<action-name>

OpenWhisk injects HTTP context into args:
    __ow_method      — HTTP method (GET, POST, ...)
    __ow_headers     — request headers dict
    __ow_path        — request path
    __ow_query       — query string
    __ow_body        — request body (base64 if binary)
"""
import json


def main(args: dict) -> dict:
    """
    Web action that handles both GET (query params) and POST (JSON body).
    Returns a structured HTTP response with status code and headers.
    """
    method = args.get('__ow_method', 'GET').upper()
    name   = args.get('name', 'OpenServerless')

    # Log request details (visible in activation logs)
    print(f'[web-hello] method={method} name={name}')

    # Return structured HTTP response
    # 'body' is returned as-is to the HTTP client
    # 'statusCode' sets the HTTP status (default 200)
    # 'headers' sets response headers
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Powered-By': 'Apache OpenServerless',
        },
        'body': json.dumps({
            'message': f'Hello {name}',
            'method':  method,
        })
    }
