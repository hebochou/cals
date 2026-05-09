import math
import urllib.parse

from cals_app.core.security import _current_user
from cals_app.services.logic import _favorite_set, attach_display_codes, load_attempts, load_mistakes, load_questions
from cals_app.utils.helpers import level_to_star, parse_tags

PAGE_SIZE = 51


def _student_status_sets(username):
    favorite_ids = _favorite_set(username)
    correct_ids = set()
    for attempt in load_attempts(username):
        if attempt.get('is_correct') is True and isinstance(attempt.get('q_id'), int):
            correct_ids.add(attempt['q_id'])
    mistake_ids = set()
    for mistake in load_mistakes(username):
        if isinstance(mistake.get('q_id'), int):
            mistake_ids.add(mistake['q_id'])
    return favorite_ids, correct_ids, mistake_ids


def _paginate_items(items, page, page_size=PAGE_SIZE):
    total_count = len(items)
    total_pages = max(1, math.ceil(total_count / page_size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], page, total_pages, total_count


def _build_page_url(base_path, page, params=None):
    query = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, list):
            filtered = [item for item in value if item not in (None, '', [])]
            if filtered:
                query[key] = filtered
        elif value != '':
            query[key] = value
    query['page'] = page
    encoded = urllib.parse.urlencode(query, doseq=True)
    return f'{base_path}?{encoded}' if encoded else base_path


def _parse_page_arg(args):
    page_raw = (args.get('page', '1') or '').strip()
    return int(page_raw) if page_raw.isdigit() else 1


def _load_enabled_questions():
    questions = [question for question in load_questions() if bool(question.get('enabled', True))]
    attach_display_codes(questions)
    for question in questions:
        question['level_star'] = level_to_star(question.get('level'))
    return questions


def _collect_question_tags(questions):
    tags = []
    for question in questions:
        for tag in question.get('tags', []):
            if tag not in tags:
                tags.append(tag)
    return tags


def _question_bank_filters(args):
    code_filter = (args.get('code', '') or '').strip()
    type_filter = (args.get('type', '') or '').strip()
    difficulty_filter = (args.get('difficulty', '') or '').strip()
    tags_list = [tag.strip() for tag in args.getlist('tags') if tag.strip()]
    tags_filter = parse_tags((args.get('tags', '') or '').strip()) if not tags_list else tags_list
    return code_filter, type_filter, difficulty_filter, tags_filter


def _filter_question_bank(questions, args):
    code_filter, type_filter, difficulty_filter, tags_filter = _question_bank_filters(args)
    filtered = []
    for question in questions:
        if code_filter and code_filter not in str(question.get('code_display', '')):
            continue
        if type_filter and question.get('type') != type_filter:
            continue
        if difficulty_filter and difficulty_filter.isdigit() and question.get('level_star') != int(difficulty_filter):
            continue
        if tags_filter:
            q_tags = question.get('tags', [])
            if not any(tag in q_tags for tag in tags_filter):
                continue
        filtered.append(question)
    filtered = sorted(filtered, key=lambda row: row.get('id', 0))
    return filtered, code_filter, type_filter, difficulty_filter, tags_filter


def _favorite_status_context():
    return _student_status_sets(_current_user())
