from datetime import datetime, timedelta

from cals_app.services.shared import attach_display_codes, load_attempts, load_questions
from cals_app.utils.helpers import _parse_dt, html_to_text, level_to_star


def _load_admin_questions(include_usage=True):
    questions = load_questions()
    attach_display_codes(questions)
    usage_by_qid = {}
    if include_usage:
        for attempt in load_attempts():
            qid = attempt.get("q_id")
            if isinstance(qid, int):
                usage_by_qid[qid] = usage_by_qid.get(qid, 0) + 1
    for question in questions:
        question["level_star"] = level_to_star(question.get("level"))
        if include_usage:
            question["usage_count"] = usage_by_qid.get(question.get("id"), 0)
    return questions


def _parse_created_range(created_from, created_to):
    created_from_dt = None
    created_to_dt = None
    if created_from:
        try:
            created_from_dt = datetime.strptime(created_from, "%Y-%m-%d")
        except Exception:
            created_from_dt = None
    if created_to:
        try:
            created_to_dt = datetime.strptime(created_to, "%Y-%m-%d") + timedelta(days=1)
        except Exception:
            created_to_dt = None
    return created_from_dt, created_to_dt


def _question_filters_from_args(args, include_status=False):
    q_kw = (args.get("q", "") or "").strip()
    type_filter = (args.get("type", "") or "").strip()
    difficulty_filter = (args.get("difficulty", "") or "").strip()
    status_filter = (args.get("status", "") or "").strip() if include_status else ""
    created_from = (args.get("created_from", "") or "").strip()
    created_to = (args.get("created_to", "") or "").strip()
    page_raw = (args.get("page", "1") or "1").strip()
    page = int(page_raw) if page_raw.isdigit() else 1
    page = max(1, page)
    created_from_dt, created_to_dt = _parse_created_range(created_from, created_to)
    return {
        "q_kw": q_kw,
        "type_filter": type_filter,
        "difficulty_filter": difficulty_filter,
        "status_filter": status_filter,
        "created_from": created_from,
        "created_to": created_to,
        "created_from_dt": created_from_dt,
        "created_to_dt": created_to_dt,
        "page": page,
    }


def _filter_admin_questions(questions, filters, text_mode="raw"):
    filtered = []
    for question in questions:
        if filters["q_kw"]:
            title_text = html_to_text(question.get("title", "")) if text_mode == "text" else question.get("title", "")
            hay = f"{title_text} {question.get('code_display', '')}"
            if filters["q_kw"] not in hay:
                continue
        if filters["type_filter"] and question.get("type") != filters["type_filter"]:
            continue
        if filters["difficulty_filter"] and filters["difficulty_filter"].isdigit():
            if question.get("level_star") != int(filters["difficulty_filter"]):
                continue
        if filters["status_filter"] == "enabled" and not bool(question.get("enabled", True)):
            continue
        if filters["status_filter"] == "disabled" and bool(question.get("enabled", True)):
            continue
        if filters["created_from_dt"] or filters["created_to_dt"]:
            ts = _parse_dt(question.get("createdAt", ""))
            if not ts:
                continue
            if filters["created_from_dt"] and ts < filters["created_from_dt"]:
                continue
            if filters["created_to_dt"] and ts >= filters["created_to_dt"]:
                continue
        filtered.append(question)
    return filtered


def _paginate_items(items, page, per_page=20):
    total_count = len(items)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    return items[start : start + per_page], page, total_pages, total_count
