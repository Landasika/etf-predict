#!/usr/bin/env python3
"""
Docker 配置验证脚本
检查 Dockerfile、docker-compose.yml 和环境变量配置是否正确
"""
import os
import sys
import json
from pathlib import Path

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} 不存在: {filepath}")
        return False

def check_dockerfile():
    """检查 Dockerfile 配置"""
    print("\n📦 检查 Dockerfile...")

    dockerfile_path = Path("Dockerfile")
    if not check_file_exists(dockerfile_path, "Dockerfile"):
        return False

    with open(dockerfile_path, 'r') as f:
        content = f.read()

    checks = {
        "多阶段构建": "FROM python:3.11-slim AS builder" in content,
        "非特权用户": "useradd -r -g appuser appuser" in content,
        "健康检查": "HEALTHCHECK" in content,
        "工作目录": "WORKDIR /app" in content,
        "暴露端口": "EXPOSE 8000" in content,
    }

    for check_name, result in checks.items():
        if result:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - 未配置")

    return all(checks.values())

def check_docker_compose():
    """检查 docker-compose.yml 配置"""
    print("\n🐳 检查 docker-compose.yml...")

    compose_path = Path("docker-compose.yml")
    if not check_file_exists(compose_path, "docker-compose.yml"):
        return False

    try:
        with open(compose_path, 'r') as f:
            content = f.read()

        checks = {
            "版本声明": "version:" in content,
            "服务定义": "services:" in content,
            "端口映射": "8000:8000" in content or "API_PORT" in content,
            "环境变量": "environment:" in content,
            "数据卷": "volumes:" in content,
            "网络配置": "networks:" in content,
            "重启策略": "restart:" in content,
        }

        for check_name, result in checks.items():
            if result:
                print(f"  ✅ {check_name}")
            else:
                print(f"  ❌ {check_name} - 未配置")

        return all(checks.values())
    except Exception as e:
        print(f"  ❌ 解析错误: {e}")
        return False

def check_env_example():
    """检查环境变量模板"""
    print("\n🔐 检查环境变量配置...")

    env_path = Path(".env.docker.example")
    if not check_file_exists(env_path, ".env.docker.example"):
        return False

    with open(env_path, 'r') as f:
        content = f.read()

    required_vars = [
        "TUSHARE_TOKEN",
        "API_PORT",
        "AUTH_KEY",
    ]

    all_present = True
    for var in required_vars:
        if var in content:
            print(f"  ✅ {var}")
        else:
            print(f"  ❌ {var} - 未定义")
            all_present = False

    return all_present

def check_dockerignore():
    """检查 .dockerignore"""
    print("\n🚫 检查 .dockerignore...")

    ignore_path = Path(".dockerignore")
    if not check_file_exists(ignore_path, ".dockerignore"):
        return False

    with open(ignore_path, 'r') as f:
        content = f.read()

    should_ignore = [
        "__pycache__",
        ".git",
        "*.log",
        "data/*.db",
    ]

    all_present = True
    for item in should_ignore:
        if item in content:
            print(f"  ✅ {item}")
        else:
            print(f"  ⚠️  {item} - 未忽略（可能不需要）")

    return True

def check_config_env_support():
    """检查 config.py 环境变量支持"""
    print("\n⚙️  检查 config.py 环境变量支持...")

    try:
        with open("config.py", 'r') as f:
            content = f.read()

        checks = {
            "_get_env 函数": "def _get_env" in content,
            "_get_env_bool 函数": "def _get_env_bool" in content,
            "_apply_env_overrides 函数": "def _apply_env_overrides" in content,
            "TUSHARE_TOKEN 支持": "TUSHARE_TOKEN" in content,
            "API_PORT 支持": "API_PORT" in content,
        }

        for check_name, result in checks.items():
            if result:
                print(f"  ✅ {check_name}")
            else:
                print(f"  ❌ {check_name} - 未实现")

        return all(checks.values())
    except Exception as e:
        print(f"  ❌ 检查失败: {e}")
        return False

def check_health_endpoint():
    """检查健康检查端点"""
    print("\n💚 检查健康检查端点...")

    try:
        with open("api/main.py", 'r') as f:
            content = f.read()

        if '@app.get("/health")' in content:
            print("  ✅ /health 端点已定义")
            return True
        else:
            print("  ❌ /health 端点未定义")
            return False
    except Exception as e:
        print(f"  ❌ 检查失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🔍 Docker 配置验证")
    print("=" * 60)

    results = {
        "Dockerfile": check_dockerfile(),
        "docker-compose.yml": check_docker_compose(),
        "环境变量模板": check_env_example(),
        ".dockerignore": check_dockerignore(),
        "config.py 环境变量支持": check_config_env_support(),
        "健康检查端点": check_health_endpoint(),
    }

    print("\n" + "=" * 60)
    print("📊 验证结果")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("🎉 所有检查通过！可以开始构建 Docker 镜像")
        print("\n📝 下一步：")
        print("   1. cp .env.docker.example .env")
        print("   2. 编辑 .env 文件，填写 TUSHARE_TOKEN")
        print("   3. docker-compose build")
        print("   4. docker-compose up -d")
        return 0
    else:
        print("⚠️  部分检查失败，请修复后重试")
        return 1

if __name__ == '__main__':
    sys.exit(main())
