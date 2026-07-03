#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

image_mode="local"
if [[ "${1:-}" == "--all-images" ]]; then
    image_mode="all"
elif [[ -n "${1:-}" ]]; then
    echo "Usage: bash scripts/uninstall.sh [--all-images]"
    exit 2
fi

down_args=(--volumes --remove-orphans --rmi "${image_mode}")
integration_file="${ROOT_DIR}/docker/docker-compose.avaros.yml"
prevention_file="${ROOT_DIR}/docker/docker-compose.prevention.yml"
active_config_files="$(
    docker ps -a \
        --format '{{ index .Labels "com.docker.compose.project.config_files" }}' \
        2>/dev/null || true
)"

# Remove legacy 0.1.0/early-0.1.1 resources that used global fixed names.
# Only resources carrying an AVAROS release project label are eligible.
legacy_projects="$(
    docker ps -a \
        --filter 'label=com.docker.compose.project' \
        --format '{{ index .Labels "com.docker.compose.project" }}' \
        2>/dev/null \
        | grep -E '^avaros-dia-v[0-9]+' \
        | sort -u || true
)"
while IFS= read -r legacy_project; do
    [[ -n "${legacy_project}" ]] || continue
    docker compose -p "${legacy_project}" down "${down_args[@]}" || true
done <<<"${legacy_projects}"

for legacy_volume in avaros-data ovos-config hivemind-data; do
    legacy_owner="$(
        docker volume inspect \
            --format '{{ index .Labels "com.docker.compose.project" }}' \
            "${legacy_volume}" 2>/dev/null || true
    )"
    if [[ "${legacy_owner}" =~ ^avaros-dia-v[0-9]+ ]]; then
        docker volume rm "${legacy_volume}" >/dev/null 2>&1 || true
    fi
done

legacy_network_owner="$(
    docker network inspect \
        --format '{{ index .Labels "com.docker.compose.project" }}' \
        avaros-network 2>/dev/null || true
)"
if [[ "${legacy_network_owner}" =~ ^avaros-dia-v[0-9]+ ]]; then
    docker network rm avaros-network >/dev/null 2>&1 || true
fi

# Remove optional AVAROS compose variants only when Docker labels prove they
# were started from this extracted release directory.
integration_active=false
prevention_active=false
if grep -Fq "${integration_file}" <<<"${active_config_files}"; then
    integration_active=true
fi
if grep -Fq "${prevention_file}" <<<"${active_config_files}"; then
    prevention_active=true
fi

if [[ "${integration_active}" == true && "${prevention_active}" == true ]]; then
    docker compose \
        -f "${integration_file}" \
        -f "${prevention_file}" \
        down "${down_args[@]}"
elif [[ "${integration_active}" == true ]]; then
    docker compose -f "${integration_file}" down "${down_args[@]}"
elif [[ "${prevention_active}" == true ]]; then
    docker compose -f "${prevention_file}" down "${down_args[@]}"
fi

docker compose --profile "*" down \
    "${down_args[@]}"

echo "Removed detected AVAROS containers, networks, named volumes, and ${image_mode} images."
echo "The extracted release directory remains at: ${ROOT_DIR}"
echo "Remove it from its parent directory if you also want to delete the files."
