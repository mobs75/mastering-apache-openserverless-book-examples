# Mastering Apache OpenServerless — Book Examples

Code examples for the book **"Mastering Apache OpenServerless: Building Modern Serverless Platforms on Kubernetes"** (Apress).

## Structure

| Directory | Chapter | Topic |
|-----------|---------|-------|
| ch04-plugins-operators/ | Chapter 4 | Plugins, Services and Operators in Apache OpenServerless |
| ch05-streaming/ | Chapter 5 | The Streaming Model and Event-Driven Execution |
| ch06-spark-operator/ | Chapter 6 | Spark Operator Development in Apache OpenServerless (case study) |
| ch07-ops-cli/ | Chapter 7 | The OpenServerless ops CLI |
| ch08-core-repository/ | Chapter 8 | The OpenServerless Core Repository |
| ch09-deployment/ | Chapter 9 | Deploying Apache OpenServerless |
| ch10-runtimes/ | Chapter 10 | OpenServerless Runtimes |
| ch11-development-workflow/ | Chapter 11 | Development Workflow in Apache OpenServerless |
| ch12-security/ | Chapter 12 | Security in OpenServerless and the ops CLI |
| ch13-engine-room/ | Chapter 13 | Engine Room |

Chapters 1–3 are conceptual and have no companion code.

## Requirements

- Apache OpenServerless 0.9.0-incubating
- The `ops` CLI, installed as described in the official guide:
  https://openserverless.apache.org/docs/installation/install-cli/
  (for example: `go install github.com/apache/openserverless-cli/cmd/ops@0.9.0`)
- kubectl and a Kubernetes cluster (or Docker, for `ops setup mini` / `ops setup devcluster`)

## Notes

- The examples follow the 0.9.0-incubating naming: namespace `openserverless`,
  CRD group `openserverless.org`, operator `openserverless-operator`,
  SeaweedFS as the S3-compatible object storage (MinIO is no longer used),
  and the `oplugins` task bundle.
- **Spark is not part of the official Apache OpenServerless distribution.**
  The files in `ch06-spark-operator/` come from the author's fork of the
  operator and are provided as a case study; see the README in that folder.
- The examples were developed on a MicroK8s cluster running on Multipass VMs;
  replace hostnames, IP addresses, and user names with the values of your
  own environment.
