# ch06-spark-operator — Chapter 6
## Mastering Apache OpenServerless

Source files for the Spark Operator case study of Chapter 6.

> **Note** Spark is **not** part of the official Apache OpenServerless
> distribution. These files come from the author's fork of the operator
> (`mobs75/openserverless-operator`, branch
> `feature/spark-reconciliation-plus-main`, commit `cf0e986`), which predates
> the 0.9.0-incubating rebranding: this is why the Python package and the
> template paths still use the `nuvolaris` name. In the fork, `plugin-spark/`
> corresponds to the `nuvolaris/` package and `nuvolaris/templates/`.
>
> If you need Spark in an OpenServerless installation today, the approach
> suggested by the project maintainers is to install it in the same
> Kubernetes cluster through Kubeflow (SparkApplication CRD) and to integrate
> it with an ops CLI plugin, as discussed in Chapter 5. For new platform
> components, follow the Streamer pattern described in Chapter 5.

## Structure

```
ch06-spark-operator/
├── plugin-spark/
│   ├── spark.py                          # Kopf operator: create/delete/patch + SparkJob handlers
│   ├── spark_notifier.py                 # SparkJob status notifications
│   └── templates/
│       ├── spark-configmap-tpl.yaml      # spark-defaults.conf ConfigMap
│       ├── spark-master-sts-tpl.yaml     # Master StatefulSet (stable DNS, readinessProbe)
│       ├── spark-worker-sts-tpl.yaml     # Worker StatefulSet (parametric, SPARK_PUBLIC_DNS)
│       ├── spark-history-dep-tpl.yaml    # History Server Deployment
│       ├── spark-history-pvc-tpl.yaml    # Shared PVC (pvc_access_mode configurable)
│       ├── spark-nginx-proxy-tpl.yaml    # nginx reverse proxy for the Web UIs
│       ├── sparkjob-driver-tpl.yaml      # Driver Job created for each SparkJob
│       ├── spark-rbac.yaml               # RBAC used by the templates
│       ├── spark-watcher-deployment.yaml.j2
│       └── spark-reconciler-cronjob.yaml.j2
├── deploy/
│   └── spark/
│       ├── 00-spark-rbac.yaml            # ServiceAccount + Role + RoleBinding
│       ├── 01..08-*.yaml                 # base manifests (configmap, PVC, master, workers, history)
│       └── spark-crd-extension.yaml      # SparkJob CRD extension
└── services/                             # client examples for the platform services
```

## SSH Tunnel and Web UI Access

```bash
# Open tunnel (replace the placeholders with your cluster values)
lsof -ti:32080 | xargs kill -9 2>/dev/null
ssh -L 32080:<cluster-node-ip>:32080 <user>@<server-ip> -N &

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

## Bugs Found During Development (resolved in the fork)

| # | Location | Symptom | Fix |
|---|---|---|---|
| 1 | scale_workers(), get_cluster_info() | TypeError: default= instead of defval= | Replaced default= with defval= |
| 2 | create() templates_filter | No worker pods deployed | spark-worker-sts.yaml added to processing |
| 3 | spark-history-pvc-tpl.yaml | PVC RWO fails on multi-node | {{pvc_access_mode}} variable |
