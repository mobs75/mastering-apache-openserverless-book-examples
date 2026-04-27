#!/bin/bash
# setup-microk8s-multipass.sh — Deploy OpenServerless on MicroK8s + Multipass
# Chapter 9 — Mastering Apache OpenServerless
#
# Tested on: Hetzner VPS, Ubuntu 22.04, ops v0.1.0
# Architecture: 1 master + 3 worker nodes via Multipass VMs
#
# Usage:
#   chmod +x setup-microk8s-multipass.sh
#   ./setup-microk8s-multipass.sh
set -euo pipefail

MASTER_VM="k8s-master"
KUBECONFIG_PATH="/var/snap/microk8s/current/credentials/client.config"
NS="nuvolaris"

# Helper: run command on k8s-master with KUBECONFIG set
mk() {
    multipass exec "$MASTER_VM" -- bash -c \
        "export KUBECONFIG=$KUBECONFIG_PATH && $*"
}

echo "=== Step 1: Install ops CLI on k8s-master ==="
multipass exec "$MASTER_VM" -- bash -c \
    "curl -sL https://raw.githubusercontent.com/apache/openserverless/main/install.sh | bash && \
     echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc"

echo "=== Step 2: Configure API host ==="
multipass exec "$MASTER_VM" -- bash -c \
    "~/.local/bin/ops config apihost http://localhost:30233"

echo "=== Step 3: Deploy OpenServerless (initial deploy without SeaweedFS) ==="
multipass exec "$MASTER_VM" -- bash -c "
export OPERATOR_COMPONENT_REDIS=true
export OPERATOR_COMPONENT_MONGODB=true
export OPERATOR_COMPONENT_POSTGRES=true
export OPERATOR_COMPONENT_SEAWEEDFS=false   # Enable after initial deploy (see NOTE)
export OPERATOR_COMPONENT_STATIC=true
export OPERATOR_COMPONENT_CRON=true
export OPERATOR_COMPONENT_MINIO=false
cd ~/.ops/*/olaris/setup/kubernetes && ~/.local/bin/ops setup kubernetes deploy
"

echo "=== Step 4: Wait for core pods ==="
mk "microk8s kubectl wait --for=condition=ready pod \
    -l app=controller -n $NS --timeout=300s" || echo "WARN: timeout waiting for controller"

echo "=== Step 5: Retrieve credentials from CouchDB ==="
COUCH_PASS=$(multipass exec "$MASTER_VM" -- bash -c \
    "export KUBECONFIG=$KUBECONFIG_PATH && \
     microk8s kubectl exec -n $NS couchdb-0 -- env | grep COUCHDB_PASSWORD | cut -d= -f2")

echo "=== Step 6: Configure .wskprops ==="
multipass exec "$MASTER_VM" -- bash -c "
COUCH_PASS=$(mk "microk8s kubectl exec -n $NS couchdb-0 -- env | grep COUCHDB_PASSWORD | cut -d= -f2" 2>/dev/null || echo '')
AUTH=\$(microk8s kubectl exec -n $NS couchdb-0 -- \
    curl -s http://whisk_admin:\${COUCH_PASS}@localhost:5984/${NS}_subjects/nuvolaris \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[\"uuid\"]+\":\"+d[\"key\"])')
cat > ~/.wskprops << WSKEOF
APIHOST=http://localhost:30233
AUTH=\$AUTH
NAMESPACE=nuvolaris
WSKEOF
echo '.wskprops written'
"

echo "=== Done! Verify with: ==="
echo "  multipass exec k8s-master -- ~/.local/bin/ops action list"
echo ""
echo "NOTE: To enable SeaweedFS after initial deploy, run:"
echo "  multipass exec k8s-master -- microk8s kubectl patch wsk/controller -n $NS --type=merge \\"
echo "    -p '{\"spec\":{\"components\":{\"minio\":false,\"seaweedfs\":true}}}'"
