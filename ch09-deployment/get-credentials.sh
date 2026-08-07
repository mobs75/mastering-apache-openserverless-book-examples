#!/bin/bash
# get-credentials.sh — Retrieve credentials for all OpenServerless services
# Chapter 9 — Mastering Apache OpenServerless
#
# Reads all passwords and connection strings directly from the Whisk CRD
# and from CouchDB. Run this after every deploy because credentials
# are regenerated each time.
#
# Usage:
#   chmod +x get-credentials.sh
#   ./get-credentials.sh              # print all credentials
#   ./get-credentials.sh --wskprops   # also write ~/.wskprops
#   ./get-credentials.sh --env        # print as export statements
#
# Requirements:
#   - kubectl configured and pointing to the nuvolaris namespace
#   - jq installed (apt install jq / brew install jq)

set -euo pipefail

NS="nuvolaris"
WRITE_WSKPROPS=false
ENV_FORMAT=false

for arg in "$@"; do
  case $arg in
    --wskprops) WRITE_WSKPROPS=true ;;
    --env)      ENV_FORMAT=true ;;
  esac
done

# ── Helper ──────────────────────────────────────────────────────────────────
get_crd() {
    kubectl get wsk/controller -n "$NS" -o jsonpath="$1" 2>/dev/null || echo ""
}

section() { echo ""; echo "══════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════"; }

# ── OpenWhisk / ops CLI ──────────────────────────────────────────────────────
section "OpenWhisk / ops CLI"

COUCH_PASS=$(kubectl exec -n "$NS" couchdb-0 -- \
    env 2>/dev/null | grep COUCHDB_PASSWORD | cut -d= -f2 || echo "")

if [ -n "$COUCH_PASS" ]; then
    AUTH=$(kubectl exec -n "$NS" couchdb-0 -- \
        curl -s "http://whisk_admin:${COUCH_PASS}@localhost:5984/${NS}_subjects/nuvolaris" \
        2>/dev/null | python3 -c \
        'import sys,json; d=json.load(sys.stdin); print(d["uuid"]+":"+d["key"])' \
        2>/dev/null || echo "")
else
    AUTH=""
fi

APIHOST="http://localhost:30233"

echo "APIHOST   = $APIHOST"
echo "AUTH      = $AUTH"
echo "NAMESPACE = $NS"

if [ "$WRITE_WSKPROPS" = true ] && [ -n "$AUTH" ]; then
    cat > ~/.wskprops << WSKEOF
APIHOST=$APIHOST
AUTH=$AUTH
NAMESPACE=$NS
WSKEOF
    echo "→ ~/.wskprops written"
fi

# ── CouchDB ──────────────────────────────────────────────────────────────────
section "CouchDB"
COUCH_USER="whisk_admin"
echo "HOST      = couchdb.${NS}.svc.cluster.local:5984"
echo "USER      = $COUCH_USER"
echo "PASSWORD  = $COUCH_PASS"
echo "URL       = http://${COUCH_USER}:${COUCH_PASS}@couchdb.${NS}.svc.cluster.local:5984"

# ── Redis ────────────────────────────────────────────────────────────────────
section "Redis"
REDIS_PASS=$(get_crd '{.spec.redis.nuvolaris.password}')
echo "HOST      = redis.${NS}.svc.cluster.local:6379"
echo "PASSWORD  = $REDIS_PASS"
echo "URL       = redis://:${REDIS_PASS}@redis.${NS}.svc.cluster.local:6379"

# ── PostgreSQL ───────────────────────────────────────────────────────────────
section "PostgreSQL"
PG_PASS=$(get_crd '{.spec.postgres.nuvolaris.password}')
PG_ADMIN_PASS=$(get_crd '{.spec.postgres.admin.password}')
echo "HOST      = nuvolaris-postgres.${NS}.svc.cluster.local:5432"
echo "DATABASE  = nuvolaris"
echo "USER      = nuvolaris"
echo "PASSWORD  = $PG_PASS"
echo "ADMIN_PWD = $PG_ADMIN_PASS"
echo "URL       = postgresql://nuvolaris:${PG_PASS}@nuvolaris-postgres.${NS}.svc.cluster.local:5432/nuvolaris"
echo ""
echo "NOTE: Run once after deploy to grant schema permissions:"
echo "  PGPASSWORD=$PG_ADMIN_PASS psql -U postgres -d nuvolaris \\"
echo "    -h nuvolaris-postgres.${NS}.svc.cluster.local \\"
echo "    -c \"GRANT ALL ON SCHEMA public TO nuvolaris;\""

# ── FerretDB / MongoDB ───────────────────────────────────────────────────────
section "FerretDB / MongoDB"
echo "HOST      = nuvolaris-mongodb-svc.${NS}.svc.cluster.local:27017"
echo "USER      = nuvolaris"
echo "PASSWORD  = $PG_PASS  (same as PostgreSQL nuvolaris password)"
echo "AUTH_MECH = PLAIN (not SCRAM — FerretDB v1.6.0 limitation)"
echo "URL       = mongodb://nuvolaris:${PG_PASS}@nuvolaris-mongodb-svc.${NS}.svc.cluster.local:27017/?authSource=\$external&authMechanism=PLAIN"

# ── SeaweedFS / S3 ───────────────────────────────────────────────────────────
section "SeaweedFS / S3"
SEAWEED_PASS=$(get_crd '{.spec.seaweedfs.nuvolaris.password}')
echo "ENDPOINT  = http://seaweedfs.${NS}.svc.cluster.local:9000"
echo "ACCESS_KEY= nuvolaris"
echo "SECRET_KEY= $SEAWEED_PASS"
echo "NOTE: signature_version='s3v4' required, region_name='us-east-1' (ignored by SeaweedFS)"

# ── Kafka ────────────────────────────────────────────────────────────────────
section "Kafka"
echo "BROKER    = kafka.${NS}.svc.cluster.local:9092"
echo "NOTE: No authentication. Use application-specific topic names (not internal OW topics)"
echo "INTERNAL TOPICS (do NOT use): _completed0, health, ..."

# ── MinIO (if enabled) ───────────────────────────────────────────────────────
section "MinIO (if enabled)"
MINIO_PASS=$(get_crd '{.spec.minio.nuvolaris.password}')
if [ -n "$MINIO_PASS" ]; then
    echo "ENDPOINT  = http://minio.${NS}.svc.cluster.local:9000"
    echo "ACCESS_KEY= nuvolaris"
    echo "SECRET_KEY= $MINIO_PASS"
else
    echo "MinIO not enabled or not deployed (replaced by SeaweedFS)"
fi

# ── ENV format output ────────────────────────────────────────────────────────
if [ "$ENV_FORMAT" = true ]; then
    section "Export statements (copy-paste into your shell or .env)"
    echo "export OW_APIHOST=$APIHOST"
    echo "export OW_AUTH=$AUTH"
    echo "export REDIS_PASSWORD=$REDIS_PASS"
    echo "export PG_PASSWORD=$PG_PASS"
    echo "export PG_ADMIN_PASSWORD=$PG_ADMIN_PASS"
    echo "export MONGO_PASSWORD=$PG_PASS"
    echo "export S3_SECRET_KEY=$SEAWEED_PASS"
    echo "export S3_ENDPOINT=http://seaweedfs.${NS}.svc.cluster.local:9000"
    echo "export KAFKA_BROKER=kafka.${NS}.svc.cluster.local:9092"
fi

echo ""
echo "Done. Credentials change after every ops deploy."
