#!/bin/bash
# Generate self-signed TLS certificate for AVAROS development
#
# Usage: ./generate-dev-cert.sh [output-dir]
#
# Creates a self-signed certificate valid for 365 days with SANs
# for localhost and avaros.local. Suitable for development only —
# use Let's Encrypt for production (see nginx-production.conf).

set -euo pipefail

OUTPUT_DIR="${1:-$(dirname "$0")/ssl}"
mkdir -p "$OUTPUT_DIR"

if [[ -f "$OUTPUT_DIR/cert.pem" && -f "$OUTPUT_DIR/key.pem" ]]; then
    echo "Certificates already exist in $OUTPUT_DIR"
    echo "Delete them first if you want to regenerate."
    exit 0
fi

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$OUTPUT_DIR/key.pem" \
    -out "$OUTPUT_DIR/cert.pem" \
    -subj "/CN=avaros.local/O=AVAROS-WASABI/C=TR" \
    -addext "subjectAltName=DNS:avaros.local,DNS:localhost,IP:127.0.0.1"

echo ""
echo "Self-signed certificate generated in $OUTPUT_DIR"
echo "  cert.pem — certificate"
echo "  key.pem  — private key"
echo ""
echo "Valid for: 365 days"
echo "SANs: avaros.local, localhost, 127.0.0.1"
