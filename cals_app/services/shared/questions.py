import json

from cals_app.core.db import _db_connect
from cals_app.utils.helpers import type_prefix


def _db_ensure_tag_category(cur, name):
    cur.execute("INSERT INTO tag_categories (name,sort_order) VALUES (%s,0) ON DUPLICATE KEY UPDATE name=name", (name,))
    cur.execute("SELECT id FROM tag_categories WHERE name=%s LIMIT 1", (name,))
    row = cur.fetchone()
    return int(row[0])


def _db_ensure_tag_item(cur, category_id, name):
    cur.execute("SELECT id FROM tag_items WHERE category_id=%s AND name=%s LIMIT 1", (category_id, name))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute("INSERT INTO tag_items (category_id,name) VALUES (%s,%s)", (category_id, name))
    cur.execute("SELECT LAST_INSERT_ID()")
    return int(cur.fetchone()[0])


def _db_replace_question_tags(cur, question_id, tags):
    cur.execute("DELETE FROM question_tags WHERE question_id=%s", (question_id,))
    cat_set = set()
    cat_with_sub = set()
    sub_count = 0
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        tag = tag.strip()
        if not tag:
            continue
        if ":" in tag:
            cat, sub = tag.split(":", 1)
            cat = cat.strip()
            sub = sub.strip()
            if not cat or not sub or sub_count >= 3:
                continue
            cat_id = _db_ensure_tag_category(cur, cat)
            item_id = _db_ensure_tag_item(cur, cat_id, sub)
            cur.execute(
                "INSERT IGNORE INTO question_tags (question_id,category_id,item_id) VALUES (%s,%s,%s)",
                (question_id, cat_id, item_id),
            )
            cat_set.add(cat)
            cat_with_sub.add(cat)
            sub_count += 1
        else:
            cat_set.add(tag)
    for cat in cat_set:
        if cat in cat_with_sub:
            continue
        cat_id = _db_ensure_tag_category(cur, cat)
        cur.execute(
            "INSERT IGNORE INTO question_tags (question_id,category_id,item_id) VALUES (%s,%s,NULL)",
            (question_id, cat_id),
        )


def _db_upsert_question_answer(cur, question_id, q_type, answer):
    answer_text = None
    if q_type == "coding":
        answer_text = answer or ""
        answer_json = {
            "title": "",
            "stem": "",
            "input_desc": "",
            "output_desc": "",
            "sample_input": "",
            "sample_output": "",
            "constraints": "",
            "hint": "",
        }
    elif q_type == "text":
        answer_json = {"answer": answer or "", "variants": []}
    else:
        answer_json = answer if answer is not None else ""
    cur.execute(
        "INSERT INTO question_answers (question_id,answer_json,answer_text) VALUES (%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE answer_json=VALUES(answer_json), answer_text=VALUES(answer_text)",
        (question_id, json.dumps(answer_json, ensure_ascii=False), answer_text),
    )


def load_questions():
    return _db_load_questions()


def attach_display_codes(questions):
    counters = {"single": 0, "multi": 0, "text": 0, "coding": 0}
    for question in questions:
        q_type = question.get("type")
        if q_type not in counters:
            continue
        if question.get("code"):
            question["code_display"] = question["code"]
        else:
            counters[q_type] += 1
            question["code_display"] = f"{type_prefix(q_type)}{counters[q_type]:04d}"


def _db_load_questions():
    conn = _db_connect()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,code,type,title_html,explain_html,level,enabled,created_at,updated_at "
                "FROM questions ORDER BY id DESC"
            )
            rows = cur.fetchall()
            questions = []
            by_id = {}
            for row in rows:
                question = {
                    "id": row[0],
                    "code": row[1],
                    "type": row[2],
                    "title": row[3] or "",
                    "explain": row[4] or "",
                    "level": row[5],
                    "enabled": bool(row[6]),
                    "created_at": str(row[7]) if row[7] else "",
                    "createdAt": str(row[7]) if row[7] else "",
                    "updated_at": str(row[8]) if row[8] else "",
                    "options": [],
                    "answer": None,
                    "answer_meta": {},
                    "tags": [],
                    "tags_ui": [],
                }
                questions.append(question)
                by_id[question["id"]] = question
            if not questions:
                return []
            qids = [question["id"] for question in questions]
            placeholders = ",".join(["%s"] * len(qids))
            cur.execute(
                f"SELECT question_id,opt_key,opt_text FROM question_options WHERE question_id IN ({placeholders}) "
                "ORDER BY question_id ASC, id ASC",
                qids,
            )
            for qid, opt_key, opt_text in cur.fetchall():
                if qid in by_id:
                    by_id[qid]["options"].append({"key": opt_key, "text": opt_text})
            cur.execute(
                f"SELECT question_id,answer_json,answer_text FROM question_answers WHERE question_id IN ({placeholders})",
                qids,
            )
            for qid, answer_json, answer_text in cur.fetchall():
                question = by_id.get(qid)
                if not question:
                    continue
                if question["type"] == "coding":
                    question["answer"] = answer_text or ""
                    try:
                        parsed = json.loads(answer_json) if answer_json else {}
                        question["answer_meta"] = parsed if isinstance(parsed, dict) else {}
                    except Exception:
                        question["answer_meta"] = {}
                elif question["type"] == "text":
                    try:
                        parsed = json.loads(answer_json) if answer_json else {}
                        question["answer"] = parsed.get("answer", "")
                    except Exception:
                        question["answer"] = ""
                else:
                    try:
                        question["answer"] = json.loads(answer_json) if answer_json else None
                    except Exception:
                        question["answer"] = None
            cur.execute(
                f"SELECT qt.question_id, c.name, i.name FROM question_tags qt "
                f"JOIN tag_categories c ON qt.category_id = c.id "
                f"LEFT JOIN tag_items i ON qt.item_id = i.id "
                f"WHERE qt.question_id IN ({placeholders})",
                qids,
            )
            cat_only_by_qid = {}
            subs_by_qid = {}
            for qid, category, item in cur.fetchall():
                if item:
                    subs_by_qid.setdefault(qid, {}).setdefault(category, []).append(item)
                else:
                    cat_only_by_qid.setdefault(qid, []).append(category)
            for question in questions:
                qid = question["id"]
                subs = subs_by_qid.get(qid, {})
                cat_only = cat_only_by_qid.get(qid, [])
                full = []
                ui = []
                for category, items in subs.items():
                    for item in sorted(items):
                        full.append(f"{category}:{item}")
                    if category not in ui:
                        ui.append(category)
                for category in sorted(cat_only):
                    if category not in subs:
                        full.append(category)
                    if category not in ui:
                        ui.append(category)
                question["tags"] = full
                question["tags_ui"] = ui
            return questions
    finally:
        try:
            conn.close()
        except Exception:
            pass
