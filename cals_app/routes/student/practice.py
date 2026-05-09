import json
import random
import urllib.error

from flask import current_app, flash, redirect, render_template, request, session, url_for

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
)
from cals_app.utils.helpers import (
    _compare_outputs,
    _runner_post_json,
    _runner_url,
    _unescape_sample_text,
    fisher_yates_shuffle,
    now_text,
)

from .blueprint import student_bp
from .common import _collect_question_tags, _load_enabled_questions


@student_bp.route("/student/practice", methods=["GET", "POST"])
def student_practice():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    questions = _load_enabled_questions()
    if not questions:
        flash("题库为空，请联系管理员添加题目", "error")
        return redirect(url_for("student_bp.student_home"))

    all_tags = _collect_question_tags(questions)

    if request.method == "POST":
        q_id = int(request.form.get("q_id", 0))
        question = next((item for item in questions if item["id"] == q_id), None)
        if not question:
            flash("题目不存在或已下线", "error")
            return redirect(url_for("student_bp.student_practice"))

        mode = (request.form.get("mode", "random") or "random").strip() or "random"
        tag = (request.form.get("tag", "") or "").strip()
        difficulty = (request.form.get("difficulty", "") or "").strip()
        selected_types = [item.strip() for item in request.form.getlist("types") if (item or "").strip()]
        selected_types = [item for item in selected_types if item in {"single", "multi", "text", "coding"}]

        q_type = question.get("type")
        if q_type == "multi":
            user_ans = request.form.getlist("answer")
            is_correct = set(user_ans) == set(question.get("answer", []))
        elif q_type == "single":
            user_ans = (request.form.get("answer", "") or "").strip()
            is_correct = user_ans == question.get("answer")
        elif q_type == "coding":
            user_ans = request.form.get("answer", "") or ""
            ok, msg = _evaluate_coding_question(question, user_ans)
            is_correct = ok
            if not ok:
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

        if is_correct is True:
            flash("回答正确！", "success")
        elif is_correct is False:
            flash("回答错误", "error")
            log_mistake(
                {
                    "username": session["user"],
                    "q_id": q_id,
                    "code": question.get("code_display"),
                    "type": q_type,
                    "tags": question.get("tags", []),
                    "level_star": question.get("level_star", 1),
                    "wrong_answer": user_ans,
                    "timestamp": now_text(),
                }
            )
        else:
            flash("已提交", "success")

        log_attempt(
            {
                "username": _current_user(),
                "q_id": q_id,
                "type": q_type,
                "level_star": question.get("level_star", 1),
                "tags": question.get("tags", []),
                "mode": mode,
                "selected_tag": tag,
                "selected_difficulty": difficulty,
                "is_correct": is_correct,
                "timestamp": now_text(),
            }
        )

        recommend_meta = _recommend_meta(_current_user(), window=20) if mode == "recommend" else None
        return render_template(
            "student/practice.html",
            question=question,
            show_result=True,
            is_correct=is_correct,
            user_answer=user_ans,
            mode=mode,
            selected_tag=tag,
            selected_difficulty=difficulty,
            all_tags=all_tags,
            favorited=(question.get("id") in _favorite_set(_current_user())),
            can_view_plain_answers=can_view_plain_answers(),
            recommend_meta=recommend_meta,
            selected_types=selected_types,
        )

    mode = (request.args.get("mode", "") or "").strip()
    tag = (request.args.get("tag", "") or "").strip()
    difficulty = (request.args.get("difficulty", "") or "").strip()
    chapter = (request.args.get("chapter", "") or "").strip()
    diff = (request.args.get("diff", "") or "").strip()
    selected_types = [item.strip() for item in request.args.getlist("types") if (item or "").strip()]
    selected_types = [item for item in selected_types if item in {"single", "multi", "text", "coding"}]
    redo_id = (request.args.get("redo_id", "") or "").strip()

    if redo_id.isdigit():
        question = next((item for item in questions if item["id"] == int(redo_id)), None)
        if question:
            return render_template(
                "student/practice.html",
                question=question,
                mode=mode or "redo",
                selected_tag=tag,
                selected_difficulty=difficulty,
                all_tags=all_tags,
                favorited=(question.get("id") in _favorite_set(_current_user())),
                can_view_plain_answers=can_view_plain_answers(),
            )

    chapters = [
        "基本数据类型",
        "基本算数运算",
        "键盘输入与屏幕输出",
        "选择控制结构",
        "循环控制结构",
        "函数与模块化",
        "数组",
        "指针",
        "字符串",
        "结构体",
    ]
    if not mode or mode == "chapter_select":
        return render_template(
            "student/practice.html",
            question=None,
            mode="chapter_select",
            chapters=chapters,
            selected_chapter="",
            selected_diff="",
            selected_types=selected_types,
        )

    if mode == "chapter":
        if not chapter or chapter not in chapters:
            flash("请先选择章节", "error")
            return render_template(
                "student/practice.html",
                question=None,
                mode="chapter_select",
                chapters=chapters,
                selected_chapter=chapter if chapter in chapters else "",
                selected_diff=diff,
                selected_types=selected_types,
            )

        if diff == "easy":
            allowed = {1, 2}
        elif diff == "medium":
            allowed = {2, 3}
        elif diff == "hard":
            allowed = {4, 5}
        else:
            diff = "random"
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

        if not pool:
            flash("该章节/难度下暂无题目，请联系管理员添加题目或调整筛选", "error")
            return render_template(
                "student/practice.html",
                question=None,
                mode="chapter_select",
                chapters=chapters,
                selected_chapter=chapter,
                selected_diff=diff,
                selected_types=selected_types,
            )

        pool_ids = [question["id"] for question in pool]
        shuffled_ids = fisher_yates_shuffle(pool_ids)
        mistake_qids = {item.get("q_id") for item in load_mistakes(_current_user()) if isinstance(item.get("q_id"), int)}
        solved_qids = {
            item.get("q_id")
            for item in load_attempts(_current_user())
            if item.get("is_correct") is True and isinstance(item.get("q_id"), int)
        }
        solved_qids.update(mistake_qids)
        unseen_ids = [qid for qid in shuffled_ids if qid not in solved_qids]

        if not unseen_ids:
            flash("太棒了！你已经完成了该筛选条件下的所有新题目，暂无更多未做题目。", "success")
            return render_template(
                "student/practice.html",
                question=None,
                mode="chapter_select",
                chapters=chapters,
                selected_chapter=chapter,
                selected_diff=diff,
                selected_types=selected_types,
            )

        initial_k = min(6, len(unseen_ids))
        picked_ids = unseen_ids[:initial_k]
        remaining_ids = unseen_ids[initial_k:]
        picked_questions = [next(question for question in pool if question["id"] == qid) for qid in picked_ids]
        return render_template(
            "student/practice_chapter.html",
            questions=picked_questions,
            remaining_ids=remaining_ids,
            mode="chapter",
            selected_tag=chapter,
            selected_difficulty=diff,
            selected_types=selected_types,
            all_tags=all_tags,
            favorited_ids=_favorite_set(_current_user()),
            can_view_plain_answers=can_view_plain_answers(),
        )

    if mode == "recommend":
        allowed_types = set(selected_types) if selected_types else None
        question, meta = _pick_recommended_question(_current_user(), questions, allowed_types=allowed_types)
        if not question:
            flash("题库为空，请联系管理员添加题目", "error")
            return redirect(url_for("student_bp.student_home"))
        if not meta.get("ready"):
            flash(f"还需要再完成 {meta.get('need', 0)} 道题后开启智能推荐，当前为探索阶段", "success")
        if "tag_scores" in meta:
            meta["tag_scores"] = meta["tag_scores"][:10]
        return render_template(
            "student/practice.html",
            question=question,
            mode="recommend",
            selected_tag=",".join(meta.get("focus_tags", []) or []),
            selected_difficulty=str(round((meta.get("acc", 0) or 0) * 100)),
            selected_types=selected_types,
            recommend_meta=meta,
            all_tags=all_tags,
            favorited=(question.get("id") in _favorite_set(_current_user())),
            can_view_plain_answers=can_view_plain_answers(),
        )

    if mode == "random":
        tag = ""
        difficulty = ""

    if mode == "wrong":
        ids = []
        for mistake in load_mistakes(_current_user()):
            qid = mistake.get("q_id")
            if isinstance(qid, int) and qid not in ids:
                ids.append(qid)
        pool = [question for question in questions if question.get("id") in ids]
        if pool:
            question = random.choice(pool)
            return render_template(
                "student/practice.html",
                question=question,
                mode=mode,
                selected_tag=tag,
                selected_difficulty=difficulty,
                all_tags=all_tags,
                favorited=(question.get("id") in _favorite_set(_current_user())),
                can_view_plain_answers=can_view_plain_answers(),
            )
        flash("暂无错题，已切换为随机练习", "success")
        mode = "random"

    if mode == "tag" and tag:
        pool = [question for question in questions if tag in (question.get("tags", []) or [])]
        if pool:
            question = random.choice(pool)
            return render_template(
                "student/practice.html",
                question=question,
                mode=mode,
                selected_tag=tag,
                selected_difficulty=difficulty,
                all_tags=all_tags,
                favorited=(question.get("id") in _favorite_set(_current_user())),
                can_view_plain_answers=can_view_plain_answers(),
            )
        flash("该标签下暂无题目，已切换为随机练习", "error")
        mode = "random"

    if mode == "difficulty" and difficulty.isdigit():
        level = int(difficulty)
        pool = [question for question in questions if question.get("level_star") == level]
        if pool:
            question = random.choice(pool)
            return render_template(
                "student/practice.html",
                question=question,
                mode=mode,
                selected_tag=tag,
                selected_difficulty=difficulty,
                all_tags=all_tags,
                favorited=(question.get("id") in _favorite_set(_current_user())),
                can_view_plain_answers=can_view_plain_answers(),
            )
        flash("该难度下暂无题目，已切换为随机练习", "error")
        mode = "random"

    question = random.choice(questions)
    return render_template(
        "student/practice.html",
        question=question,
        mode=mode or "random",
        selected_tag=tag,
        selected_difficulty=difficulty,
        all_tags=all_tags,
        favorited=(question.get("id") in _favorite_set(_current_user())),
        can_view_plain_answers=can_view_plain_answers(),
    )


