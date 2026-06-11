"""
postgres_action.py — OpenServerless action using PostgreSQL built-in service.
Chapter 13 — Mastering Apache OpenServerless

PostgreSQL 16 managed by Kubegres operator (primary + replica).
Available at: nuvolaris-postgres.nuvolaris.svc.cluster.local:5432

IMPORTANT: Use psycopg (v3), NOT psycopg2.
    import psycopg      # correct — v3 API
    import psycopg2     # ModuleNotFoundError — not available

One-time permission setup (run once after deploy):
    PGPASSWORD=<admin_pwd> psql -U postgres -d nuvolaris \
      -h nuvolaris-postgres.nuvolaris.svc.cluster.local \
      -c "GRANT ALL ON SCHEMA public TO nuvolaris;"

Deploy:
    ops action create postgres-demo postgres_action.py --kind python:3.11

Test:
    ops action invoke postgres-demo --result --param cmd ping
    ops action invoke postgres-demo --result --param cmd create
    ops action invoke postgres-demo --result --param cmd insert \
        --param name event --param value "user signup"
    ops action invoke postgres-demo --result --param cmd select
"""
import psycopg  # psycopg v3 — NOT psycopg2
import os


PG_HOST = os.environ.get('PG_HOST', 'nuvolaris-postgres.nuvolaris.svc.cluster.local')
PG_PORT = int(os.environ.get('PG_PORT', 5432))
PG_DB   = os.environ.get('PG_DB',   'nuvolaris')
PG_USER = os.environ.get('PG_USER', 'nuvolaris')
PG_PASS = os.environ.get('PG_PASSWORD', '')


def get_connection():
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASS
    )


def main(args: dict) -> dict:
    cmd = args.get('cmd', 'ping')

    with get_connection() as conn:
        with conn.cursor() as cur:

            if cmd == 'ping':
                cur.execute('SELECT version()')
                return {'result': cur.fetchone()[0]}

            elif cmd == 'create':
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id    SERIAL PRIMARY KEY,
                        name  TEXT NOT NULL,
                        value TEXT,
                        ts    TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                conn.commit()
                return {'result': 'table created'}

            elif cmd == 'insert':
                cur.execute(
                    'INSERT INTO events (name, value) VALUES (%s, %s) RETURNING id',
                    (args.get('name', 'event'), args.get('value', ''))
                )
                row_id = cur.fetchone()[0]
                conn.commit()
                return {'id': row_id, 'result': 'inserted'}

            elif cmd == 'select':
                cur.execute('SELECT id, name, value FROM events ORDER BY id DESC LIMIT 10')
                rows = [{'id': r[0], 'name': r[1], 'value': r[2]} for r in cur.fetchall()]
                return {'result': rows}

            else:
                return {'error': f'Unknown command: {cmd}. Supported: ping, create, insert, select'}
