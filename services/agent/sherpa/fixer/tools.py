"""Workspace tools for the coding agent, confined to the store directory of a temp clone."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.genai import types

from sherpa.gitrepo import run

BLOCKED_PARTS = {".git", "node_modules", ".next", "dist", "build", "coverage"}
SECRET_NAME_RE = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|credentials|secret)", re.I)
MAX_READ = 60_000
MAX_WRITE = 200_000


class ToolError(Exception):
    pass


@dataclass
class Workspace:
    root: Path  # the store directory; nothing outside it may be read or written
    changed: set[str] = field(default_factory=set)
    last_build_ok: bool | None = None
    last_build_output: str = ""
    installed_hash: str = ""
    _install_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _prewarm: asyncio.Task | None = field(default=None, repr=False)

    def resolve(self, rel: str, *, write: bool = False) -> Path:
        rel = (rel or ".").replace("\\", "/").lstrip("/")
        path = (self.root / rel).resolve()
        if path != self.root.resolve() and self.root.resolve() not in path.parents:
            raise ToolError(f"{rel} is outside the store directory")
        parts = set(path.relative_to(self.root.resolve()).parts)
        if parts & BLOCKED_PARTS:
            raise ToolError(f"{rel} is in a blocked directory")
        if SECRET_NAME_RE.search(path.name) and path.name != ".env.example":
            raise ToolError(f"{rel} looks like a secrets file and is off limits")
        if write and path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"}:
            raise ToolError("binary files cannot be written")
        return path

    def peek(self, rel: str) -> str | None:
        """Current text of a file, or None if it doesn't exist (for streaming diffs to the console)."""
        try:
            p = self.resolve(rel)
        except ToolError:
            return None
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None

    # --- tools --------------------------------------------------------------
    def list_dir(self, path: str = ".") -> str:
        base = self.resolve(path)
        if not base.is_dir():
            raise ToolError(f"{path} is not a directory")
        out = []
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(self.root)
            if set(rel.parts) & BLOCKED_PARTS or len(rel.parts) - len(base.relative_to(self.root).parts) > 3:
                continue
            out.append(f"{rel.as_posix()}{'/' if p.is_dir() else ''}")
            if len(out) >= 300:
                out.append("... (truncated)")
                break
        return "\n".join(out) or "(empty)"

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        p = self.resolve(path)
        if not p.is_file():
            raise ToolError(f"{path} does not exist")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        s = max(1, start_line or 1)
        e = min(len(lines), end_line or len(lines))
        text = "\n".join(f"{i:4d}| {lines[i - 1]}" for i in range(s, e + 1))
        return text[:MAX_READ] + (
            "\n... (truncated, use start_line/end_line)" if len(text) > MAX_READ else ""
        )

    def search_code(self, pattern: str, glob: str | None = None) -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"bad regex: {exc}") from exc
        hits = []
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root).as_posix()
            if not p.is_file() or set(p.relative_to(self.root).parts) & BLOCKED_PARTS:
                continue
            if glob and not fnmatch.fnmatch(rel, glob):
                continue
            if p.suffix not in {
                ".js",
                ".mjs",
                ".cjs",
                ".ts",
                ".tsx",
                ".jsx",
                ".html",
                ".css",
                ".json",
                ".md",
            }:
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{n}: {line.strip()[:200]}")
                    if len(hits) >= 120:
                        return "\n".join(hits) + "\n... (truncated)"
        return "\n".join(hits) or "no matches"

    def write_file(self, path: str, content: str) -> str:
        if len(content) > MAX_WRITE:
            raise ToolError("file too large")
        p = self.resolve(path, write=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self.changed.add(p.relative_to(self.root).as_posix())
        self.last_build_ok = None
        return f"wrote {path} ({len(content.splitlines())} lines)"

    def apply_patch(self, path: str, old: str, new: str) -> str:
        p = self.resolve(path, write=True)
        if not p.is_file():
            raise ToolError(f"{path} does not exist; use write_file to create it")
        text = p.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise ToolError(f"`old` must match exactly once in {path}; it matched {count} times")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        self.changed.add(p.relative_to(self.root).as_posix())
        self.last_build_ok = None
        return f"patched {path}"

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not re.search(r"KEY|SECRET|TOKEN|PASSWORD", k)}
        env.update(
            {
                "CI": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
                "npm_config_audit": "false",
                "npm_config_fund": "false",
            }
        )
        return env

    async def install_deps(self) -> tuple[bool, str]:
        """npm install, skipped when package.json and the lockfile haven't changed since the last install."""
        async with self._install_lock:
            pkg, lock = self.root / "package.json", self.root / "package-lock.json"
            if not pkg.exists():
                return False, "no package.json"
            deps_hash = hashlib.sha256(
                pkg.read_bytes() + (lock.read_bytes() if lock.exists() else b"")
            ).hexdigest()
            if deps_hash == self.installed_hash and (self.root / "node_modules").exists():
                return True, "dependencies unchanged; install skipped"
            install = ["npm", "ci"] if lock.exists() else ["npm", "install"]
            code, out = await run(*install, cwd=self.root, timeout=420, env=self._env())
            if code != 0 and install[1] == "ci":
                code, out = await run("npm", "install", cwd=self.root, timeout=420, env=self._env())
            if code == 0:
                self.installed_hash = deps_hash
            return code == 0, out[-1500:]

    def prewarm(self) -> None:
        """Start installing dependencies in the background while the agent reads and plans."""
        if self._prewarm is None and (self.root / "package.json").exists():
            self._prewarm = asyncio.create_task(self.install_deps())

    async def run_build(self) -> str:
        pkg = self.root / "package.json"
        if not pkg.exists():
            raise ToolError("no package.json in the store directory")
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        env = self._env()
        ok, out = await self.install_deps()
        logs = [f"$ npm install -> {'ok' if ok else 'failed'}\n{out}"]
        for script in ("build", "test"):
            if ok and script in scripts:
                code, out = await run("npm", "run", script, cwd=self.root, timeout=420, env=env)
                logs.append(f"$ npm run {script} -> {code}\n{out[-3000:]}")
                ok = code == 0
        self.last_build_ok = ok
        self.last_build_output = "\n\n".join(logs)
        return ("BUILD PASSED\n" if ok else "BUILD FAILED\n") + self.last_build_output


