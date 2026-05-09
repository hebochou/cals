import hashlib
import time
import urllib.error

from flask import current_app, render_template, request, session

from cals_app.core.security import _current_user, can_view_plain_answers
from cals_app.services.logic import (
    _evaluate_coding_question,
    _favorite_set,
    _pick_recommended_question,
    _recommend_meta,
    load_attempts,
    load_mistakes,
    log_attempt,
    log_mistake,
    next_mistake_id,
    remove_mistake,
)
from cals_app.utils.helpers import _runner_post_json, fisher_yates_shuffle, level_to_star, now_text

from .blueprint import compile_cache, student_bp
from .common import _load_enabled_questions


@student_bp.route("/student/api/practice/chapter/pool", methods=["GET"])
def api_practice_chapter_pool():
    if "user" not in session:
        return {"ok": False, "msg": "Unauthorized"}, 401

    mode = request.args.get("mode", "")
    chapter = request.args.get("chapter", "")
    diff = request.args.get("difficulty", "")
    selected_types = request.args.getlist("types")
    questions = _load_enabled_questions()

    if mode == "recommend":
        allowed_types = set(selected_types) if selected_types else None
        question, _ = _pick_recommended_question(session["user"], questions, allowed_types=allowed_types)
        if not question:
            return {"ok": True, "pool": []}
        return {"ok": True, "pool": [question["id"]]}

    if diff == "easy":
        allowed = {1, 2}
    elif diff == "medium":
        allowed = {2, 3}
    elif diff == "hard":
        allowed = {4, 5}
    else:
        allowed = {1, 2, 3, 4, 5}

    pool = []
    for question in questions:
        tags = question.get("tags", []) or []
        if not any((item == chapter) or (isinstance(item, str) and item.startswith(f"{chapter}:")) for item in tags):
            continue
        if question.get("level_star") not in allowed:
            continue
        if selected_types and question.get("type") not in set(selected_types):
            continue
        pool.append(question)

    pool_ids = fisher_yates_shuffle([question["id"] for question in pool])
    solved_qids = {
        item.get("q_id")
        for item in load_attempts(session["user"])
        if isinstance(item.get("q_id"), int) and item.get("is_correct") is True
    }
    for mistake in load_mistakes(session["user"]):
        qid = mistake.get("q_id")
        if isinstance(qid, int):
            solved_qids.add(qid)
    unseen_ids = [qid for qid in pool_ids if qid not in solved_qids]
    return {"ok": True, "pool": unseen_ids}


@student_bp.route("/student/api/practice/chapter/redo_later", methods=["POST"])
def api_practice_chapter_redo_later():
    if "user" not in session:
        return "Unauthorized", 401

    q_id = (request.form.get("q_id", "") or "").strip()
    if not q_id.isdigit():
        return "Bad Request", 400

    remove_mistake(session["user"], int(q_id))
    return {"ok": True}, 200


@student_bp.route("/student/api/practice/chapter/compile", methods=["POST"])
def api_practice_chapter_compile():
    if "user" not in session:
        return {"status": "failed", "log": "未登录", "error_code": 1}, 401

    q_id_raw = (request.form.get("q_id", "") or "").strip()
    code = request.form.get("code", "") or ""
    if not q_id_raw.isdigit():
        return {"status": "failed", "log": "无效的题目ID", "error_code": 1}, 400

    qid = int(q_id_raw)
    question = next((item for item in _load_enabled_questions() if item.get("id") == qid), None)
    if not question or question.get("type") != "coding":
        return {"status": "failed", "log": "非编程题", "error_code": 1}, 400

    meta = question.get("answer_meta") if isinstance(question.get("answer_meta"), dict) else {}
    sample_input = meta.get("sample_input", "")
    sample_output = meta.get("sample_output", "")
    time_limit_ms = int(meta.get("constraints", {}).get("time_limit_ms") or 1500)
    run_timeout = max(0.5, min(10.0, time_limit_ms / 1000.0))

    user_id = session["user"]
    code_md5 = hashlib.md5(code.encode("utf-8")).hexdigest()
    cache_key = f"compile_{user_id}_{qid}_{code_md5}"
    now = time.time()
    if cache_key in compile_cache:
        cached = compile_cache[cache_key]
        if now < cached["expires_at"]:
            return cached["data"], 200
        del compile_cache[cache_key]

    try:
        try:
            result = _runner_post_json(
                "/run",
                {"code": code, "stdin": sample_input, "compile_timeout": 10.0, "run_timeout": run_timeout},
                timeout=12,
            )
        except urllib.error.URLError as exc:
            current_app.logger.error(f"Compile URLError: {exc.reason}")
            return {"status": "failed", "log": "编译服务维护中，可直接提交", "error_code": 1}, 200
        except urllib.error.HTTPError as exc:
            return {"status": "failed", "log": f"编译服务错误 HTTP {getattr(exc, 'code', '未知')}", "error_code": 1}, 200
        except Exception as exc:
            return {"status": "failed", "log": f"请求编译服务异常: {exc}", "error_code": 1}, 200

        if not result or not result.get("ok"):
            resp = {"status": "failed", "log": "沙盒服务异常", "error_code": 1}
        elif not result.get("compile_ok"):
            resp = {"status": "failed", "log": result.get("stderr") or "编译超时或遇到未知错误", "error_code": 1}
        else:
            resp = {
                "status": "success",
                "log": "编译成功",
                "error_code": 0,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "sample_input": sample_input,
                "sample_output": sample_output,
                "run_ok": result.get("run_ok", False),
            }

        compile_cache[cache_key] = {"data": resp, "expires_at": now + 300}
        current_app.logger.info(f"Compile user={user_id} qid={qid} len={len(code)} status={resp['status']}")
        return resp, 200
    except urllib.error.URLError:
        return {"status": "failed", "log": "编译服务维护中，可直接提交", "error_code": 1}, 200
    except Exception as exc:
        return {"status": "failed", "log": f"服务器异常: {exc}", "error_code": 1}, 500


