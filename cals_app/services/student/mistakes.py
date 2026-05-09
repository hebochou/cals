import json

from cals_app.core.db import _db_connect


def load_mistakes(username=None):
    conn = _db_connect()
    if conn:
        try:
            with conn.cursor() as cur:
                if username:
                    cur.execute('SELECT id, username, q_id, code, q_type, tags, level_star, wrong_answer, timestamp FROM mistakes_log WHERE username=%s ORDER BY timestamp IS NULL, timestamp DESC, id DESC', (username,))
                else:
                    cur.execute('SELECT id, username, q_id, code, q_type, tags, level_star, wrong_answer, timestamp FROM mistakes_log ORDER BY timestamp IS NULL, timestamp DESC, id DESC')
                rows = cur.fetchall()
                return [{
                    'id': row[0], 'username': row[1], 'q_id': row[2], 'code': row[3], 'type': row[4],
                    'tags': json.loads(row[5]) if row[5] else [], 'level_star': row[6], 'wrong_answer': row[7], 'timestamp': row[8],
                } for row in rows]
        except Exception:
            pass
        finally:
            conn.close()
    return []


def remove_mistake(username, q_id):
    conn = _db_connect()
    if conn:
        try:
            conn.autocommit(True)
            with conn.cursor() as cur:
                cur.execute('DELETE FROM mistakes_log WHERE username=%s AND q_id=%s', (username, q_id))
        except Exception:
            pass
        finally:
            conn.close()


def remove_mistake_by_id(username, m_id):
    conn = _db_connect()
    if conn:
        try:
            conn.autocommit(True)
            with conn.cursor() as cur:
                cur.execute('DELETE FROM mistakes_log WHERE username=%s AND id=%s', (username, m_id))
        except Exception:
            pass
        finally:
            conn.close()


def log_mistake(mistake_data):
    conn = _db_connect()
    if conn:
        try:
            conn.autocommit(True)
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO mistakes_log (id, username, q_id, code, q_type, tags, level_star, wrong_answer, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    (
                        mistake_data.get('id'), mistake_data.get('username'), mistake_data.get('q_id'), mistake_data.get('code'),
                        mistake_data.get('type'), json.dumps(mistake_data.get('tags', []), ensure_ascii=False),
                        mistake_data.get('level_star'), mistake_data.get('wrong_answer'), mistake_data.get('timestamp'),
                    ),
                )
        except Exception:
            pass
        finally:
            conn.close()


def next_mistake_id():
    try:
        conn = _db_connect()
    except Exception:
        return 1
    if not conn:
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM mistakes_log')
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 1
    except Exception:
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
