#!/usr/bin/env python3
"""
GitHub Secret Lister Script

Lists all secret names in a GitHub Repository, Environment, or Organization using GitHub REST API.

Requirements & Design:
- Token MUST be passed explicitly via CLI argument (`-t` / `--token`).
- Target MUST be passed via (`-to` / `--to`):
  * 'owner/repo' format for Repository or Environment Secrets.
  * 'org' name (without '/') for Organization Secrets.
- No loading of local environment files (.env) or automatic environment fallbacks.

Usage Examples:
---------------
1. List secret names in a Repository:
   python3 scripts/github/list_secrets.py -to your-org/your-repo -t "ghp_xxxxxxxxxxxx"

2. List secret names in an Organization:
   python3 scripts/github/list_secrets.py -to your-org -t "ghp_xxxxxxxxxxxx"

3. List secret names in JSON format with metadata:
   python3 scripts/github/list_secrets.py -to your-org -t "ghp_xxxxxxxxxxxx" --json

4. List secret names in a specific Environment:
   python3 scripts/github/list_secrets.py -to your-org/your-repo -e production -t "ghp_xxxxxxxxxxxx"
"""

import argparse
import json
import os
import sys
import requests


def get_headers(token: str) -> dict:
    """Returns standard headers for GitHub API requests."""
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def list_repo_secrets(token: str, owner: str, repo: str) -> list:
    """
    Fetches all repository Actions secrets with pagination.
    """
    headers = get_headers(token)
    secrets = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets?per_page={per_page}&page={page}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            raise RuntimeError(
                f"Failed to list secrets for repo '{owner}/{repo}'. "
                f"Status Code: {res.status_code}, Response: {res.text}"
            )

        data = res.json()
        fetched_secrets = data.get("secrets", [])
        secrets.extend(fetched_secrets)

        total_count = data.get("total_count", 0)
        if len(secrets) >= total_count or not fetched_secrets:
            break
        page += 1

    return secrets


def list_org_secrets(token: str, org: str) -> list:
    """
    Fetches all Organization secrets with pagination.
    """
    headers = get_headers(token)
    secrets = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/orgs/{org}/actions/secrets?per_page={per_page}&page={page}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            raise RuntimeError(
                f"Failed to list secrets for organization '{org}'. "
                f"Status Code: {res.status_code}, Response: {res.text}"
            )

        data = res.json()
        fetched_secrets = data.get("secrets", [])
        secrets.extend(fetched_secrets)

        total_count = data.get("total_count", 0)
        if len(secrets) >= total_count or not fetched_secrets:
            break
        page += 1

    return secrets


def list_env_secrets(token: str, owner: str, repo: str, env_name: str) -> list:
    """
    Fetches all Environment secrets with pagination.
    """
    headers = get_headers(token)

    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    res = requests.get(repo_url, headers=headers, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch repository metadata for '{owner}/{repo}'. "
            f"Status Code: {res.status_code}, Response: {res.text}"
        )
    repo_id = res.json()["id"]

    secrets = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repositories/{repo_id}/environments/{env_name}/secrets?per_page={per_page}&page={page}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            raise RuntimeError(
                f"Failed to list secrets for environment '{env_name}' in repo '{owner}/{repo}'. "
                f"Status Code: {res.status_code}, Response: {res.text}"
            )

        data = res.json()
        fetched_secrets = data.get("secrets", [])
        secrets.extend(fetched_secrets)

        total_count = data.get("total_count", 0)
        if len(secrets) >= total_count or not fetched_secrets:
            break
        page += 1

    return secrets


def main():
    parser = argparse.ArgumentParser(
        description="List GitHub secret names for a repository, environment, or organization."
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
        help="Optional target environment name for Environment Secrets.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output raw JSON array of secret objects with metadata.",
    )

    args = parser.parse_args()

    token = args.token

    try:
        if "/" in args.to:
            owner, repo = args.to.split("/", 1)
            if not owner or not repo:
                print(
                    f"Error: Invalid repository format '{args.to}'. Both owner and repo name must be non-empty.",
                    file=sys.stderr,
                )
                sys.exit(1)

            if args.environment:
                secrets = list_env_secrets(
                    token=token, owner=owner, repo=repo, env_name=args.environment
                )
            else:
                secrets = list_repo_secrets(token=token, owner=owner, repo=repo)
        else:
            if args.environment:
                print(
                    "Error: Environment secrets require a repository in 'owner/repo' format.",
                    file=sys.stderr,
                )
                sys.exit(1)

            org = args.to.strip()
            secrets = list_org_secrets(token=token, org=org)

        if args.as_json:
            print(json.dumps(secrets, indent=2, ensure_ascii=False))
        else:
            if not secrets:
                print("No secrets found.")
            else:
                for secret in secrets:
                    print(secret["name"])

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
