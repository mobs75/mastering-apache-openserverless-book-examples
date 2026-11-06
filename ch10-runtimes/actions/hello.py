"""
hello.py — Basic OpenServerless action
Chapter 10 — Mastering Apache OpenServerless

Mandatory Python action signature:
  - Function name: main
  - Parameter: args (dict)
  - Returns: dict (JSON-serializable)

Deploy:
    ops action create hello hello.py --kind python:3.11

Invoke:
    ops action invoke hello --result
    ops action invoke hello --result --param name Alessio

Web action (HTTP endpoint, no auth; <apihost> is the API host you logged in to,
and devel is the example user and namespace used in the book):
    ops action update hello --web true
    curl "<apihost>/api/v1/web/devel/default/hello?name=Alessio"
"""


def main(args: dict) -> dict:
    name = args.get('name', 'OpenServerless')
    print(f'Invocation with name={name}')  # Visible in: ops activation logs <id>
    return {'body': f'Hello {name}'}
