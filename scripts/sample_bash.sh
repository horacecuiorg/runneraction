#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
# Treat unset variables as an error
# Prevent errors in a pipeline from being masked
set -euo pipefail

# Ensure we print a usage helper
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  -n, --name NAME Name to greet (default: World)"
    exit 1
}

NAME="World"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            ;;
        -n|--name)
            NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "Hello, ${NAME}! This is a Bash script running in runneraction."
echo "Running check on environment variables..."
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "Running inside GitHub Actions!"
else
    echo "Running locally."
fi
