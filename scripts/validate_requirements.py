"""Validate requirement card structure and common credential assignment patterns."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SECTIONS = (
    "要解决的问题", "已确认的行为", "验收标准", "已知的坑",
    "参考实现", "测试模板", "与项目无关化", "待确认",
)
EVIDENCE_NOTICE = (
    "测试通过只证明来源仓库测试行为，不代表其他平台或生产环境已验证。"
)
CREDENTIAL_PATTERN = re.compile(
    r"(?i)(?<![\w-])(?:[a-z0-9]+[_-])*"
    r"(?:token|password|cookie|secret|api[_-]?key|密码|密钥)"
    r"(?:[_-][a-z0-9]+)*(?![\w-])[\"'`]*\s*[:=：]\s*\S+"
    r"|-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"
)


def validate_document(name: str, content: str) -> list[str]:
    """Return safe diagnostics without echoing any suspected credential values."""
    errors = []
    for line_number, line in enumerate(content.splitlines(), 1):
        if CREDENTIAL_PATTERN.search(line):
            errors.append(f"{name}:{line_number}: suspected credential")
    if name == "README.md":
        return errors
    if name != "_template.md" and not re.fullmatch(
        r"[a-z]+(?:-[a-z0-9]+)*\.md", name
    ):
        errors.append(f"{name}: expected lowercase English kebab-case filename")
    headings = re.findall(r"^## (.+?)\s*$", content, re.MULTILINE)
    for section in REQUIRED_SECTIONS:
        if section not in headings:
            errors.append(f"{name}: missing section: {section}")
    if EVIDENCE_NOTICE not in content:
        errors.append(f"{name}: missing fixed evidence notice")
    return errors


def validate_library(directory: Path) -> list[str]:
    """Check the README, template and each top-level Markdown requirement card."""
    errors = [
        f"{name}: required file missing"
        for name in ("README.md", "_template.md")
        if not (directory / name).is_file()
    ]
    for path in sorted(directory.glob("*.md")):
        errors.extend(validate_document(path.name, path.read_text(encoding="utf-8")))
    return errors


def main() -> int:
    errors = validate_library(ROOT / "requirements")
    for error in errors:
        print(error)
    if errors:
        return 1
    print("[OK] Requirement structure and credential scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
