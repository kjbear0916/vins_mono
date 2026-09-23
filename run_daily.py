"""
Daily workflow runner.
Reads tasks from task_daily.txt, runs each through the coding agent,
and writes a timestamped log per run (under logs/).

Usage:
    python run_daily.py            # run tasks listed in task_daily.txt
    python run_daily.py mytasks.txt
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows consoles (cp950 default breaks Chinese text)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import simple_coding_agent as agent  # noqa: E402

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Also root the sandbox at the project dir so tasks live next to the scripts
os.environ.setdefault("AGENT_WORKSPACE", str(BASE_DIR / "agent_workspace"))


def load_tasks(path: Path) -> list[str]:
    """Read non-empty, non-comment lines from the task file."""
    if not path.exists():
        raise FileNotFoundError(f"任务文件不存在: {path}")
    tasks = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            tasks.append(line)
    return tasks


def run_one(task: str, log_path: Path) -> int:
    """Run a single task, write output to log_path. Returns 0 on success, 1 on failure."""
    with open(log_path, "w", encoding="utf-8") as f:
        def logger(text):
            print(text)
            f.write(text + "\n")
            f.flush()

        logger(f"[{datetime.now().isoformat()}] TASK: {task}")
        try:
            answer = agent.run_agent(task, logger=logger)
            logger(f"\n[{datetime.now().isoformat()}] DONE")
            logger(f"\n=== FINAL ANSWER ===\n{answer}")
            return 0
        except Exception as e:
            logger(f"\n[{datetime.now().isoformat()}] ERROR: {e}")
            return 1


def main():
    task_file = BASE_DIR / (sys.argv[1] if len(sys.argv) > 1 else "task_daily.txt")
    print(f"读取任务文件: {task_file}")
    tasks = load_tasks(task_file)
    if not tasks:
        print("任务文件是空的（没有有效任务）。")

    date_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    failed = 0
    for i, task in enumerate(tasks, 1):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = LOGS_DIR / f"{date_stamp}_task{i:02d}.log"
        print(f"\n══════════════════════════════════════════════")
        print(f"执行任务 {i}/{len(tasks)}: {task}")
        print(f"日志: {log_path}")
        if run_one(task, log_path) != 0:
            failed += 1

    print(f"\n完成。共 {len(tasks)} 项任务，成功 {len(tasks) - failed} 项，失败 {failed} 项。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())