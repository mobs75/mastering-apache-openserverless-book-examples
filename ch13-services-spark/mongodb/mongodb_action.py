"""
mongodb_action.py — OpenServerless action using FerretDB/MongoDB built-in service.
Chapter 13 — Mastering Apache OpenServerless

FerretDB is MongoDB-compatible with PostgreSQL backend.
Available at: nuvolaris-mongodb-svc.nuvolaris.svc.cluster.local:27017

IMPORTANT (FerretDB v1.6.0 quirks):
  - authMechanism must be 'PLAIN' (SCRAM-SHA-1/256 not supported)
  - authSource must be '$external'
  - Password is the PostgreSQL nuvolaris user password, not a MongoDB password

Deploy:
    ops action create mongodb-demo mongodb_action.py --kind python:3.11

Test:
    ops action invoke mongodb-demo --result --param cmd ping
    ops action invoke mongodb-demo --result --param cmd insert \
        --param type alert --param message "test event"
    ops action invoke mongodb-demo --result --param cmd find
"""
from pymongo import MongoClient
import os


MONGO_HOST = os.environ.get('MONGO_HOST', 'nuvolaris-mongodb-svc.nuvolaris.svc.cluster.local')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USER = os.environ.get('MONGO_USER', 'nuvolaris')
MONGO_PASS = os.environ.get('MONGO_PASSWORD', '')  # Use PostgreSQL nuvolaris password


def get_client():
    # FerretDB requires PLAIN auth with PostgreSQL credentials
    return MongoClient(
        host=MONGO_HOST,
        port=MONGO_PORT,
        username=MONGO_USER,
        password=MONGO_PASS,
        authSource='$external',
        authMechanism='PLAIN'
    )


def main(args: dict) -> dict:
    cmd             = args.get('cmd', 'ping')
    db_name         = args.get('database', 'myapp')
    collection_name = args.get('collection', 'events')

    client = get_client()
    db     = client[db_name]
    col    = db[collection_name]

    if cmd == 'ping':
        result = db.command('ping')
        return {'result': result}

    elif cmd == 'insert':
        doc = {k: v for k, v in args.items() if k not in ('cmd', 'database', 'collection')}
        result = col.insert_one(doc)
        return {'id': str(result.inserted_id), 'result': 'inserted'}

    elif cmd == 'find':
        query = {}
        if 'filter_key' in args:
            query[args['filter_key']] = args.get('filter_value', '')
        docs = list(col.find(query, {'_id': 0}, limit=10))
        return {'result': docs}

    elif cmd == 'delete':
        result = col.delete_many({})
        return {'deleted': result.deleted_count, 'result': 'ok'}

    else:
        return {'error': f'Unknown command: {cmd}. Supported: ping, insert, find, delete'}
