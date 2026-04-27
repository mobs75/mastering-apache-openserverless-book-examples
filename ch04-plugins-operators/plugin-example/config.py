"""
config.py — Configuration management for the example plugin.

Isolates spec reading and validation from operator.py,
keeping the Kopf handler clean and testable in isolation.
"""


def load_config(spec, name, namespace):
    """
    Read the Custom Resource spec and return a flat config dict
    ready to be passed to Jinja2 templates.
    """
    return {
        "name": name,
        "namespace": namespace,
        "replicas": spec.get("replicas", 1),
        "version": spec.get("version", "1.0.0"),
        "storage_size": spec.get("storage", "1Gi"),
        "image": f"example-service:{spec.get('version', '1.0.0')}",
        "secret_name": f"{name}-secret",
    }
