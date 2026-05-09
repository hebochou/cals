from datetime import datetime, timedelta

from flask import redirect, render_template, session, url_for

from cals_app.core.security import _current_user
from cals_app.services.logic import load_attempts
from cals_app.utils.helpers import _parse_dt

from .blueprint import student_bp


@student_bp.route('/student/home')
def student_home():
    if 'user' not in session:
        return redirect(url_for('auth_bp.login'))
    return render_template('student/home.html')


@student_bp.route('/student/api/stats')
def student_api_stats():
    if 'user' not in session:
        return {'ok': False, 'error': 'not_logged_in'}, 401
    username = _current_user()
    attempts = load_attempts(username)
    solved_ids = set()
    day_set = set()
    graded = [attempt for attempt in attempts if attempt.get('is_correct') in (True, False)]
    correct = [attempt for attempt in graded if attempt.get('is_correct') is True]
    for attempt in attempts:
        qid = attempt.get('q_id')
        if isinstance(qid, int):
            solved_ids.add(qid)
        ts = _parse_dt(attempt.get('timestamp', ''))
        if ts:
            day_set.add(ts.date())
    streak = 0
    if day_set:
        day = max(day_set)
        while day in day_set:
            streak += 1
            day = day - timedelta(days=1)
    accuracy = round((len(correct) / len(graded)) * 100, 2) if graded else 0
    type_counts = {'单选': 0, '多选': 0, '填空': 0, '编程': 0}
    for attempt in attempts:
        q_type = attempt.get('type')
        if q_type == 'single':
            type_counts['单选'] += 1
        elif q_type == 'multi':
            type_counts['多选'] += 1
        elif q_type == 'text':
            type_counts['填空'] += 1
        elif q_type == 'coding':
            type_counts['编程'] += 1
    today = datetime.now().date()
    labels = []
    counts = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%m-%d'))
        count = 0
        for attempt in attempts:
            ts = _parse_dt(attempt.get('timestamp', ''))
            if ts and ts.date() == day:
                count += 1
        counts.append(count)
    return {
        'ok': True,
        'data': {
            'solved_count': len(solved_ids),
            'accuracy_percent': accuracy,
            'streak_days': streak,
            'trend': {'labels': labels, 'values': counts},
            'type_dist': {'labels': ['单选', '多选', '填空', '编程'], 'values': [type_counts['单选'], type_counts['多选'], type_counts['填空'], type_counts['编程']]},
        },
    }, 200