@student_bp.route("/student/api/practice/chapter/get_question", methods=["GET"])
def api_practice_chapter_get_question():
    if "user" not in session:
        return "Unauthorized", 401

    q_id = request.args.get("q_id", "")
    mode = request.args.get("mode", "chapter")
    if not q_id.isdigit():
        return "Bad Request", 400

    question = next((item for item in _load_enabled_questions() if item.get("id") == int(q_id)), None)
    if not question:
        return "Not found", 404

    return render_template(
        "student/partials/chapter_question.html",
        q=question,
        mode=mode,
        favorited_ids=_favorite_set(_current_user()),
        can_view_plain_answers=can_view_plain_answers(),
    )


@student_bp.route("/student/api/practice/chapter/explanation", methods=["GET"])
def api_practice_chapter_explanation():
    if "user" not in session:
        return {"ok": False, "msg": "Unauthorized"}, 401

    q_id = request.args.get("q_id", "")
    if not q_id.isdigit():
        return {"ok": False, "msg": "Bad Request"}, 400

    question = next((item for item in _load_enabled_questions() if item.get("id") == int(q_id)), None)
    if not question:
        return {"ok": False, "msg": "Not found"}, 404

    q_type = question.get("type")
    ans = question.get("answer")
    if q_type in ["single", "text"]:
        ans_text = str(ans)
    elif q_type == "multi":
        ans_text = ", ".join(ans) if isinstance(ans, list) else str(ans)
    elif q_type == "coding":
        ans_text = "请查看题目描述中的样例，或参考下方解析代码。"
    else:
        ans_text = str(ans)
    return {"ok": True, "answer": ans_text, "explanation": question.get("explain", "")}


@student_bp.route("/student/api/practice/chapter/submit", methods=["POST"])
def api_practice_chapter_submit():
    if "user" not in session:
        return {"is_correct": False, "msg": "Unauthorized"}, 401

    q_id = int(request.form.get("q_id", 0))
    question = next((item for item in _load_enabled_questions() if item["id"] == q_id), None)
    if not question:
        return {"is_correct": False, "msg": "Question not found"}, 404

    q_type = question.get("type")
    is_correct = False
    msg = ""
    user_ans = ""
    if q_type == "multi":
        user_ans = request.form.getlist("answer")
        is_correct = set(user_ans) == set(question.get("answer", []))
    elif q_type == "single":
        user_ans = (request.form.get("answer", "") or "").strip()
        is_correct = user_ans == question.get("answer")
    elif q_type == "coding":
        user_ans = request.form.get("answer", "") or ""
        ok, error_msg = _evaluate_coding_question(question, user_ans)
        is_correct = ok
        if not ok:
            msg = error_msg
            user_ans = f"【{msg}】\n\n{user_ans}"
    else:
        user_ans = (request.form.get("answer", "") or "").strip()
        expected = question.get("answer")
        variants = question.get("accept_variants", []) or []
        if isinstance(expected, str):
            cands = [expected] + [item for item in variants if isinstance(item, str)]
            is_correct = user_ans in [item.strip() for item in cands if isinstance(item, str)]
        else:
            is_correct = user_ans == expected

    log_attempt(
        {
            "username": _current_user(),
            "q_id": q_id,
            "type": q_type,
            "level_star": level_to_star(question.get("level")),
            "tags": question.get("tags", []),
            "mode": request.form.get("mode", "chapter"),
            "is_correct": is_correct,
            "timestamp": now_text(),
        }
    )

    if not is_correct:
        log_mistake(
            {
                "id": next_mistake_id(),
                "username": session["user"],
                "q_id": q_id,
                "code": question.get("code") or question.get("code_display"),
                "type": q_type,
                "tags": question.get("tags", []),
                "level_star": level_to_star(question.get("level")),
                "wrong_answer": user_ans,
                "timestamp": now_text(),
            }
        )
    else:
        remove_mistake(session["user"], q_id)

    recommend_meta = None
    if request.form.get("mode") == "recommend":
        recommend_meta = _recommend_meta(_current_user(), window=20)
        if "tag_scores" in recommend_meta:
            recommend_meta["tag_scores"] = recommend_meta["tag_scores"][:10]
    return {"is_correct": is_correct, "msg": msg, "recommend_meta": recommend_meta}
