# PR #71: explicit request and context ownership

Source correction from `faa492d`; no deployment or live configuration change. All quoted values and replies in this document are **synthetic**, captured through the actual signed-widget transport against isolated fixtures.

## Root causes and correction

1. Retained finding context could claim broad words such as “when”, “period” or “explain” before a new operation or metric subject was grounded. Weather metrics intentionally bypass the old factory/counter freshness route. The UTC scope correction in `faa492d` exposed this latent precedence error: the deployed `c9b15f0` had clarified earlier in scope validation.
2. Native metric detail did not preserve a requested timestamp field; even a correctly selected metric could answer with its value/metadata instead. Explicit metric reads now ground uniquely before contextual/semantic fallback, carry the selected inventory snapshot to narration, and use the requested field. Value requests remain value requests. Missing timestamps remain unavailable facts, never guessed times or zeroes.
3. State merges retained finding IDs, entity IDs and periods after unrelated topic switches. State now changes ownership between existing operation groups, preserving organization/language and genuine within-domain follow-ups. Invalid finding-selection clarifications retain their bounded collection; unresolved new subjects do not retain the unrelated finding. Unsupported historical timestamp requests and unbound timestamp shorthand stop safely rather than allowing a semantic trend proposal or a latest-record substitution.

The existing metric inventory is authoritative for latest observation metadata. Original values, UTC observation instants and query semantics are retained. No domain calculation, source client, aggregation, evaluation authorization, widget security, TLS, framework, model, threshold or dependency was changed.

## Captured control and corrected replies

The signed `faa492d` control used 12 turns: its four target timestamp requests produced three wrong-subject answers and one answer to the wrong field. The final candidate matrix includes matching EN/TR requests and independent variants.

| Synthetic question | `faa492d` control | Corrected candidate |
|---|---|---|
| When was the latest humidity reading recorded in UTC? | The evaluation window is 01 September 2026 00:00 UTC to 01 October 2026 00:00 UTC. The longest gap ran from 31 August 2026 18:00 UTC to 01 September 2026 18:17 UTC, lasting 24 hours 17 minutes. The rule selects gaps whose end falls in the lookback window; the duration covers the whole gap, which may start before that window. | Humidity - Open Weather: latest recorded timestamp 15 October 2026 22:30 UTC. |
| What is the timestamp of the latest humidity observation? | Humidity - Open Weather: 60%; 16 October 2026 01:30. | Humidity - Open Weather: latest recorded timestamp 16 October 2026 01:30. |
| Son nem ölçümü ne zaman kaydedildi? | Değerlendirme aralığı 01.09.2026 03:00 ile 01.10.2026 03:00. En uzun boşluk 31.08.2026 21:00 ile 01.09.2026 21:17 arasında 24 saat 17 dakika sürdü. Kural, bitişi değerlendirme aralığına giren boşlukları seçer; süre boşluğun tamamına aittir ve başlangıcı bu aralıktan önce olabilir. | Humidity - Open Weather: son kayıt zamanı 16.10.2026 01:30. |

## Verification and readiness

- **2,568 passed, 417 optional skips, 1 expected failure** across services, use cases, clients, domain, adapters, profile reload and Turkish-language preservation tests. This includes **28 new ownership/field contracts**. It is not a claim that the wider deployment/integration suite was rerun.
- **55 final signed synthetic turns**: actual widget ConnectionManager → origin-bound proxy → HiveMind → OVOS → AVAROS/multilingual E5 → native/scoped HTTP clients. Assert original inputs, signed organization/locale, one reply, separate display/speech delivery, expected operation, source metric/finding IDs, unchanged UTC observations, API targets and inclusive query bounds. Runtime Python source hashes match the corrected source.
- Cover finding → timestamp/value → finding, finding → regression/model-period → metric → meter/link → finding, scoped OEE comparisons → native metric reads, genuine finding evidence/trigger/entity/period follow-ups, inventory reversal, missing observation time, unknown subject, unsupported historical snapshots and one contained source error. Negative/informational evaluation turns produce **zero evaluation POSTs**. Existing positive evaluation authorization regressions pass with mocks.
- Focused undefined-name/import checks and `git diff --check` pass. Frontend source is unchanged. Frozen control, intermediate failures and final captures remain separately under `.qa/avaros-topic-ownership-20261017/` outside Git.

Ready for another **controlled deployment attempt**, subject to the established preflight/rollback checks. The shared FutureGen deployment was untouched in this task. No new live Reneryo/MDSP, microphone/STT, audible TTS or human-listening acceptance is claimed. The grammar and operations remain bounded by the existing MVP; ambiguous/unsupported subjects and historical latest-observation snapshots clarify or report unavailable rather than silently substituting another subject or period.
