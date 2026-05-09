import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from cals_app import create_app


ROOT_DIR = Path(__file__).resolve().parent


def _runner_url():
    return os.environ.get("RUNNER_URL", "http://127.0.0.1:18080").rstrip("/")


def _runner_health_ok(timeout=2):
    try:
        with urllib.request.urlopen(_runner_url() + "/health", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _wait_runner_ready(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _runner_health_ok(timeout=2):
            return True
        time.sleep(1)
    return False


def _start_runner_once():
    if os.environ.get("CALS_SKIP_RUNNER") == "1":
        print("[CALS] 已跳过编译运行器自动启动（CALS_SKIP_RUNNER=1）")
        return

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return

    if _runner_health_ok():
        print(f"[CALS] 编译运行器已就绪：{_runner_url()}")
        return

    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        print("[CALS] 未找到 docker 命令，无法自动启动编译运行器")
        return

    print("[CALS] 正在启动编译运行器 c_runner ...")
    try:
        proc = subprocess.run(
            [docker_cmd, "compose", "up", "-d", "--build", "c_runner"],
            cwd=str(ROOT_DIR),
            check=False,
        )
    except Exception as exc:
        print(f"[CALS] 启动编译运行器失败：{exc}")
        return

    if proc.returncode != 0:
        print(f"[CALS] docker compose 返回非 0 状态码：{proc.returncode}")
        return

    if _wait_runner_ready(timeout=25):
        print(f"[CALS] 编译运行器启动成功：{_runner_url()}")
    else:
        print(f"[CALS] 编译运行器未在预期时间内就绪：{_runner_url()}")


load_dotenv()
_start_runner_once()
app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
