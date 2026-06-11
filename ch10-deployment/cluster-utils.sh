#!/bin/bash
# cluster-utils.sh — Daily utility commands for OpenServerless
# Chapter 9 — Mastering Apache OpenServerless
#
# A collection of useful one-liners and functions for operating
# an OpenServerless cluster on MicroK8s/Multipass.
#
# Usage:
#   source cluster-utils.sh     # load all functions in current shell
#   mk <command>                # run kubectl on k8s-master via Multipass
#   ows-pods                    # show all nuvolaris pods
#   ows-logs <pod>              # tail logs of a pod
#   ows-restart <component>     # restart a component
#   ows-enable <component>      # enable a component in Whisk CRD
#   ows-disable <component>     # disable a component in Whisk CRD
#   ows-status                  # full cluster status

NS="nuvolaris"
KUBECONFIG_PATH="/var/snap/microk8s/current/credentials/client.config"

# ── Multipass helper ─────────────────────────────────────────────────────────
# Run kubectl on k8s-master via Multipass
mk() {
    multipass exec k8s-master -- bash -c \
        "export KUBECONFIG=$KUBECONFIG_PATH && microk8s kubectl $*"
}

# ── Pod management ───────────────────────────────────────────────────────────
ows-pods() {
    echo "=== All pods in namespace: $NS ==="
    kubectl get pods -n "$NS" -o wide
}

ows-logs() {
    local pod="${1:-}"
    local lines="${2:-100}"
    if [ -z "$pod" ]; then
        echo "Usage: ows-logs <pod-name> [lines]"
        echo "Available pods:"
        kubectl get pods -n "$NS" --no-headers -o custom-columns=NAME:.metadata.name
        return 1
    fi
    kubectl logs -n "$NS" "$pod" --tail="$lines" -f
}

ows-logs-operator() {
    echo "=== Operator logs (last 5 min) ==="
    kubectl logs -n "$NS" nuvolaris-operator-0 --since=5m
}

ows-logs-controller() {
    echo "=== Controller logs (last 5 min) ==="
    kubectl logs -n "$NS" controller-0 --since=5m
}

# ── Component management ─────────────────────────────────────────────────────
ows-enable() {
    local component="${1:-}"
    if [ -z "$component" ]; then
        echo "Usage: ows-enable <component>"
        echo "Components: redis mongodb postgres seaweedfs minio kafka cron static"
        return 1
    fi
    echo "Enabling $component..."
    kubectl patch wsk/controller -n "$NS" --type=merge \
        -p "{\"spec\":{\"components\":{\"$component\":true}}}"
    echo "Done. Watch: kubectl get pods -n $NS -w"
}

ows-disable() {
    local component="${1:-}"
    if [ -z "$component" ]; then
        echo "Usage: ows-disable <component>"
        return 1
    fi
    echo "Disabling $component..."
    kubectl patch wsk/controller -n "$NS" --type=merge \
        -p "{\"spec\":{\"components\":{\"$component\":false}}}"
}

ows-components() {
    echo "=== Active components ==="
    kubectl get wsk/controller -n "$NS" -o jsonpath='{.spec.components}' | \
        python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  {k}: {v}') for k,v in sorted(d.items())]"
}

# ── Restart helpers ──────────────────────────────────────────────────────────
ows-restart() {
    local component="${1:-}"
    if [ -z "$component" ]; then
        echo "Usage: ows-restart <operator|controller|redis|couchdb|kafka|postgres>"
        return 1
    fi
    case "$component" in
        operator)   kubectl rollout restart statefulset nuvolaris-operator -n "$NS" ;;
        controller) kubectl rollout restart statefulset controller -n "$NS" ;;
        redis)      kubectl rollout restart statefulset redis -n "$NS" ;;
        couchdb)    kubectl rollout restart statefulset couchdb -n "$NS" ;;
        kafka)      kubectl rollout restart statefulset kafka-0 -n "$NS" 2>/dev/null || \
                    kubectl delete pod kafka-0 -n "$NS" ;;
        postgres)   kubectl rollout restart statefulset nuvolaris-postgresql -n "$NS" ;;
        *)          echo "Unknown component: $component" ; return 1 ;;
    esac
    echo "Restarting $component... watch with: kubectl get pods -n $NS -w"
}

