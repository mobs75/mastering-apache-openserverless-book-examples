"""
Apache Spark Operator for OpenServerless
Chapter 6 — Mastering Apache OpenServerless
"""
import kopf, logging, time, subprocess
import nuvolaris.kustomize as kus
import nuvolaris.kube as kube
import nuvolaris.config as cfg
import nuvolaris.util as util
import nuvolaris.operator_util as operator_util


def get_spark_config_data():
    namespace = cfg.get('nuvolaris.namespace', defval='nuvolaris')
    data = {
        "name": "spark", "namespace": namespace,
        "spark_image": cfg.get('spark.image', defval='apache/spark:3.5.0'),
        "spark_version": cfg.get('spark.version', defval='3.5.0'),
        "master_replicas": cfg.get('spark.master.replicas', defval=1),
        "master_memory": cfg.get('spark.master.memory', defval='1g'),
        "master_cpu": cfg.get('spark.master.cpu', defval='1000m'),
        "master_port": cfg.get('spark.master.port', defval=7077),
        "master_webui_port": cfg.get('spark.master.webui-port', defval=8080),
        "worker_replicas": cfg.get('spark.worker.replicas', defval=3),
        "worker_memory": cfg.get('spark.worker.memory', defval='2g'),
        "worker_container_memory": cfg.get('spark.worker.container-memory', defval='3Gi'),
        "worker_cpu": cfg.get('spark.worker.cpu', defval='2000m'),
        "worker_cores": cfg.get('spark.worker.cores', defval=2),
        "worker_webui_port": cfg.get('spark.worker.webui-port', defval=8081),
        "history_enabled": cfg.get('spark.history-server.enabled', defval=True),
        "history_port": cfg.get('spark.history-server.port', defval=18080),
        "history_volume_size": cfg.get('spark.history-server.volume-size', defval=10),
        "event_log_enabled": cfg.get('spark.event-log.enabled', defval=True),
        "event_log_dir": cfg.get('spark.event-log.dir', defval='/tmp/spark-events'),
        "storage_class": cfg.get("nuvolaris.storageclass"),
        "ha_enabled": cfg.get('spark.ha.enabled', defval=False),
        "ha_zookeeper_url": cfg.get('spark.ha.zookeeper-url', defval=''),
        "affinity": cfg.get('affinity', defval=False),
        "tolerations": cfg.get('tolerations', defval=False),
        "spark_uid": cfg.get('spark.uid', defval=185),
        "pvc_access_mode": cfg.get('spark.pvc-access-mode', defval='ReadWriteOnce'),
    }
    util.couch_affinity_tolerations_data(data)
    return data


def create(owner=None):
    logging.info("*** creating spark cluster")
    data = get_spark_config_data()
    kus.processTemplate("spark", "spark-configmap-tpl.yaml", data, "spark-configmap.yaml")
    kus.processTemplate("spark", "spark-master-sts-tpl.yaml", data, "spark-master-sts.yaml")
    kus.processTemplate("spark", "spark-worker-sts-tpl.yaml", data, "spark-worker-sts.yaml")
    kus.processTemplate("spark", "spark-nginx-proxy-tpl.yaml", data, "spark-nginx-proxy.yaml")
    if data['history_enabled']:
        kus.processTemplate("spark", "spark-history-pvc-tpl.yaml", data, "spark-history-pvc.yaml")
        kus.processTemplate("spark", "spark-history-dep-tpl.yaml", data, "spark-history-dep.yaml")
    tplp = []
    if data.get('affinity') or data.get('tolerations'):
        tplp.append("affinity-tolerance-sts-core-attach.yaml")
    kust = kus.patchTemplates("spark", tplp, data) if tplp else ""
    templates = ["spark-rbac.yaml"]
    templates_filter = [
        "spark-configmap.yaml", "spark-master-sts.yaml", "spark-worker-sts.yaml",
        "04-spark-master-svc.yaml", "06-spark-worker-svc.yaml", "08-spark-history-svc.yaml",
        "spark-nginx-proxy.yaml"
    ]
    if data['history_enabled']:
        templates_filter.extend(["spark-history-pvc.yaml", "spark-history-dep.yaml"])
    spec = kus.restricted_kustom_list("spark", kust, templates=templates,
                                      templates_filter=templates_filter, data=data)
    if owner:
        kopf.append_owner_reference(spec['items'], owner)
    else:
        cfg.put("state.spark.spec", spec)
    res = kube.apply(spec)
    util.wait_for_pod_ready(
        "{.items[?(@.metadata.labels.component == 'spark-master')].metadata.name}",
        timeout="300s"
    )
    configure_spark(data)
    return res


