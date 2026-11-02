"""Shared Codex-native rendering and project detection helpers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "build",
    "dist",
    "node_modules",
    "release",
    "target",
    "vendor",
}

CONVERSATION_ARCHIVE_POLICY = Path(".ai-skill/project/conversation-archive.json")
CONVERSATION_ARCHIVE_CADENCES = ("off", "manual", "daily", "weekly")
WORKFLOW_INTEGRATION_POLICY = Path(".ai-skill/project/workflow-integration.json")
WORKFLOW_INTEGRATION_MODES = ("enabled", "disabled")
WORKFLOW_MODES = ("skill-only", "flow-lite", "flow-standard", "flow-automated")
WORKFLOW_SYSTEM_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MANAGED_SKILLS = Path(".ai-skill/project/managed-skills.json")
SKILL_SELECTION = Path(".ai-skill/project/skill-selection.json")
SKILL_GROUPS = ("core",)
UNDISTRIBUTED_PARTS = {"__pycache__", "history", "snapshots", "workflows"}


def is_distributable_path(relative: Path) -> bool:
    """Return whether a framework-relative path belongs in Codex payloads."""
    return (
        relative.suffix.lower() != ".pyc"
        and relative.name != "_template.md"
        and not UNDISTRIBUTED_PARTS.intersection(relative.parts)
    )


def validate_workflow_system_id(system_id: str | None) -> str:
    """Return a valid stable workflow system ID or raise a clear error."""
    if not system_id or not WORKFLOW_SYSTEM_ID_PATTERN.fullmatch(system_id):
        raise ValueError(
            "Enabled workflow integration requires a lowercase kebab-case system ID"
        )
    return system_id


def configure_conversation_archive(project_path: Path, cadence: str) -> bool:
    """Create the first project archive policy without overwriting a choice."""
    if cadence not in CONVERSATION_ARCHIVE_CADENCES:
        raise ValueError(f"Invalid conversation archive cadence: {cadence}")
    policy_path = project_path / CONVERSATION_ARCHIVE_POLICY
    if policy_path.exists():
        return False
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "cadence": cadence,
                "output_directory": ".ai-skill/project/conversations",
                "retention_days": None,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return True


def configure_workflow_integration(
    project_path: Path,
    mode: str,
    system_id: str | None,
    workflow_mode: str | None = None,
) -> bool:
    """Create the first workflow integration policy without overwriting a choice."""
    if mode not in WORKFLOW_INTEGRATION_MODES:
        raise ValueError(f"Invalid workflow integration mode: {mode}")
    if mode == "enabled":
        system_id = validate_workflow_system_id(system_id)
        workflow_mode = workflow_mode or "flow-lite"
    elif system_id is not None:
        raise ValueError("Disabled workflow integration cannot set a system ID")
    else:
        workflow_mode = "skill-only"
    if workflow_mode not in WORKFLOW_MODES:
        raise ValueError(f"Invalid workflow mode: {workflow_mode}")
    if mode == "disabled" and workflow_mode != "skill-only":
        raise ValueError("Disabled workflow integration requires skill-only mode")

    policy_path = project_path / WORKFLOW_INTEGRATION_POLICY
    if policy_path.exists():
        return False
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "enabled": mode == "enabled",
                "mode": workflow_mode,
                "system_id": system_id,
                "routing": "project",
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return True


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Return simple YAML frontmatter and the Markdown body."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, text[match.end():]


def _native_skill_text(name: str, description: str, body: str) -> str:
    encoded_description = json.dumps(description, ensure_ascii=False)
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {encoded_description}\n"
        "---\n\n"
        f"{body.rstrip()}\n"
    )


def native_skill_payloads(skill_root: Path) -> dict[Path, str]:
    """Compile canonical Markdown and authored Codex skills to native files."""
    payloads: dict[Path, str] = {}

    for source in sorted((skill_root / "skills").rglob("*.md")):
        if source.name.startswith("_") or source.name == "README.md":
            continue
        metadata, body = parse_frontmatter(source)
        skill_id = metadata.get("id")
        title = metadata.get("title")
        if not skill_id or not title:
            continue
        trigger = metadata.get("trigger", "相关工程任务")
        description = metadata.get("description", f"Apply {title} when work involves: {trigger}.")
        payloads[Path(skill_id) / "SKILL.md"] = _native_skill_text(
            skill_id, description, body
        )

    for source in sorted((skill_root / "commands").glob("*.md")):
        metadata, body = parse_frontmatter(source)
        name = metadata.get("codex_name", f"ai-{source.stem}")
        description = metadata.get("description", f"Run the {source.stem} workflow.")
        payloads[Path(name) / "SKILL.md"] = _native_skill_text(
            name, description, body
        )

    authored_root = skill_root / "codex" / "skills"
    if authored_root.exists():
        for source in sorted(authored_root.rglob("*")):
            if source.is_file():
                relative = source.relative_to(authored_root)
                if not is_distributable_path(relative):
                    continue
                payloads[relative] = source.read_text(encoding="utf-8")

    return payloads


def native_skill_catalog(skill_root: Path) -> list[dict[str, str]]:
    """List each central skill once, using the same precedence as compilation."""
    catalog: dict[str, dict[str, str]] = {}
    sources = [
        *sorted((skill_root / "skills").rglob("*.md")),
        *sorted((skill_root / "commands").glob("*.md")),
        *sorted((skill_root / "codex/skills").glob("*/SKILL.md")),
    ]
    for source in sources:
        metadata, _ = parse_frontmatter(source)
        relative = source.relative_to(skill_root)
        if relative.parts[0] == "commands":
            name = metadata.get("codex_name", f"ai-{source.stem}")
            kind = "workflow"
        elif relative.parts[0] == "codex":
            name = metadata.get("name", "")
            kind = "native"
        else:
            name = metadata.get("id", "")
            kind = "guidance"
        if not name or source.name.startswith("_") or source.name == "README.md":
            continue
        group = "core"
        catalog[name] = {
            "name": name, "source": relative.as_posix(), "kind": kind,
            "group": group, "owner": "ai-skill", "description": metadata.get("description", metadata.get("title", "")),
        }
    return [catalog[name] for name in sorted(catalog)]


def project_skill_groups(project_path: Path) -> list[str]:
    """Preserve existing installations; new projects start with core skills."""
    policy = project_path / SKILL_SELECTION
    if policy.exists():
        data = json.loads(policy.read_text(encoding="utf-8"))
        groups = data.get("groups")
        if data.get("version") != 1 or not isinstance(groups, list) or not groups or any(group not in SKILL_GROUPS for group in groups):
            raise ValueError(f"Invalid skill selection: {policy}")
        return groups
    if (project_path / ".ai-skill/framework/RULES.md").exists():
        return list(SKILL_GROUPS)
    return ["core"]


def select_project_skill_groups(project_path: Path, groups: list[str]) -> None:
    """Persist an additive selection without removing existing capabilities."""
    if any(group not in SKILL_GROUPS for group in groups):
        raise ValueError("Unknown skill group")
    selected = sorted(set(project_skill_groups(project_path)) | set(groups))
    policy = project_path / SKILL_SELECTION
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(json.dumps({"version": 1, "groups": selected}, indent=2) + "\n", encoding="utf-8")


def project_skill_payloads(skill_root: Path, project_path: Path) -> dict[Path, str]:
    """Select packages, keeping support files with their parent skill."""
    groups = project_skill_groups(project_path)
    names = {skill["name"] for skill in native_skill_catalog(skill_root) if skill["group"] in groups}
    return {path: content for path, content in native_skill_payloads(skill_root).items() if path.parts[0] in names}


def sync_payloads(destination: Path, payloads: dict[Path, str]) -> None:
    """Write generated payloads without touching unrelated directories."""
    for relative, content in payloads.items():
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")


def sync_project_skills(
    project_path: Path, payloads: dict[Path, str], *, dry_run: bool = False,
) -> list[str]:
    """Preserve local edits and return conflicts, blocking each affected package."""
    manifest_path = project_path / MANAGED_SKILLS
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"version": 1, "files": {}}
    if not isinstance(manifest, dict) or manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError(f"Invalid managed skill manifest: {manifest_path}")
    previous = manifest["files"]
    # Read the old snapshot before deployment replaces it. Unknown authored files
    # are adopted only if they already equal the current central payload.
    legacy = native_skill_payloads(project_path / ".ai-skill/framework")
    destination = project_path / ".agents/skills"
    try:
        destination.resolve().relative_to(project_path.resolve())
    except ValueError:
        raise ValueError(f"Skill directory escapes project: {destination}") from None
    conflicts: list[str] = []
    blocked: set[str] = set()
    current_files: dict[Path, str | None] = {}
    for relative, content in payloads.items():
        output = destination / relative
        try:
            output.resolve().relative_to(destination.resolve())
        except ValueError:
            raise ValueError(f"Skill target escapes destination: {output}") from None
        current = output.read_text(encoding="utf-8") if output.is_file() else None
        current_files[relative] = current
        baseline = previous.get(relative.as_posix())
        if baseline is None and relative in legacy:
            baseline = hashlib.sha256(legacy[relative].encode("utf-8")).hexdigest()
        locally_changed = current is not None and hashlib.sha256(current.encode("utf-8")).hexdigest() != baseline
        locally_deleted = relative.as_posix() in previous and not output.exists()
        if output.is_dir() or locally_deleted or (current != content and locally_changed):
            conflicts.append(relative.as_posix())
            blocked.add(relative.parts[0])
    if dry_run:
        return conflicts
    next_files = dict(previous)
    for relative, content in payloads.items():
        if relative.parts[0] in blocked:
            continue
        if current_files[relative] != content:
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
        next_files[relative.as_posix()] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"version": 1, "files": next_files}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return conflicts


def payload_drift(destination: Path, payloads: dict[Path, str]) -> list[str]:
    """Return missing or different generated files."""
    drifted: list[str] = []
    for relative, content in payloads.items():
        output = destination / relative
        current = output.read_text(encoding="utf-8") if output.exists() else None
        if current != content:
            drifted.append(str(output))
    return drifted


def mirror_payloads(destination: Path, payloads: dict[Path, str]) -> None:
    """Mirror a fully generated directory, removing only stale generated entries."""
    expected_roots = {relative.parts[0] for relative in payloads}
    if destination.exists():
        for child in destination.iterdir():
            if child.name in expected_roots:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    sync_payloads(destination, payloads)


def mirror_drift(destination: Path, payloads: dict[Path, str]) -> list[str]:
    """Return payload drift including stale top-level generated entries."""
    drifted = payload_drift(destination, payloads)
    expected_roots = {relative.parts[0] for relative in payloads}
    if destination.exists():
        drifted.extend(
            str(child)
            for child in destination.iterdir()
            if child.name not in expected_roots
        )
    return drifted


def framework_files(skill_root: Path) -> list[Path]:
    """Return files that form the portable framework snapshot."""
    files = [skill_root / "RULES.md", skill_root / "router.md"]
    for directory in ("core", "skills", "commands", "evolution"):
        files.extend(
            path for path in sorted((skill_root / directory).rglob("*"))
            if path.is_file()
            and is_distributable_path(path.relative_to(skill_root))
        )
    for relative in (
        "scripts/skill_factory.py", "scripts/codex_support.py",
        "scripts/init-project.py",
        "docs/skill-model-evaluation.md", "evals/model-task-cases.json",
        "evals/core-behavior-cases.json",
    ):
        source = skill_root / relative
        if source.exists():
            files.append(source)
    files.extend(
        source
        for source in sorted((skill_root / "codex/skills").rglob("*"))
        if source.is_file()
        and is_distributable_path(source.relative_to(skill_root))
    )
    files.extend(
        source
        for source in sorted((skill_root / "evals/fixtures/core").rglob("*"))
        if source.is_file()
        and is_distributable_path(source.relative_to(skill_root))
    )
    return files


def deploy_framework(skill_root: Path, destination: Path) -> None:
    """Copy the canonical framework while leaving project knowledge separate."""
    for source in framework_files(skill_root):
        relative = source.relative_to(skill_root)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)


def _read_package_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _git_tracked_files(project_path: Path) -> set[Path] | None:
    """Return index paths, or None when Git detection is unavailable."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "ls-files", "--cached", "-z"],
            capture_output=True, check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return {Path(os.fsdecode(path)) for path in result.stdout.split(b"\0") if path}