# ── Service connectivity checks ───────────────────────────────────────────────
ows-check() {
    echo "=== Service connectivity ==="

    echo -n "Controller API:  "
    curl -s http://localhost:30233/api/v1 | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print('OK — v' + d.get('api_version','?'))" \
        2>/dev/null || echo "FAIL"

    echo -n "CouchDB:         "
    kubectl exec -n "$NS" couchdb-0 -- \
        curl -s http://localhost:5984 2>/dev/null | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print('OK — ' + d.get('couchdb','?'))" \
        2>/dev/null || echo "FAIL"

    echo -n "Redis:           "
    kubectl exec -n "$NS" redis-0 -- redis-cli ping 2>/dev/null || echo "FAIL"

    echo -n "PostgreSQL:      "
    kubectl get pod -n "$NS" -l app=nuvolaris-postgresql \
        --no-headers 2>/dev/null | awk '{print "OK — " $1 " " $3}' || echo "not deployed"

    echo -n "SeaweedFS:       "
    kubectl get pod -n "$NS" -l app=seaweedfs \
        --no-headers 2>/dev/null | awk '{print "OK — " $1 " " $3}' || echo "not deployed"

    echo -n "Kafka:           "
    kubectl get pod -n "$NS" kafka-0 \
        --no-headers 2>/dev/null | awk '{print "OK — " $3}' || echo "not deployed"
}

# ── Full status ───────────────────────────────────────────────────────────────
ows-status() {
    ows-pods
    echo ""
    ows-components
    echo ""
    ows-check
}

# ── wskprops helpers ──────────────────────────────────────────────────────────
ows-whoami() {
    echo "=== Current ops/wsk configuration ==="
    if [ -f ~/.wskprops ]; then
        cat ~/.wskprops
    else
        echo "~/.wskprops not found"
    fi
    echo ""
    echo "ops config:"
    ops config get 2>/dev/null || echo "ops not configured"
}

ows-action-test() {
    local name="verify-$$"
    echo "=== Quick action smoke test ==="
    cat > /tmp/verify-action.py << 'PYEOF'
def main(args):
    return {'body': 'Hello ' + args.get('name', 'OpenServerless')}
PYEOF
    ops action create "$name" /tmp/verify-action.py --kind python:3.11 2>/dev/null
    RESULT=$(ops action invoke "$name" --result --param name World 2>/dev/null)
    ops action delete "$name" 2>/dev/null
    rm -f /tmp/verify-action.py
    echo "Result: $RESULT"
    echo "$RESULT" | grep -q "Hello World" && echo "✅ OK" || echo "❌ FAIL"
}

# ── Runtime inspection ────────────────────────────────────────────────────────
ows-runtime-libs() {
    echo "=== Libraries available in python:3.11 runtime ==="
    POD=$(kubectl get pods -n "$NS" --no-headers \
        -o custom-columns=NAME:.metadata.name | grep prewarm-python | head -1)
    if [ -z "$POD" ]; then
        echo "No prewarm python pod found — invoke an action first to warm up the runtime"
        return 1
    fi
    kubectl exec -n "$NS" "$POD" -- pip list 2>/dev/null | \
        grep -iE 'psycopg|redis|mongo|kafka|requests|boto|pymongo|numpy|pandas'
}

echo "cluster-utils.sh loaded. Available commands:"
echo "  ows-status        full cluster status"
echo "  ows-pods          list all pods"
echo "  ows-logs <pod>    tail pod logs"
echo "  ows-check         service connectivity"
echo "  ows-components    show active components"
echo "  ows-enable  <c>   enable a component"
echo "  ows-disable <c>   disable a component"
echo "  ows-restart <c>   restart a component"
echo "  ows-whoami        show current credentials"
echo "  ows-action-test   quick smoke test"
echo "  ows-runtime-libs  list python:3.11 libraries"
echo "  mk <kubectl cmd>  run kubectl via Multipass"
