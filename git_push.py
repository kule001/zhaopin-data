#!/usr/bin/env python3
"""
推送 data.json 到 GitHub 仓库
用于定时任务和手动更新
"""
import subprocess
import sys
import os
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

def run(cmd, cwd=REPO_DIR):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  ❌ {cmd}\n  {result.stderr.strip()}')
        return False, result.stderr
    return True, result.stdout.strip()

def main():
    print(f'=== Git Push to GitHub ===')
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'目录: {REPO_DIR}')

    # 1. 检查是否有变更
    ok, out = run('git status --porcelain')
    if not ok:
        print('Git 仓库未初始化, 跳过推送')
        return
    if not out:
        print('没有变更, 跳过')
        return

    print(f'变更文件:\n{out}')

    # 2. add + commit + push
    ok, _ = run('git add data.json')
    if not ok:
        return
    commit_msg = f'update data: {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    ok, _ = run(f'git commit -m "{commit_msg}"')
    if not ok:
        # 可能没有变更
        pass
    ok, _ = run('git push origin main')
    if ok:
        print('✅ 推送成功')
    else:
        print('⚠️ 推送失败, 请检查远程仓库配置')

if __name__ == '__main__':
    main()
