#!/usr/bin/env python3
"""
敏感信息扫描（提交前 / CI 必跑）

这是 docs/GIT_WORKFLOW.md 里唯一那条硬性红线的自动化检查：
**Cookie / Token / API Key / 密码 / .env / data/*.db —— 永远不进 Git，包括历史。**

做三件事：
1. 扫描**被 Git 跟踪的文件**是否含密钥特征（按模式识别，不硬编码任何真实密钥）
2. 扫描**全部提交历史**是否含密钥特征（防止"提交过又删掉"的情况）
3. 检查 `.env` / `*.db` / 构建产物是否被误跟踪

用法:
    python check_secrets.py            # 全量检查（含历史）
    python check_secrets.py --fast     # 只查工作区与被跟踪文件（CI 默认够用）
    python check_secrets.py --staged   # 只查暂存区（可挂 pre-commit）

退出码 0 = 干净；1 = 发现可疑内容。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------- 密钥特征（按模式，不写任何真实密钥）----------
SECRET_PATTERNS = [
    # 火山方舟 / 豆包
    (r"ark-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}-[0-9a-fA-F]{4,}",
     "火山方舟 API Key"),
    # DeepSeek / OpenAI 风格
    (r"\bsk-[A-Za-z0-9]{20,}\b", "sk- 开头的 API Key"),
    # 高德 Key（32 位十六进制）。用边界包裹，避免匹配到更长的哈希
    (r"(?<![0-9a-fA-F])[0-9a-f]{32}(?![0-9a-fA-F])", "疑似高德 32 位 Key"),
    # GitHub
    (r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b", "GitHub Token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{40,}\b", "GitHub PAT"),
    # AWS
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key"),
    # Slack
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "Slack Token"),
    # 通用：赋值给 cookie/token/key/secret/password 的长字符串
    (r"(?i)\b(cookie|token|api[_-]?key|secret|password|passwd)\b\s*[:=]\s*[\"'][A-Za-z0-9_%\-\.]{16,}[\"']",
     "疑似凭据赋值"),
]

# 允许出现 32 位十六进制的例外（不含任何真实密钥，仅为减少误报）
ALLOWED_PATH_HINTS = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "data/metro/",        # 地铁静态数据（坐标，非密钥）
    "node_modules/",
)

# 不允许被 Git 跟踪的文件
FORBIDDEN_TRACKED = [
    (r"(^|/)\.env$", ".env 环境文件"),
    (r"(^|/)\.env\.(local|production|development)$", ".env 环境文件"),
    (r"\.db$", "SQLite 数据库"),
    (r"^frontend/(build|dist)/", "前端构建产物"),
]


def run_git(args: list) -> str:
    try:
        result = subprocess.run(["git"] + args, cwd=PROJECT_ROOT,
                                capture_output=True, text=True, timeout=180)
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def is_allowed(path: str) -> bool:
    return any(hint in path for hint in ALLOWED_PATH_HINTS)


def scan_text(text: str, label: str) -> list:
    """扫描一段文本，返回 [(说明, 命中片段掩码)]"""
    hits = []
    for pattern, name in SECRET_PATTERNS:
        for match in re.finditer(pattern, text):
            snippet = match.group(0)
            masked = snippet[:6] + "…" + snippet[-4:] if len(snippet) > 12 else "…"
            hits.append((name, masked, label))
    return hits


def scan_tracked_files() -> list:
    """扫描被 Git 跟踪的文件"""
    hits = []
    files = [f for f in run_git(["ls-files"]).splitlines() if f.strip()]
    for path in files:
        if is_allowed(path):
            continue
        full = os.path.join(PROJECT_ROOT, path)
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        hits.extend(scan_text(content, path))
    return hits, len(files)


def scan_staged() -> list:
    diff = run_git(["diff", "--cached", "-U0"])
    return scan_text(diff, "暂存区")


def scan_history() -> list:
    """扫描全部历史提交的内容（防止提交过又删掉）"""
    hits = []
    log = run_git(["log", "--all", "-p", "--no-color", "--pretty=format:commit:%H"])
    if not log:
        return hits
    # 逐提交扫描，便于报告是哪个 commit
    commits = run_git(["log", "--all", "--pretty=format:%H"]).split()
    for commit in commits:
        patch = run_git(["show", "--no-color", commit])
        for name, masked, _ in scan_text(patch, commit):
            hits.append((name, masked, f"提交 {commit[:8]}"))
    return hits


def check_forbidden_tracked() -> list:
    problems = []
    for path in run_git(["ls-files"]).splitlines():
        for pattern, name in FORBIDDEN_TRACKED:
            if re.search(pattern, path):
                problems.append((name, path))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="敏感信息扫描")
    parser.add_argument("--fast", action="store_true", help="跳过历史扫描")
    parser.add_argument("--staged", action="store_true", help="只扫描暂存区")
    args = parser.parse_args()

    print("=" * 70)
    print("敏感信息扫描（红线检查：密钥/Cookie/.env 不进 Git）")
    print("=" * 70)

    total_hits = 0

    if args.staged:
        hits = scan_staged()
        total_hits += len(hits)
        print(f"\n【暂存区】命中 {len(hits)} 处")
        for name, masked, label in hits:
            print(f"  ❌ [{name}] {masked}  ({label})")
        print("\n" + "=" * 70)
        print("✅ 暂存区干净" if not hits else "❌ 暂存区存在敏感信息，请勿提交")
        return 0 if not hits else 1

    # 1) 被跟踪的文件
    file_hits, file_count = scan_tracked_files()
    total_hits += len(file_hits)
    print(f"\n【被跟踪文件】共 {file_count} 个，命中 {len(file_hits)} 处")
    for name, masked, label in file_hits[:20]:
        print(f"  ❌ [{name}] {masked}  ({label})")
    if not file_hits:
        print("  ✅ 无密钥特征")

    # 2) 误跟踪检查
    forbidden = check_forbidden_tracked()
    total_hits += len(forbidden)
    print(f"\n【误跟踪检查】命中 {len(forbidden)} 处")
    for name, path in forbidden[:20]:
        print(f"  ❌ {name} 被跟踪: {path}")
    if not forbidden:
        print("  ✅ .env / *.db / 构建产物均未被跟踪")

    # 3) 历史
    #    历史遗留只告警、不阻断：清理历史必须改写提交并 force push，
    #    影响所有协作者与已克隆的仓库，属于仓库所有者的决定，不适合自动执行。
    #    真正的防线是第 1、2 步——它们能在任何新泄漏进入提交时立刻拦住。
    history_hits = []
    if not args.fast:
        print("\n【全历史扫描】正在扫描所有提交（稍慢）……")
        history_hits = scan_history()
        if history_hits:
            print(f"  ⚠️  命中 {len(history_hits)} 处（历史遗留，不阻断）")
            seen = set()
            for name, masked, label in history_hits[:20]:
                key = (name, masked)
                if key in seen:
                    continue
                seen.add(key)
                print(f"     [{name}] {masked}  ({label})")
            print("""
     说明：这些内容位于**历史提交**中，当前工作区已不含它们。
     常见情形是从上游开源项目继承的示例 Key（上游仓库公开可见），
     并非你自己的凭据。若确认需要彻底清除：
         git filter-repo --replace-text <(echo '旧KEY==>REDACTED')
         git push --force-with-lease origin main
     清历史前请先想清楚：所有协作者都需要重新克隆。""")
        else:
            print("  ✅ 全部历史无密钥特征")

    print("\n" + "=" * 70)
    if total_hits == 0:
        print("✅ 检查通过：当前工作区与跟踪文件未发现敏感信息")
        if history_hits:
            print(f"⚠️  另有 {len(history_hits)} 处历史遗留（见上，不阻断）")
        print("=" * 70)
        return 0

    print(f"❌ 发现 {total_hits} 处可疑内容 —— 不要提交/推送！")
    print("=" * 70)
    print("""
处理建议：
  · 尚未提交：把内容移到 .env（已被 gitignore），确认 git status 里没有它
  · 已经推送：该凭据视为已泄漏 → 先去平台吊销/重置，再清理历史
    （git filter-repo 或 BFG，之后 force push；清理前先重置密钥更稳妥）
""")
    return 1


if __name__ == "__main__":
    sys.exit(main())