@student_bp.route("/student/coding/run_sample", methods=["POST"])
def student_coding_run_sample():
    if "user" not in session:
        return {"ok": False, "error": "not_logged_in"}, 401

    q_id_raw = (request.form.get("q_id", "") or "").strip()
    code = request.form.get("code", "") or ""
    if not q_id_raw.isdigit():
        return {"ok": False, "error": "bad_q_id"}, 400

    qid = int(q_id_raw)
    question = next((item for item in _load_enabled_questions() if item.get("id") == qid), None)
    if not question or question.get("type") != "coding":
        return {"ok": False, "error": "not_coding_question"}, 400

    meta = question.get("answer_meta") if isinstance(question.get("answer_meta"), dict) else {}
    stdin_text = _unescape_sample_text(meta.get("sample_input") or "")
    expected_output = _unescape_sample_text(meta.get("sample_output") or "")

    try:
        result = _runner_post_json(
            "/run",
            {"code": code, "stdin": stdin_text, "compile_timeout": 2.0, "run_timeout": 1.5},
            timeout=10,
        )
        judged = None
        if result and result.get("ok") and result.get("compile_ok") and "stdout" in result:
            judged = _compare_outputs(result.get("stdout", ""), expected_output) if expected_output != "" else None
        return {"ok": True, "data": result, "stdin": stdin_text, "expected": expected_output, "sample_passed": judged}, 200
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read()
        except Exception:
            raw = b""
        detail = None
        try:
            detail = json.loads((raw or b"{}").decode("utf-8", errors="ignore") or "{}")
        except Exception:
            try:
                detail = (raw or b"").decode("utf-8", errors="ignore")
            except Exception:
                detail = ""
        return {"ok": False, "error": "runner_http_error", "runner": _runner_url(), "status": getattr(exc, "code", None), "detail": detail}, 502
    except urllib.error.URLError as exc:
        return {"ok": False, "error": "runner_unavailable", "runner": _runner_url(), "detail": str(exc)}, 503
    except Exception as exc:
        current_app.logger.error(f"sample_runner_error: {exc}")
        return {"ok": False, "error": "runner_error"}, 500
