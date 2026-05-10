﻿from datetime import datetime, timedelta

from cals_app.utils.helpers import _parse_dt, level_to_star, next_suffix_by_type, type_prefix

from .attempts import load_attempts
from .questions import attach_display_codes, load_questions


def _range_since(range_key):
    now = datetime.now()
    if range_key == "day":
        return now - timedelta(days=1)
    if range_key == "month":
        return now - timedelta(days=30)
    if range_key == "year":
        return now - timedelta(days=365)
    return now - timedelta(days=7)


def _admin_compute_stats(range_key):
    questions = load_questions()
    attach_display_codes(questions)
    for question in questions:
        question["level_star"] = level_to_star(question.get("level"))
    attempts = load_attempts()
    since = _range_since(range_key)
    filtered = []
    for attempt in attempts:
        ts = _parse_dt(attempt.get("timestamp", ""))
        if ts and ts >= since:
            filtered.append(attempt)
    total_submissions = len(filtered)
    graded = [attempt for attempt in filtered if attempt.get("is_correct") in (True, False)]
    graded_count = len(graded)
    correct_count = len([attempt for attempt in graded if attempt.get("is_correct") is True])
    accuracy_percent = round((correct_count / graded_count) * 100, 2) if graded_count else 0
    type_counts = {"单选": 0, "多选": 0, "填空": 0, "编程": 0}
    for question in questions:
        q_type = question.get("type")
        if q_type == "single":
            type_counts["单选"] += 1
        elif q_type == "multi":
            type_counts["多选"] += 1
        elif q_type == "text":
            type_counts["填空"] += 1
        elif q_type == "coding":
            type_counts["编程"] += 1
    level_counts = {str(i): 0 for i in range(1, 6)}
    for question in questions:
        star = str(level_to_star(question.get("level")))
        level_counts[star] = level_counts.get(star, 0) + 1
    if range_key == "day":
        labels = [f"{hour:02d}:00" for hour in range(24)]
        buckets = {key: 0 for key in labels}
        for attempt in filtered:
            ts = _parse_dt(attempt.get("timestamp", ""))
            if ts:
                buckets[f"{ts.hour:02d}:00"] += 1
        trend = {"labels": labels, "values": [buckets[key] for key in labels]}
    elif range_key == "week":
        today = datetime.now().date()
        labels = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        buckets = {key: 0 for key in labels}
        for attempt in filtered:
            ts = _parse_dt(attempt.get("timestamp", ""))
            if ts:
                key = ts.strftime("%m-%d")
                if key in buckets:
                    buckets[key] += 1
        trend = {"labels": labels, "values": [buckets[key] for key in labels]}
    elif range_key == "month":
        today = datetime.now().date()
        labels = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(29, -1, -1)]
        buckets = {key: 0 for key in labels}
        for attempt in filtered:
            ts = _parse_dt(attempt.get("timestamp", ""))
            if ts:
                key = ts.strftime("%m-%d")
                if key in buckets:
                    buckets[key] += 1
        trend = {"labels": labels, "values": [buckets[key] for key in labels]}
    else:
        today = datetime.now().date()
        labels = []
        for i in range(11, -1, -1):
            month = (today.month - i - 1) % 12 + 1
            year = today.year + (today.month - i - 1) // 12
            labels.append(f"{year}-{month:02d}")
        buckets = {key: 0 for key in labels}
        for attempt in filtered:
            ts = _parse_dt(attempt.get("timestamp", ""))
            if ts:
                key = ts.strftime("%Y-%m")
                if key in buckets:
                    buckets[key] += 1
        trend = {"labels": labels, "values": [buckets[key] for key in labels]}
    usage_by_qid = {}
    for attempt in filtered:
        qid = attempt.get("q_id")
        if isinstance(qid, int):
            usage_by_qid[qid] = usage_by_qid.get(qid, 0) + 1
    q_by_id = {question.get("id"): question for question in questions if isinstance(question, dict)}
    top = []
    for qid, count in sorted(usage_by_qid.items(), key=lambda item: item[1], reverse=True)[:10]:
        question = q_by_id.get(qid, {})
        top.append({"id": qid, "code": question.get("code_display", "-"), "title": question.get("title", ""), "count": count})
    return {
        "total_questions": len(questions),
        "total_submissions": total_submissions,
        "graded_count": graded_count,
        "accuracy_percent": accuracy_percent,
        "trend": trend,
        "type_dist": {
            "labels": ["单选", "多选", "填空", "编程"],
            "values": [type_counts["单选"], type_counts["多选"], type_counts["填空"], type_counts["编程"]],
        },
        "level_dist": {"labels": [f"{i}" for i in range(1, 6)], "values": [level_counts[str(i)] for i in range(1, 6)]},
        "top_questions": top,
    }


def _admin_next_code_map(questions):
    next_suffix = next_suffix_by_type(questions)
    return {key: f"{type_prefix(key)}{next_suffix[key]:04d}" for key in next_suffix}
