"""Render videos/<topic>/script.md into videos/<topic>/renders/<timestamp>/.

Thin wrapper around upstream cli.py so upstream code stays untouched:

    uv run python tools/render.py great-stink
    uv run python tools/render.py great-stink --voice-name kokoro:bf_emma

An optional first line "# Title" in script.md becomes the video subject
(used for search terms) and is not narrated. Any extra arguments are passed
to cli.py after the defaults, so they override them.
"""

import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ARGS = [
    "--video-aspect", "16:9",
    "--video-source", "pixabay",
    "--voice-name", "kokoro:af_heart",
    "--match-materials-to-script",
    "--video-concat-mode", "sequential",
    "--video-count", "1",
]


def topic_dir(topic: str, root: Path = ROOT) -> Path:
    videos = (root / "videos").resolve()
    d = (videos / topic).resolve()
    if d.parent != videos:
        raise SystemExit(f"topic must be a folder name under videos/, got {topic!r}")
    return d


def read_script(d: Path) -> tuple[str, str]:
    path = d / "script.md"
    if not path.is_file():
        raise SystemExit(f"missing {path} - write the script there first")
    text = path.read_text(encoding="utf-8").strip()
    first, _, rest = text.partition("\n")
    if first.startswith("# "):
        return first[2:].strip(), rest.strip()
    return d.name.replace("-", " ").title(), text


def render(d: Path, tasks_dir: Path = ROOT / "storage" / "tasks", extra_args=()):
    subject, script = read_script(d)
    task_id = str(uuid.uuid4())
    cmd = [
        sys.executable, str(ROOT / "cli.py"), *DEFAULT_ARGS,
        "--task-id", task_id,
        "--video-subject", subject,
        "--video-script", script,
        *extra_args,
    ]
    out = d / "renders" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True)
    log_path = out / "render.log"
    print(f"rendering {d.name}, log: {log_path}", flush=True)
    with open(log_path, "wb") as log:
        code = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    task = tasks_dir / task_id
    if task.is_dir():
        for f in task.iterdir():
            shutil.move(str(f), out / f.name)
        task.rmdir()
    return out, code


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    d = topic_dir(argv[0])
    out, code = render(d, extra_args=argv[1:])
    print(f"{'done' if code == 0 else f'FAILED (exit {code})'}: {out.relative_to(ROOT)}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
