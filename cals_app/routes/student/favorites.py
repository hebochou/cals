from flask import redirect, render_template, request, session, url_for

from cals_app.core.security import _current_user
from cals_app.services.logic import _db_get_favorite_ids_ordered, _db_toggle_favorite

from .blueprint import student_bp
from .common import _build_page_url, _favorite_status_context, _load_enabled_questions, _paginate_items, _parse_page_arg


@student_bp.route('/student/favorite/toggle', methods=['POST'])
def student_toggle_favorite():
    if 'user' not in session:
        return {'ok': False, 'error': 'not_logged_in'}, 401
    q_id = (request.form.get('q_id', '') or '').strip()
    if not q_id.isdigit():
        return {'ok': False, 'error': 'bad_q_id'}, 400
    result = _db_toggle_favorite(_current_user(), int(q_id))
    if result is None:
        return {'ok': False, 'error': 'db_error'}, 500
    return {'ok': True, 'favorited': bool(result)}


@student_bp.route('/student/favorites')
def student_favorites():
    if 'user' not in session:
        return redirect(url_for('auth_bp.login'))
    favorite_order = _db_get_favorite_ids_ordered(_current_user())
    favorite_set = set(favorite_order)
    question_map = {question.get('id'): question for question in _load_enabled_questions() if question.get('id') in favorite_set}
    questions = [question_map[qid] for qid in favorite_order if qid in question_map]
    favorites, correct_ids, mistake_ids = _favorite_status_context()
    page = _parse_page_arg(request.args)
    page_items, page, total_pages, total_count = _paginate_items(questions, page)
    return render_template(
        'student/favorites.html',
        questions=page_items,
        favorite_ids=sorted(list(favorites)),
        correct_ids=sorted(list(correct_ids)),
        mistake_ids=sorted(list(mistake_ids)),
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        pager_prev_url=_build_page_url('/student/favorites', page - 1) if page > 1 else None,
        pager_next_url=_build_page_url('/student/favorites', page + 1) if page < total_pages else None,
        pager_base_path='/student/favorites',
        pager_params={},
    )
