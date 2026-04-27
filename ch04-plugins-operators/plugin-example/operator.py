"""
operator.py — Kopf-based Kubernetes operator for the example plugin.

This is the executive engine of the plugin. It watches the Example CRD
and reacts to create / update / delete events by generating Kubernetes
resources via Jinja2 + Kustomize and applying them with kube.apply().

Pattern is identical for every OpenServerless plugin:
  spec → config.py → Jinja2 templates → Kustomize → kube.apply()
"""

import kopf
import logging

from . import config as cfg

logger = logging.getLogger(__name__)


# ── CREATE ─────────────────────────────────────────────────────────────────

@kopf.on.create('example.nuvolaris.org', 'v1', 'examples')
def create_example(spec, name, namespace, **kwargs):
    """
    Called when a new Example CR is created.
    Renders templates, assembles with Kustomize, applies to cluster.
    """
    logger.info(f"[example] create: name={name} namespace={namespace}")

    # 1. Build configuration dict from CR spec
    data = cfg.load_config(spec, name, namespace)

    # 2. Render Jinja2 templates
    # (in a real plugin: from nuvolaris import kustomize, kube)
    # resources = kustomize.render_templates('plugins/example/templates', data)

    # 3. Apply OwnerReference so Kubernetes GC cleans up on CR delete
    # kopf.append_owner_reference(resources['items'], owner=kwargs['body'])

    # 4. Apply to cluster
    # for resource in resources['items']:
    #     kube.apply(resource, namespace)

    # 5. Wait for pod readiness
    # util.wait_for_pod_ready(f"app={name}", namespace)

    logger.info(f"[example] create done: name={name}")
    return {"message": f"Example {name} created", "version": data["version"]}


# ── UPDATE ─────────────────────────────────────────────────────────────────

@kopf.on.update('example.nuvolaris.org', 'v1', 'examples')
def update_example(spec, name, namespace, **kwargs):
    """
    Called when the Example CR spec changes.
    Re-renders templates and re-applies — idempotent via kubectl apply.
    """
    logger.info(f"[example] update: name={name}")
    data = cfg.load_config(spec, name, namespace)
    # Re-render and re-apply (same pipeline as create)
    logger.info(f"[example] update done: name={name}")
    return {"message": f"Example {name} updated", "version": data["version"]}


# ── DELETE ─────────────────────────────────────────────────────────────────

@kopf.on.delete('example.nuvolaris.org', 'v1', 'examples')
def delete_example(spec, name, namespace, **kwargs):
    """
    Called when the Example CR is deleted.
    OwnerReferences handle automatic GC of child resources.
    """
    logger.info(f"[example] delete: name={name}")
    # kube.delete_all(name, namespace)
    logger.info(f"[example] delete done: name={name}")
