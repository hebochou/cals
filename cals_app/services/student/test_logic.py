import cals_app.services.student.evaluation as evaluation_mod
import cals_app.services.student.recommendations as rec_mod


def test_ui_tags_from_full_deduplicates_categories():
    assert rec_mod._ui_tags_from_full(["数组:一维", "数组:二维", "字符串", "字符串"]) == ["数组", "字符串"]


def test_recommend_meta_uses_recent_window(monkeypatch):
    monkeypatch.setattr(
        rec_mod,
        "load_attempts",
        lambda username: [
            {"q_id": 1, "tags": ["数组"], "is_correct": False},
            {"q_id": 2, "tags": ["数组"], "is_correct": True},
            {"q_id": 3, "tags": ["字符串"], "is_correct": True},
        ],
    )
    meta = rec_mod._recommend_meta("alice", window=2)
    assert meta["ready"] is False
    assert meta["need"] == 17
    assert meta["acc"] == 1.0
    assert meta["focus_tags"][0] in {"数组", "字符串"}


def test_pick_recommended_question_returns_random_choice_when_not_ready(monkeypatch):
    monkeypatch.setattr(rec_mod, "_recommend_meta", lambda username, window=20: {"ready": False, "need": 1, "acc": 0.0})
    monkeypatch.setattr(rec_mod.random, "choice", lambda pool: pool[0])
    question, meta = rec_mod._pick_recommended_question("alice", [{"id": 1, "enabled": True}, {"id": 2, "enabled": True}])
    assert question["id"] == 1
    assert meta["ready"] is False


def test_evaluate_coding_question_returns_true_when_output_matches(monkeypatch):
    monkeypatch.setattr(
        evaluation_mod,
        "_runner_post_json",
        lambda path, data, timeout=12: {"ok": True, "compile_ok": True, "run_ok": True, "stdout": "42\n"},
    )
    ok, msg = evaluation_mod._evaluate_coding_question(
        {"answer_meta": {"sample_input": "", "sample_output": "42\n", "constraints": {"time_limit_ms": 1000}}},
        "int main(){}",
    )
    assert ok is True
    assert msg == ""


def test_evaluate_coding_question_returns_compile_error_message(monkeypatch):
    monkeypatch.setattr(
        evaluation_mod,
        "_runner_post_json",
        lambda path, data, timeout=12: {"ok": True, "compile_ok": False, "stderr": "syntax error"},
    )
    ok, msg = evaluation_mod._evaluate_coding_question(
        {"answer_meta": {"sample_input": "", "sample_output": "", "constraints": {"time_limit_ms": 1000}}},
        "broken",
    )
    assert ok is False
    assert msg == "syntax error"
