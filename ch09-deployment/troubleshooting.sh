#!/bin/bash
# troubleshooting.sh — Known issues and fixes for OpenServerless
# Chapter 9 — Mastering Apache OpenServerless
#
# Documents and fixes for known issues encountered on
# OpenServerless 0.1.0 on MicroK8s/Multipass.
#
# Usage:
#   ./troubleshooting.sh list           # list all known issues
#   ./troubleshooting.sh fix-cron       # fix cron scheduler credentials
#   ./troubleshooting.sh fix-static     # fix nuvolaris-static Init:0/1
#   ./troubleshooting.sh fix-operator   # restart operator after 401 error
#   ./troubleshooting.sh fix-wskprops   # regenerate ~/.wskprops

set -euo pipefail

NS="nuvolaris"
KUBECONFIG_PATH="/var/snap/microk8s/current/credentials/client.config"

# ── Issue list ───────────────────────────────────────────────────────────────
cmd_list() {
cat << 'EOF'
Known issues in OpenServerless 0.1.0:

  1. nuvolaris-static-0 stuck in Init:0/1
     Cause:  SeaweedFS not available — init container waits for
             seaweedfs.nuvolaris.svc.cluster.local
     Fix:    ./troubleshooting.sh fix-static

  2. Cron scheduler 401 Unauthorized after operator restart
     Cause:  CronJob cron-init uses controller_admin credentials
             which lack access to nuvolaris_whisks CouchDB database
     Symptom: "query failed with 401" in cron-init job logs
     Fix:    ./troubleshooting.sh fix-cron

  3. ops action list: "API host not valid"
     Cause:  ~/.wskprops missing or APIHOST wrong
     Fix:    ./troubleshooting.sh fix-wskprops

  4. Operator 401 Unauthorized (whisk-system)
     Cause:  OpenWhisk secrets regenerated but controller uses old ones
     Fix:    ./troubleshooting.sh fix-operator

  5. SeaweedFS not created despite being enabled in CRD
     Cause:  Bug in operator Python/Kopf — logs "seaweedfs=create"
             but pod/sts/svc are not created
     Fix:    ./troubleshooting.sh fix-seaweedfs

  6. FerretDB: "Unsupported authentication mechanism SCRAM-SHA-1/256"
     Cause:  FerretDB v1.6.0 only supports PLAIN auth
     Fix:    Use authMechanism='PLAIN', authSource='$external',
             and the PostgreSQL nuvolaris password (not MongoDB CRD password)

  7. PostgreSQL: "permission denied for schema public"
     Cause:  nuvolaris user lacks CREATE on schema public
     Fix:    ./troubleshooting.sh fix-postgres-grant

  8. SeaweedFS upload: "'dict' object has no attribute 'encode'"
     Cause:  put_object content must be string, not dict
     Fix:    Serialize with json.dumps() before upload
EOF
}

