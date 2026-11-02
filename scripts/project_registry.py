"""Inspect known project integration markers and explicitly register exact paths."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from project_governance import load_registry

ROOT = Path(__file__).resolve().parents[1]
MARKERS = (".ai-skill/framework/RULES.md", ".ai-skill/project/managed-skills.json",
           ".agents/skills/project-knowledge-evolution/SKILL.md")
WORKFLOW = ".ai-skill/project/workflow-integration.json"


def integration_status(path: Path) -> dict:
    """Read fixed integration markers only; existence does not establish currency."""
    result = {"skill": "not_detected", "workflow": "unselected", "markers": [], "error": None}
    try:
        root = path.resolve()
        if not root.is_dir():
            return {**result, "skill": "unavailable", "error": "项目目录不可读取"}
        for relative in (*MARKERS, WORKFLOW):
            marker = root / relative
            if not marker.resolve().is_relative_to(root):
                raise ValueError("接入标记指向项目外部，未读取")
            if marker.is_file():
                result["markers"].append(relative)
        if MARKERS[0] in result["markers"]:
            result["skill"] = "detected"
        elif any(marker in result["markers"] for marker in MARKERS):
            result["skill"] = "partial"
        if WORKFLOW in result["markers"]:
            marker = root / WORKFLOW
            if marker.stat().st_size > 65536:
                raise ValueError("工作流接入标记超过读取上限")
            policy = json.loads(marker.read_text(encoding="utf-8"))
            if not isinstance(policy, dict) or policy.get("version") != 1 or type(policy.get("enabled")) is not bool:
                raise ValueError("工作流接入标记格式无效")
            result["workflow"] = "enabled" if policy["enabled"] else "disabled"
    except (OSError, ValueError) as error:
        result["error"] = str(error)
        result["workflow"] = "unknown"
    return result


def discover_known(root: Path) -> dict:
    """Inspect only an explicit saved-path inventory, without recursive discovery."""
    source = root / "governance/known-projects.json"
    result = {"projects": [], "errors": [], "known_count": 0, "imported_at": None,
              "source": "尚未导入已知项目清单"}
    if not source.exists():
        return result
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("projects"), list):
        raise ValueError("已知项目清单格式无效")
    result.update(known_count=len(data["projects"]), imported_at=data.get("imported_at"),
                  source=data.get("source", "用户提供的项目路径清单"))
    registered = {project.path for project in load_registry(root / "governance/projects.json")}
    seen = {root.resolve(), *registered}
    for item in data["projects"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not Path(item["path"]).is_absolute():
            result["errors"].append({"path": str(item), "error": "需要明确的绝对项目路径"})
            continue
        path = Path(item["path"]).resolve()
        if path in seen:
            continue
        seen.add(path)
        status = integration_status(path)
        if status["error"]:
            result["errors"].append({"path": str(path), "error": status["error"]})
        if status["markers"]:
            result["projects"].append({"name": item.get("label") or path.name, "path": str(path), "connection": status})
    return result


def register_project(root: Path, path_value: str, name: str = "") -> dict:
    """Register one user-chosen path without modifying the project or its cadence."""
    if not isinstance(path_value, str) or not Path(path_value.strip()).is_absolute():
        raise ValueError("请输入项目的完整绝对路径")
    target = Path(path_value.strip()).resolve()
    if not target.is_dir() or target == root.resolve() or target == Path(target.anchor):
        raise ValueError("请选择实际软件项目目录，不能登记磁盘根目录或中央 Skill 库自身")
    if not isinstance(name, str):
        raise ValueError("项目名称必须是文字")
    name = name.strip() or target.name
    if len(name) > 100 or any(ord(char) < 32 for char in name):
        raise ValueError("项目名称过长或包含控制字符")
    registry = root / "governance/projects.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    lock = registry.with_suffix(".lock")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError("其他会话正在登记项目，请稍后重试") from error
    temporary = None
    try:
        with handle:
            handle.write(f"pid={os.getpid()}\n")
        projects = load_registry(registry)
        for project in projects:
            if project.path == target:
                return {"registered": True, "created": False, "name": project.name, "path": str(target)}
        if any(project.name == name for project in projects):
            raise ValueError("该名称已用于其他路径，请更换项目名称；原登记保持不变")
        original = registry.read_bytes()
        data = json.loads(original)
        data["projects"].append({"name": name, "path": str(target), "enabled": True, "sync_approved": False})
        descriptor, filename = tempfile.mkstemp(prefix="projects-", suffix=".tmp", dir=registry.parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        if registry.read_bytes() != original:
            raise ValueError("注册表在保存前被其他工具修改，请刷新后重试")
        os.replace(temporary, registry)
        return {"registered": True, "created": True, "name": name, "path": str(target)}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("discover", "register"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--path")
    parser.add_argument("--name", default="")
    args = parser.parse_args()
    try:
        result = discover_known(args.root.resolve()) if args.command == "discover" else register_project(args.root.resolve(), args.path, args.name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"[ERROR] {error}\n")


if __name__ == "__main__":
    main()
