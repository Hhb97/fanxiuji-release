#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""《凡修纪》发布脚本：复制 APK（规范命名）→ 计算 SHA-256 → 更新 version.json。

只改本地文件，不会自动 git commit / push，便于人工复核后再发布。

用法示例：
  python publish.py ..\mortal-cultivation-idle\app\build\outputs\apk\release\app-release.apk ^
      --version-code 3 --version-name 1.2.0 ^
      --notes "新增内容A|修复问题B"

默认下载直链指向本 GitHub 仓库：
  https://github.com/<repo>/raw/main/releases/fanxiuji-v<版本名>-release.apk

main 分支的 releases/ 只保留最新一个 APK：jsDelivr 镜像对单个仓库有 50 MB 上限，
超过后两个镜像都返回 403。旧版本留在 git 历史里，按各自标签下载（见 README「历史版本」）。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RELEASES = os.path.join(ROOT, "releases")
VERSION_JSON = os.path.join(ROOT, "version.json")
DEFAULT_REPO = "Hhb97/fanxiuji-release"


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    # Windows 控制台默认 GBK，统一用 UTF-8 输出中文
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="发布《凡修纪》新版本")
    ap.add_argument("apk", help="待发布的 APK 路径（gradlew assembleRelease 产物）")
    ap.add_argument("--version-code", type=int, required=True, help="versionCode（整数，必须递增，且与 APK 一致）")
    ap.add_argument("--version-name", required=True, help="版本名，如 1.2.0")
    ap.add_argument("--min-supported", type=int, default=1,
                    help="最低可用 versionCode，低于此值 App 会提示「重要更新」")
    ap.add_argument("--notes", default="版本更新", help="更新日志，多条用 | 分隔")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="GitHub 仓库 owner/name，用于生成下载直链")
    ap.add_argument("--branch", default="main", help="发布分支")
    ap.add_argument("--download-url", default="", help="自定义 APK 直链（如 CDN）；留空则用 GitHub 直链")
    ap.add_argument("--channel", default="stable", help="发布渠道，需与 App 的 update.json 一致")
    args = ap.parse_args()

    if not os.path.isfile(args.apk):
        raise SystemExit("找不到 APK：%s" % args.apk)
    if not re.fullmatch(r"[0-9A-Za-z.\-]+", args.version_name):
        raise SystemExit("版本名只能包含字母、数字、点和横线：%s" % args.version_name)

    old = {}
    if os.path.isfile(VERSION_JSON):
        with open(VERSION_JSON, encoding="utf-8") as f:
            old = json.load(f)
    if args.version_code <= int(old.get("latestVersionCode", 0)):
        raise SystemExit("versionCode 必须大于当前 %s" % old.get("latestVersionCode", 0))

    os.makedirs(RELEASES, exist_ok=True)
    name = "fanxiuji-v%s-release.apk" % args.version_name
    dest = os.path.join(RELEASES, name)
    if os.path.exists(dest):
        raise SystemExit("已存在同名 APK，拒绝覆盖：%s" % dest)
    shutil.copy2(args.apk, dest)
    # 只保留最新 APK：旧包留在 git 历史与标签里，main 上删除，避免超过 jsDelivr 单仓库 50 MB 上限
    removed = []
    for f in sorted(os.listdir(RELEASES)):
        if f.endswith(".apk") and f != name:
            os.remove(os.path.join(RELEASES, f))
            removed.append(f)

    download_url = args.download_url or "https://github.com/%s/raw/%s/releases/%s" % (args.repo, args.branch, name)
    data = {
        "latestVersionCode": args.version_code,
        "latestVersionName": args.version_name,
        "minSupportedVersionCode": args.min_supported,
        "apkFileName": name,
        "apkSizeBytes": os.path.getsize(dest),
        "apkSha256": sha256(dest),
        "downloadUrl": download_url,
        "releaseNotes": [n.strip() for n in args.notes.split("|") if n.strip()],
        "publishedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "channel": args.channel,
    }
    with open(VERSION_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("已发布到本地发布仓库：")
    print("  APK      :", dest)
    print("  大小     :", data["apkSizeBytes"], "bytes")
    print("  SHA-256  :", data["apkSha256"])
    print("  直链     :", download_url)
    print("  version.json 已更新为", data["latestVersionName"], "(", data["latestVersionCode"], ")")
    if removed:
        print("  已从 releases/ 移除旧包（仍可按标签下载）：", "、".join(removed))
        print("  记得把 README「历史版本」里上一版的链接改成标签地址：")
        print("    https://github.com/%s/raw/v<旧版本>/releases/<旧文件名>" % args.repo)
    print("\n复核后执行：")
    print("  git add -A version.json releases/ README.md")
    print('  git commit -m "release: v%s"' % data["latestVersionName"])
    print("  git tag v%s" % data["latestVersionName"])
    print("  git push origin %s --tags" % args.branch)
    print("\n推送后刷新 jsDelivr 镜像缓存（浏览器打开即可）：")
    print("  https://purge.jsdelivr.net/gh/%s@%s/version.json" % (args.repo, args.branch))


if __name__ == "__main__":
    main()
