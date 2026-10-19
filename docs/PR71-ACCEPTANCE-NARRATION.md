# PR #71: acceptance narration refinement

Based on `c9b15f0`. This correction is source-only; the controlled live deployment remains unchanged. All examples and measurements below are **synthetic**, captured from the baseline and candidate with the same inputs. They are not real factory data or human audio acceptance.

## Verified semantics and corrections

- Reneryo `packages/common/src/UtilUnit.ts` at `e74b9c7850a0cda4a49cbf8a94291bf3eb079ad5` defines the temperature base unit as Celsius. Native Reneryo observations remain authoritative. AVAROS now narrates the first/last aggregate difference in °C, including zero and negative starting values; it does not calculate a Celsius percentage or invent a temperature stability threshold. Other trend behavior is retained.
- MDSP `src/services/profiler.ts` and `src/rules/supportedRules.ts` at `33ffa7abe2e382f89ab38db8cc434db57d730821` select significant recent gaps by **gap end**, retaining the full interval and duration. `recentGapCount` is the maximum per-resource count, not the sum or an incident count. AVAROS uses the recorded evaluation window and explains the full gap separately, consistently to the nearest minute. It does not clip or repair evidence.
- MDSP `src/rules/nextReview.ts` grounds significance: missing coverage, source suitability for current monitoring, and model period/fit review. Narration adds these meanings without asserting equipment failure, a specific integration cause, an approved policy, a model execution schedule, or a replacement model.
- The shared observation formatter omits zone details for verified local time by default. Missing/invalid bindings still use labelled UTC; naive timestamps remain unassigned. Explicit UTC/detail requests affect presentation only, through request-local arguments. Queries continue to use the verified organization calendar and UTC bounds. Turkish speech expands local calendar dates without requiring a zone suffix.
- Latest-value answers lose nested parentheses; singular counts and unnamed SEUs avoid awkward wording and unnecessary IDs. Metric identities needed for grounding and explicitly requested metadata remain available. Raw evidence and identifiers remain in the structured response.

## Captured before/after

| Synthetic question | Baseline display | Candidate display |
|---|---|---|
| Show outdoor temperature trend in September 2026. | Outdoor temperature is increasing by 33.9% over September 2026. | Outdoor temperature, September 2026: first 17.1 °C, last 22.9 °C; a rise of 5.8 °C. |
| What is the current outdoor temperature value? | Outdoor temperature: 22.9 °C (01 October 2026 01:30 (Europe/Istanbul, UTC+03:00)). | Outdoor temperature: 22.9 °C; 01 October 2026 01:30. |
| Eylül 2026 dış ortam sıcaklığı eğilimini göster. | Outdoor temperature, Eylül 2026 döneminde %33,9 oranında artıyor. | Outdoor temperature, Eylül 2026: ilk değer 17,1 °C, son değer 22,9 °C; 5,8 °C artış. |
| En son sıcaklık değeri nedir? | Outdoor temperature: 22,9 °C (01.10.2026 01:30 (Europe/Istanbul, UTC+03:00)). | Outdoor temperature: 22,9 °C; 01.10.2026 01:30. |

Candidate Turkish speech for the last row: “Outdoor temperature: 22,9 derece Celsius; 1 Ekim 2026 saat 01:30.”

An independent synthetic continuity fixture crosses a 30-day window boundary: the full gap starts before the window, ends inside it, and lasts **24 hours 17 minutes**. Both languages show the actual window and full gap dates, explain why they differ, and retain the original UTC instants and `durationSeconds=87420`. This is not an MDSP calculation defect or a newly executed evaluation.

## Verification

- `tests/test_services`, `tests/test_use_cases`, `tests/test_clients`, `tests/test_domain`: **2,339 passed, 417 optional skips, 1 expected failure**. The focused new/updated contracts cover temperature increase/decrease/no-net-change, zero/negative origins, date/year rollover, explicit UTC and zone details, DST and fractional offsets, unavailable bindings, tenant isolation, full-gap/window semantics, count meaning, model significance, and source preservation. Existing ambiguous inventory and incompatible-unit regressions pass.
- **14 signed synthetic turns** through the existing widget ConnectionManager → origin-bound proxy → HiveMind → OVOS → AVAROS/E5 → scoped HTTP clients. Each keeps original input and signed organization/locale, emits one reply, and delivers separate display/speech strings. Tests include explicit UTC/details, EN/TR Celsius trends, local dates, gap explanation/evidence/period follow-ups, reversed ambiguous inventory, and a local-bucket meter abstention. **Zero evaluation POSTs**.
- Focused undefined-name/unused-import lint and `git diff --check` pass. Frontend source is unchanged. Local raw captures are under `.qa/avaros-acceptance-narration-20261017/` outside Git.

The wider integration/deployment suite was not rerun in this narration task. These checks do not verify the new revision against live Reneryo/MDSP, microphone STT, actual TTS playback, or human listening. Native aggregation limits and arbitrary timezone conversion remain outside this correction. Deployment and live EN/TR listening acceptance require a separate step; no live configuration, services, evaluations, data, or PR target were changed.
