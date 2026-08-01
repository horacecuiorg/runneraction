#!/usr/bin/env python3
"""
GitHub Secret Management Script

Creates or updates GitHub Repository, Environment, or Organization secrets using GitHub REST API.

Requirements & Design:
- Token MUST be passed explicitly via CLI argument (`-t` / `--token`).
- Target target MUST be passed via (`-to` / `--to`):
  * 'owner/repo' format for Repository or Environment Secrets.
  * 'org' name (without '/') for Organization Secrets.
- No loading of local environment files (.env) or automatic environment fallbacks.

Usage Examples:
---------------
1. Create or update a secret in a Repository:
   python3 scripts/github/set_secret.py -to your-org/your-repo -n MY_SECRET -v "secret_value" -t "ghp_xxxxxxxxxxxx"

2. Create or update an Organization Secret (Default visibility 'all' for Free/Paid orgs):
   python3 scripts/github/set_secret.py -to your-org -n ORG_SECRET -v "secret_value" -t "ghp_xxxxxxxxxxxx"

3. Pass secret value via pipe / stdin:
   echo "secret_value" | python3 scripts/github/set_secret.py -to your-org/your-repo -n MY_SECRET -t "ghp_xxxxxxxxxxxx"

4. Create or update a secret in a specific Environment:
   python3 scripts/github/set_secret.py -to your-org/your-repo -e production -n DEPLOY_KEY -v "key_val" -t "ghp_xxxxxxxxxxxx"
"""

import argparse
import os
import sys
from base64 import b64encode
import requests

try:
    from nacl import encoding, public
except ImportError:
    print(
        "Error: 'PyNaCl' library is missing. Please install it using 'pip install PyNaCl'.",
        file=sys.stderr,
    )
    sys.exit(1)


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """
    Encrypts a plaintext secret string using GitHub's public key (Libsodium SealedBox).
    """
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder)
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


def get_headers(token: str) -> dict:
    """Returns standard headers for GitHub API requests."""
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def create_or_update_repo_secret(
    token: str, owner: str, repo: str, secret_name: str, secret_value: str
):
    """Creates or updates a Repository Actions secret."""
    headers = get_headers(token)

    pk_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    res = requests.get(pk_url, headers=headers, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch public key for repo '{owner}/{repo}'. "
            f"Status Code: {res.status_code}, Response: {res.text}"
        )

    pk_data = res.json()
    key_id = pk_data["key_id"]
    public_key_b64 = pk_data["key"]

    encrypted_val = encrypt_secret(public_key_b64, secret_value)

    secret_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_val,
        "key_id": key_id,
    }

    put_res = requests.put(secret_url, headers=headers, json=payload, timeout=15)
    if put_res.status_code in (201, 204):
        action = "Created" if put_res.status_code == 201 else "Updated"
        print(f"Successfully {action} secret '{secret_name}' in repo '{owner}/{repo}'.")
    else:
        raise RuntimeError(
            f"Failed to create/update secret '{secret_name}' in repo '{owner}/{repo}'. "
            f"Status Code: {put_res.status_code}, Response: {put_res.text}"
        )


def create_or_update_org_secret(
    token: str, org: str, secret_name: str, secret_value: str, visibility: str = "all"
):
    """Creates or updates an Organization secret."""
    headers = get_headers(token)

    pk_url = f"https://api.github.com/orgs/{org}/actions/secrets/public-key"
    res = requests.get(pk_url, headers=headers, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch public key for organization '{org}'. "
            f"Status Code: {res.status_code}, Response: {res.text}"
        )

    pk_data = res.json()
    key_id = pk_data["key_id"]
    public_key_b64 = pk_data["key"]

    encrypted_val = encrypt_secret(public_key_b64, secret_value)

    secret_url = f"https://api.github.com/orgs/{org}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_val,
        "key_id": key_id,
        "visibility": visibility,
    }

    put_res = requests.put(secret_url, headers=headers, json=payload, timeout=15)
    if put_res.status_code in (201, 204):
        action = "Created" if put_res.status_code == 201 else "Updated"
        print(f"Successfully {action} organization secret '{secret_name}' in org '{org}'.")
    else:
        raise RuntimeError(
            f"Failed to create/update secret '{secret_name}' in org '{org}'. "
            f"Status Code: {put_res.status_code}, Response: {put_res.text}"
        )


