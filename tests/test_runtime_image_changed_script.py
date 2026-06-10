import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "ci/docker/runtime-image-changed.sh"


def run(command: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_EMAIL": "ci@example.test",
            "GIT_AUTHOR_NAME": "CI Test",
            "GIT_COMMITTER_EMAIL": "ci@example.test",
            "GIT_COMMITTER_NAME": "CI Test",
        }
    )
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def commit(repo: Path, message: str) -> None:
    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-m", message], cwd=repo)


def write(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo)
    write(repo, "Dockerfile", "FROM python:3.14-slim\n")
    write(repo, ".dockerignore", ".git\n")
    write(repo, "pyproject.toml", "[project]\nname = 'app'\nversion = '0.1.0'\n")
    write(repo, "uv.lock", "# lock\n")
    write(repo, "src/app.py", "print('hello')\n")
    write(repo, "README.md", "# app\n")
    commit(repo, "initial runtime")
    return repo


def test_exits_zero_when_runtime_inputs_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    run(["git", "tag", "v0.1.0"], cwd=repo)
    write(repo, "src/app.py", "print('changed')\n")
    commit(repo, "change runtime")

    result = run([str(SCRIPT)], cwd=repo)

    assert result.returncode == 0
    assert "runtime image inputs changed" in result.stdout


def test_exits_one_when_only_non_runtime_files_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    run(["git", "tag", "v0.1.0"], cwd=repo)
    write(repo, "docs/usage.md", "docs only\n")
    commit(repo, "change docs")

    result = run([str(SCRIPT)], cwd=repo, check=False)

    assert result.returncode == 1
    assert "runtime image inputs did not change" in result.stdout


def test_exits_one_when_only_ci_helper_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    run(["git", "tag", "v0.1.0"], cwd=repo)
    write(repo, "ci/docker/helper.sh", "#!/bin/sh\n")
    commit(repo, "change ci helper")

    result = run([str(SCRIPT)], cwd=repo, check=False)

    assert result.returncode == 1
    assert "runtime image inputs did not change" in result.stdout


def test_exits_zero_without_previous_semver_tag(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    result = run([str(SCRIPT)], cwd=repo)

    assert result.returncode == 0
    assert "no previous semver tag" in result.stdout
