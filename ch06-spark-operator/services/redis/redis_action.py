"""
redis_action.py — OpenServerless action using Redis built-in service.
Chapter 6 — Mastering Apache OpenServerless

Redis is available at: redis.openserverless.svc.cluster.local:6379
The redis library (v5.2.1) is pre-installed in the python:3.11 runtime.

Deploy:
    ops action create redis-demo redis_action.py --kind python:3.11

Test:
    ops action invoke redis-demo --result --param cmd ping
    ops action invoke redis-demo --result --param cmd set --param key mykey --param value hello
    ops action invoke redis-demo --result --param cmd get --param key mykey
    ops action invoke redis-demo --result --param cmd incr --param key counter
    ops action invoke redis-demo --result --param cmd expire --param key mykey --param ttl 60
"""
import redis
import os


REDIS_HOST     = os.environ.get('REDIS_HOST', 'redis.openserverless.svc.cluster.local')
REDIS_PORT     = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')


def get_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True  # Returns str instead of bytes
    )


def main(args: dict) -> dict:
    cmd = args.get('cmd', 'ping')
    r = get_client()

    if cmd == 'ping':
        return {'result': r.ping()}

    elif cmd == 'set':
        key   = args['key']
        value = args['value']
        ttl   = int(args.get('ttl', 0))
        if ttl > 0:
            r.setex(key, ttl, value)
        else:
            r.set(key, value)
        return {'key': key, 'value': value, 'result': 'ok'}

    elif cmd == 'get':
        key = args['key']
        return {'key': key, 'result': r.get(key)}

    elif cmd == 'del':
        key = args['key']
        r.delete(key)
        return {'key': key, 'result': 'deleted'}

    elif cmd == 'incr':
        key = args['key']
        return {'key': key, 'result': r.incr(key)}

    elif cmd == 'expire':
        key = args['key']
        ttl = int(args['ttl'])
        r.expire(key, ttl)
        return {'key': key, 'ttl': ttl, 'result': 'ok'}

    else:
        return {'error': f'Unknown command: {cmd}. Supported: ping, set, get, del, incr, expire'}
