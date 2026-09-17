# Reneryo Future Gen integration

This feature branch adds a narrow conversational layer on top of the existing
OVOS skill, session memory, Reneryo profile, REST infrastructure, bilingual
resources, HiveMind proxy, and embeddable widget.

## Data boundaries

- `ReneryoClient` reads meters, metrics, Reneryo-aggregated trends, and saved
  regression results through organization-scoped `/a` APIs. AVAROS does not
  reproduce Reneryo counter or regression calculations.
- `MdspClient` reads active finding list/detail through MDSP's service API.
- All Reneryo, MDSP, HiveMind, and session-signing credentials remain
  server-side.
- Follow-up memory contains only bounded identifiers, metric/period context,
  and the active finding; utterance text is not persisted.

## Finding handoff

Reneryo validates the logged-in user's access to a finding and requests a
short-lived AVAROS widget session. The signed session is bound to the Reneryo
origin and carries the organization, exact finding ID, entity, metric, and
language. The HiveMind proxy validates those claims, injects them into OVOS
message context, and translates the existing encrypted backend connection so
the long-lived HiveMind client credentials never reach the browser.

Required deployment settings are documented in `.env.example`. The AVAROS
host must be configured with a Future Gen read-only Reneryo access token, MDSP
service credentials, the public Reneryo origin, a session-signing secret, and
the matching Reneryo-to-AVAROS service token.

## Supported MVP queries

English and Turkish queries can list meters and metrics, summarize a named
metric trend, list saved regression models, list active MDSP findings, explain
the selected finding, and continue with the selected finding/metric/period as
session context. Responses include structured evidence for the widget.
