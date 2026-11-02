"""Branch, commit, push and pull-request helpers for store repos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sherpa.config import get_settings
from sherpa.gitrepo import parse_repo, run

API = "https://api.github.com"
AUTHOR = ("Sherpa", "sherpa@users.noreply.github.com")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=8),
    retry=retry_if_exception_type(httpx.TransportError),
)


@_retry
async def _call(method: str, path: str, **kw: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, f"{API}{path}", headers=_headers(), **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub {method} {path} failed: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


async def git(workdir: Path, *args: str, timeout: int = 120) -> str:
    code, out = await run("git", *args, cwd=workdir, timeout=timeout)
    if code != 0:
        token = get_settings().github_token
        raise RuntimeError(f"git {args[0]} failed: {out.replace(token, '***') if token else out}"[-600:])
    return out


async def commit_and_push(workdir: Path, branch: str, message: str, paths: list[str] | None = None) -> str:
    """Create `branch`, commit the given paths (or everything) and push. Returns the commit sha."""
    await git(workdir, "checkout", "-B", branch)
    # Never commit dependencies or build output, even if the repo lacks a .gitignore.
    exclude = workdir / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(
        "\n".join(["node_modules/", ".next/", "dist/", "build/", "coverage/", ".env", ".env.*"]) + "\n",
        encoding="utf-8",
    )
    await git(workdir, "add", "--all", "--", *(paths or ["."]))
    name, email = AUTHOR
    await git(workdir, "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message)
    await git(workdir, "push", "--force", "origin", f"HEAD:refs/heads/{branch}", timeout=180)
    return (await git(workdir, "rev-parse", "HEAD")).strip()


async def default_branch(repo: str) -> str:
    owner, name = parse_repo(repo)
    return (await _call("GET", f"/repos/{owner}/{name}"))["default_branch"]


async def open_pr(repo: str, head: str, base: str, title: str, body: str) -> dict[str, Any]:
    owner, name = parse_repo(repo)
    existing = await _call(
        "GET", f"/repos/{owner}/{name}/pulls", params={"head": f"{owner}:{head}", "state": "open"}
    )
    if isinstance(existing, list) and existing:
        pr = existing[0]
        await _call(
            "PATCH", f"/repos/{owner}/{name}/pulls/{pr['number']}", json={"title": title, "body": body}
        )
        return pr
    return await _call(
        "POST",
        f"/repos/{owner}/{name}/pulls",
        json={"title": title, "head": head, "base": base, "body": body},
    )


async def comment(repo: str, number: int, body: str) -> str:
    owner, name = parse_repo(repo)
    res = await _call("POST", f"/repos/{owner}/{name}/issues/{number}/comments", json={"body": body})
    return res.get("html_url", "")