def create_or_update_env_secret(
    token: str, owner: str, repo: str, env_name: str, secret_name: str, secret_value: str
):
    """Creates or updates an Environment Secret."""
    headers = get_headers(token)

    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    res = requests.get(repo_url, headers=headers, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch repository metadata for '{owner}/{repo}'. "
            f"Status Code: {res.status_code}, Response: {res.text}"
        )
    repo_id = res.json()["id"]

    pk_url = f"https://api.github.com/repositories/{repo_id}/environments/{env_name}/secrets/public-key"
    res = requests.get(pk_url, headers=headers, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch public key for environment '{env_name}' in '{owner}/{repo}'. "
            f"Status Code: {res.status_code}, Response: {res.text}"
        )

    pk_data = res.json()
    key_id = pk_data["key_id"]
    public_key_b64 = pk_data["key"]

    encrypted_val = encrypt_secret(public_key_b64, secret_value)

    secret_url = f"https://api.github.com/repositories/{repo_id}/environments/{env_name}/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_val,
        "key_id": key_id,
    }

    put_res = requests.put(secret_url, headers=headers, json=payload, timeout=15)
    if put_res.status_code in (201, 204):
        action = "Created" if put_res.status_code == 201 else "Updated"
        print(
            f"Successfully {action} secret '{secret_name}' in environment '{env_name}' for repo '{owner}/{repo}'."
        )
    else:
        raise RuntimeError(
            f"Failed to create/update secret '{secret_name}' in environment '{env_name}'. "
            f"Status Code: {put_res.status_code}, Response: {put_res.text}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Create or update GitHub secrets for a repository, environment, or organization."
    )

    parser.add_argument(
        "-to",
        "--to",
        "--repo",
        "-r",
        dest="to",
        required=True,
        help="Target target: 'owner/repo' format for Repository secret, or 'org_name' for Organization secret.",
    )
    parser.add_argument(
        "-n",
        "--name",
        "--secret-name",
        dest="name",
        required=True,
        help="Name of the secret to set.",
    )
    parser.add_argument(
        "-v",
        "--value",
        "--secret-value",
        dest="value",
        default=None,
        help="Secret value (plaintext). If omitted, will attempt to read from stdin.",
    )
    parser.add_argument(
        "-t",
        "--token",
        dest="token",
        required=True,
        help="GitHub Personal Access Token (PAT). Required.",
    )
    parser.add_argument(
        "-e",
        "--env",
        "--environment",
        dest="environment",
        default=None,
        help="Optional target environment name for Environment Secret (requires 'owner/repo' target).",
    )
    parser.add_argument(
        "--visibility",
        dest="visibility",
        choices=["all", "private", "selected"],
        default="all",
        help="Visibility for Organization Secret (default: 'all'). Note: GitHub Free Orgs must use 'all' or 'selected'.",
    )

    args = parser.parse_args()

    token = args.token

    secret_value = args.value
    if secret_value is None:
        if not sys.stdin.isatty():
            secret_value = sys.stdin.read().rstrip("\r\n")
        else:
            print(
                "Error: Secret value is required. Pass --value (-v) or pipe value to stdin.",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        if "/" in args.to:
            # Repository or Environment Secret
            owner, repo = args.to.split("/", 1)
            if not owner or not repo:
                print(
                    f"Error: Invalid repository format '{args.to}'. Both owner and repo name must be non-empty.",
                    file=sys.stderr,
                )
                sys.exit(1)

            if args.environment:
                create_or_update_env_secret(
                    token=token,
                    owner=owner,
                    repo=repo,
                    env_name=args.environment,
                    secret_name=args.name,
                    secret_value=secret_value,
                )
            else:
                create_or_update_repo_secret(
                    token=token,
                    owner=owner,
                    repo=repo,
                    secret_name=args.name,
                    secret_value=secret_value,
                )
        else:
            # Organization Secret
            if args.environment:
                print(
                    "Error: Environment secrets require a repository in 'owner/repo' format.",
                    file=sys.stderr,
                )
                sys.exit(1)

            org = args.to.strip()
            create_or_update_org_secret(
                token=token,
                org=org,
                secret_name=args.name,
                secret_value=secret_value,
                visibility=args.visibility,
            )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
