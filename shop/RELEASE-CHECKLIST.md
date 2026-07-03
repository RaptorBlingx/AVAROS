# AVAROS WASABI Shop release checklist

## Package

- [x] Version is consistent in code, docs, archive, and listing
- [x] `scripts/build-release.sh` completes
- [x] ZIP checksum is generated
- [x] ZIP size is within the shop upload limit
- [x] ZIP clean extraction, environment generation, and Compose validation pass
- [x] Custom Web UI port and same-origin HiveMind WebSocket handshake pass
- [x] Server-backed TTS endpoint returns WAV page-media audio for browser playback
- [x] AVAROS-scoped clean-uninstall script validated
- [x] Cross-release Compose naming collision removed
- [x] Clean Ubuntu installation tested on ports 8080 and 9090
- [x] Demo profile starts and returns data
- [x] Base stack health checks pass
- [x] No `.env`, keys, tokens, cookies, logs, databases, or TLS private keys
- [x] No internal development documents
- [x] Apache-2.0 license included

## Documentation

- [x] README quick start verified
- [x] Installation guide verified
- [x] Configuration guide verified
- [x] Operations and backup procedure verified
- [x] Security checklist reviewed
- [x] PREVENTION scope accurately described
- [x] DocuBoT explicitly marked out of scope
- [x] Replication notes included

## Shop

- [x] Storefront and authenticated back office return HTTP 200
- [x] Seller profile is active
- [x] Product type is Virtual product
- [x] Category is Skills
- [x] Product is free unless a commercial decision approves a price
- [x] Download file and checksum uploaded
- [x] Quick-start and checksum attachments uploaded
- [x] Product cover and three configuration screenshots uploaded
- [x] Product preview checked on desktop and mobile
- [x] Guest cart and public attachment downloads tested
- [x] Complete a customer checkout and verify the post-order virtual ZIP link
- [x] All 241 configured countries are active and country-dependent state selection is verified
- [x] Complete a Turkey checkout and verify virtual products do not require a physical carrier
- [x] Product approval/publication completed

## Security

- [x] Hidden files and `/.git/` are blocked
- [x] Shop admin password is not a default
- [x] Shop database credentials are rotated from defaults
- [x] Hivemind credentials are rotated
- [x] Direct container ports are firewalled
- [x] Release archive excludes `.env`, keys, logs, databases, and TLS private keys
- [x] HTTPS certificate is valid
- [x] Logs contain no current reusable credentials
- [x] Post-publication database backup exists

## WASABI evidence

- [x] Live shop URL recorded
- [x] Product URL recorded
- [x] Screenshot of published product retained
- [x] Download/install test evidence retained
- [ ] Shop evaluation form requested/completed
- [ ] Operational cost and sustainability model added to Experiment Handbook
