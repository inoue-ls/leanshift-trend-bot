import os
import pathlib
import shutil
import signal
import subprocess
import time
from datetime import date

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "run_daily.sh"

# main.py の代わり: 1 秒かかる実行をまねて、実行回数を残し、当日分の outputs を作る
FAKE_MAIN = """
import pathlib, time
from datetime import date
time.sleep(1)
with open("runs.txt", "a") as f:
    f.write("run\\n")
pathlib.Path("outputs").mkdir(exist_ok=True)
pathlib.Path("outputs", f"{date.today().isoformat()}_trends.md").write_text("ok")
"""


@pytest.fixture
def project(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts" / "run_daily.sh")
    (tmp_path / "main.py").write_text(FAKE_MAIN)
    return tmp_path


def start(project: pathlib.Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["bash", str(project / "scripts" / "run_daily.sh")],
        cwd=project,
        start_new_session=True,
    )


def test_survives_terminal_hangup(project: pathlib.Path) -> None:
    # .bashrc から & で起動したジョブは、ターミナルを閉じるとプロセスグループごと SIGHUP を受ける
    proc = start(project)
    time.sleep(0.5)
    os.killpg(proc.pid, signal.SIGHUP)
    proc.wait(timeout=10)

    assert (project / "outputs" / f"{date.today().isoformat()}_trends.md").exists()
    log = (project / "logs" / f"{date.today().isoformat()}.log").read_text()
    assert "完了" in log


def test_second_start_while_running_is_skipped(project: pathlib.Path) -> None:
    # cron と .bashrc が同時に起動しても main.py は 1 回だけ走る
    first = start(project)
    time.sleep(0.2)
    second = start(project)
    first.wait(timeout=10)
    second.wait(timeout=10)

    assert (project / "runs.txt").read_text() == "run\n"
    log = (project / "logs" / f"{date.today().isoformat()}.log").read_text()
    assert "[SKIP] 実行中" in log


# core.daily_triage の代わり: 起動された時点のログを残す
FAKE_TRIAGE = """
import pathlib
from datetime import date
log = pathlib.Path("logs", f"{date.today().isoformat()}.log").read_text()
pathlib.Path("triage.txt").write_text(log)
"""


def _with_fake_triage(project: pathlib.Path) -> None:
    (project / "core").mkdir()
    (project / "core" / "__init__.py").write_text("")
    (project / "core" / "daily_triage.py").write_text(FAKE_TRIAGE)


def test_triage_runs_after_the_result_is_logged(project: pathlib.Path) -> None:
    _with_fake_triage(project)

    proc = start(project)
    proc.wait(timeout=10)

    assert proc.returncode == 0
    assert "完了" in (project / "triage.txt").read_text()


def test_triage_runs_even_when_main_fails_and_exit_code_is_kept(project: pathlib.Path) -> None:
    _with_fake_triage(project)
    (project / "main.py").write_text("import sys\nsys.exit(3)\n")

    proc = start(project)
    proc.wait(timeout=10)

    assert proc.returncode == 3
    assert "失敗 (exit 3)" in (project / "triage.txt").read_text()
