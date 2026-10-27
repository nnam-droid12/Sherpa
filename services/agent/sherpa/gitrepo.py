"""Shallow clones of store repos into a temp dir, authenticated with the scoped GitHub token."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from sherpa.config import get_settings

REPO_RE = re.compile(r"^(?:https://github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def parse_repo(repo: str) -> tuple[str, str]:
    m = REPO_RE.match(repo.strip())
    if not m:
        raise ValueError(f"not a GitHub repo: {repo!r}")
    return m.group(1), m.group(2)


async def run(*args: str, cwd: Path | None = None, timeout: int = 300, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return 124, "timed out"
    return proc.returncode or 0, out.decode(errors="ignore")


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


async def clone(repo: str, branch: str | None = None) -> Path:
    owner, name = parse_repo(repo)
    token = get_settings().github_token
    auth = f"x-access-token:{token}@" if token else ""
    dest = Path(tempfile.mkdtemp(prefix=f"sherpa-{name}-"))
    args = ["git", "clone", "--depth", "50"]
    if branch:
        args += ["--branch", branch]
    args += [f"https://{auth}github.com/{owner}/{name}.git", str(dest)]
    code, out = await run(*args, timeout=180)
    if code != 0:
        raise RuntimeError(f"git clone failed: {_redact(out, token)[-400:]}")
    return dest
