# Controlled FutureGen MVP acceptance

This is an operator plan, not deployment authorization. The observation-time
correction extends PR #71 from `b3cd772`; it does not configure a real timezone,
change Reneryo/MDSP calculations, or deploy anything.

## Prerequisites and approval boundary

1. Record the exact approved PR HEAD. Obtain approval for the AVAROS deployment
   window, the organization/profile configuration update, and the rollback plan.
   No merge, release tag, database migration, Reneryo/MDSP deployment, credential
   rotation, or new infrastructure is needed for this correction.
2. An administrator must verify the real organization UUID and its IANA timezone.
   Reneryo currently exposes no organization timezone field. Do not infer it
   from language, browser, hostname, server TZ, or a test label such as
   `futuregen`. In the active `reneryo` profile, merge this binding into the
   existing `extra_settings` through the existing operator configuration path:

   ```json
   {"organization_timezones": {"<verified organization UUID>": "<verified IANA zone>"}}
   ```

   Preserve the complete profile, credentials, asset/metric mappings and all
   other extra settings. Verify the saved binding before testing calendar
   questions. Do not alter SQLite directly or set only an unrelated
   `site_timezone`. Missing/invalid bindings retain explicitly labelled UTC
   observation narration; local-calendar questions still clarify.
3. Recheck real Reneryo access and MDSP findings from the skill's actual clients
   with existing server-side credentials and the real organization. The earlier
   review bridge used the literal `futuregen`; that is not the real tenant ID.
   A 403 for that literal must not be treated as evidence of a service outage or
   resolved by relaxing tenant checks. A findings GET returning 200 establishes
   read access, not freshness of every assessment or evaluation success.
4. Use a real logged-in FutureGen session at its existing HTTPS origin. Verify
   that Reneryo issues a short-lived, origin-bound widget session for the same
   organization; the widget uses the approved AVAROS script and WSS proxy.
   Permanent credentials remain server-side. Keep the existing scoped MDSP CA
   mount and TLS verification. Do not bypass these through the standalone chat.
5. Arrange an EN/TR speaker, microphone and supported browser (the widget uses
   browser SpeechRecognition). Permit microphone access and check network access
   to the browser's recognition service. Server EN/TR Piper models and espeak
   fallback already exist. Confirm permitted use of the existing Turkish demo
   voice as documented in [TURKISH_PIPER_VOICE.md](TURKISH_PIPER_VOICE.md).

## Existing deployment path — execute only after approval

The audited deployment is `/home/ubuntu/avaros-ovos-skill` on
`avaros.int.arti.ac`, using `docker-compose.yml` plus
`docker/docker-compose.futuregen.yml`. Use these live Compose descriptors,
not the legacy WASABI rebuild script or a new release project/volume.

Before changing the checkout/profile, retain the current Git revision, clean
tracked status, container start times, image IDs and recoverable image tags.
Securely back up `.env`, both Compose files and the settings database using a
consistent SQLite backup; retain ownership/permissions and the current
`avaros-data`, OVOS and HiveMind volumes. Preserve existing rollback files,
proxy configuration and scoped certificate mounts. Do not print or commit
secrets or production measurements. Confirm that any schema initialization
performed by the candidate is compatible with the retained database; stop if
an unexpected migration is required.

Advance only the intended checkout to the approved commit. Build both product
services so the skill and served application/widget agree:

```sh
docker compose -f docker-compose.yml -f docker/docker-compose.futuregen.yml build avaros avaros-web-ui
docker compose -f docker-compose.yml -f docker/docker-compose.futuregen.yml up -d --no-deps avaros avaros-web-ui
```

Apply/read back the verified timezone binding through the existing profile
settings path. Verify container source against the approved commit, actual
semantic-router readiness, the served widget bundle and browser cache refresh,
not just the static health version. Keep MDSP, Reneryo, proxy, OVOS, HiveMind,
wakeword, exporter and their data intact; do not run `down -v`, broad `up`, or
reset/init/generator scripts on the shared deployment.

If rollback is needed, restore the recorded checkout and exact previous
skill/web images using the same Compose project. Restore the pre-test profile
configuration through the supported settings path; use the consistent database
backup only if a database restore is actually required and separately approved.
Keep the current database unless restoration is necessary. Verify the previous
source/images and session path after rollback.

## One bounded acceptance session

First type the questions inside the actual FutureGen widget. Then repeat the
key questions by EN/TR push-to-talk and listen to the replies. Use actual
inventory names and periods whose source coverage has been checked; do not
assume synthetic aliases or old manual checklists describe today's data.

| Check | Pass condition |
| --- | --- |
| Inventory and latest observation | Correct scoped source/subject, value and unit; displayed and spoken timestamp matches the verified organization timezone, including date rollover. UTC source evidence still represents the original instant. |
| Yesterday / previous month | Local midnight/month bounds become the correct UTC API bounds. No period/subject substitution when empty. |
| Timestamp around a date boundary | Local displayed date and speech agree; offset identifies the zone. Do not change a source monthly bucket label into a different month. DST and repeated-hour cases have synthetic tests; a normal live session does not independently verify DST transitions. |
| Spoken ten days / on gün and a decimal percentage | Inspect the actual STT transcript first, then operation, subject, bounds/quantity and source. Distinguish recognition errors from resolution errors. Use only configured KPI scenarios. |
| Ambiguous subject / incompatible units | Clarify the subject; retain individual meter values and units, with no invented total. |
| Native local consumption limit | Exact local week/month totals may abstain when Reneryo's auto-selected UTC buckets do not align. No AVAROS proration or aggregation workaround. If such exact totals are mandatory, acceptance remains blocked on a Reneryo-owned capability. |
| MDSP finding and evidence/period follow-up | Real organization reaches the existing finding, its rule evidence and provisional status. Narrated observation/window times are local, underlying evidence unchanged. |
| Informational/negative evaluation questions | No evaluation POST. A real evaluation is a separate, explicitly approved action because it writes MDSP evaluation/findings state. |
| EN/TR audio | One reply; accurate spoken date, quantity, unit, limitations and language; audible playback, no duplicate speech/echo pickup, and recovery after the reply. Text and actual audio convey the same facts. |

Retain exact question, actual transcript, verbatim displayed/spoken response,
request/session correlation, selected source IDs, UTC bounds, timezone binding
and source comparison in access-controlled evidence outside Git. Do not invent
an improved answer in the evidence. Use no-data and unavailable responses as
acceptance outcomes when they accurately reflect source/aggregation limits.

Approve the MVP only after real signed-session text and human audio checks pass
for the agreed scope. Automated synthetic transport tests, installed TTS models,
health endpoints and source review alone do not constitute live/audio acceptance.
