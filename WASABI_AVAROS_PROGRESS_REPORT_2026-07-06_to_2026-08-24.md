# AVAROS Progress and Platform-Agnostic Validation Report

**Reporting period:** 6 July 2026 to 24 August 2026

**Prepared for:** WASABI follow-up evaluation

**Prepared on:** 24 August 2026
**Purpose:** post-meeting progress and platform-agnostic validation evidence

---

## 1. Reporting Scope

This report covers progress from 6 July 2026 through 24 August 2026.

Work completed before that meeting is outside the scope of this report and is not counted as progress for the present evaluation period.

The principal objective during this period was to validate the AVAROS platform-agnostic architecture by configuring and operating two independent open-source projects—ThingsBoard Community Edition and OpenEMS—alongside the Reneryo profile used in earlier AVAROS work.

---

## 2. Executive Summary

Since 6 July 2026, AVAROS has progressed in three connected areas:

1. The platform adapter and profile mechanism has been exercised against different external systems rather than only one reference platform.
2. The assistant’s query handling and evidence presentation have been strengthened so that cross-platform answers preserve the requested asset, metric, period, source, and capability boundary.
3. The three configured platform profiles can be switched while the services remain online, with the relevant settings, assets, mappings, capabilities, dashboards, and conversation state refreshed for the selected source.

The principal result is:

> AVAROS is currently configured with separate Reneryo, ThingsBoard CE, and OpenEMS profiles. The ThingsBoard and OpenEMS experiments show that the AVAROS adapter can handle different authentication methods, entity models, API endpoints, response structures, metric names, units, and available capabilities without making either external platform a required AVAROS dependency.

Reneryo is one configured example and the source used in earlier AVAROS work. It is not the foundation that defines the AVAROS core. The ThingsBoard CE and OpenEMS integrations were implemented specifically to validate this distinction.

This result should be understood accurately. AVAROS does not connect automatically to every arbitrary platform. A new source still requires a reachable API and explicit configuration for authentication, entities, fields or metrics, response extraction, units, and enabled questions. What the experiment demonstrates is that these differences can be handled through the adapter, profile, and mapping layers instead of rebuilding the conversational core for each platform.

---

## 3. Progress Since the 6 July Meeting

### 3.1 The generic adapter was exercised with materially different platforms

Earlier AVAROS validation centred on Reneryo data. During this reporting period, the same AVAROS runtime was configured to read and interpret native data from ThingsBoard CE and OpenEMS.

The shared AVAROS components remain the same across the three profiles:

- The AVAROS/OVOS interaction path.
- Text and browser voice interaction.
- The embeddable “Ask AVAROS” widget.
- Profile selection and activation.
- Canonical metric and result models.
- Natural-language routing and response construction.
- Evidence, freshness, and availability reporting.
- The read-only and advisory operating boundary.

The adapter and active profile supply the source-specific details:

- Platform endpoint.
- Authentication method and request headers.
- Asset, device, or system identifiers.
- Metric or channel identifiers.
- Request templates and parameters.
- JSON value and time-series extraction paths.
- Source units and any configured normalization.
- Capabilities that should be enabled or withheld for that source.

This separation is the core of the platform-agnostic experiment. The external systems do not need to share the same backend, API design, entity naming, or software architecture. They do need to expose data through an interface that can be mapped accurately.

### 3.2 Authentication and request configuration were exercised and extended

The three platforms use different connection conventions. The experiment exercised the adapter’s existing profile-level authentication flexibility with the session-cookie method used by the earlier Reneryo example and HTTP Basic authentication for OpenEMS. A configurable custom authorization-header option was added for the ThingsBoard CE connection. Bearer-token and unauthenticated REST configurations remain available where applicable.

The mapping interface can construct requests with asset or resource identifiers, time ranges, and platform-specific query parameters. It can then extract either a current scalar value or a historical series from the configured response structure.

This is externally relevant because the platform differences are resolved at the integration boundary. The user continues to ask an AVAROS question in the same way, while the active profile determines how that question is translated into a valid source request.

### 3.3 Profile switching and isolation were strengthened

Profile switching now refreshes the AVAROS state used by the assistant and web interface. The refresh covers:

- Active source status.
- Platform configuration.
- Asset and metric mappings.
- Dashboard and KPI views.
- Setup-wizard state.
- Asset-to-metric linking.
- Voice-widget conversation state.
- The capabilities advertised for the selected profile.

This prevents information from the previous profile from remaining visible or being used after a switch. For example, a ThingsBoard device should not be treated as an OpenEMS asset, and an OpenEMS battery capability should not appear as a Reneryo or ThingsBoard capability without a real mapping.

The profile-specific capability set is applied consistently to the assistant help and browser interface. This keeps the questions and functions presented to a user aligned with the mapped capabilities of the selected source.

