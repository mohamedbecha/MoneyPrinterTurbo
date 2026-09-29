import subprocess
from pathlib import Path

import pytest

from tools import render


def _topic(tmp_path, text):
    d = tmp_path / "videos" / "great-stink"
    d.mkdir(parents=True)
    (d / "script.md").write_text(text, encoding="utf-8")
    return d


def test_read_script_uses_heading_as_subject_and_strips_it(tmp_path):
    d = _topic(tmp_path, "# The Great Stink of 1858\n\nIn the summer of 1858...\n")
    subject, script = render.read_script(d)
    assert subject == "The Great Stink of 1858"
    assert script == "In the summer of 1858..."


def test_read_script_falls_back_to_slug_subject(tmp_path):
    d = _topic(tmp_path, "In the summer of 1858...\n")
    assert render.read_script(d) == ("Great Stink", "In the summer of 1858...")


def test_read_script_requires_script_md(tmp_path):
    with pytest.raises(SystemExit, match="script.md"):
        render.read_script(tmp_path / "videos" / "missing")


def test_render_moves_task_dir_into_topic_renders(tmp_path, monkeypatch):
    d = _topic(tmp_path, "# Subject\n\nBody.\n")
    tasks = tmp_path / "storage" / "tasks"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        task_id = cmd[cmd.index("--task-id") + 1]
        (tasks / task_id).mkdir(parents=True)
        (tasks / task_id / "final-1.mp4").write_bytes(b"mp4")
        kwargs["stdout"].write(b"log line\n")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(render.subprocess, "run", fake_run)
    out, code = render.render(d, tasks_dir=tasks, extra_args=["--voice-name", "kokoro:bf_emma"])

    assert code == 0
    assert out.parent == d / "renders"
    assert (out / "final-1.mp4").read_bytes() == b"mp4"
    assert (out / "render.log").read_bytes() == b"log line\n"
    assert not any(tasks.iterdir())
    cmd = calls[0]
    assert cmd[cmd.index("--video-script") + 1] == "Body."
    assert cmd[cmd.index("--video-subject") + 1] == "Subject"
    assert cmd[cmd.index("--video-aspect") + 1] == "16:9"
    # extra args come last so they override the defaults
    assert cmd[-2:] == ["--voice-name", "kokoro:bf_emma"]


def test_render_keeps_partial_output_on_failure(tmp_path, monkeypatch):
    d = _topic(tmp_path, "Body.\n")
    tasks = tmp_path / "storage" / "tasks"

    def fake_run(cmd, **kwargs):
        (tasks / cmd[cmd.index("--task-id") + 1]).mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 1)

    monkeypatch.setattr(render.subprocess, "run", fake_run)
    out, code = render.render(d, tasks_dir=tasks)
    assert code == 1
    assert out.is_dir() and (out / "render.log").exists()


def test_topic_dir_rejects_path_escape(tmp_path):
    with pytest.raises(SystemExit):
        render.topic_dir("../etc", root=tmp_path)
