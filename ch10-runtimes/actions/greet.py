"""
greet.py — Action used inside the 'demo' package.
Chapter 10 — Mastering Apache OpenServerless

Package default params are automatically available in args.
Parameter precedence (highest to lowest):
  1. Invocation params (--param)
  2. Action default params
  3. Package default params

Deploy inside a package:
    ops package create demo
    ops package update demo --param name 'OpenServerless User'
    ops action create demo/greet greet.py --kind python:3.11

Test:
    ops action invoke demo/greet --result
    # Output: {"body": "Hello OpenServerless User"}  (uses package default)

    ops action invoke demo/greet --result --param name Alessio
    # Output: {"body": "Hello Alessio"}  (invocation overrides package default)
"""


def main(args: dict) -> dict:
    name = args.get('name', 'OpenServerless')
    greeting = args.get('greeting', 'Hello')
    print(f'Greeting: {greeting} {name}')
    return {'body': f'{greeting} {name}'}
