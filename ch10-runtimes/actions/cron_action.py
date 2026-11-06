"""
cron_action.py — Action scheduled automatically by the OpenServerless cron scheduler.
Chapter 10 — Mastering Apache OpenServerless

The cron scheduler is a Kubernetes CronJob (cron-init) that runs every minute.
It scans CouchDB for actions annotated with 'cron' and invokes them according
to the cron expression. It is an optional component: enable it with
    ops config enable --cron
    ops update apply

Deploy with cron annotation:
    ops action create my-cron-job cron_action.py \
        --kind python:3.11 \
        -a cron '* * * * *'

Deploy with autoexec (runs once at startup):
    ops action create my-startup-job cron_action.py \
        --kind python:3.11 \
        -a autoexec true

Verify the cron scheduler is running:
    kubectl get cronjob cron-init -n openserverless

Verify automatic invocations:
    ops activation list --limit 10
"""
import datetime
import os


def main(args: dict) -> dict:
    """
    Example cron action.
    Called automatically every minute by the cron scheduler.
    args may contain parameters set at deploy time with --param.
    """
    now       = datetime.datetime.utcnow().isoformat()
    task_name = args.get('task', 'default-task')

    print(f'[cron] {now} — executing task: {task_name}')

    # Your scheduled logic here:
    # - cleanup expired records
    # - poll external APIs
    # - generate periodic reports
    # - trigger downstream actions

    return {
        'status':    'ok',
        'task':      task_name,
        'executed_at': now,
    }
