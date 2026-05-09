from flask import flash, redirect, render_template, request, session, url_for

from cals_app.services.logic import load_mistakes, remove_mistake_by_id
from cals_app.utils.helpers import now_text

from .blueprint import student_bp
from .common import (
    _build_page_url,
    _load_enabled_questions,
    _paginate_items,
    _parse_page_arg,
)


@student_bp.route("/student/mistakes")
def student_mistakes():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    questions = _load_enabled_questions()
    current_user_mistakes = load_mistakes(session["user"])
    tag_filter = (request.args.get("tag", "") or "").strip()

    all_tags = []
    formatted_mistakes = []
    for mistake in current_user_mistakes:
        for tag in mistake.get("tags", []):
            if tag not in all_tags:
                all_tags.append(tag)
        if tag_filter and tag_filter not in mistake.get("tags", []):
            continue
        question = next((item for item in questions if item["id"] == mistake["q_id"]), None)
        if not question:
            continue
        formatted_mistakes.append(
            {
                "id": mistake.get("id"),
                "question": {
                    "id": question["id"],
                    "code": mistake.get("code") or question.get("code_display"),
                    "title": question["title"],
                    "type": question["type"],
                    "tags": question.get("tags", []),
                    "tags_ui": question.get("tags_ui", []),
                    "level_star": question.get("level_star", 1),
                    "answer": question.get("answer", ""),
                    "explain": question.get("explain", ""),
                },
                "user_answer": mistake.get("wrong_answer", ""),
                "timestamp": mistake.get("timestamp", now_text()),
            }
        )

    formatted_mistakes = sorted(formatted_mistakes, key=lambda row: row.get("timestamp", ""), reverse=True)
    page = _parse_page_arg(request.args)
    page_items, page, total_pages, total_count = _paginate_items(formatted_mistakes, page)
    pager_params = {"tag": tag_filter}
    return render_template(
        "student/mistakes.html",
        mistakes=page_items,
        all_tags=all_tags,
        tag_filter=tag_filter,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        pager_prev_url=_build_page_url("/student/mistakes", page - 1, pager_params) if page > 1 else None,
        pager_next_url=_build_page_url("/student/mistakes", page + 1, pager_params) if page < total_pages else None,
        pager_base_path="/student/mistakes",
        pager_params=pager_params,
    )


@student_bp.route("/student/mistakes/remove", methods=["POST"])
def student_mistake_remove():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    mistake_id = (request.form.get("mistake_id", "") or "").strip()
    if mistake_id.isdigit():
        remove_mistake_by_id(session["user"], int(mistake_id))
        flash("已移除错题", "success")
    return redirect(url_for("student_bp.student_mistakes", tag=request.args.get("tag", "").strip() or None))