def detect_project(project_path: Path) -> str:
    """Build a deterministic, evidence-based project profile."""
    languages: set[str] = set()
    frameworks: set[str] = set()
    commands: dict[str, str] = {}
    tracked_files = _git_tracked_files(project_path)
    root_names = (
        {path.name for path in tracked_files if len(path.parts) == 1}
        if tracked_files is not None
        else {path.name for path in project_path.iterdir()}
    )

    package_path = project_path / "package.json"
    package = _read_package_json(package_path) if "package.json" in root_names else {}
    dependencies = {
        **package.get("dependencies", {}),
        **package.get("devDependencies", {}),
    }
    dependency_map = {
        "electron": "Electron",
        "next": "Next.js",
        "react": "React",
        "vue": "Vue",
        "svelte": "Svelte",
        "typescript": "TypeScript",
    }
    for dependency, label in dependency_map.items():
        if dependency in dependencies:
            frameworks.add(label)
    if package:
        languages.add("JavaScript/TypeScript")
        for key in ("test", "build", "dev", "start", "format", "lint"):
            value = package.get("scripts", {}).get(key)
            if value:
                commands[key] = f"npm run {key}"

    if "pyproject.toml" in root_names or any(
        name.startswith("requirements") and name.endswith(".txt") for name in root_names
    ):
        languages.add("Python")
        if "pyproject.toml" in root_names:
            frameworks.add("Python project")
        commands.setdefault("test", "python -m pytest")
    if "go.mod" in root_names:
        languages.add("Go")
        commands.setdefault("test", "go test ./...")
        commands.setdefault("build", "go build ./...")

    extension_map = {
        ".go": "Go",
        ".js": "JavaScript/TypeScript",
        ".jsx": "JavaScript/TypeScript",
        ".py": "Python",
        ".rs": "Rust",
        ".ts": "JavaScript/TypeScript",
        ".tsx": "JavaScript/TypeScript",
    }
    if tracked_files is not None:
        languages.update(
            extension_map[path.suffix.lower()]
            for path in tracked_files
            if path.suffix.lower() in extension_map
            and not SKIP_DIRS.intersection(path.parts[:-1])
        )
        top_level = sorted({
            path.parts[0] for path in tracked_files
            if len(path.parts) > 1 and path.parts[0] not in SKIP_DIRS
            and not path.parts[0].startswith(".")
        })[:20]
    else:
        source_count = 0
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
            for filename in files:
                language = extension_map.get(Path(filename).suffix.lower())
                if language:
                    languages.add(language)
                    source_count += 1
            if source_count >= 5000:
                break

        top_level = sorted(
            item.name for item in project_path.iterdir()
            if item.is_dir() and item.name not in SKIP_DIRS and not item.name.startswith(".")
        )[:20]
    project_name = package.get("name") or (
        "未识别" if tracked_files is not None else project_path.name
    )
    lines = [
        "# 自动识别的项目画像",
        "",
        "> 本文件由 ai-skill 初始化器根据仓库证据生成，可重复刷新。",
        "> 用户维护的长期事实请写入 `context.md`、`preferences.md` 或 `decisions.md`。",
        "",
        f"- 项目名称: {project_name}",
        "- 项目路径: 仓库根目录",
        f"- 语言: {', '.join(sorted(languages)) or '未识别'}",
        f"- 框架: {', '.join(sorted(frameworks)) or '未识别'}",
        f"- 顶层业务目录: {', '.join(top_level) or '无'}",
        "",
        "## 可用命令",
        "",
    ]
    if commands:
        lines.extend(f"- {name}: `{command}`" for name, command in sorted(commands.items()))
    else:
        lines.append("- 未从标准清单识别；执行前读取项目文档和 CI 配置。")
    lines.extend([
        "",
        "## 识别边界",
        "",
        "- 这是静态探测结果，不代表真实运行、打包或发布已验证。",
        "- 当前源码、测试和用户最新明确决定优先于本文件。",
        "",
    ])
    return "\n".join(lines)


