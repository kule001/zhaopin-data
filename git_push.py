#!/usr/bin/env python3
"""
通过 GitHub API 上传 data.json 到仓库
因为 github.com 被墙，使用 api.github.com 进行文件上传
"""
import json
import base64
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime

# 配置
REPO = "kule001/zhaopin-data"
BRANCH = "main"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FILE_PATH = "data.json"
LOCAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

API_BASE = f"https://api.github.com/repos/{REPO}"


def github_request(method, url, data=None):
    """发送 GitHub API 请求"""
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "git_push.py",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  API Error {e.code}: {error_body}")
        return None


def get_file_sha():
    """获取远程文件当前 SHA（需要用于更新）"""
    url = f"{API_BASE}/contents/{FILE_PATH}?ref={BRANCH}"
    result = github_request("GET", url)
    if result and "sha" in result:
        return result["sha"]
    return None


def upload_file():
    """上传/更新文件到 GitHub"""
    if not os.path.exists(LOCAL_FILE):
        print(f"  ❌ 文件不存在: {LOCAL_FILE}")
        return False

    if not TOKEN:
        print("  ❌ 缺少 GITHUB_TOKEN 环境变量")
        return False

    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    # 获取当前 SHA（如果是已存在的文件）
    sha = get_file_sha()

    body = {
        "message": f"update data: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    url = f"{API_BASE}/contents/{FILE_PATH}"
    result = github_request("PUT", url, body)

    if result and "content" in result:
        print(f"  ✅ 上传成功: {result['content']['html_url']}")
        return True
    return False


def main():
    print(f"=== GitHub API Upload ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"仓库: {REPO}")
    print(f"文件: {FILE_PATH}")

    if upload_file():
        print("✅ 完成")
    else:
        print("❌ 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
