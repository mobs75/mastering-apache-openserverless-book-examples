# plugin-example — Chapter 4

Example OpenServerless plugin demonstrating the standard three-level architecture:

```
Plugin (OpenServerless level)
  └── Operator (Kubernetes level — Kopf)
        └── Service (real cluster component)
```

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Plugin registration — discovered by ops CLI |
| `crd.yaml` | Custom Resource Definition |
| `config.py` | Spec reading and validation |
| `operator.py` | Kopf handlers: create / update / delete |
| `kustomization.yaml` | Kustomize assembly |
| `opsfile.yml` | ops CLI commands |
| `templates/` | Jinja2 YAML templates |
| `tests/` | Unit tests with kube.apply() mocks |

## Quick start

```bash
# Install CRD and operator
ops example install

# Deploy an instance
ops example deploy NAME=my-example REPLICAS=1

# Check status
ops example status

# Remove
ops example remove NAME=my-example
```

## Running tests

```bash
pip install pytest kopf
python -m pytest tests/ -v
```
