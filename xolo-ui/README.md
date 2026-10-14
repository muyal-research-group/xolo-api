# Xolo UI

Local Nuxt/Vuetify administration console for the Xolo API.

The console authenticates platform users through `/api/v4/platform/session`. It uses an opaque HttpOnly session cookie and a CSRF cookie/header pair. It never stores or requests `X-Admin-Token`, and account API keys are managed resources rather than console login credentials.

## Development

Dependencies are locked with pnpm. After they have been installed, run:

```bash
pnpm dev
```

The default API endpoint is `http://localhost:10000/api/v4`. Override it with `NUXT_PUBLIC_API_BASE` when needed. For local access, the console automatically aligns `localhost` and `127.0.0.1` with the hostname used in the browser so SameSite session cookies work across the UI and API ports.

## Production build

```bash
pnpm build
node .output/server/index.mjs
```

Compose binds the console to `127.0.0.1:3000` by default. A `ui-v<version>` Git tag publishes `nachocode/xolo:ui-<version>` after verifying that the tag matches `VERSION`.
