"""
test_config.py — Unit tests for config.py
Chapter 4 — Mastering Apache OpenServerless
Run with: python -m pytest tests/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import load_config

def test_load_config_defaults():
    result = load_config({}, "test-example", "openserverless")
    assert result["name"] == "test-example"
    assert result["namespace"] == "openserverless"
    assert result["replicas"] == 1
    assert result["version"] == "1.0.0"
    assert result["storage_size"] == "1Gi"
    assert result["secret_name"] == "test-example-secret"

def test_load_config_custom():
    spec = {"replicas": 3, "version": "2.0.0", "storage": "10Gi"}
    result = load_config(spec, "my-svc", "production")
    assert result["replicas"] == 3
    assert result["version"] == "2.0.0"
    assert result["storage_size"] == "10Gi"
    assert result["image"] == "example-service:2.0.0"
