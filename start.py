#!/usr/bin/env python3
"""
HouseSearch Local v1 - 一键启动脚本

用法（在项目根目录执行）:
    python start.py setup       # 安装依赖 + 生成 .env + 建目录
    python start.py backend     # 启动后端 http://localhost:8000
    python start.py frontend    # 启动前端 http://localhost:5173
    python start.py seed        # 写入演示数据（便于验证前端展示）
"""

import argparse
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


def venv_python() -> str:
    """优先使用项目内 .venv 的解释器（若存在）"""
    candidate = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def run_backend():
    """启动后端服务（工作目录必须是项目根目录，否则 backend.* 绝对导入会失败）"""
    print("🚀 启动后端服务: http://localhost:8000  (文档: /docs)")
    subprocess.run([
        venv_python(), "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ], cwd=PROJECT_ROOT)


def run_frontend():
    """启动前端开发服务器"""
    print("🎨 启动前端开发服务器: http://localhost:5173")
    if not os.path.exists(os.path.join(FRONTEND_DIR, "package.json")):
        print("❌ 前端代码未找到")
        return

    if not os.path.exists(os.path.join(FRONTEND_DIR, "node_modules")):
        print("📦 未检测到 node_modules，先执行 npm install ...")
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR)

    subprocess.run(["npm", "run", "dev"], cwd=FRONTEND_DIR)


def setup():
    """初始化环境"""
    print("📦 安装 Python 依赖...")
    subprocess.run(
        [venv_python(), "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=PROJECT_ROOT,
        check=False,
    )

    # 确保数据目录存在
    os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)

    # 创建 .env 文件（如果不存在）
    env_path = os.path.join(PROJECT_ROOT, ".env")
    env_example = os.path.join(PROJECT_ROOT, ".env.example")
    if not os.path.exists(env_path):
        print("📝 创建 .env 配置文件...")
        if os.path.exists(env_example):
            with open(env_example, "r", encoding="utf-8") as f:
                content = f.read()
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("✅ 已创建 .env，请编辑配置（高德 Key / Cookie）后再启动")
        else:
            print("⚠️ .env.example 不存在")

    print("✅ 初始化完成")


def run_seed():
    """写入演示数据"""
    subprocess.run([venv_python(), os.path.join(PROJECT_ROOT, "seed_demo.py")], cwd=PROJECT_ROOT)


def setup_frontend():
    """设置前端（从原项目复制并适配）"""
    import shutil

    source = os.path.join(os.path.dirname(PROJECT_ROOT), "HouseSearch-master", "House-Map.newUI")
    target = FRONTEND_DIR

    if not os.path.exists(source):
        print(f"❌ 源前端目录不存在: {source}")
        print("请确保 HouseSearch-master 与当前项目同级")
        return

    print(f"📂 复制前端代码到 {target}...")

    if os.path.exists(target):
        shutil.rmtree(target)

    shutil.copytree(source, target)

    # 修改前端 API 地址
    constant_file = os.path.join(target, "src", "constant.ts")
    if os.path.exists(constant_file):
        with open(constant_file, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace(
            'export const API_BASE_URL = "https://web.house2048.cn/api";',
            'export const API_BASE_URL = "http://localhost:8000/api";'
        )

        with open(constant_file, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ 前端 API 地址已修改为本地")

    print("📦 安装前端依赖...")
    subprocess.run(["npm", "install"], cwd=target)

    print("✅ 前端设置完成")


def main():
    parser = argparse.ArgumentParser(description="HouseSearch Local v1 启动脚本")
    parser.add_argument(
        "command",
        choices=["backend", "frontend", "setup", "setup_frontend", "seed", "all"],
        help="要执行的命令"
    )

    args = parser.parse_args()

    if args.command == "backend":
        run_backend()
    elif args.command == "frontend":
        run_frontend()
    elif args.command == "setup":
        setup()
    elif args.command == "setup_frontend":
        setup_frontend()
    elif args.command == "seed":
        run_seed()
    elif args.command == "all":
        print("请分别运行: python start.py backend 和 python start.py frontend")


if __name__ == "__main__":
    main()
