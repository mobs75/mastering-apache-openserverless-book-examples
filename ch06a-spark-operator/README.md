# ch06-spark-operator — Chapter 6
## Mastering Apache OpenServerless

Source files for the Spark Operator chapter.

## Structure

```
ch06-spark-operator/
├── plugin-spark/
│   ├── spark.py                          # Kopf operator: create/delete/patch + SparkJob handlers
│   └── templates/
│       ├── spark-configmap-tpl.yaml      # spark-defaults.conf ConfigMap
│       ├── spark-master-sts-tpl.yaml     # Master StatefulSet (stable DNS, readinessProbe)
│       ├── spark-worker-sts-tpl.yaml     # Worker StatefulSet (parametric, SPARK_PUBLIC_DNS)
│       ├── spark-history-dep-tpl.yaml    # History Server Deployment
│       ├── spark-history-pvc-tpl.yaml    # Shared PVC (pvc_access_mode configurable)
│       └── spark-nginx-proxy-tpl.yaml    # nginx reverse proxy (8 location blocks)
└── deploy/
    └── spark/
        └── 00-spark-rbac.yaml            # ServiceAccount + Role + RoleBinding
```

## SSH Tunnel and Web UI Access

```bash
# Open tunnel (replace with your cluster values)
lsof -ti:32080 | xargs kill -9 2>/dev/null
ssh -L 32080:10.115.160.209:32080 mobs75@135.181.161.34 -N &

# Add to /etc/hosts once
127.0.0.1  spark.local
```

| UI | URL |
|---|---|
| Spark Master | http://spark.local:32080/ |
| Worker 0 | http://spark.local:32080/worker-0/ |
| Worker 1 | http://spark.local:32080/worker-1/ |
| Worker 2 | http://spark.local:32080/worker-2/ |
| History Server | http://spark.local:32080/history/ |
| App jobs | http://spark.local:32080/history/<APP_ID>/jobs/ |
| App stages | http://spark.local:32080/history/<APP_ID>/stages/ |
| App executors | http://spark.local:32080/history/<APP_ID>/executors/ |

## Known Bugs (feature/spark-integration branch)

| # | Location | Symptom | Fix |
|---|---|---|---|
| 1 | scale_workers(), get_cluster_info() | TypeError: default= instead of defval= | Replace default= with defval= |
| 2 | create() templates_filter | No worker pods deployed | Add spark-worker-sts.yaml to processing |
| 3 | spark-history-pvc-tpl.yaml | PVC RWO fails on multi-node | Fixed: {{pvc_access_mode}} variable |
