import urllib.parse

from flask import flash, redirect, render_template, request, session, url_for

from cals_app.core.security import _current_user
from cals_app.services.logic import _favorite_set

from .blueprint import student_bp
from .common import (
    _build_page_url,
    _collect_question_tags,
    _favorite_status_context,
    _filter_question_bank,
    _load_enabled_questions,
    _paginate_items,
    _parse_page_arg,
)


@student_bp.route('/student/questions')
def student_questions():
    if 'user' not in session:
        return redirect(url_for('auth_bp.login'))
    questions = _load_enabled_questions()
    filtered, code_filter, type_filter, difficulty_filter, tags_filter = _filter_question_bank(questions, request.args)
    all_tags = _collect_question_tags(questions)
    favorites, correct_ids, mistake_ids = _favorite_status_context()
    page = _parse_page_arg(request.args)
    page_items, page, total_pages, total_count = _paginate_items(filtered, page)
    pager_params = {'code': code_filter, 'type': type_filter, 'difficulty': difficulty_filter, 'tags': tags_filter}
    qs = urllib.parse.urlencode({**{k: v for k, v in pager_params.items() if v not in ('', None, [])}, 'page': page}, doseq=True)
    return render_template(
        'student/questions.html',
        questions=page_items,
        all_tags=all_tags,
        code_filter=code_filter,
        type_filter=type_filter,
        difficulty_filter=difficulty_filter,
        tags_filter=tags_filter,
        favorite_ids=sorted(list(favorites)),
        correct_ids=sorted(list(correct_ids)),
        mistake_ids=sorted(list(mistake_ids)),
        qs=qs,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        pager_prev_url=_build_page_url('/student/questions', page - 1, pager_params) if page > 1 else None,
        pager_next_url=_build_page_url('/student/questions', page + 1, pager_params) if page < total_pages else None,
        pager_base_path='/student/questions',
        pager_params=pager_params,
    )


@student_bp.route('/student/questions/<int:q_id>')
def student_question_view(q_id):
    if 'user' not in session:
        return redirect(url_for('auth_bp.login'))
    questions = _load_enabled_questions()
    filtered, _, _, _, _ = _filter_question_bank(questions, request.args)
    current = next((question for question in filtered if question.get('id') == q_id), None)
    if not current:
        flash('题目不存在或不在当前筛选范围内', 'error')
        return redirect(url_for('student_bp.student_questions', **request.args))
    idx = next((i for i, question in enumerate(filtered) if question.get('id') == q_id), -1)
    prev_id = filtered[idx - 1]['id'] if idx > 0 else None
    next_id = filtered[idx + 1]['id'] if idx >= 0 and idx < len(filtered) - 1 else None
    qs = request.query_string.decode('utf-8', errors='ignore')
    return render_template(
        'student/question_view.html',
        question=current,
        prev_id=prev_id,
        next_id=next_id,
        qs=qs,
        favorited=(current.get('id') in _favorite_set(_current_user())),
    )
