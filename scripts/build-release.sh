#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.1.1}"
PACKAGE_NAME="avaros-dia-v${VERSION}"
DIST_DIR="${ROOT_DIR}/dist"
STAGE_DIR="${DIST_DIR}/.stage-${PACKAGE_NAME}"
PACKAGE_DIR="${STAGE_DIR}/${PACKAGE_NAME}"
ARCHIVE="${DIST_DIR}/${PACKAGE_NAME}.zip"
trap 'rm -rf "${STAGE_DIR}"' EXIT

command -v rsync >/dev/null 2>&1 || {
    echo "rsync is required to build the release."
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required to create the ZIP archive."
    exit 1
}

rm -rf "${STAGE_DIR}" "${ARCHIVE}"
mkdir -p "${PACKAGE_DIR}" "${DIST_DIR}"

cp \
    "${ROOT_DIR}/README.md" \
    "${ROOT_DIR}/LICENSE" \
    "${ROOT_DIR}/CHANGELOG.md" \
    "${ROOT_DIR}/.env.example" \
    "${ROOT_DIR}/requirements.txt" \
    "${ROOT_DIR}/launch_skill.py" \
    "${PACKAGE_DIR}/"

cp "${ROOT_DIR}/docker-compose.release.yml" "${PACKAGE_DIR}/docker-compose.yml"

rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    --exclude 'build/' \
    --exclude '*.egg-info/' \
    "${ROOT_DIR}/skill/" "${PACKAGE_DIR}/skill/"

rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    --exclude 'frontend/node_modules/' \
    --exclude 'frontend/dist/' \
    --exclude 'frontend/src/**/__tests__/' \
    --exclude 'frontend/src/test/' \
    --exclude 'frontend/**/*.test.ts' \
    --exclude 'frontend/**/*.test.tsx' \
    --exclude 'frontend/public/wizard-preset-humanenerdia.json' \
    "${ROOT_DIR}/web-ui/" "${PACKAGE_DIR}/web-ui/"

rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    --exclude 'training/' \
    --exclude 'README.md' \
    "${ROOT_DIR}/services/" "${PACKAGE_DIR}/services/"

rsync -a \
    --exclude 'docker-compose.dev.yml' \
    --exclude 'docker-compose.e2e.yml' \
    --exclude 'docker-compose.e2e-voice.yml' \
    --exclude 'Dockerfile.e2e' \
    --exclude 'Dockerfile.prevention' \
    --exclude '*.e2e.conf' \
    --exclude '.env' \
    --exclude 'logs/' \
    --exclude 'nginx/ssl/*.pem' \
    "${ROOT_DIR}/docker/" "${PACKAGE_DIR}/docker/"

mkdir -p "${PACKAGE_DIR}/tools"

rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    --exclude 'data/*.json' \
    "${ROOT_DIR}/tools/prevention-addon/" \
    "${PACKAGE_DIR}/tools/prevention-addon/"

rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    "${ROOT_DIR}/tools/prevention-data-sync/" \
    "${PACKAGE_DIR}/tools/prevention-data-sync/"

mkdir -p "${PACKAGE_DIR}/tools/reneryo-data-generator"
cp \
    "${ROOT_DIR}/tools/reneryo-data-generator/__init__.py" \
    "${ROOT_DIR}/tools/reneryo-data-generator/Dockerfile" \
    "${ROOT_DIR}/tools/reneryo-data-generator/main.py" \
    "${ROOT_DIR}/tools/reneryo-data-generator/data.py" \
    "${ROOT_DIR}/tools/reneryo-data-generator/patterns.py" \
    "${ROOT_DIR}/tools/reneryo-data-generator/mapping_output.json" \
    "${ROOT_DIR}/tools/reneryo-data-generator/requirements.txt" \
    "${PACKAGE_DIR}/tools/reneryo-data-generator/"

rsync -a "${ROOT_DIR}/user-docs/" "${PACKAGE_DIR}/user-docs/"
rsync -a "${ROOT_DIR}/examples/" "${PACKAGE_DIR}/examples/"

mkdir -p "${PACKAGE_DIR}/scripts"
cp \
    "${ROOT_DIR}/scripts/prepare-env.sh" \
    "${ROOT_DIR}/scripts/uninstall.sh" \
    "${PACKAGE_DIR}/scripts/"

find "${PACKAGE_DIR}" -type f \
    \( -name '.gitignore' -o -name '.gitkeep' \) \
    -delete

find "${PACKAGE_DIR}" -type f \
    \( -name '.env' -o -name '*.pem' -o -name '*.key' -o -name '*.log' \) \
    -print -quit | grep -q . && {
        echo "Release validation failed: secret or runtime files found."
        exit 1
    }

(
    cd "${STAGE_DIR}"
    python3 -m zipfile -c "${ARCHIVE}" "${PACKAGE_NAME}"
)

(
    cd "${DIST_DIR}"
    sha256sum "${PACKAGE_NAME}.zip" > "${PACKAGE_NAME}.zip.sha256"
)

echo "Created ${ARCHIVE}"
echo "Created ${ARCHIVE}.sha256"
