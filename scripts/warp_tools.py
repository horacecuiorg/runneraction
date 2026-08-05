#!/usr/bin/env python3
"""WARP 设备管理工具 — 消费 Upstash 中的 CF 临时 token (零静态高权凭据)

用法:
  warp-tools.py list                                  # 列出所有 WARP 设备
  warp-tools.py delete <device_name>                  # 删除指定设备
  warp-tools.py cleanup [hours] [--dry-run]           # 清理 non_identity 且不活跃 >N 小时(默认6) 的设备
                                                      # --dry-run 只列出不删除 (默认启用 dry-run)

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
from datetime import datetime, timezone

UPSTASH_KEY = os.environ.get("UPSTASH_KEY", "cf:warp:temp_token")
CF_API = "https://api.cloudflare.com/client/v4"
NON_IDENTITY_PREFIX = "non_identity"


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


def get_service_token_map(cf_token, account_id):
    """{service_token_id: name} 映射"""
    resp = http("GET", f"{CF_API}/accounts/{account_id}/access/service_tokens",
                headers={"Authorization": f"Bearer {cf_token}"})
    return {t.get("id"): t.get("name", "?") for t in resp.get("result", [])}


def get_non_identity_token_id(cf_token, account_id):
    """WARP Login App 的 non_identity policy 绑定的 service token id (无则 None)"""
    resp = http("GET", f"{CF_API}/accounts/{account_id}/access/apps",
                headers={"Authorization": f"Bearer {cf_token}"})
    for a in resp.get("result", []):
        if a.get("type") == "warp" or "warp" in a.get("domain", "").lower():
            for p in a.get("policies", []):
                if p.get("decision") == "non_identity":
                    for inc in p.get("include", []):
                        if "service_token" in inc:
                            return inc["service_token"].get("token_id")
    return None


def auth_label(email, st_map, non_id_token_id):
    """设备认证显示: 普通邮箱直显; non_identity 显示绑定的 service token 名"""
    if not email:
        return "N/A"
    if email.startswith(NON_IDENTITY_PREFIX):
        name = st_map.get(non_id_token_id) if non_id_token_id else None
        return f"{name} (non_identity)" if name else "non_identity"
    return email


def list_devices(cf_token, account_id):
    st_map = get_service_token_map(cf_token, account_id)
    non_id_token_id = get_non_identity_token_id(cf_token, account_id)
    resp = http("GET", f"{CF_API}/accounts/{account_id}/devices",
                headers={"Authorization": f"Bearer {cf_token}"})
    devices = resp.get("result", [])
    if not devices:
        print("📭 无 WARP 设备")
        return
    print(f"📱 WARP 设备 ({len(devices)} 台):\n")
    for idx, d in enumerate(devices, 1):
        user = d.get("user", {})
        name = d.get("name", "?")
        os_extra = d.get("os_version_extra") or ""
        os_str = d.get("os_version", "?")
        if os_extra:
            os_str += f" ({os_extra})"
        print(f"{idx}. `{name}`")
        print(f"   - 认证: {auth_label(user.get('email'), st_map, non_id_token_id)}")
        print(f"   - 类型: {d.get('device_type','?')} | 系统: {os_str}")
        print(f"   - 模型: {d.get('model','?')}")
        print(f"   - IP: {d.get('ip','?')} | MAC: {d.get('mac_address','?')}")
        print(f"   - 版本: {d.get('version','?')} | 活跃: {str(d.get('last_seen','?'))[:19]}")
        print(f"   - 创建: {str(d.get('created','?'))[:10]} | ID: {d.get('id','?')}")
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


def parse_last_seen(raw):
    """解析 CF last_seen (ISO 8601) → 时区感知 datetime; 解析失败返回 None"""
    if not raw:
        return None
    try:
        s = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def cleanup_devices(cf_token, account_id, hours, dry_run=True):
    """清理 non_identity 认证 + 不活跃超过 hours 小时的设备"""
    st_map = get_service_token_map(cf_token, account_id)
    non_id_token_id = get_non_identity_token_id(cf_token, account_id)
    resp = http("GET", f"{CF_API}/accounts/{account_id}/devices",
                headers={"Authorization": f"Bearer {cf_token}"})
    devices = resp.get("result", [])
    now = datetime.now(timezone.utc)
    cutoff = hours * 3600

    targets = []
    for d in devices:
        user = d.get("user", {})
        email = user.get("email", "")
        if not email.startswith(NON_IDENTITY_PREFIX):
            continue
        last = parse_last_seen(d.get("last_seen"))
        if last is None:
            print(f"⚠️ 跳过 (无法解析 last_seen): {d.get('name')}")
            continue
        inactive = (now - last).total_seconds()
        if inactive > cutoff:
            targets.append((d, inactive))

    if not targets:
        print(f"✅ 无符合条件的设备 (non_identity 且不活跃 > {hours}h)")
        return

    print(f"🎯 命中 {len(targets)} 台 (non_identity 且不活跃 > {hours}h):\n")
    for d, inactive in targets:
        print(f"`{d.get('name')}`")
        print(f"   - 认证: {auth_label(d.get('user',{}).get('email'), st_map, non_id_token_id)}")
        print(f"   - ID: {d.get('id')} | 类型: {d.get('device_type','?')} | IP: {d.get('ip','?')}")
        print(f"   - 不活跃: {int(inactive//3600)}h {int(inactive%3600//60)}m | 最后活跃: {str(d.get('last_seen','?'))[:19]}")
        print()

    if dry_run:
        print(f"🛡️  dry-run 模式: 未执行删除。确认无误后去掉 --dry-run 或设 dry_run=false 再跑。")
        return

    print(f"🗑️  正在删除 {len(targets)} 台设备...")
    for d, _ in targets:
        del_resp = http("DELETE", f"{CF_API}/accounts/{account_id}/devices/{d.get('id')}",
                        headers={"Authorization": f"Bearer {cf_token}"})
        if del_resp.get("success"):
            print(f"✅ 已删除: `{d.get('name')}`")
        else:
            print(f"❌ 删除失败: `{d.get('name')}` {json.dumps(del_resp, ensure_ascii=False)[:200]}")


def main():
    load_env()
    args = sys.argv[1:]
    action = args[0] if args else "list"
    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    if not account_id:
        sys.exit("❌ 未设置 CF_ACCOUNT_ID")

    cf_token = get_cf_token()
    print("🔑 CF 临时 token 获取成功\n")

    if action == "list":
        list_devices(cf_token, account_id)
    elif action == "delete":
        target = args[1] if len(args) > 1 else None
        if not target:
            sys.exit("用法: warp-tools.py delete <device_name>")
        delete_device(cf_token, account_id, target)
    elif action == "cleanup":
        hours = 6
        dry_run = True
        for a in args[1:]:
            if a == "--dry-run":
                dry_run = True
            elif a == "--apply":
                dry_run = False
            else:
                try:
                    hours = int(a)
                except ValueError:
                    sys.exit(f"❌ 无法解析参数: {a} (支持: 小时数 / --dry-run / --apply)")
        cleanup_devices(cf_token, account_id, hours, dry_run)
    else:
        sys.exit(f"❌ 未知操作: {action} (支持: list | delete | cleanup)")


if __name__ == "__main__":
    main()
