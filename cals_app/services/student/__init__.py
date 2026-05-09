from .accounts import (
    _db_ensure_default_users,
    _db_get_student_by_student_no,
    _db_get_user,
    _db_get_user_id_by_username,
    _db_touch_last_login,
    _db_update_user_password_hash,
    verify_user_password,
)
from .analytics import _admin_compute_stats, _admin_next_code_map, _range_since
from .attempts import load_attempts, log_attempt
from .evaluation import _evaluate_coding_question
from .favorites import (
    _db_get_favorite_ids,
    _db_get_favorite_ids_ordered,
    _db_toggle_favorite,
    _favorite_set,
)
from .mistakes import (
    load_mistakes,
    log_mistake,
    next_mistake_id,
    remove_mistake,
    remove_mistake_by_id,
)
from .questions import (
    _db_ensure_tag_category,
    _db_ensure_tag_item,
    _db_load_questions,
    _db_replace_question_tags,
    _db_upsert_question_answer,
    attach_display_codes,
    load_questions,
)
from .recommendations import (
    _pick_recommended_question,
    _pick_recommended_questions_list,
    _recommend_meta,
    _ui_tags_from_full,
)

__all__ = [
    '_db_ensure_default_users', '_db_get_user', '_db_get_student_by_student_no',
    '_db_update_user_password_hash', '_db_touch_last_login', 'verify_user_password',
    '_db_get_user_id_by_username', '_db_get_favorite_ids', '_db_get_favorite_ids_ordered',
    '_db_toggle_favorite', '_favorite_set', '_db_ensure_tag_category',
    '_db_replace_question_tags', '_db_upsert_question_answer', 'load_questions',
    'attach_display_codes', 'load_attempts', 'load_mistakes', 'remove_mistake',
    'remove_mistake_by_id', 'log_mistake', 'log_attempt', 'next_mistake_id',
    '_ui_tags_from_full', '_evaluate_coding_question', '_pick_recommended_question', '_pick_recommended_questions_list',
    '_admin_compute_stats', '_admin_next_code_map', '_range_since', '_db_ensure_tag_item',
    '_db_load_questions', '_recommend_meta',
]
