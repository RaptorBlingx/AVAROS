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

When MDSP uses the scoped internal CA, set `MDSP_TLS_CA_HOST_PATH` to that CA
certificate and include `docker/docker-compose.futuregen.yml` in Compose
commands. The CA is mounted read-only into the skill container; certificate
verification remains enabled.

## Embedded hands-free voice

The Reneryo widget can opt into the existing server-side `hey_jarvis`
openWakeWord socket while it remains collapsed. Browser `getUserMedia` audio
is resampled to 16 kHz PCM by the existing worklet and crosses the same
origin-bound signed-session boundary before reaching the private wake service.
The widget shows an explicit `Wake on` indicator whenever that microphone
stream is armed.

After detection, the widget pauses its microphone stream, gives a localized
readiness acknowledgement, then opens a fresh Silero-VAD capture window for
the following utterance. A pinned local multilingual whisper.cpp base Q5 model
transcribes that request and independently detects English or Turkish; the
wake phrase never chooses the request language. The transcript and detected
locale enter the existing signed HiveMind connection, so organization/finding
context, conversational routing, semantic fallback, and EN/TR TTS are
unchanged. Microphone streaming stays paused during routing and TTS, then
re-arms after playback to prevent self-triggering.

Server-side post-wake capture is a per-socket opt-in used by the embedded
widget. Detection-only clients, including the existing full AVAROS UI flow,
retain their prior behavior. Browser SpeechRecognition remains only the
manual push-to-talk fallback; wake turns never depend on its fixed locale or
optional server-based browser recognition.

## Supported MVP queries

English and Turkish queries can list meters and metrics, summarize a named
metric trend, list saved regression models, list active MDSP findings, explain
the selected finding, and continue with the selected finding/metric/period as
session context. Responses include structured evidence for the widget.

## Local semantic routing

Registered OVOS/Padatious intents and existing deterministic fallback checks
remain the first routing path. If they cannot resolve a Reneryo request, the
skill may use the locally bundled
[`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small)
embedding model (MIT license) to choose among the existing canonical Future
Gen actions. The image uses the pinned
[`Xenova/multilingual-e5-small`](https://huggingface.co/Xenova/multilingual-e5-small)
INT8 ONNX conversion; its model checksum is verified during the build.

The semantic layer returns only an action, language, supported period slot,
and confidence/ambiguity metadata. It never answers a Reneryo question itself
and receives no raw factory records. Existing organization-scoped clients and
deterministic formatters remain authoritative. Finding follow-ups are available
only with an active finding in the bounded signed/session context. Requests
below the configured confidence or separation margin are clarified instead of
guessed.

All inference is CPU-local after image build. No inference API key or runtime
cloud connection is used. `AVAROS_SEMANTIC_ROUTING_ENABLED=false` disables the
optional layer without affecting deterministic intents.

The bundled model directory is about 129 MiB (118 MiB ONNX file). In the
prototype container on the AVAROS-class two-CPU host, resolver initialization
took about 1.7 seconds, 50 sequential classifications had a 7.8 ms median and
11.3 ms p95, and the isolated process peaked near 588 MiB RSS. These figures are
capacity guidance rather than an application-level memory delta.
