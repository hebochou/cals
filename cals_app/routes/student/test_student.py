from werkzeug.datastructures import MultiDict

from cals_app.routes.student.common import _build_page_url, _filter_question_bank, _paginate_items


def test_paginate_items_caps_page_and_counts():
    items = list(range(120))
    page_items, page, total_pages, total_count = _paginate_items(items, page=99, page_size=51)
    assert page == 3
    assert total_pages == 3
    assert total_count == 120
    assert page_items == list(range(102, 120))


def test_build_page_url_preserves_lists_and_skips_empty_values():
    url = _build_page_url("/student/questions", 2, {"type": "single", "tags": ["数组", "字符串"], "code": ""})
    assert url == "/student/questions?type=single&tags=%E6%95%B0%E7%BB%84&tags=%E5%AD%97%E7%AC%A6%E4%B8%B2&page=2"


def test_filter_question_bank_applies_all_supported_filters():
    questions = [
        {"id": 1, "code_display": "S0001", "type": "single", "level_star": 2, "tags": ["数组", "数组:一维"]},
        {"id": 2, "code_display": "M0002", "type": "multi", "level_star": 4, "tags": ["字符串"]},
    ]
    args = MultiDict([("code", "S0001"), ("type", "single"), ("difficulty", "2"), ("tags", "数组")])
    filtered, code_filter, type_filter, difficulty_filter, tags_filter = _filter_question_bank(questions, args)
    assert [row["id"] for row in filtered] == [1]
    assert code_filter == "S0001"
    assert type_filter == "single"
    assert difficulty_filter == "2"
    assert tags_filter == ["数组"]
