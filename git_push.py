#!/usr/bin/env python3
"""
通过 GitHub API 上传 data.json + data.js 到仓库
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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
        print(f"  API Error {e.code}: {error_body[:300]}")
        return None


def upload_single_file(file_path, remote_path, commit_msg):
    """上传单个文件到 GitHub"""
    local_path = os.path.join(SCRIPT_DIR, file_path)
    if not os.path.exists(local_path):
        print(f"  [WARN] Skip {file_path}: file not found")
        return False

    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    # 获取当前 SHA
    sha = None
    result = github_request("GET", f"{API_BASE}/contents/{remote_path}?ref={BRANCH}")
    if result and "sha" in result:
        sha = result["sha"]

    body = {
        "message": commit_msg,
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    result = github_request("PUT", f"{API_BASE}/contents/{remote_path}", body)
    if result and "content" in result:
        print(f"  [OK] Upload {remote_path}: {result['content']['html_url']}")
        return True
    return False


def main():
    print(f"=== GitHub API Upload ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Repo: {REPO}")

    if not TOKEN:
        print("  [FAIL] 缺少 GITHUB_TOKEN 环境变量")
        sys.exit(1)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    ok = True

    # 1) Push data.json
    if not upload_single_file("data.json", "data.json", f"update data.json: {ts}"):
        ok = False

    # 2) Push data.js (auto-generated from data.json)
    if not upload_single_file("data.js", "data.js", f"update data.js: {ts}"):
        ok = False

    if ok:
        print("[OK] All files pushed")
    else:
        print("[WARN] Some files failed to push")
        sys.exit(1)


if __name__ == "__main__":
    main()
