# Kairos Focus extension

Build locally with `npm ci && npm run build`. Load `dist` using Chrome's Load unpacked button at `chrome://extensions`.

1. Start Kairos locally, sign in, add a blocklist, and create a pairing code in Settings.
2. Open the extension and enter that code. The server defaults to `http://localhost:8000`; change it in Server settings if needed.
3. Put the unpacked extension ID in the web application's `VITE_EXTENSION_ID` and restart Vite. This enables immediate start/end sync. The fallback checks every 30 seconds.
4. During a session, navigation rules block selected domains. Chrome alarms remove the rules at the deadline even when the server is unavailable. Ending or pausing a session removes the rules.

The extension reads no page content or browsing history. Basic blocking uses DNR block actions. The optional reminder page requires host permission granted from the popup. Revoke the bearer token from Kairos settings.

The manifest contains localhost development origins only. Before any public release, configure exact app/API origins, permissions, privacy-policy URL, and Web Store account. Nothing is published or installed automatically.