def merge_managed_block(existing: str, block: str) -> str:
    """Insert or replace the ai-skill block without overwriting user content."""
    newline = "\r\n" if "\r\n" in existing else "\n"
    start = "<!-- ai-skill:start -->"
    end = "<!-- ai-skill:end -->"
    normalized_block = block.rstrip().replace("\r\n", "\n").replace("\n", newline)
    managed = f"{start}{newline}{normalized_block}{newline}{end}"
    pattern = re.compile(
        rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL
    )
    if pattern.search(existing):
        return pattern.sub(managed, existing).rstrip() + newline
    if existing.strip():
        return existing.rstrip() + newline * 2 + managed + newline
    return managed + newline


def codex_agents_block() -> str:
    """Return the canonical project-level Codex instructions."""
    return """# ai-skill Codex 入口

本项目已接入 `.ai-skill`。每次任务：

1. 遵守 `.ai-skill/framework/RULES.md`。
2. 读取 `.ai-skill/project/detected.md`，并在相关时读取 `context.md`、`zones.md`、`preferences.md` 和 `decisions.md`。
3. Codex 会从 `.agents/skills/` 自动发现原生 skills；按任务匹配加载，不要无条件读取全部正文。
4. 完成实现、调试、审查、构建或发布任务后，使用 `$project-knowledge-evolution` 判断是否有已验证知识需要沉淀。
5. 当前源码、测试、真实运行证据和用户最新明确决定优先于历史知识。

不得把密码、Cookie、token、密钥、原始会话全文或未证实根因写入知识库。"""


