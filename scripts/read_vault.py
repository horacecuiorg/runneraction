#!/usr/bin/env python3
import argparse
import json
import os
import sys
import requests
import urllib3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress SSL warnings if verification is skipped
if os.getenv("VAULT_SKIP_VERIFY", "false").strip().lower() == "true":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==========================================
# Custom Exception Classes for Vault Errors
# ==========================================

class VaultError(Exception):
    """Base exception class for all Vault operations."""
    pass

class VaultConfigurationError(VaultError):
    """Raised when Vault address or token is not properly configured."""
    pass

class VaultConnectionError(VaultError):
    """Raised when there is a network connection issue with Vault."""
    pass

class VaultAuthenticationError(VaultError):
    """Raised when Vault returns 401 Unauthorized or 403 Forbidden (Auth issues)."""
    pass

class VaultNotFoundError(VaultError):
    """Raised when the requested Vault secret path does not exist (404)."""
    pass

class VaultKeyNotFoundError(VaultError):
    """Raised when the path exists but the requested key does not exist inside it."""
    pass

# ==========================================
# Core Secret Retrieval Function
# ==========================================

def read_vault_key(path: str, key_name: str = None) -> str:
    """
    Read a KV value from HashiCorp Vault.
    
    :param path: The Vault secret API path (e.g. '/v1/kv/data/home' or 'kv/data/home')
    :param key_name: The key inside the secret (e.g. 'euftp_eu1_name')
    :return: The string value associated with the key
    :raises VaultConfigurationError: If address or token is missing
    :raises VaultConnectionError: If network request fails
    :raises VaultAuthenticationError: If token is invalid or unauthorized (401/403)
    :raises VaultNotFoundError: If secret path is not found (404)
    :raises VaultKeyNotFoundError: If key does not exist in secret data
    :raises VaultError: For other HTTP errors or malformed data
    """
    vault_addr = os.getenv("VAULT_ADDR") or os.getenv("VAULT_URL")
    if vault_addr:
        vault_addr = vault_addr.strip()
        
    vault_token = os.getenv("VAULT_TOKEN")
    if vault_token:
        vault_token = vault_token.strip()
 
    if not vault_addr:
        raise VaultConfigurationError("VAULT_ADDR or VAULT_URL environment variable is not set.")
    if not vault_token:
        raise VaultConfigurationError("VAULT_TOKEN environment variable is not set.")

    # Ensure path starts with a slash
    if not path.startswith('/'):
        path = '/' + path

    # If the path doesn't start with /v1, prepend it
    if not path.startswith('/v1/'):
        path = '/v1' + path

    # Construct the API URL
    url = f"{vault_addr.rstrip('/')}{path}"
    headers = {
        "X-Vault-Token": vault_token
    }

    try:
        skip_verify = os.getenv("VAULT_SKIP_VERIFY", "false").strip().lower() == "true"
        response = requests.get(url, headers=headers, timeout=10, verify=not skip_verify)

        
        # Handle HTTP status codes specifically
        if response.status_code in (401, 403):
            raise VaultAuthenticationError(
                f"Authentication/Authorization failed (Status {response.status_code}). "
                f"Details: {response.text}"
            )
        elif response.status_code == 404:
            raise VaultNotFoundError(
                f"Secret path '{path}' not found (Status 404)."
            )
        
        # Raise for other HTTP errors (500, etc.)
        response.raise_for_status()
        
    except requests.exceptions.Timeout as e:
        raise VaultConnectionError(f"Connection timeout to Vault server: {e}")
    except requests.exceptions.ConnectionError as e:
        raise VaultConnectionError(f"Failed to connect to Vault server at {vault_addr}: {e}")
    except requests.exceptions.HTTPError as e:
        raise VaultError(f"HTTP error occurred while calling Vault: {e}")
    except requests.exceptions.RequestException as e:
        raise VaultError(f"Request exception occurred: {e}")

    try:
        data = response.json()
    except ValueError as e:
        raise VaultError(f"Failed to parse Vault response as JSON: {e}. Body: {response.text}")

    # Vault KV v2 wraps data inside data['data']['data']
    # Vault KV v1 has it directly under data['data']
    secret_data = data.get("data", {})
    
    if isinstance(secret_data, dict) and "data" in secret_data:
        actual_secrets = secret_data["data"]
    else:
        actual_secrets = secret_data

    if not isinstance(actual_secrets, dict):
        raise VaultError(f"Malformed response structure from Vault path '{path}'. Expected key-value object.")

    # If no key_name is specified, return the entire dictionary as a JSON string
    if not key_name:
        return json.dumps(actual_secrets, indent=2, ensure_ascii=False)

    if key_name not in actual_secrets:
        available_keys = list(actual_secrets.keys())
        raise VaultKeyNotFoundError(
            f"Key '{key_name}' not found in path '{path}'. Available keys: {available_keys}"
        )

    return actual_secrets[key_name]

# ==========================================
# CLI Execution Entry Point
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Read a KV value from HashiCorp Vault.")
    parser.add_argument("-p", "--path", default="/v1/kv/data/home", help="Vault secret path (e.g., /v1/kv/data/home)")
    parser.add_argument("-k", "--key", default=None, help="Name of the key to retrieve (if omitted, returns all keys as JSON)")
    
    args = parser.parse_args()
    
    try:
        value = read_vault_key(args.path, args.key)
        print(value)
    except VaultError as e:
        print(f"Vault Operation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
