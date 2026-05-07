# Embeddable AVAROS Widget

AVAROS provides a single-file browser widget for trusted factory dashboards,
MES screens, and internal intranet portals. The widget connects directly to
HiveMind over WebSocket and sends the same text or push-to-talk utterances that
the AVAROS Web UI sends to OVOS.

## Trust Model

The current widget is an internal/trusted deployment model. The HiveMind access
key and encryption key are visible in the page source because the browser must
use them to open the WebSocket connection and decode AVAROS responses. Use this
version only on controlled internal pages, not public internet sites.

For public websites, add a backend-issued short-lived widget session token and
origin allow-list before exposing the widget.

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
  data-disabled-modes="wake-word">
</script>
```

Wake-word mode is disabled by default for embedded v1. Users can always type in
the widget and can use push-to-talk voice when microphone access is available.
The `data-avaros-url` value powers the widget's Open AVAROS shortcut.

## Required Runtime Conditions

- AVAROS Web UI must serve `/avaros-widget.js`.
- HiveMind must be reachable from the browser at the generated `data-host` URL.
- `HIVEMIND_CLIENT_KEY` must be configured for the Web UI/voice stack.
- `HIVEMIND_CLIENT_CRYPTO_KEY` should be configured when HiveMind responses are
  encrypted; the Settings generator includes it as `data-encryption-key`.
- Microphone features require HTTPS or `localhost`.
- The host page must allow WebSocket connections to the AVAROS/HiveMind URL.

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
6. Click the microphone action and test push-to-talk on HTTPS or localhost.
7. In the browser console, run:

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
