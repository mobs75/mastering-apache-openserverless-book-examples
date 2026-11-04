#!/bin/bash
# setup-microk8s-multipass.sh — Deploy Apache OpenServerless on MicroK8s + Multipass
# Chapter 9 — Mastering Apache OpenServerless
#
# Tested with: Apache OpenServerless 0.9.0-incubating, ops 0.9.0
# Architecture: 1 master + 3 worker nodes via Multipass VMs (MicroK8s cluster
# already created, for example with the Pulumi program described in Chapter 9)
#
# The script uses the official "cluster" deployment path (ops setup cluster),
# which deploys the platform on an existing Kubernetes cluster, then installs
# the streamer, the system API and Tika, logs in and creates the default user.
#
# Usage:
#   chmod +x setup-microk8s-multipass.sh
#   ./setup-microk8s-multipass.sh
set -euo pipefail

MASTER_VM="k8s-master"
NS="openserverless"
APIHOST="${APIHOST:-auto}"     # or an explicit hostname, e.g. my-platform.example.com
OPS='$HOME/go/bin/ops'         # where "go install" puts the ops binary on k8s-master

# Helper: run a command on k8s-master
vm() {
    multipass exec "$MASTER_VM" -- bash -c "$*"
}

echo "=== Step 1: Install the ops CLI on k8s-master (from the official sources) ==="
# See https://openserverless.apache.org/docs/installation/install-cli/
vm "command -v go >/dev/null || sudo snap install go --classic"
vm "go install github.com/apache/openserverless-cli/cmd/ops@0.9.0"
vm "grep -q 'go/bin' ~/.bashrc || echo 'export PATH=\$PATH:\$HOME/go/bin' >> ~/.bashrc"
# First run: downloads the tasks and the prerequisite tools (kubectl, helm, ...)
vm "$OPS -info"

echo "=== Step 2: Point kubectl to the MicroK8s cluster ==="
vm "mkdir -p ~/.kube && microk8s config > ~/.kube/config && chmod 600 ~/.kube/config"
vm "$OPS debug kube info || microk8s kubectl cluster-info"

echo "=== Step 3: Configure the platform ==="
vm "$OPS config apihost $APIHOST"
vm "$OPS config enable --redis --mongodb --postgres --seaweedfs --static --cron"

echo "=== Step 4: Deploy Apache OpenServerless on the existing cluster ==="
vm "$OPS setup cluster"

echo "=== Step 5: Verify ==="
vm "$OPS setup status"
vm "microk8s kubectl -n $NS get pods"

echo ""
echo "=== Done! ==="
echo "ops setup cluster has already logged in (credentials in ~/.wskprops on k8s-master)."
echo "Verify with:"
echo "  multipass exec $MASTER_VM -- bash -lc 'ops action list'"
echo "  multipass exec $MASTER_VM -- bash -lc 'ops invoke hello/hello name=World'"
