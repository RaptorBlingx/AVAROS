#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
EXAMPLE_FILE="${ROOT_DIR}/.env.example"

if [[ -e "${ENV_FILE}" && "${1:-}" != "--force" ]]; then
    echo ".env already exists. Use --force to replace it."
    exit 1
fi

command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required to generate deployment credentials."
    exit 1
}

api_key="$(openssl rand -hex 32)"
postgres_password="$(openssl rand -hex 24)"
hivemind_master="$(openssl rand -hex 16)"
hivemind_key="$(openssl rand -hex 16)"
hivemind_secret="$(openssl rand -hex 16)"
hivemind_crypto="$(openssl rand -hex 8)"
tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

awk \
    -v api_key="${api_key}" \
    -v postgres_password="${postgres_password}" \
    -v hivemind_master="${hivemind_master}" \
    -v hivemind_key="${hivemind_key}" \
    -v hivemind_secret="${hivemind_secret}" \
    -v hivemind_crypto="${hivemind_crypto}" \
    '
    BEGIN { FS = OFS = "=" }
    $1 == "AVAROS_WEB_API_KEY" { $2 = api_key }
    $1 == "POSTGRES_PASSWORD" { $2 = postgres_password }
    $1 == "HIVEMIND_MASTER_KEY" { $2 = hivemind_master }
    $1 == "HIVEMIND_CLIENT_KEY" { $2 = hivemind_key }
    $1 == "HIVEMIND_CLIENT_SECRET" { $2 = hivemind_secret }
    $1 == "HIVEMIND_CLIENT_CRYPTO_KEY" { $2 = hivemind_crypto }
    { print }
    ' "${EXAMPLE_FILE}" > "${tmp_file}"

install -m 600 "${tmp_file}" "${ENV_FILE}"
echo "Created ${ENV_FILE} with generated deployment credentials."
echo "Keep this file private and back it up securely."
