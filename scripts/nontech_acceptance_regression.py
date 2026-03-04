#!/usr/bin/env python3
"""非技术用户验收回归脚本。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORGE = ROOT / "forge.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def case_first_install_assets() -> tuple[bool, str]:
    requirements = (ROOT / "requirements.txt").exists()
    env_example = (ROOT / ".env.example").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    has_nontech_guide = "5分钟上手（非技术）" in readme
    ok = requirements and env_example and has_nontech_guide
    detail = "requirements/.env.example/README 非技术入口已就绪"
    return ok, detail


def case_first_generate_discovery() -> tuple[bool, str]:
    result = _run([sys.executable, str(FORGE), "list"])
    ok = (
        result.returncode == 0
        and "【平台】" in result.stdout
        and "【内容类型】" in result.stdout
    )
    return ok, "list 命令可见平台与类型"


def case_templates_ready() -> tuple[bool, str]:
    template_dir = ROOT / "config" / "material_templates"
    names = [
        "route_guide.json",
        "gear_review.json",
        "question_answer.json",
        "project_promotion.json",
    ]
    for name in names:
        file_path = template_dir / name
        if not file_path.exists():
            return False, f"模板缺失: {name}"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if "keywords" not in data:
            return False, f"模板缺少 keywords: {name}"
    return True, "4 类模板均可直接填写"


def case_save_publish_flags() -> tuple[bool, str]:
    result = _run([sys.executable, str(FORGE), "generate", "-h"])
    stdout = result.stdout
    ok = result.returncode == 0 and "-s, --save" in stdout and "--publish" in stdout
    return ok, "generate 帮助包含保存与发布参数"


def case_failure_recovery_message() -> tuple[bool, str]:
    result = _run(
        [
            sys.executable,
            str(FORGE),
            "generate",
            "-p",
            "bad_platform",
            "-t",
            "攻略",
            "-k",
            "测试",
        ]
    )
    merged = (result.stdout or "") + (result.stderr or "")
    ok = (
        result.returncode != 0
        and "错误:" in merged
        and "修复:" in merged
        and "示例:" in merged
    )
    return ok, "失败场景输出三段式修复提示"


def main() -> int:
    parser = argparse.ArgumentParser(description="非技术用户验收回归")
    parser.add_argument("--core-only", action="store_true", help="只跑核心 2 条用例")
    args = parser.parse_args()

    all_cases = [
        ("首次安装", case_first_install_assets),
        ("首次生成", case_first_generate_discovery),
        ("模板输入", case_templates_ready),
        ("保存发布", case_save_publish_flags),
        ("失败恢复", case_failure_recovery_message),
    ]
    cases = all_cases[:2] if args.core_only else all_cases

    print("=" * 50)
    print("非技术用户验收回归")
    print("=" * 50)

    failed = 0
    for idx, (name, fn) in enumerate(cases, 1):
        ok, detail = fn()
        status = "✓" if ok else "✗"
        print(f"{idx}. {status} {name}: {detail}")
        if not ok:
            failed += 1

    print("-" * 50)
    print(f"通过: {len(cases) - failed}/{len(cases)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
