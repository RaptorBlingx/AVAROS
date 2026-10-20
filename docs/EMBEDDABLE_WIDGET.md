# Embeddable AVAROS Widget

AVAROS provides a single-file browser widget for the authenticated Reneryo
application. Reneryo issues a short-lived, origin-bound signed widget session;
AVAROS validates it before proxying the widget's HiveMind and cross-origin
wake-word WebSockets.

## Trust Model

The Reneryo embed does not receive reusable HiveMind credentials. The signed
session is bounded to organization/finding context, expected browser origin,
and a short expiry. Same-origin AVAROS UI wake sockets remain supported;
cross-origin wake sockets require a valid signed session. Microphone PCM is
transported over TLS only after the signed session is validated as the first
WebSocket control message, keeping the token out of URLs and access logs. Audio
is processed locally in the AVAROS deployment and is not persisted, except for
private transcription temporary files deleted when the local process exits.

## Generate The Script Tag

1. Open the AVAROS Web UI.
2. Go to Settings.
3. Open Embeddable Widget.
4. Confirm the status is Ready.
5. Choose position, theme, size, and label.
6. Copy the generated script tag.
7. Paste it before the closing `</body>` tag of the trusted host page.

Example:

```html
<script
  async
  src="https://avaros.example.com/avaros-widget.js"
  data-host="wss://avaros.example.com/hivemind/"
  data-avaros-url="https://avaros.example.com/"
  data-client-name="avaros-web-client"
  data-access-key="HIVEMIND_CLIENT_KEY"
  data-encryption-key="HIVEMIND_CLIENT_CRYPTO_KEY"
  data-position="bottom-right"
  data-theme="auto"
  data-size="medium"
  data-label="Ask AVAROS"
  data-disabled-modes="none">
</script>
```

The Reneryo integration starts in text mode. The user explicitly enables wake
mode in the widget; after microphone permission is granted, a visible badge
remains on the collapsed button. Text and push-to-talk remain available.

## Required Runtime Conditions

- AVAROS Web UI must serve `/avaros-widget.js`.
- HiveMind must be reachable from the browser at the generated `data-host` URL.
- `HIVEMIND_CLIENT_KEY` must be configured for the Web UI/voice stack.
- `HIVEMIND_CLIENT_CRYPTO_KEY` should be configured when HiveMind responses are
  encrypted; the Settings generator includes it as `data-encryption-key`.
- Microphone features require HTTPS or `localhost`.
- The host page must allow WebSocket connections to the AVAROS/HiveMind URL.
- Wake mode requires the page to remain open. Background-tab throttling,
  suspended laptops, mobile screen locking, and browser power policies can
  pause audio processing; this is not an OS-level/background assistant.
- Browsers may require the wake-mode click before microphone capture and audio
  playback. A denied permission is surfaced in the widget and does not remove
  text/push-to-talk fallbacks.

## Public API

The widget exposes `window.AvarosWidget` after loading:

```js
window.AvarosWidget.open();
window.AvarosWidget.close();
window.AvarosWidget.send("forecast energy for Line 1");
window.AvarosWidget.isConnected();
window.AvarosWidget.activateVoice();
window.AvarosWidget.destroy();
```

## Manual Smoke Test

1. Create a plain HTML page on a trusted internal host.
2. Paste the generated script tag.
3. Confirm the floating bubble appears above the page content.
4. Open the bubble and send `forecast energy for Line 1`.
5. Confirm AVAROS replies in the panel.
6. Enable wake-word mode and collapse the widget. Confirm the visible `Wake on`
   badge, say `Hey Jarvis`, and ask an English question.
7. After the spoken response finishes and wake mode re-arms, say `Hey Jarvis`
   and ask a Turkish question, then repeat in English. Confirm EN -> TR -> EN
   transcription, responses, and voices without changing a language selector.
8. Confirm silence, microphone denial, and a temporary socket interruption are
   reported cleanly and that text/push-to-talk remain usable.
9. In the browser console, run:

```js
window.AvarosWidget.open();
window.AvarosWidget.send("what if OEE reaches 90 percent for Line 2");
window.AvarosWidget.close();
window.AvarosWidget.destroy();
```

## Build Verification

Run:

```bash
cd web-ui/frontend
npm run typecheck
npm test
npm run build
npm run build:widget
```

The widget build should produce `dist/avaros-widget.js` as a single IIFE
bundle.

## Signed widget session renewal

The embedding host owns authenticated session issuance. The widget must not receive service credentials or mint its own sessions. Existing AVAROS signed-token expiry, signature, organization and origin validation remains unchanged.

The Reneryo integration previously deferred token renewal while `isConnected()` was true. Its immutable five-minute token could expire while the established socket remained healthy, then be reused for a HiveMind reconnect or a newly activated wake-word socket.

### Integration contract

After the widget loader's `load` event, attach an asynchronous provider:

```ts
window.AvarosWidget.setSessionTokenProvider(async (forceRefresh = false) => {
  // Return a current token issued through the authenticated host backend.
  // Coalesce concurrent calls. Renew before expiry or when forceRefresh is true.
  return hostSession.getToken(forceRefresh);
});
```

Reneryo's companion change on `fix/avaros-session-renewal` implements this through its existing general/finding assistant-session endpoints, without changing their scope or authentication. It renews 60 seconds before expiration, retries failed renewal after 30 seconds, checks freshness on socket connection (including after background timer throttling), and disposes pending results when the embedding scope changes. Failed renewal does not hand an expired token to a socket.

The callback is installed outside React state. Both HiveMind and wake-word clients resolve it immediately before opening each new socket. Authorization renewal does not destroy the widget, reconnect healthy sockets, replay the initial prompt, change the conversation session ID, or clear the transcript. Pending authorization is ignored after teardown.

An explicit `1008 / Expired widget session` response triggers one forced-renewal attempt on each socket path. Rejection of the refreshed attempt stops automatic authorization recovery. Other policy/authentication rejections are not converted into success or retried as expiry. Existing network reconnect behavior remains available. Existing embeds without a session provider retain their credential/static-token behavior.

### Release requirements

This is a coordinated AVAROS widget and Reneryo frontend change. Release the widget API before the Reneryo frontend integration and ensure the new widget bundle is served rather than a stale cached bundle. Existing open tabs need one reload to load the new client code; subsequent renewals do not remount the widget. No backend schema, migration, token TTL, service-token exposure, or authorization relaxation is required. Existing tokens remain valid under their existing rules.

No merge or deployment is authorized by the implementation task. Production acceptance after an approved coordinated release should repeat a session beyond five minutes, transport loss, wake activation, voice-mode switching, and a follow-up using retained context.
