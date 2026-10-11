#!/usr/bin/env python3
"""校验课程页面的 YAML 文件头。

范围:documents/ 下 vol*、cookbook、reading 三个区域的 .md(appendix 是档案,不校验)。
规则:必填 title/volume/chapter/order/status,可选 section/description/tools。
只用标准库,frontmatter 限定为"一层键值加一个 tools 子表"的受限 YAML,够用且不引依赖。

用法:python3 tools/validate_frontmatter.py(在仓库根执行,自行扫描范围)
"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = ("title", "volume", "chapter", "order", "status")
STATUS_ENUM = ("draft", "reviewed", "verified")
SCOPE_DIRS = ("vol0-introduction", "vol1-first-use", "vol2-bytes-to-tree",
              "vol3-consumers", "vol4-toy-compiler", "vol5-verification",
              "cookbook", "reading")


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """解析首个 --- 包围块。返回 (字段表, 错误说明)。仅支持一层键值与 tools 子表。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "文件第一行不是 --- 开头的 frontmatter 块"
    fields: dict = {}
    in_tools = False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return fields, ""
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith((" ", "\t")) and in_tools:
            key, _, value = stripped.partition(":")
            fields.setdefault("tools", {})[key.strip()] = value.strip().strip('"')
            continue
        in_tools = False
        key, sep, value = stripped.partition(":")
        if not sep:
            return None, f"无法解析的行: {stripped}"
        if value.strip() == "":
            in_tools = key.strip() == "tools"
            if in_tools:
                fields["tools"] = {}
            continue
        fields[key.strip()] = value.strip().strip('"')
    return None, "frontmatter 块没有闭合(缺少结尾 ---)"


def validate(path: Path, fields: dict, errors: list[str], warns: list[str]) -> None:
    def need_int(name: str, lo: int, hi: int) -> None:
        value = fields.get(name)
        try:
            number = int(value)
        except (TypeError, ValueError):
            errors.append(f"{path}: {name} 应为整数,当前是 {value!r}")
            return
        if not lo <= number <= hi:
            errors.append(f"{path}: {name}={number} 超出范围 [{lo}, {hi}]")

    missing = [name for name in REQUIRED if name not in fields]
    if missing:
        errors.append(f"{path}: 缺少必填字段 {', '.join(missing)}")
        return
    if not fields["title"]:
        errors.append(f"{path}: title 为空")
    if fields["status"] not in STATUS_ENUM:
        errors.append(f"{path}: status 只能是 {'/'.join(STATUS_ENUM)},当前是 {fields['status']!r}")
    need_int("volume", 0, 5)
    need_int("chapter", 0, 18)
    need_int("order", 0, 999)
    if "section" in fields:
        need_int("section", 1, 99)
    if "description" not in fields:
        warns.append(f"{path}: 建议补 description(站点摘要用)")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors: list[str] = []
    warns: list[str] = []
    found = 0
    for scope in SCOPE_DIRS:
        for path in sorted((root / "documents" / scope).rglob("*.md")):
            found += 1
            fields, problem = parse_frontmatter(path.read_text(encoding="utf-8"))
            if fields is None:
                errors.append(f"{path}: {problem}")
                continue
            validate(path, fields, errors, warns)
    if found == 0:
        warns.append("范围内没有找到任何 .md,确认目录是否为空")
    for message in warns:
        print(f"提示 {message}")
    for message in errors:
        print(f"错误 {message}", file=sys.stderr)
    print(f"共扫描 {found} 个文件,{len(errors)} 个错误")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
