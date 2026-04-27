"""
upper.py — Action that converts 'name' field to uppercase.
Chapter 10 — Mastering Apache OpenServerless

Used as first step in the hello-pipeline sequence.
Passes through all input fields and adds/overwrites 'name'.

Deploy:
    ops action create upper upper.py --kind python:3.11
"""


def main(args: dict) -> dict:
    name = args.get('name', 'world')
    # Best practice: preserve all input fields when building pipeline steps
    return {**args, 'name': name.upper()}
