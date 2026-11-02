"""Observe registered projects and select due knowledge reviews, without a scheduler."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from project_governance import load_registry, machine_id

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TZ = timezone(timedelta(hours=8))
SKIP = {".git", ".agents", ".ai-skill", ".venv", "venv", "node_modules", "dist", "build", "release",
        "releases", "out", "target", "vendor", "coverage", "__pycache__", ".pytest_cache", ".next",
        "logs", "data", "models", "downloads", "artifacts", ".cache",
        "win-unpacked", "win-ia32-unpacked", "win-arm64-unpacked", "linux-unpacked",
        "linux-arm64-unpacked"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".cjs", ".mjs", ".vue", ".svelte",
                   ".go", ".rs", ".css", ".scss", ".html", ".md", ".json", ".toml", ".yaml", ".yml", ".spec"}
KNOWLEDGE = ("knowledge", "evolution", "decisions.md", "preferences.md")


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp needs timezone")
    return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def choose_interval(policy: dict, state: dict, now: datetime) -> tuple[int, str]:
    base = policy["base_days"]
    current = state.get("effective_days", base)
    if not policy["adaptive"]:
        return base, "人工固定频率"
    if state.get("availability") != "available":
        return current, "项目不可读取，保持频率"
    recent = [event for event in state.get("events", []) if now - timedelta(hours=48) <= parse_time(event["at"]) <= now]
    development = [event for event in recent if event["files"] > event["knowledge_files"]]
    development_days = {parse_time(event["at"]).astimezone(LOCAL_TZ).date() for event in development}
    if len(development_days) >= 2:
        return 1, "近48小时两个不同日期检测到开发变化，升为每日"
    continuous = parse_time(state.get("continuous_since", now.isoformat()))
    last_activity = parse_time(state.get("last_development_at") or state.get("first_observed_at", now.isoformat()))
    idle = (now - max(continuous, last_activity)).total_seconds() / 86400
    desired, reason = current, "活动未达到调整条件，保持频率"
    if idle >= 14:
        desired, reason = 7, "连续完整观察14天无开发变化，降为每周"
    elif idle >= 7 and current == 1:
        desired, reason = 2, "连续完整观察7天无开发变化，降为每两天"
    elif development and current == 7:
        desired, reason = 2, "近48小时检测到开发变化，升为每两天"
    if desired > current and state.get("changed_at") and now - parse_time(state["changed_at"]) < timedelta(days=2):
        return current, "调频后48小时观察期，暂不降频"
    return desired, reason


def scan_project(root: Path) -> dict[str, str]:
    """Hash bounded source and authored knowledge; never follow external links."""
    root = root.resolve()
    files: set[Path] = set()
    visited = 0
    def scan_error(error: OSError) -> None:
        raise error

    def collect(start: Path, suffixes: set[str]) -> None:
        nonlocal visited
        for directory, dirs, names in os.walk(start, followlinks=False, onerror=scan_error):
            dirs[:] = [name for name in dirs if name.lower() not in SKIP and not name.startswith(".") and not name.endswith(".app")
                       and not (Path(directory) / name).is_symlink()
                       and not (Path(directory) / name).is_junction()]
            for name in names:
                visited += 1
                if visited > 30000:
                    raise ValueError("项目文件超过扫描上限，检测不完整，保持频率")
                path = Path(directory) / name
                if path.suffix.lower() in suffixes and not name.startswith("."):
                    files.add(path)

    collect(root, SOURCE_SUFFIXES)
    for relative in KNOWLEDGE:
        path = root / ".ai-skill/project" / relative
        chain = (root / ".ai-skill", root / ".ai-skill/project", path)
        if any(part.is_symlink() or part.is_junction() for part in chain):
            continue
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            collect(path, {".md"})
    result = {}
    total = 0
    for path in sorted(files):
        if not path.resolve().is_relative_to(root) or path.is_symlink() or path.is_junction():
            continue
        stat = path.stat()
        if stat.st_size > 5 * 1024 * 1024:
                raise ValueError(f"{path.relative_to(root)} 超过5MB，检测不完整，保持频率")
        total += stat.st_size
        if total > 100 * 1024 * 1024:
            raise ValueError("源码内容超过100MB，检测不完整，保持频率")
        data = path.read_bytes()
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("扫描期间文件仍在写入，稍后重试")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return result


def fingerprint(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


class CadenceService:
    """Own cadence settings, observations and review receipts in the central library."""

    def __init__(self, root: Path, machine: str | None = None):
        self.root = root.resolve()
        self.machine = machine or machine_id()
        self.path = self.root / "governance/cadence" / f"{self.machine}.json"
        # Shared pre-split file; only seeds a machine that has no file of its own yet.
        self.legacy_path = self.root / "governance/cadence.json"

    def read(self) -> dict:
        if not self.path.exists():
            if not self.legacy_path.exists():
                return {"version": 1, "revision": 0, "projects": {}, "last_tick_at": None}
            data = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("projects"), dict):
                raise ValueError("Invalid cadence state; refusing to reset it")
            local = {name for name, project in self.registry().items() if project.local}
            data["projects"] = {name: entry for name, entry in data["projects"].items() if name in local}
            return data
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("projects"), dict):
            raise ValueError("Invalid cadence state; refusing to reset it")
        return data

    @contextmanager
    def write(self) -> Iterator[dict]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError as error:
            raise ValueError("Another cadence operation is active; retry after it finishes") from error
        temporary = self.path.with_suffix(".tmp")
        try:
            with handle:
                handle.write(f"pid={os.getpid()}\n")
            data = self.read()
            yield data
            with temporary.open("w", encoding="utf-8", newline="\n") as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write("\n")
            os.replace(temporary, self.path)
        finally:
            lock.unlink()

    def registry(self) -> dict:
        return {project.name: project for project in load_registry(self.root / "governance/projects.json")}

    @staticmethod
    def entry(data: dict, name: str) -> dict:
        return data["projects"].setdefault(name, {"policy": {"selected": False, "base_days": 7, "adaptive": True}, "state": {}})

    def configure(self, name: str, policy: dict, *, revision: int, now: datetime | None = None) -> None:
        if name not in self.registry():
            raise ValueError("Only registered projects can be selected")
        if set(policy) != {"selected", "base_days", "adaptive"} or type(policy["selected"]) is not bool or type(policy["adaptive"]) is not bool:
            raise ValueError("Invalid selection policy")
        if type(policy["base_days"]) is not int or policy["base_days"] not in (1, 2, 7):
            raise ValueError("Cadence must be 1, 2 or 7 days")
        with self.write() as data:
            if data["revision"] != revision:
                raise ValueError("设置已被另一个页面修改，请刷新后再保存")
            entry = self.entry(data, name)
            previous = entry["policy"]
            if policy["base_days"] != previous["base_days"] or policy["adaptive"] != previous["adaptive"]:
                entry["state"]["effective_days"] = policy["base_days"]
                entry["state"]["reason"] = "用户更新基础频率"
                entry["state"]["changed_at"] = (now or utc_now()).isoformat()
            entry["policy"] = policy
            data["revision"] += 1

    def tick(self, now: datetime | None = None) -> dict:
        now = now or utc_now()
        with self.write() as data:
            for name, project in self.registry().items():
                if not project.local:
                    continue
                entry = self.entry(data, name)
                state = entry["state"]
                if not project.enabled:
                    state["availability"] = "disabled"
                    continue
                if not project.path.is_dir():
                    state.update(availability="missing", reason="项目目录不可用，保持频率")
                    state["continuous_since"] = now.isoformat()
                    continue
                try:
                    files = scan_project(project.path)
                except (OSError, ValueError) as error:
                    state.update(availability="error", reason=str(error), continuous_since=now.isoformat())
                    continue
                last = state.get("last_observed_at")
                if last and now < parse_time(last):
                    raise ValueError("Observation clock moved backwards")
                if not last or now - parse_time(last) > timedelta(hours=36) or state.get("availability") != "available":
                    state["continuous_since"] = now.isoformat()
                state.setdefault("first_observed_at", now.isoformat())
                previous = state.get("files")
                changed = [] if previous is None else sorted(name for name in set(files) | set(previous) if files.get(name) != previous.get(name))
                events = [event for event in state.get("events", []) if parse_time(event["at"]) >= now - timedelta(days=30)]
                if changed:
                    knowledge = sum(name.startswith(".ai-skill/project/") for name in changed)
                    events.append({"at": now.isoformat(), "files": len(changed), "knowledge_files": knowledge})
                    state["last_activity_at"] = now.isoformat()
                    if len(changed) > knowledge:
                        state["last_development_at"] = now.isoformat()
                state.update(files=files, last_observed_at=now.isoformat(), availability="available", events=events,
                             observed_digest=fingerprint(files), last_changed_files=changed[:50])
                sampled = set(state.get("sampled_dates", []))
                sampled.add(now.astimezone(LOCAL_TZ).date().isoformat())
                state["sampled_dates"] = sorted(sampled)[-30:]
                old = state.get("effective_days", entry["policy"]["base_days"])
                days, reason = choose_interval(entry["policy"], state, now)
                if days != old:
                    state["changed_at"] = now.isoformat()
                    history = state.setdefault("adjustments", [])
                    history.append({"at": now.isoformat(), "from": old, "to": days, "reason": reason})
                    state["adjustments"] = history[-20:]
                state.update(effective_days=days, reason=reason)
            data["last_tick_at"] = now.isoformat()
        return self.board(now)

    def board(self, now: datetime | None = None) -> dict:
        now = now or utc_now()
        data = self.read()
        rows = []
        for name, project in self.registry().items():
            entry = self.entry(data, name)
            policy, state = entry["policy"], entry["state"]
            days = state.get("effective_days", policy["base_days"])
            completed = state.get("last_completed_at")
            next_due = parse_time(completed) + timedelta(days=days) if completed else now
            if state.get("retry_after"):
                next_due = max(next_due, parse_time(state["retry_after"]))
            active = state.get("active_run")
            if active and parse_time(active["expires_at"]) <= now:
                active = None
            available = state.get("availability", "not_observed") if project.local else "not_local"
            if available == "available" and (not state.get("last_observed_at")
                    or now - parse_time(state["last_observed_at"]) > timedelta(hours=36)):
                available = "stale"
            recent = [event for event in state.get("events", []) if now - timedelta(hours=48) <= parse_time(event["at"]) <= now]
            history = []
            for offset in range(13, -1, -1):
                date = (now.astimezone(LOCAL_TZ) - timedelta(days=offset)).date()
                count = sum(parse_time(event["at"]).astimezone(LOCAL_TZ).date() == date for event in state.get("events", []))
                history.append({"date": date.isoformat(), "events": count, "observed": date.isoformat() in state.get("sampled_dates", [])})
            rows.append({"name": name, "path": str(project.path), **policy, "effective_days": days,
                         "reason": {"stale": "检测已超过36小时，请重新检测", "not_local": "项目不在本机，由所在机器记录"}.get(
                             available, state.get("reason", "尚未采样，等待建立活动基线")), "availability": available,
                         "due": policy["selected"] and project.enabled and available == "available" and now >= next_due and not active,
                         "next_due_at": next_due.isoformat() if policy["selected"] else None,
                         "last_observed_at": state.get("last_observed_at"), "last_activity_at": state.get("last_activity_at"),
                         "last_completed_at": completed, "last_result": state.get("last_result"),
                         "active_run": active, "events_48h": len(recent),
                         "knowledge_changes_48h": sum(event["knowledge_files"] for event in recent),
                         "pending_changes": bool(state.get("observed_digest")) and state.get("observed_digest") != state.get("reviewed_digest"),
                         "knowledge_files": sum(path.startswith(".ai-skill/project/") for path in state.get("files", {})),
                         "history": history, "adjustments": state.get("adjustments", []),
                         "last_receipt": state.get("last_receipt")})
        return {"revision": data["revision"], "generated_at": now.isoformat(), "last_tick_at": data.get("last_tick_at"),
                "scheduler": "user-managed", "machine": self.machine, "projects": rows}

    def claim(self, name: str, now: datetime | None = None) -> dict:
        now = now or utc_now()
        with self.write() as data:
            row = next((row for row in self.board(now)["projects"] if row["name"] == name), None)
            if not row or not row["due"]:
                raise ValueError("Project is not due, unavailable, unselected or already claimed")
            state = self.entry(data, name)["state"]
            job = {"run_id": secrets.token_hex(12), "claimed_at": now.isoformat(),
                   "expires_at": (now + timedelta(hours=6)).isoformat(), "source_digest": state["observed_digest"]}
            state["active_run"] = job
            return {"project": name, "path": row["path"], **job,
                    "instruction": "先在项目内核实并沉淀知识；有通用证据才提中央候选。未经稳定版验收不下发。完成后提交实际证据回执。"}

    def complete(self, name: str, run_id: str, status: str, evidence: Path, now: datetime | None = None) -> None:
        now = now or utc_now()
        if status not in {"completed", "no_change", "failed"}:
            raise ValueError("Invalid completion status")
        content = evidence.read_bytes() if evidence.is_file() else b""
        if not content or len(content) > 2 * 1024 * 1024:
            raise ValueError("Nonempty evidence report up to 2MB required")
        if name not in self.registry():
            raise ValueError("Unknown project")
        with self.write() as data:
            state = self.entry(data, name)["state"]
            job = state.get("active_run")
            if not job or job["run_id"] != run_id or parse_time(job["expires_at"]) <= now:
                raise ValueError("Unknown or expired claim; do not overwrite another run")
            output = self.root / "governance/receipts" / f"{run_id}.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as handle:
                handle.write(content)
            state.update(active_run=None, last_result=status,
                         last_receipt={"run_id": run_id, "status": status, "at": now.isoformat(),
                                       "evidence": str(output), "sha256": hashlib.sha256(content).hexdigest()})
            if status in {"completed", "no_change"}:
                state.update(last_completed_at=now.isoformat(), reviewed_digest=job["source_digest"], retry_after=None)
            else:
                state["retry_after"] = (now + timedelta(hours=6)).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tick", "status", "claim", "complete"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--project")
    parser.add_argument("--run-id")
    parser.add_argument("--result", choices=("completed", "no_change", "failed"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    service = CadenceService(args.root)
    try:
        if args.command == "tick":
            result = service.tick()
            result["due_projects"] = [row["name"] for row in result["projects"] if row["due"]]
        elif args.command == "status":
            result = service.board()
        elif args.command == "claim":
            result = service.claim(args.project)
        else:
            if not all((args.project, args.run_id, args.result, args.evidence)):
                raise ValueError("complete requires project, run-id, result and evidence")
            service.complete(args.project, args.run_id, args.result, args.evidence)
            result = {"recorded": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"[ERROR] {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