# ── Fix: cron scheduler credentials ─────────────────────────────────────────
cmd_fix_cron() {
    echo "=== Fix: Cron scheduler credentials (issue #2) ==="

    # Get whisk_admin credentials from CouchDB
    COUCH_PASS=$(kubectl exec -n "$NS" couchdb-0 -- \
        env 2>/dev/null | grep COUCHDB_PASSWORD | cut -d= -f2)

    WHISK_ADMIN_KEY=$(kubectl exec -n "$NS" couchdb-0 -- \
        curl -s "http://whisk_admin:${COUCH_PASS}@localhost:5984/${NS}_subjects/whisk-system" \
        2>/dev/null | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(d["uuid"]+":"+d["key"])' 2>/dev/null)

    echo "Patching cron-init CronJob with whisk_admin credentials..."
    # Get current env JSON and replace credentials
    CURRENT_ENV=$(kubectl get cronjob cron-init -n "$NS" \
        -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].env[0].value}')

    NEW_ENV=$(echo "$CURRENT_ENV" | python3 -c "
import sys, json
d = json.load(sys.stdin)
d['couchdb.controller.user'] = 'whisk_admin'
d['couchdb.controller.password'] = '${COUCH_PASS}'
print(json.dumps(d))
")

    kubectl patch cronjob cron-init -n "$NS" --type=json -p \
        "[{\"op\":\"replace\",\"path\":\"/spec/jobTemplate/spec/template/spec/containers/0/env/0/value\",\"value\":$(echo $NEW_ENV | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')}]"

    echo "Done. Verify with: kubectl logs -n $NS -l job-name --tail=20"
}

# ── Fix: nuvolaris-static Init:0/1 ──────────────────────────────────────────
cmd_fix_static() {
    echo "=== Fix: nuvolaris-static stuck in Init:0/1 (issue #1) ==="
    echo "Step 1: Enable SeaweedFS, disable MinIO in CRD"
    kubectl patch wsk/controller -n "$NS" --type=merge \
        -p '{"spec":{"components":{"minio":false,"seaweedfs":true,"static":false}}}'

    echo "Step 2: Restart operator"
    kubectl rollout restart statefulset nuvolaris-operator -n "$NS"

    echo "Step 3: Wait 30s for operator to reconcile..."
    sleep 30

    echo "Step 4: Force delete stuck static pod if present"
    kubectl delete pod nuvolaris-static-0 -n "$NS" \
        --grace-period=0 --force 2>/dev/null || true
    kubectl delete sts nuvolaris-static -n "$NS" 2>/dev/null || true

    echo "Step 5: Re-enable static"
    kubectl patch wsk/controller -n "$NS" --type=merge \
        -p '{"spec":{"components":{"static":true}}}'

    echo "Done. Watch: kubectl get pods -n $NS -w"
}

# ── Fix: operator 401 ────────────────────────────────────────────────────────
cmd_fix_operator() {
    echo "=== Fix: Operator 401 Unauthorized (issue #4) ==="
    echo "Restarting controller StatefulSet..."
    kubectl rollout restart statefulset controller -n "$NS"
    kubectl rollout status statefulset controller -n "$NS" --timeout=120s
    echo "Done."
}

# ── Fix: ~/.wskprops ─────────────────────────────────────────────────────────
cmd_fix_wskprops() {
    echo "=== Fix: Regenerate ~/.wskprops (issue #3) ==="
    COUCH_PASS=$(kubectl exec -n "$NS" couchdb-0 -- \
        env 2>/dev/null | grep COUCHDB_PASSWORD | cut -d= -f2)
    AUTH=$(kubectl exec -n "$NS" couchdb-0 -- \
        curl -s "http://whisk_admin:${COUCH_PASS}@localhost:5984/${NS}_subjects/nuvolaris" \
        2>/dev/null | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(d["uuid"]+":"+d["key"])')
    cat > ~/.wskprops << WSKEOF
APIHOST=http://localhost:30233
AUTH=$AUTH
NAMESPACE=nuvolaris
WSKEOF
    echo "~/.wskprops written:"
    cat ~/.wskprops
}

# ── Fix: SeaweedFS not created ────────────────────────────────────────────────
cmd_fix_seaweedfs() {
    echo "=== Fix: SeaweedFS not created by operator (issue #5) ==="
    echo "Step 1: Patch CRD"
    kubectl patch wsk/controller -n "$NS" --type=merge \
        -p '{"spec":{"components":{"minio":false,"seaweedfs":true}}}'
    echo "Step 2: Restart operator"
    kubectl rollout restart statefulset nuvolaris-operator -n "$NS"
    echo "Step 3: Apply SeaweedFS manifests manually from operator pod"
    sleep 15
    OPERATOR_POD=$(kubectl get pods -n "$NS" -l app=nuvolaris-operator \
        --no-headers -o custom-columns=NAME:.metadata.name | head -1)
    kubectl exec -n "$NS" "$OPERATOR_POD" -- \
        kubectl apply -f /home/nuvolaris/deploy/seaweedfs/ 2>/dev/null || \
        echo "Manual apply failed — manifests path may differ. Check operator pod."
    echo "Watch: kubectl get pods -n $NS -w"
}

# ── Fix: PostgreSQL schema grant ──────────────────────────────────────────────
cmd_fix_postgres_grant() {
    echo "=== Fix: PostgreSQL schema permissions (issue #7) ==="
    PG_ADMIN_PASS=$(kubectl get wsk/controller -n "$NS" \
        -o jsonpath='{.spec.postgres.admin.password}' 2>/dev/null || echo "")
    if [ -z "$PG_ADMIN_PASS" ]; then
        echo "Cannot read admin password from CRD. Check: kubectl get wsk/controller -n $NS -o yaml"
        return 1
    fi
    PGPASSWORD="$PG_ADMIN_PASS" psql \
        -U postgres \
        -d nuvolaris \
        -h "nuvolaris-postgres.${NS}.svc.cluster.local" \
        -c "GRANT ALL ON SCHEMA public TO nuvolaris;"
    echo "Done. Grant persists in database."
}

# ── Main ─────────────────────────────────────────────────────────────────────
CMD="${1:-list}"
case "$CMD" in
    list)                cmd_list ;;
    fix-cron)            cmd_fix_cron ;;
    fix-static)          cmd_fix_static ;;
    fix-operator)        cmd_fix_operator ;;
    fix-wskprops)        cmd_fix_wskprops ;;
    fix-seaweedfs)       cmd_fix_seaweedfs ;;
    fix-postgres-grant)  cmd_fix_postgres_grant ;;
    *)
        echo "Usage: $0 {list|fix-cron|fix-static|fix-operator|fix-wskprops|fix-seaweedfs|fix-postgres-grant}"
        exit 1
        ;;
esac
