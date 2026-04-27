#!/bin/bash
# verify-cluster.sh — Verify OpenServerless cluster health end-to-end
# Chapter 9 — Mastering Apache OpenServerless
set -euo pipefail

KUBECONFIG_PATH="/var/snap/microk8s/current/credentials/client.config"
NS="nuvolaris"

mk() { multipass exec k8s-master -- bash -c "export KUBECONFIG=$KUBECONFIG_PATH && $*"; }

echo "=== Pod status ==="
mk "microk8s kubectl get pods -n $NS"

echo ""
echo "=== Services ==="
mk "microk8s kubectl get svc -n $NS"

echo ""
echo "=== CRD Whisk active components ==="
mk "microk8s kubectl get wsk/controller -n $NS -o yaml | grep -A 20 'components:'"

echo ""
echo "=== Controller API ping ==="
mk "curl -s http://localhost:30233/api/v1 | python3 -m json.tool" \
    || echo "WARN: controller not responding on port 30233"

echo ""
echo "=== Hello World smoke test ==="
mk "cat > /tmp/hello-verify.py << 'PYEOF'
def main(args):
    return {'body': 'Hello ' + args.get('name', 'OpenServerless')}
PYEOF"

mk "~/.local/bin/ops action create verify-hello /tmp/hello-verify.py \
    --kind python:3.11 2>/dev/null || \
    ~/.local/bin/ops action update verify-hello /tmp/hello-verify.py \
    --kind python:3.11"

RESULT=$(mk "~/.local/bin/ops action invoke verify-hello \
    --result --param name World 2>/dev/null")
echo "Result: $RESULT"

# Cleanup
mk "~/.local/bin/ops action delete verify-hello 2>/dev/null || true"

echo ""
echo "=== Service connectivity ==="
echo -n "Redis: "
mk "microk8s kubectl exec -n $NS redis-0 -- redis-cli ping 2>/dev/null" || echo "not ready"

echo -n "CouchDB: "
mk "microk8s kubectl exec -n $NS couchdb-0 -- \
    curl -s http://localhost:5984 | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[\"couchdb\"])'" \
    || echo "not ready"

echo ""
echo "=== All checks complete ==="
