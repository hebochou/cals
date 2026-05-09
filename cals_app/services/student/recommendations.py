import random

from cals_app.utils.helpers import level_to_star

from .attempts import load_attempts


def _ui_tags_from_full(tags):
    ui = []
    seen = set()
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        name = tag.split(':', 1)[0].strip()
        if name and name not in seen:
            seen.add(name)
            ui.append(name)
    return ui


def _recommend_tags(tags):
    normalized = []
    seen = set()
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        value = tag.strip()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _recommended_target_level(acc):
    if acc < 0.6:
        return 2
    if acc < 0.85:
        return 3
    return 4


def _recommended_candidate_scores(meta, pool):
    focus = set((meta or {}).get('focus_tags', [])[:3])
    weakness = (meta or {}).get('weakness_dict', {}) or {}
    acc = float((meta or {}).get('acc', 0) or 0)
    target = _recommended_target_level(acc)
    candidates = []
    for question in pool:
        tags = _recommend_tags(question.get('tags', []))
        if not tags:
            continue
        purity = len(tags)
        if purity <= 0:
            continue
        match_score = sum(weakness.get(tag, 0.0) for tag in tags if tag in focus)
        level = question.get('level_star') or level_to_star(question.get('level'))
        try:
            level_value = int(level)
        except Exception:
            level_value = level_to_star(question.get('level'))
        score = (match_score * 10) + (5.0 / purity) - (abs(level_value - target) * 2) + random.random()
        candidates.append((score, question))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def _pick_recommended_question(username, questions, allowed_types=None, meta=None, excluded_ids=None):
    pool = [q for q in questions if bool(q.get('enabled', True))]
    if allowed_types:
        pool = [q for q in pool if q.get('type') in allowed_types]
    excluded = set(excluded_ids or [])
    if excluded:
        pool = [q for q in pool if q.get('id') not in excluded]
    if meta is None:
        meta = _recommend_meta(username, window=20)
    if not pool:
        return None, meta
    if not meta.get('ready'):
        return random.choice(pool), meta
    candidates = _recommended_candidate_scores(meta, pool)
    if not candidates:
        return random.choice(pool), meta
    top_candidates = [question for _, question in candidates[:5]]
    return random.choice(top_candidates), meta


def _pick_recommended_questions_list(username, questions, allowed_types=None):
    meta = _recommend_meta(username, window=20)
    pool = [q for q in questions if bool(q.get('enabled', True))]
    if allowed_types:
        pool = [q for q in pool if q.get('type') in allowed_types]
    if not pool:
        return [], meta
    if not meta.get('ready'):
        random.shuffle(pool)
        return pool, meta
    ordered = []
    excluded_ids = set()
    for _ in range(len(pool)):
        picked, meta = _pick_recommended_question(username, pool, allowed_types=allowed_types, meta=meta, excluded_ids=excluded_ids)
        if not picked:
            break
        qid = picked.get('id')
        if not isinstance(qid, int) or qid in excluded_ids:
            break
        excluded_ids.add(qid)
        ordered.append(picked)
    if len(ordered) < len(pool):
        rest = [q for q in pool if q.get('id') not in excluded_ids]
        random.shuffle(rest)
        ordered.extend(rest)
    return ordered, meta


def _recommend_meta(username, window=20):
    attempts = load_attempts(username)
    graded = [attempt for attempt in attempts if attempt.get('is_correct') in (True, False)]
    recent_graded = graded[-window:] if window > 0 else graded
    need = max(0, 20 - len(graded))
    correct_count = len([attempt for attempt in recent_graded if attempt.get('is_correct') is True])
    acc = (correct_count / len(recent_graded)) if recent_graded else 0.0
    weakness = {}
    freq = {}
    wrong = {}
    recent_ids = []
    for attempt in attempts:
        qid = attempt.get('q_id')
        if isinstance(qid, int):
            recent_ids.append(qid)
    for attempt in graded:
        tags = _recommend_tags(attempt.get('tags', []))
        if not tags:
            continue
        for tag in tags:
            freq[tag] = freq.get(tag, 0) + 1
            wrong.setdefault(tag, 0)
            weakness.setdefault(tag, 0.0)
        if attempt.get('is_correct') is True:
            for tag in tags:
                weakness[tag] *= 0.5
        else:
            penalty = 1.0 / len(tags)
            for tag in tags:
                weakness[tag] += penalty
                wrong[tag] = wrong.get(tag, 0) + 1
    scored = []
    for tag in freq:
        scored.append({
            'tag': tag, 'freq': freq.get(tag, 0), 'mistakes': wrong.get(tag, 0),
            'weakness': round(weakness.get(tag, 0.0), 2), 'wrong': wrong.get(tag, 0),
            'score': round(weakness.get(tag, 0.0), 2),
        })
    scored.sort(key=lambda row: (row['weakness'], row['mistakes'], row['freq'], row['tag']), reverse=True)
    focus = [row['tag'] for row in scored[:3]]
    return {
        'ready': len(graded) >= 20, 'need': need, 'acc': acc, 'weakness_dict': weakness,
        'tag_scores': scored, 'focus_tags': focus, 'recent_ids': recent_ids[-20:],
    }
