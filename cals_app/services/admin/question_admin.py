﻿import json

from cals_app.core.db import _db_connect
from cals_app.services.shared.questions import _db_replace_question_tags, _db_upsert_question_answer
from cals_app.utils.helpers import generate_code


def _get_actor_id(cur, username):
    if not username:
        return None
    cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1", (username,))
    actor_row = cur.fetchone()
    return int(actor_row[0]) if actor_row and actor_row[0] is not None else None


def _write_audit_log(cur, question_id, actor_id, action, detail):
    if not actor_id:
        return
    cur.execute(
        "INSERT INTO question_audit_logs (question_id,actor_user_id,action,detail_json,created_at) "
        "VALUES (%s,%s,%s,%s,NOW())",
        (question_id, actor_id, action, json.dumps(detail, ensure_ascii=False)),
    )


def _delete_question_relations(cur, question_ids):
    ids = sorted({int(qid) for qid in (question_ids or []) if int(qid) > 0})
    if not ids:
        raise ValueError("请先选择题目")
    placeholders = ",".join(["%s"] * len(ids))
    relation_tables = [
        ("question_options", "question_id"),
        ("question_tags", "question_id"),
        ("question_answers", "question_id"),
        ("question_audit_logs", "question_id"),
        ("favorites", "question_id"),
        ("attempts_log", "q_id"),
        ("mistakes_log", "q_id"),
    ]
    for table_name, column_name in relation_tables:
        cur.execute(f"DELETE FROM {table_name} WHERE {column_name} IN ({placeholders})", ids)
    try:
        cur.execute(f"DELETE FROM coding_questions WHERE question_id IN ({placeholders})", ids)
    except Exception:
        pass
    cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", ids)
    return ids


def _question_option_rows(question_id, question_data):
    if question_data.get("type") not in {"single", "multi"}:
        return []
    return [
        (question_id, opt.get("key"), opt.get("text"))
        for opt in (question_data.get("options", []) or [])
        if opt.get("key") and opt.get("text")
    ]


def _get_connection():
    conn = _db_connect()
    if not conn:
        raise RuntimeError("数据库连接失败")
    return conn


def delete_question(question_id):
    conn = _get_connection()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            _delete_question_relations(cur, [question_id])
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def toggle_question_enabled(question_id, actor_username=None):
    conn = _get_connection()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.execute("UPDATE questions SET enabled=IF(enabled=1,0,1) WHERE id=%s", (question_id,))
            cur.execute("SELECT enabled FROM questions WHERE id=%s", (question_id,))
            row = cur.fetchone()
            enabled_val = int(row[0]) if row else 1
            actor_id = _get_actor_id(cur, actor_username)
            _write_audit_log(cur, question_id, actor_id, "toggle_enabled", {"enabled": bool(enabled_val)})
        conn.commit()
        return bool(enabled_val)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def batch_update_questions(op, question_ids, actor_username=None):
    ids = sorted({int(qid) for qid in (question_ids or []) if int(qid) > 0})
    if not ids:
        raise ValueError("请先选择题目")
    conn = _get_connection()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            actor_id = _get_actor_id(cur, actor_username)
            if op == "delete":
                _delete_question_relations(cur, ids)
            elif op in {"enable", "disable"}:
                target = 1 if op == "enable" else 0
                placeholders = ",".join(["%s"] * len(ids))
                cur.execute(f"UPDATE questions SET enabled=%s WHERE id IN ({placeholders})", [target] + ids)
                for question_id in ids:
                    _write_audit_log(cur, question_id, actor_id, "batch_enabled", {"enabled": bool(target)})
            else:
                raise ValueError("无效操作")
        conn.commit()
        return ids
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def create_question(question_data, enabled, actor_username=None, existing_questions=None):
    if not question_data:
        raise ValueError("题目信息不能为空")
    code = generate_code(existing_questions or [], question_data["type"])
    conn = _get_connection()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO questions (code,type,title_html,explain_html,level,enabled,created_at,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                (
                    code,
                    question_data["type"],
                    question_data.get("title", ""),
                    question_data.get("explain", ""),
                    int(question_data.get("level") or 1),
                    enabled,
                ),
            )
            cur.execute("SELECT LAST_INSERT_ID()")
            question_id = int(cur.fetchone()[0])
            rows = _question_option_rows(question_id, question_data)
            if rows:
                cur.executemany("INSERT INTO question_options (question_id,opt_key,opt_text) VALUES (%s,%s,%s)", rows)
            _db_upsert_question_answer(cur, question_id, question_data["type"], question_data.get("answer"))
            _db_replace_question_tags(cur, question_id, question_data.get("tags", []))
            actor_id = _get_actor_id(cur, actor_username)
            _write_audit_log(cur, question_id, actor_id, "create", {"code": code})
        conn.commit()
        return {"id": question_id, "code": code}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def update_question(question_id, existing_question, all_questions, question_data, enabled, actor_username=None):
    if not existing_question:
        raise ValueError("题目不存在")
    if not question_data:
        raise ValueError("题目信息不能为空")
    other_questions = [question for question in (all_questions or []) if question.get("id") != question_id]
    keep_existing_code = existing_question.get("type") == question_data["type"] and existing_question.get("code")
    code = existing_question.get("code") if keep_existing_code else generate_code(other_questions, question_data["type"])
    conn = _get_connection()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE questions SET code=%s,type=%s,title_html=%s,explain_html=%s,level=%s,enabled=%s,updated_at=NOW() "
                "WHERE id=%s",
                (
                    code,
                    question_data["type"],
                    question_data.get("title", ""),
                    question_data.get("explain", ""),
                    int(question_data.get("level") or 1),
                    enabled,
                    question_id,
                ),
            )
            cur.execute("DELETE FROM question_options WHERE question_id=%s", (question_id,))
            rows = _question_option_rows(question_id, question_data)
            if rows:
                cur.executemany("INSERT INTO question_options (question_id,opt_key,opt_text) VALUES (%s,%s,%s)", rows)
            _db_upsert_question_answer(cur, question_id, question_data["type"], question_data.get("answer"))
            _db_replace_question_tags(cur, question_id, question_data.get("tags", []))
            actor_id = _get_actor_id(cur, actor_username)
            _write_audit_log(cur, question_id, actor_id, "update", {"code": code})
        conn.commit()
        return {"id": question_id, "code": code}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
