import urllib.error

from cals_app.utils.helpers import _compare_outputs, _runner_post_json, _unescape_sample_text


def _evaluate_coding_question(question, user_code):
    meta = question.get("answer_meta") if isinstance(question.get("answer_meta"), dict) else {}
    stdin_text = _unescape_sample_text(meta.get("sample_input") or "")
    expected_output = _unescape_sample_text(meta.get("sample_output") or "")
    time_limit_ms = int(meta.get("constraints", {}).get("time_limit_ms") or 1500)
    run_timeout = max(0.5, min(10.0, time_limit_ms / 1000.0))
    try:
        result = _runner_post_json(
            "/run",
            {"code": user_code or "", "stdin": stdin_text, "compile_timeout": 10.0, "run_timeout": run_timeout},
            timeout=12,
        )
    except urllib.error.URLError:
        return False, "无法连接到编译服务"
    except Exception:
        return False, "编译服务异常"

    if not result or not result.get("ok"):
        return False, "编译服务异常"
    if not result.get("compile_ok"):
        return False, (result.get("stderr") or "编译错误").strip()
    if result.get("run_ok") is False:
        return False, (result.get("stderr") or "运行失败").strip()
    if expected_output == "":
        return True, ""
    if _compare_outputs(result.get("stdout", ""), expected_output):
        return True, ""
    return False, "输出不符合预期"
