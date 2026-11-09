import subprocess

import pytest

from sherpa.fixer import github


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    sh(tmp_path, "init", "-q", "--bare", str(origin))
    sh(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / ".gitignore").write_text("generated.log\n")
    (work / "server.js").write_text("old\n")
    sh(work, "add", "-A")
    sh(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    sh(work, "remote", "add", "origin", str(origin))
    return work, origin


@pytest.mark.asyncio
async def test_an_ignored_path_in_the_list_does_not_fail_the_commit(repo):
    work, origin = repo
    (work / "server.js").write_text("new\n")
    (work / "generated.log").write_text("noise\n")
    sha = await github.commit_and_push(work, "fix", "fix: change", paths=["server.js", "generated.log"])
    assert sh(origin, "rev-parse", "refs/heads/fix") == sha
    assert sh(work, "show", "--name-only", "--format=", sha) == "server.js"


@pytest.mark.asyncio
async def test_nothing_to_commit_returns_the_current_head(repo):
    work, origin = repo
    head = sh(work, "rev-parse", "HEAD")
    assert await github.commit_and_push(work, "fix", "fix: nothing", paths=["server.js"]) == head
    assert sh(work, "log", "--oneline").count("\n") == 0  # still only the base commit
