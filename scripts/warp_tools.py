#!/usr/bin/env python3
"""WARP 设备管理工具 — 消费 Upstash 中的 CF 临时 token (零静态高权凭据)

用法:
  warp-tools.py list                       # 列出所有 WARP 设备
  warp-tools.py delete <device_name>       # 删除指定设备 (预留)

环境变量 (或 ~/.env 文件):
  UPSTASH_REST_URL         Upstash REST 地址 (https://xxx.upstash.io)
  UPSTASH_REST_TOKEN_RO    Upstash 只读 token (GET 消费 cf:warp:temp_token)
  CF_ACCOUNT_ID            Cloudflare 账户 ID
  UPSTASH_KEY              可选, Redis key (默认 cf:warp:temp_token)

流程: Upstash GET 临时 token → CF API 操作 (Bearer 认证)
"""
import os
import sys
import json
import urllib.request
import urllib.error

UPSTASH_KEY = os.environ.get("UPSTASH_KEY", "cf:warp:temp_token")
CF_API = "https://api.cloudflare.com/client/v4"


def load_env():
    """从 ~/.env 加载缺失的环境变量 (不覆盖已有)"""
    env_path = os.path.expanduser("~/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)


def http(method, url, headers=None, body=None, retries=3):
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
            last_err = e
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500:
                sys.exit(f"❌ HTTP {e.code}: {e.read().decode('utf-8')[:400]}")
            if attempt < retries - 1:
                wait = 2 * (attempt + 1)
                print(f"⚠️ 请求失败 ({last_err}), {wait}s 后重试 ({attempt+2}/{retries})...")
                import time; time.sleep(wait)
    sys.exit(f"❌ 请求失败: {last_err}")


def get_cf_token():
    """从 Upstash 获取当前有效的 CF 临时 token"""
    url = os.environ.get("UPSTASH_REST_URL", "")
    ro_token = os.environ.get("UPSTASH_REST_TOKEN_RO", "")
    if not url or not ro_token:
        sys.exit("❌ 未设置 UPSTASH_REST_URL / UPSTASH_REST_TOKEN_RO")
    resp = http("GET", f"{url}/get/{UPSTASH_KEY}",
                headers={"Authorization": f"Bearer {ro_token}"})
    cf_token = resp.get("result")
    if not cf_token:
        sys.exit(f"❌ Upstash 无有效 token ({UPSTASH_KEY}) — 需先手动跑 gitea_action 的 issue-cf-token workflow 生成")
    return cf_token


def list_devices(cf_token, account_id):
    resp = http("GET", f"{CF_API}/accounts/{account_id}/devices",
                headers={"Authorization": f"Bearer {cf_token}"})
    devices = resp.get("result", [])
    if not devices:
        print("📭 无 WARP 设备")
        return
    print(f"📱 WARP 设备 ({len(devices)} 台):\n")
    for idx, d in enumerate(devices, 1):
        user = d.get("user", {})
        email = user.get("email", "N/A")
        auth = f"non_identity ({email.split('@')[0]})" if email.startswith("non_identity") else email
        name = d.get("name", "?")
        os_ver = d.get("os_version", "?")
        last_seen = d.get("last_seen", "?")[:10]
        print(f"{idx}. `{name}`")
        print(f"   - 认证: {auth}")
        print(f"   - 系统: {os_ver} | 活跃: {last_seen}")
        print()


def delete_device(cf_token, account_id, target):
    resp = http("GET", f"{CF_API}/accounts/{account_id}/devices",
                headers={"Authorization": f"Bearer {cf_token}"})
    device_id = None
    for d in resp.get("result", []):
        if d.get("name") == target:
            device_id = d.get("id")
            break
    if not device_id:
        sys.exit(f"❌ 未找到名称为 '{target}' 的设备")
    del_resp = http("DELETE", f"{CF_API}/accounts/{account_id}/devices/{device_id}",
                    headers={"Authorization": f"Bearer {cf_token}"})
    if del_resp.get("success"):
        print(f"✅ 成功删除设备: `{target}`")
    else:
        sys.exit(f"❌ 删除失败: {json.dumps(del_resp, ensure_ascii=False)[:400]}")


def main():
    load_env()
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    if not account_id:
        sys.exit("❌ 未设置 CF_ACCOUNT_ID")

    cf_token = get_cf_token()
    print("🔑 CF 临时 token 获取成功\n")

    if action == "list":
        list_devices(cf_token, account_id)
    elif action == "delete":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        if not target:
            sys.exit("用法: warp-tools.py delete <device_name>")
        delete_device(cf_token, account_id, target)
    else:
        sys.exit(f"❌ 未知操作: {action} (支持: list | delete)")


if __name__ == "__main__":
    main()
