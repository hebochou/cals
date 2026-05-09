from cals_app.core.db import _db_connect

from .accounts import _db_get_user_id_by_username


def _db_get_favorite_ids(username):
    user_id = _db_get_user_id_by_username(username)
    if not user_id:
        return set()
    conn = _db_connect()
    if not conn:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT question_id FROM favorites WHERE user_id=%s', (user_id,))
            return set(int(r[0]) for r in cur.fetchall() if r and r[0] is not None)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _db_get_favorite_ids_ordered(username):
    user_id = _db_get_user_id_by_username(username)
    if not user_id:
        return []
    conn = _db_connect()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT question_id FROM favorites WHERE user_id=%s ORDER BY created_at DESC, question_id DESC', (user_id,))
            return [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _db_toggle_favorite(username, question_id):
    user_id = _db_get_user_id_by_username(username)
    if not user_id:
        return None
    conn = _db_connect()
    if not conn:
        return None
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM favorites WHERE user_id=%s AND question_id=%s LIMIT 1', (user_id, question_id))
            exists = cur.fetchone() is not None
            if exists:
                cur.execute('DELETE FROM favorites WHERE user_id=%s AND question_id=%s', (user_id, question_id))
                conn.commit()
                return False
            cur.execute('INSERT INTO favorites (user_id,question_id,created_at) VALUES (%s,%s,NOW())', (user_id, question_id))
            conn.commit()
            return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _favorite_set(username):
    return _db_get_favorite_ids(username)