Profile activation is performed while the surrounding services remain online. Changing the active profile does not require stopping one source platform and starting another.

### 3.4 Natural-language accuracy and response evidence were improved

The post-meeting work included a substantial improvement to deterministic dialogue behavior. This was necessary because platform agnosticism is not useful if the assistant loses the user’s requested scope or presents a value without reliable source context.

The main improvements include:

- Historical requests use the requested data series and its configured aggregation rather than treating one returned row as the whole period.
- Total energy, energy per unit, consumption power, production power, grid exchange, and other energy concepts are kept distinct. An unmapped concept, such as energy cost, is identified as unavailable rather than inferred from another metric.
- Multi-asset and multi-metric questions preserve the requested scope.
- Comparisons, rankings, averages, and factory summaries can include all requested results rather than silently selecting one default asset. Comparison results retain the appropriate unit meaning; for example, differences between percentage-based indicators are expressed as percentage points where applicable.
- Relative periods, previous calendar periods, named months, and explicit date ranges are handled explicitly.
- Unknown assets, unsupported future periods, and questions about an unmapped source scope receive a clarification instead of being replaced with a valid but unrelated default. For example, if supplier data is not configured, AVAROS does not substitute a manufacturing-line result.
- Broad, malformed, or otherwise unsupported questions receive a clear response or clarification rather than failing silently.
- Short follow-up questions can reuse the preceding asset, metric, and period within a bounded in-memory conversation session.
- Definition, objective, diagnosis, recommendation, and what-if wording is distinguished from a direct KPI request. What-if answers are limited to supported, meaningful scenarios; AVAROS does not invent a result for an unmodelled process assumption.
- Browser responses can include the source profile, metric, asset, unit, period, aggregation, source observation time, sample coverage, warnings, and a query identifier.

The assistant also maintains explicit boundaries:

- It does not claim that equipment has been controlled.
- It does not invent a target when no objective is configured.
- It does not present correlation as a proven cause.
- It does not present incomplete or unavailable source data as a successful result.
- It does not advertise analytics merely because an analytics service is reachable.

### 3.5 Analytics data was made profile-aware

PREVENTION is an optional analytics component. In a multi-profile system, the availability of PREVENTION itself is not sufficient evidence that a result applies to the active platform.

AVAROS now records which profile supplied the prepared analytics dataset and checks its freshness and record availability. PREVENTION-dependent capabilities are withheld when the prepared data belongs to a different profile.

For example, the dataset currently loaded for PREVENTION was prepared from Reneryo. When OpenEMS is active, AVAROS reports that the matching analytics data is unavailable instead of applying the Reneryo analysis to OpenEMS channels.

This change is part of the platform-isolation work: switching the source must also switch the data context used to justify analytical answers.

### 3.6 Browser interaction and operational reliability were improved

Several user-visible improvements were completed after the previous meeting:

- Audio alignment between consecutive spoken sentences was corrected.
- The browser connection can be configured for a controlled local-network deployment as well as an HTTPS deployment.
- **Cancel request** stops an active request and prevents its later response from appearing as if it belongs to a newer question.
- **Stop response** stops speech that is currently playing.
- The standalone AVAROS service recovers more cleanly when the OVOS core restarts.
- The same AVAROS widget is available inside the ThingsBoard CE and OpenEMS user interfaces, in addition to the earlier Reneryo example, through a controlled integration route without modifying upstream project source code.

Microphone and wake-word functions require the browser security conditions expected for audio capture. Plain local-network platform pages support text interaction; wake-word operation requires a secure AVAROS origin.

### 3.7 Technical handover and evaluation material were updated

The technical documentation was expanded after the 6 July meeting to describe the implemented system rather than only the intended design. The material now covers:

- System boundaries and runtime components.
- The configuration and profile lifecycle.
- Adapter request construction and result normalization.
- The direct KPI, trend, comparison, and derived-metric paths.
- PREVENTION export and result boundaries.
- Browser voice, HiveMind, wake-word, and text-to-speech paths.
- API behavior and authentication boundaries.
- Intent, dialogue, and clarification behavior.
- Alerts and notification limitations.

This documentation records the implemented architecture, integration boundaries, and operational behavior.

---

## 4. Platform-Agnostic Experiment

### 4.1 Why ThingsBoard CE and OpenEMS were selected

The two open-source projects were selected because they test different parts of the adapter model.

