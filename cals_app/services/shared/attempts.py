﻿import json

from flask import current_app

from cals_app.core.db import _db_connect


def load_attempts(username=None):
    conn = _db_connect()
    if conn:
        try:
            with conn.cursor() as cur:
                if username:
                    cur.execute(
                        "SELECT username, q_id, q_type, level_star, tags, mode, is_correct, timestamp "
                        "FROM attempts_log WHERE username=%s ORDER BY id ASC",
                        (username,),
                    )
                else:
                    cur.execute(
                        "SELECT username, q_id, q_type, level_star, tags, mode, is_correct, timestamp "
                        "FROM attempts_log ORDER BY id ASC"
                    )
                rows = cur.fetchall()
                return [
                    {
                        "username": row[0],
                        "q_id": row[1],
                        "type": row[2],
                        "level_star": row[3],
                        "tags": json.loads(row[4]) if row[4] else [],
                        "mode": row[5],
                        "is_correct": bool(row[6]) if row[6] is not None else None,
                        "timestamp": row[7],
                    }
                    for row in rows
                ]
        except Exception as exc:
            try:
                current_app.logger.error(f"Failed to load attempts: {exc}")
            except Exception:
                pass
        finally:
            conn.close()
    return []


def log_attempt(attempt_data):
    conn = _db_connect()
    if conn:
        try:
            conn.autocommit(True)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO attempts_log (username, q_id, q_type, level_star, tags, mode, is_correct, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        attempt_data.get("username"),
                        attempt_data.get("q_id"),
                        attempt_data.get("type"),
                        attempt_data.get("level_star"),
                        json.dumps(attempt_data.get("tags", []), ensure_ascii=False),
                        attempt_data.get("mode"),
                        attempt_data.get("is_correct"),
                        attempt_data.get("timestamp"),
                    ),
                )
        except Exception as exc:
            try:
                current_app.logger.error(f"Failed to save attempt: {exc}")
            except Exception:
                pass
        finally:
            conn.close()
