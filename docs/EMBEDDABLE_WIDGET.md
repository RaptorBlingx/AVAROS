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
