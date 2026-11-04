#!/bin/bash
# kind-reset.sh — recreate the openserverless kind cluster
kind delete cluster --name openserverless 2>/dev/null || true
cat <<KINDEOF | kind create cluster --name openserverless --config -
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
    - |
      kind: KubeletConfiguration
      maxPods: 250
  - role: worker
    kubeadmConfigPatches:
    - |
      kind: KubeletConfiguration
      maxPods: 250
  - role: worker
    kubeadmConfigPatches:
    - |
      kind: KubeletConfiguration
      maxPods: 250
  - role: worker
    kubeadmConfigPatches:
    - |
      kind: KubeletConfiguration
      maxPods: 250
KINDEOF