def ensure_project_knowledge(project_path: Path) -> None:
    """Create project-owned knowledge files without overwriting them."""
    project_dir = project_path / ".ai-skill" / "project"
    templates = {
        "context.md": "# 项目长期上下文\n\n记录自动识别无法可靠判断、但会影响未来实现的项目事实。\n",
        "zones.md": "# 项目文件分区\n\n## 冻结区\n\n- 未配置\n\n## 受控区\n\n- 数据库 schema\n- 对外公共 API\n",
        "preferences.md": "# 用户稳定偏好\n\n只记录用户明确表达，或在至少两个独立任务中重复验证的偏好。\n",
        "decisions.md": "# 产品与架构决策\n\n记录会影响后续实现选择的当前有效决定及证据。\n",
        "knowledge/pitfalls.md": "# 项目踩坑记录\n\n仅记录已验证的现象、根因、修复和预防方式。\n",
        "knowledge/recipes.md": "# 项目操作配方\n\n记录已验证、可重复执行的多步流程。\n",
        "evolution/log.md": "# 项目知识演进日志\n",
    }
    for relative, content in templates.items():
        output = project_dir / relative
        if output.exists():
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

    detected = project_dir / "detected.md"
    detected.parent.mkdir(parents=True, exist_ok=True)
    detected.write_text(detect_project(project_path), encoding="utf-8", newline="\n")


def deploy_codex_project(skill_root: Path, project_path: Path) -> list[str]:
    """Deploy managed Codex files while preserving project-owned content."""
    select_project_skill_groups(project_path, [])
    conflicts = sync_project_skills(project_path, project_skill_payloads(skill_root, project_path))
    deploy_framework(skill_root, project_path / ".ai-skill" / "framework")
    ensure_project_knowledge(project_path)

    agents_path = project_path / "AGENTS.md"
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    with agents_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(merge_managed_block(existing, codex_agents_block()))
    return conflicts
