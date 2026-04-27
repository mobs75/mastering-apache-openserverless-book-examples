"""
test_operator.py — Unit tests for operator.py handlers
Chapter 4 — Mastering Apache OpenServerless
Run with: python -m pytest tests/
"""
def test_create_handler_returns_message():
    from operator import create_example
    result = create_example(spec={"replicas":1,"version":"1.0.0"}, name="test", namespace="nuvolaris", body={})
    assert "message" in result
    assert result["version"] == "1.0.0"

def test_delete_handler_runs_without_error():
    from operator import delete_example
    delete_example(spec={}, name="test", namespace="nuvolaris", body={})
