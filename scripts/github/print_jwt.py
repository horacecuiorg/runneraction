#!/usr/bin/env python3
"""
GitHub / General JWT Decoder Script

Parses and prints the Header and Payload of a JWT token in pretty-printed JSON format.
Optionally converts standard JWT timestamp claims (exp, iat, nbf) into human-readable UTC datetimes.

Requirements & Design:
- Supports passing JWT via CLI argument or stdin pipe.
- No local environment files (.env) loading.
- No personal user information hardcoded.

Usage Examples:
---------------
1. Decode JWT passed as CLI argument:
   python3 scripts/github/print_jwt.py "eyJhbGciOi..."

2. Pipe JWT token via stdin:
   echo "eyJhbGciOi..." | python3 scripts/github/print_jwt.py

3. Pipe from a file containing JWT:
   cat jwt.txt | python3 scripts/github/print_jwt.py
"""

import argparse
import base64
import json
import sys
from datetime import datetime, timezone


def decode_jwt(jwt_token: str):
    """
    Decodes a raw JWT string into header and payload dictionaries.

    :param jwt_token: Raw JWT string in 'header.payload.signature' format.
    :return: (header_dict, payload_dict)
    """
    jwt_token = jwt_token.strip()

    # JWT 应包含三个以 '.' 分隔的部分: Header, Payload, Signature
    parts = jwt_token.split(".")
    if len(parts) != 3:
        raise ValueError("输入的 Token 格式不符合 JWT 规范（应包含 2 个 '.'，分为 Header.Payload.Signature 三部分）")

    # Base64URL 解码辅助函数（自动补齐缺失的 '=' 填充符）
    def b64_decode(data: str) -> str:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(data).decode("utf-8")

    try:
        header = json.loads(b64_decode(parts[0]))
        payload = json.loads(b64_decode(parts[1]))
        return header, payload
    except Exception as e:
        raise ValueError(f"Base64URL / JSON 解码失败，数据可能损坏或不是有效 JWT: {e}")


def format_timestamp(ts):
    """将 Unix 时间戳转化为人类可读的 UTC 时间字符串."""
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Decode and pretty-print a JWT token's Header and Payload."
    )
    parser.add_argument(
        "token",
        nargs="?",
        default=None,
        help="JWT token string. If omitted, will attempt to read from stdin.",
    )

    args = parser.parse_args()

    # 获取输入的 JWT Token
    jwt_token = args.token
    if not jwt_token:
        if not sys.stdin.isatty():
            jwt_token = sys.stdin.read().strip()
        else:
            parser.print_help()
            sys.exit(1)

    if not jwt_token:
        print("错误: 未提供有效的 JWT Token。", file=sys.stderr)
        sys.exit(1)

    try:
        # 解码 JWT 拿到 Header 与 Payload
        header, payload = decode_jwt(jwt_token)

        # 格式化输出 Header
        print("=== Header ===")
        print(json.dumps(header, indent=2, ensure_ascii=False))

        # 格式化输出 Payload
        print("\n=== Payload ===")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        # 解析并展示常见的时间戳 Claim（iat, nbf, exp）
        time_claims = [
            ("iat", "Issued At (iat)"),
            ("nbf", "Not Before (nbf)"),
            ("exp", "Expiration Time (exp)"),
        ]
        time_info = []
        for claim, label in time_claims:
            if claim in payload and isinstance(payload[claim], (int, float)):
                human_time = format_timestamp(payload[claim])
                if human_time:
                    time_info.append(f"  - {label}: {payload[claim]} ({human_time})")

        # 打印时间戳可读信息与有效状态
        if time_info:
            print("\n=== Time Info ===")
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"Current Time : {now_utc}")
            for info in time_info:
                print(info)

            if "exp" in payload and isinstance(payload["exp"], (int, float)):
                is_expired = datetime.now(timezone.utc).timestamp() > payload["exp"]
                status = "EXPIRED ❌" if is_expired else "VALID / ACTIVE ✅"
                print(f"Token Status : {status}")

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()