[ThingsBoard Community Edition](https://thingsboard.io/installations/) is an open-source IoT platform for device management, data collection, processing, and visualization. It provides devices, assets, current telemetry, time-series data, dashboards, and REST APIs.

[OpenEMS](https://openems.github.io/openems.io/openems/latest/introduction.html) is a modular open-source energy-management platform. OpenEMS Edge communicates with devices and services, collects live data, and supports energy-management functions. OpenEMS UI provides a real-time view, while an optional backend can provide aggregation and monitoring for distributed systems.

Together they provide a useful comparison:

- ThingsBoard CE tests a general IoT device and telemetry model.
- OpenEMS tests an energy-system model with power flows, grid exchange, production, consumption, and battery state.
- Their entity models, APIs, authentication, response structures, and vocabulary are different from each other and from the previous Reneryo example.

### 4.2 ThingsBoard CE configuration and result

The AVAROS ThingsBoard profile uses native ThingsBoard devices and telemetry APIs.

Two devices are mapped for conversational queries:

- Test Device A1.
- Test Device A2.

Each of these devices has three mapped telemetry values:

- Energy per unit.
- Total energy.
- Overall equipment effectiveness (OEE).

The supported query set covers:

- A current KPI for one device.
- A different KPI from the same device.
- A comparison between the two devices.
- An energy trend from the ThingsBoard time-series endpoint.

The telemetry used for this validation is intentionally transparent simulated data. Samples are submitted with current timestamps through ThingsBoard’s native device HTTP transport and are then retrieved through the ThingsBoard API. AVAROS does not write the values directly into the platform database, and the data is not presented as physical factory-sensor evidence.

The ThingsBoard experiment confirms that AVAROS can resolve device names, translate canonical questions into ThingsBoard telemetry keys, retrieve source data, and return a source-aware answer through the existing assistant path.

It does not claim automatic support for every ThingsBoard device or feature. Only the explicitly mapped devices, metrics, and questions are within the present integration scope.

### 4.3 OpenEMS configuration and result

The AVAROS OpenEMS profile uses a running OpenEMS Edge system and its native REST channels.

One OpenEMS Edge asset is mapped to nine read-only values:

1. Total consumption energy.
2. Current consumption power.
3. Current production power.
4. Total production energy.
5. Current grid power.
6. Total grid-import energy.
7. Total grid-export energy.
8. Battery state of charge.
9. Battery power.

The OpenEMS-specific vocabulary was added to AVAROS so that questions such as “How much power is OpenEMS Edge consuming?”, “What is grid power?”, and “What is the battery state of charge?” resolve to separate native channels rather than a generic energy fallback.

AVAROS preserves the source units and the meaning of signed grid and battery values. It does not convert the OpenEMS system into a manufacturing-line model or claim that OEE, scrap, or supplier metrics exist there.

The present OpenEMS environment supplies live Edge channels but does not include an OpenEMS historical time-data backend. Historical OpenEMS trends are therefore disabled in this profile. AVAROS does not construct artificial history to make the feature appear available.

The OpenEMS experiment confirms that the same adapter framework can expose a different operational vocabulary and data model without making the assistant dependent on a manufacturing-specific backend.

### 4.4 Comparison of the three configured profiles

| Dimension | Reneryo example | ThingsBoard CE experiment | OpenEMS experiment |
|---|---|---|---|
| Source type | Manufacturing and resource-efficiency data | General IoT device telemetry | Live energy-management channels |
| AVAROS entities | Production lines and selected meters | ThingsBoard devices | OpenEMS Edge system |
| Source access used | Mapped REST resources and history | Device telemetry and time-series REST APIs | Native Edge REST channels |
| Authentication demonstrated | Session cookie | Configurable authorization header | HTTP Basic authentication |
| Example vocabulary | OEE, scrap, throughput, materials, carbon, energy | Device energy, OEE, comparison, trend | Consumption, production, grid, battery, cumulative energy |
| Historical data | Available for mapped manufacturing data | Available for the mapped energy telemetry | Not enabled because no native time-data backend is deployed |
| PREVENTION context | Available when a fresh Reneryo export is loaded | Not advertised without a matching export | Not advertised while the prepared dataset belongs to Reneryo |

The table does not imply that the three systems have equivalent features. The relevant result is that AVAROS exposes only the subset that can be mapped and supported truthfully for each active profile.

---

## 5. Verified Operational Status

At the reporting cutoff of 24 August 2026, the following operational status was verified:

- AVAROS has three independent profiles: Reneryo, ThingsBoard CE, and OpenEMS.
- The platform services operate concurrently; switching the active AVAROS profile does not require a source-platform restart.
- Both mapped ThingsBoard devices contain native telemetry for energy per unit, total energy, and OEE.
- The OpenEMS profile has a healthy source connection.
- AVAROS returns native OpenEMS values for battery state of charge, consumption power, and grid power.
- The OpenEMS capability set contains nine mapped energy channels.
- PREVENTION is reachable, but its prepared data is identified as Reneryo data and is therefore not presented as OpenEMS analytics.
- The AVAROS web, OVOS, widget, voice, wake-word, ThingsBoard CE, OpenEMS, and PREVENTION services are operational in the validation environment.

Source values continue to change. This report therefore focuses on the selected profile, source asset, metric or channel, unit, response type, and agreement with the corresponding platform data rather than fixed numerical snapshots.

---

## 6. Cross-Platform Validation Evidence

### ThingsBoard CE

The ThingsBoard CE profile validates device resolution, current telemetry retrieval, time-series access, and comparison across two native ThingsBoard devices. Its supported query set includes energy per unit, total energy, OEE, comparison between Test Device A1 and Test Device A2, and an energy trend based on ThingsBoard time-series data.

### OpenEMS

The OpenEMS profile validates a separate energy-system vocabulary and live channel model. It supports consumption power, production power, battery state of charge, battery power, grid power, and cumulative import and export energy values. Historical trends are intentionally unavailable because the present OpenEMS deployment has no native time-data backend.

### Profile isolation

Profile activation refreshes the asset list, metric mappings, enabled questions, evidence source, and conversation context for the selected platform. Reneryo remains available as a third source model with a profile-specific PREVENTION path, but it is not a required AVAROS backend.

---

## 7. Confirmed Boundaries

The following boundaries define the reported integration scope:

- The two open-source integrations are concept proofs, not production certifications.
- The ThingsBoard data is simulated but passes through the native platform ingestion and retrieval interfaces.
- The OpenEMS integration uses a simulated Edge deployment, not operational plant equipment.
- A platform must expose a suitable interface and be explicitly mapped before AVAROS can use it.
- Only configured assets, metrics, channels, and questions are presented as supported.
- OpenEMS history is unavailable until a native historical-data component is added.
- AVAROS remains read-only and advisory and does not perform device or equipment control.
- No energy saving, emissions reduction, productivity improvement, or other business outcome is claimed from these technical validations.
- The controlled widget route used to place AVAROS inside the three platform interfaces is a validation arrangement. A broader deployment would require deployment-specific access control, origin restrictions, and short-lived widget credentials.

---

## 8. Future Extension Potential

The experiment indicates that the current AVAROS core is suitable for further bounded platform integrations. The reusable parts include:

- Profile selection and isolation.
- Endpoint and authentication configuration.
- Entity and field mapping.
- Scalar and time-series extraction.
- Capability activation.
- Conversation and clarification handling.
- Evidence and source presentation.
- Read-only safety rules.
- Embedding the same assistant interface in another application.

This provides a technical basis for exploring API-enabled platforms beyond the current manufacturing and energy scope. Potential areas include customer and service platforms, enterprise-resource and supply-chain systems, maintenance and asset-management systems, quality-management systems, logistics and fleet platforms, building-management systems, operational IoT platforms, and data or analytics platforms. Each area would use its own entities, vocabulary, indicators, permissions, and source-data rules.

These areas are examples of possible extension, not implemented integrations or delivery commitments. Any new domain would require a validated domain model, permissions, terminology, entity mappings, supported questions, response rules, and evaluation data. The present result is narrower: the AVAROS core and adapter boundaries have been exercised with different external systems and are not dependent on one example platform.

---

## 9. Conclusion

The work completed since 6 July 2026 has validated the AVAROS architecture through operation across distinct external systems.

The ThingsBoard CE and OpenEMS experiments show that:

- AVAROS can use different authentication schemes and API structures.
- Different platform entities can be mapped without becoming AVAROS core entities.
- The assistant can change its available vocabulary and questions according to the active source.
- The same AVAROS/OVOS interaction and widget can be reused across the three configured profiles.
- Profile switching can preserve separation between source data, mappings, conversation state, and analytics context.
- Unsupported capabilities can remain visibly unavailable instead of being simulated.

Together, these results provide evidence that the AVAROS adapter and profile approach operates with two additional independent open-source platforms, within the explicit limitations described in this report.

---

## Verification Sources

This report draws on the following sources:

- Project repository history and current implementation from 6 July through 24 August 2026, including refreshed central and GitHub remote references.
- The current three-profile configuration and capability mappings.
- Read-only checks of AVAROS, ThingsBoard CE, OpenEMS, and PREVENTION on 24 August 2026.
- AVAROS architecture, data-lifecycle, dialogue-quality, and three-profile validation material produced during the reporting period.
- Official [ThingsBoard documentation](https://thingsboard.io/docs/) and [OpenEMS documentation](https://openems.github.io/openems.io/openems/latest/introduction.html) for the third-party platform descriptions.

No work completed before the 6 July meeting is presented as progress for this reporting period, and no unsupported production or business outcome is claimed.
