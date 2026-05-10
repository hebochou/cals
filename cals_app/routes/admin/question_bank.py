﻿import csv
from datetime import datetime
from io import StringIO

from flask import Response, flash, redirect, render_template, request, session, url_for

from cals_app.core.security import _current_user, admin_required
from cals_app.services.admin.question_admin import batch_update_questions, delete_question, toggle_question_enabled

from .blueprint import admin_bp
from cals_app.utils.helpers import html_to_text

from .common import _filter_admin_questions, _load_admin_questions, _paginate_items, _question_filters_from_args


def _handle_question_post_action():
    action = (request.form.get("action", "") or "").strip()
    try:
        if action == "delete":
            q_id = int(request.form.get("id", 0))
            delete_question(q_id)
            flash("题目已删除", "success")
        elif action == "toggle_enabled":
            q_id = int(request.form.get("id", 0))
            toggle_question_enabled(q_id, actor_username=_current_user())
            flash("状态已更新", "success")
        elif action == "batch":
            op = (request.form.get("op", "") or "").strip()
            ids = [x for x in request.form.getlist("ids") if (x or "").strip().isdigit()]
            id_list = sorted(set(int(x) for x in ids))
            batch_update_questions(op, id_list, actor_username=_current_user())
            if op == "delete":
                flash("已批量删除", "success")
            elif op in {"enable", "disable"}:
                flash("已批量更新状态", "success")
        else:
            return redirect(url_for("admin_bp.admin_questions", **request.args))
    except RuntimeError as exc:
        flash(str(exc), "error")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        flash(f"操作失败: {str(exc)}", "error")
    return redirect(url_for("admin_bp.admin_questions", **request.args))


@admin_bp.route("/admin/items", methods=["GET", "POST"])
def admin_items():
    if session.get("role") != "admin":
        return redirect(url_for("auth_bp.admin_login"))
    return redirect(url_for("admin_bp.admin_questions"))


@admin_bp.route("/admin/questions", methods=["GET", "POST"])
@admin_required
def admin_questions():
    if request.method == "POST":
        return _handle_question_post_action()

    questions = _load_admin_questions(include_usage=True)
    filters = _question_filters_from_args(request.args, include_status=False)
    filtered = _filter_admin_questions(questions, filters, text_mode="raw")
    page_items, page, total_pages, total_count = _paginate_items(filtered, filters["page"], per_page=20)
    return render_template(
        "admin/questions.html",
        questions=page_items,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        q=filters["q_kw"],
        type_filter=filters["type_filter"],
        difficulty_filter=filters["difficulty_filter"],
        status_filter=filters["status_filter"],
        created_from=filters["created_from"],
        created_to=filters["created_to"],
    )


@admin_bp.route("/admin/questions/<int:q_id>")
@admin_required
def admin_question_view(q_id):
    questions = _load_admin_questions(include_usage=False)
    filters = _question_filters_from_args(request.args, include_status=False)
    filtered = sorted(_filter_admin_questions(questions, filters, text_mode="text"), key=lambda x: x.get("id", 0))
    current = next((x for x in filtered if x.get("id") == q_id), None)
    if not current:
        flash("题目不存在或不在当前筛选范围内", "error")
        return redirect(
            url_for(
                "admin_bp.admin_questions",
                q=filters["q_kw"],
                type=filters["type_filter"],
                difficulty=filters["difficulty_filter"],
                status=filters["status_filter"],
                created_from=filters["created_from"],
                created_to=filters["created_to"],
                page=filters["page"],
            )
        )
    idx = next((i for i, x in enumerate(filtered) if x.get("id") == q_id), -1)
    prev_id = filtered[idx - 1]["id"] if idx > 0 else None
    next_id = filtered[idx + 1]["id"] if idx >= 0 and idx < len(filtered) - 1 else None
    return render_template(
        "admin/question_view.html",
        question=current,
        prev_id=prev_id,
        next_id=next_id,
        q=filters["q_kw"],
        type_filter=filters["type_filter"],
        difficulty_filter=filters["difficulty_filter"],
        status_filter=filters["status_filter"],
        created_from=filters["created_from"],
        created_to=filters["created_to"],
        page=filters["page"],
    )


@admin_bp.route("/admin/questions/export")
@admin_required
def admin_export_questions():
    questions = _load_admin_questions(include_usage=False)
    filters = _question_filters_from_args(request.args, include_status=True)
    filtered = _filter_admin_questions(questions, filters, text_mode="raw")
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "code", "title", "type", "level", "enabled", "createdAt", "tags"])
    for question in filtered:
        writer.writerow(
            [
                question.get("id"),
                question.get("code_display"),
                html_to_text(question.get("title", "")),
                question.get("type", ""),
                question.get("level", ""),
                "1" if question.get("enabled", True) else "0",
                question.get("createdAt", ""),
                ",".join(question.get("tags", []) or []),
            ]
        )
    filename = f"questions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