def delete(owner=None):
    logging.info("*** deleting spark cluster")
    spec = kus.build("spark") if owner else cfg.get("state.spark.spec")
    if spec:
        return kube.delete(spec)
    logging.warning("no spark spec found")
    return False


def patch(status, action, owner=None):
    try:
        if action == 'create':
            create(owner)
            operator_util.patch_operator_status(status, 'spark', 'on')
        else:
            delete(owner)
            operator_util.patch_operator_status(status, 'spark', 'off')
    except Exception as e:
        logging.error(f'*** failed to {action} spark: {e}')
        operator_util.patch_operator_status(status, 'spark', 'error')
        raise


def configure_spark(data):
    namespace = data['namespace']
    for attempt in range(12):
        try:
            result = subprocess.run(
                ['kubectl', 'exec', '-n', namespace, 'spark-master-0', '--',
                 'curl', '-s', 'http://localhost:8080/json/'],
                capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                if len(info.get('workers', [])) >= data['worker_replicas']:
                    break
        except Exception as e:
            logging.warning(f"attempt {attempt+1}/12: {e}")
        time.sleep(5)
    if data['event_log_enabled'] and data['history_enabled']:
        subprocess.run(['kubectl', 'exec', '-n', namespace,
                        'deployment/spark-history', '--',
                        'mkdir', '-p', data['event_log_dir']],
                       capture_output=True, text=True)


@kopf.on.create('nuvolaris.org', 'v1', 'sparkjobs')
def create_sparkjob(spec, name, namespace, status, **kwargs):
    logging.info(f"*** creating SparkJob {name}")
    try:
        job_config = _validate_sparkjob_spec(spec, name)
        driver_job = _create_spark_driver_job(job_config, name, namespace)
        kube.apply(driver_job)
        app_id = _get_spark_application_id(name, namespace)
        return _build_sparkjob_status('Running', 'SparkJob submitted',
                                      app_id=app_id, start_time=True, existing_status=status)
    except Exception as e:
        return _build_sparkjob_status('Failed', str(e), existing_status=status)


@kopf.on.delete('nuvolaris.org', 'v1', 'sparkjobs')
def delete_sparkjob(spec, name, namespace, **kwargs):
    try:
        kube.delete({'apiVersion': 'batch/v1', 'kind': 'Job',
                     'metadata': {'name': f"{name}-driver", 'namespace': namespace}})
    except Exception as e:
        logging.warning(f'cleanup: {e}')


@kopf.on.field('nuvolaris.org', 'v1', 'sparkjobs', field='spec')
def update_sparkjob(old, new, name, **kwargs):
    return {'message': 'delete and recreate to apply changes'}


def _validate_sparkjob_spec(spec, job_name):
    config = {'name': job_name, 'application': {},
              'spark': {'master': 'spark://spark-master:7077', 'conf': {},
                        'driver': {'cores': 0.5, 'memory': '512m', 'serviceAccount': 'spark'},
                        'executor': {'instances': 2, 'cores': 1, 'memory': '1g'}},
              'execution': {'restartPolicy': 'OnFailure', 'timeout': 3600, 'backoffLimit': 3},
              'dependencies': {'jars': [], 'files': [], 'pyFiles': []},
              'monitoring': {'enabled': True, 'eventLog': True, 'historyServer': True}}
    def merge(t, s):
        for k, v in s.items():
            if isinstance(v, dict) and k in t: merge(t[k], v)
            else: t[k] = v
    if spec: merge(config, spec)
    if not config['application'].get('mainApplicationFile'):
        raise ValueError("application.mainApplicationFile is required")
    return config


def _create_spark_driver_job(cfg_data, job_name, namespace):
    app, spark, exe, deps, mon = (cfg_data['application'], cfg_data['spark'],
                                   cfg_data['execution'], cfg_data['dependencies'],
                                   cfg_data['monitoring'])
    def jvm(m): return m[:-2]+'g' if m.endswith('Gi') else m[:-2]+'m' if m.endswith('Mi') else m
    parts = [
        '/opt/spark/bin/spark-submit',
        '--master', spark['master'], '--name', job_name,
        '--driver-memory', jvm(spark['driver']['memory']),
        '--num-executors', str(spark['executor']['instances']),
        '--executor-cores', str(spark['executor']['cores']),
        '--executor-memory', jvm(spark['executor']['memory']),
        '--deploy-mode', 'client',
        '--conf', 'spark.driver.bindAddress=0.0.0.0',
        '--conf', 'spark.driver.host=$MY_POD_IP',
    ]
    if mon['eventLog']: parts += ['--conf','spark.eventLog.enabled=true','--conf','spark.eventLog.dir=/tmp/spark-events']
    for k, v in spark['conf'].items(): parts += ['--conf', f'{k}={v}']
    if deps['jars']: parts += ['--jars', ','.join(deps['jars'])]
    if app.get('mainClass'): parts += ['--class', app['mainClass']]
    parts.append(app['mainApplicationFile'])
    if app.get('arguments'): parts += app['arguments']
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': f"{job_name}-driver", 'namespace': namespace,
                        'labels': {'sparkjob': job_name}},
           'spec': {'backoffLimit': exe['backoffLimit'],
                    'activeDeadlineSeconds': exe['timeout'],
                    'template': {'spec': {
                        'restartPolicy': exe['restartPolicy'],
                        'serviceAccountName': spark['driver']['serviceAccount'],
                        'containers': [{'name': 'spark-driver',
                                        'image': cfg.get('spark.image', defval='apache/spark:3.5.0'),
                                        'command': ['/bin/bash','-c'], 'args': [' '.join(parts)],
                                        'env': [{'name':'SPARK_USER','value':'spark'},
                                                {'name':'MY_POD_IP','valueFrom':{'fieldRef':{'fieldPath':'status.podIP'}}}],
                                        'volumeMounts': []}],
                        'volumes': []}}}}
    if mon['eventLog'] and mon['historyServer']:
        job['spec']['template']['spec']['containers'][0]['volumeMounts'].append(
            {'name':'spark-events','mountPath':'/tmp/spark-events'})
        job['spec']['template']['spec']['volumes'].append(
            {'name':'spark-events','persistentVolumeClaim':{'claimName':'spark-history-pvc'}})
    return job


def _build_sparkjob_status(phase, message, app_id=None, start_time=False, existing_status=None):
    import datetime
    s = existing_status.copy() if existing_status else {}
    s['phase'] = phase; s['message'] = message
    if app_id: s['applicationId'] = app_id
    if start_time: s['startTime'] = datetime.datetime.utcnow().isoformat()+'Z'
    return s


def _get_spark_application_id(job_name, namespace):
    try:
        time.sleep(5)
        r = subprocess.run(['kubectl','logs','-n',namespace,f'job/{job_name}-driver','--tail=100'],
                           capture_output=True,text=True,timeout=30)
        if r.returncode == 0:
            for line in r.stdout.split('\n'):
                if 'Submitted application' in line:
                    for p in line.split():
                        if p.startswith('application_'): return p
    except: pass
    return f"application_{int(time.time())}_{job_name}"


def _kill_spark_application(app_id, namespace):
    try:
        subprocess.run(['kubectl','exec','-n',namespace,'spark-master-0','--',
                        'curl','-X','POST',f'http://localhost:8080/app/kill/?id={app_id}'],
                       capture_output=True,text=True,timeout=10)
    except: pass