def declarations() -> list[types.FunctionDeclaration]:
    def fn(
        name: str, description: str, props: dict[str, Any], required: list[str]
    ) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=name,
            description=description,
            parameters_json_schema={"type": "object", "properties": props, "required": required},
        )

    s = {"type": "string"}
    i = {"type": "integer"}
    return [
        fn("list_dir", "List files under a directory of the store (relative path).", {"path": s}, []),
        fn(
            "read_file",
            "Read a text file with line numbers.",
            {"path": s, "start_line": i, "end_line": i},
            ["path"],
        ),
        fn(
            "search_code",
            "Regex search across store source files.",
            {"path_glob": s, "pattern": s},
            ["pattern"],
        ),
        fn(
            "write_file",
            "Create or overwrite a text file with the full content.",
            {"path": s, "content": s},
            ["path", "content"],
        ),
        fn(
            "apply_patch",
            "Replace one exact, unique occurrence of `old` with `new` in a file.",
            {"path": s, "old": s, "new": s},
            ["path", "old", "new"],
        ),
        fn("run_build", "Install dependencies and run the build and tests. Must pass before finish.", {}, []),
        fn(
            "finish",
            "Finish when every required fix is done and the build passes.",
            {
                "summary": {"type": "string", "description": "Plain-English summary for the merchant."},
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"finding": s, "change": s, "files": {"type": "array", "items": s}},
                        "required": ["finding", "change"],
                    },
                },
            },
            ["summary", "changes"],
        ),
    ]
