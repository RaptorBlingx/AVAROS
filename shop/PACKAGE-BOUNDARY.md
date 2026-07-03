# Public package boundary

The WASABI Shop archive is built from an explicit allowlist in `scripts/build-release.sh`.

## Published

- runtime source required by Docker builds
- Docker Compose and runtime Docker configuration
- `.env.example`
- credential-generation helper
- anonymized sample data
- customer-facing documentation
- license and changelog

## Not published

- root `.env` and `docker/.env`
- project planning documents, audits, decisions, reports, proposals, and task files
- `DEVELOPMENT.md`
- repository-only workflow files
- tests, E2E harnesses, developer scripts, and local audit output
- `.git/` history and repository configuration
- virtual environments, caches, frontend `node_modules`, and build output
- TLS private keys
- Docker volumes, databases, logs, and runtime PREVENTION exports
- live RENERYO writer, session cookie, mappings, and private pilot data
- WASABI Shop source code

The shop metadata under `shop/` is used to create the listing but is not included in the customer archive.
