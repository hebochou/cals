﻿from flask import flash, redirect, render_template, request, url_for

from cals_app.core.security import _current_user, admin_required
from cals_app.services.admin.question_admin import create_question, update_question
from cals_app.services.shared.analytics import _admin_next_code_map
from cals_app.services.shared.questions import attach_display_codes, load_questions
from cals_app.utils.helpers import build_question_from_form, generate_code, level_to_star

from .blueprint import admin_bp


@admin_bp.route("/admin/questions/new", methods=["GET", "POST"])
@admin_required
def admin_question_new():
    questions = load_questions()
    attach_display_codes(questions)
    next_code_map = _admin_next_code_map(questions)
    if request.method == "POST":
        new_q = build_question_from_form(request.form, 0)
        if not new_q:
            flash("请完整填写题目信息并检查格式", "error")
            return redirect(url_for("admin_bp.admin_question_new"))
        enabled = 1 if bool(request.form.get("enabled")) else 0
        try:
            create_question(new_q, enabled, actor_username=_current_user(), existing_questions=questions)
            flash("题目已新增", "success")
            return redirect(url_for("admin_bp.admin_questions"))
        except RuntimeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_bp.admin_question_new"))
        except Exception:
            flash("新增失败", "error")
            return redirect(url_for("admin_bp.admin_question_new"))
    return render_template("admin/new_question.html", edit_question=None, edit_level=None, edit_code=None, next_code_map=next_code_map)


@admin_bp.route("/admin/questions/<int:q_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_question_edit(q_id):
    questions = load_questions()
    attach_display_codes(questions)
    next_code_map = _admin_next_code_map(questions)
    existing = next((q for q in questions if q.get("id") == q_id), None)
    if not existing:
        flash("题目不存在", "error")
        return redirect(url_for("admin_bp.admin_questions"))
    if request.method == "POST":
        new_q = build_question_from_form(request.form, q_id)
        if not new_q:
            flash("请完整填写题目信息并检查格式", "error")
            return redirect(url_for("admin_bp.admin_question_edit", q_id=q_id))
        enabled = 1 if bool(request.form.get("enabled")) else 0
        try:
            update_question(q_id, existing, questions, new_q, enabled, actor_username=_current_user())
            flash("题目已更新", "success")
            return redirect(url_for("admin_bp.admin_questions"))
        except RuntimeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_bp.admin_question_edit", q_id=q_id))
        except Exception:
            flash("保存失败", "error")
            return redirect(url_for("admin_bp.admin_question_edit", q_id=q_id))
    edit_level = level_to_star(existing.get("level"))
    edit_code = existing.get("code") or existing.get("code_display")
    return render_template(
        "admin/new_question.html",
        edit_question=existing,
        edit_level=edit_level,
        edit_code=edit_code,
        next_code_map=next_code_map,
    )
