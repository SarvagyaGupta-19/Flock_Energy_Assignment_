# Urja Meter Ops — Portal Protocol & Reverse Engineering Notes

These are my technical notes on how the **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`) actually works under the hood, based on browser network inspection and examining the client bundles.

---

## 1. System Overview

The portal appears to be a legacy operations portal for a power utility in Rajasthan (Jaipur Zone). Under the hood, it is actually a single-page application built on **SvelteKit** with **Better-Auth** handling user sessions.

- **Frontend**: SvelteKit application using client-side routing, code-splitting chunks (`/_app/immutable/chunks/*`), and route loaders (`__data.json`).
- **Auth library**: Better-Auth, managing HTTP-only session cookies.
- **Dataset scale**: Exactly 403 smart meters, 40 Distribution Transformers (DTs), and ~7 days of 30-minute interval readings per meter.

---

## 2. Authentication & Session Flow

### Login
The portal login form sends a JSON payload to:
- **POST** `/api/auth/sign-in/email`
- Payload:
  ```json
  {
    "email": "operator@urja.local",
    "password": "urja-ops-2026"
  }
  ```
- Sets the session cookie:
  ```http
  Set-Cookie: __Secure-better-auth.session_token=<token>; Path=/; Secure; HttpOnly; SameSite=Lax
  ```

### Session Lifecycle & Quirks
- The session cookie is required for all internal API calls under `/portal/*`.
- When the session expires or is missing, requesting an API endpoint doesn't always return a clean `401 Unauthorized`. In several cases, it returns a `302 Found` redirecting to `/login`, or returns HTTP `200` with the HTML login page.
- In the client code, I check if the returned content type is `text/html` when JSON was requested. If so, it triggers re-authentication and retries the request.

---

## 3. Discovered Endpoints

| Endpoint | Method | Response | Notes |
| :--- | :---: | :--- | :--- |
| `/api/auth/sign-in/email` | `POST` | User metadata + cookie | Authenticates user |
| `/portal/meters/search?q={q}&page={p}` | `GET` | JSON (`{data: [...], total, page}`) | Search by meter ID or serial, 20 per page |
| `/portal/dts?page={p}` | `GET` | JSON (`{data: [...], total, page}`) | Transformers list, 20 per page (40 total) |
| `/portal/meters/{id}/geo` | `GET` | JSON (`{lat, lng}`) | Meter GPS coordinates |
| `/portal/meters/{id}/energy` | `GET` | JSON (`{data: [...]}`) | 30-minute interval energy readings |
| `/portal/keys` | `GET` | JSON (`{data: {signingSecret}}`) | Exposes HMAC signing secret |
| `/portal/export?page=1` | `GET` | JSON (`{total: 403, data: [...]}`) | Full bulk meter export (requires HMAC signature) |
| `/meters/{id}/__data.json` | `GET` | SvelteKit serialized JSON | Route loader returning nameplate & breadcrumb |

---

## 4. The Bulk Export & Cryptographic Signing

The most interesting feature is the **"Export all meters"** button on the Transformers screen (`/transformers`).

When querying `/portal/export?page=1` directly without headers, the server responds with:
```json
{
  "error": "signature_invalid",
  "message": "Missing or invalid request signature."
}
```

Looking inside the compiled SvelteKit JavaScript chunk for the Transformers page (`/_app/immutable/nodes/4.2Bgc2kUI.js`), I found the signing function:

```javascript
async function C(method, path, query, secret) {
  let timestamp = String(Math.floor(Date.now() / 1000));
  let canonical = [method, path, query, timestamp].join("\n");
  let key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
  let sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(canonical));
  return {
    timestamp: timestamp,
    signature: [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("")
  };
}
```

### Signing Protocol:
1. Fetch the active signing secret from `GET /portal/keys`:
   ```json
   {"data": {"signingSecret": "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"}}
   ```
2. Build the newline-delimited canonical message:
   ```text
   GET\n/portal/export\npage=1\n<unix_timestamp_seconds>
   ```
3. Calculate the HMAC-SHA256 hash using the signing secret.
4. Pass headers:
   - `x-timestamp`: current timestamp
   - `x-signature`: hex-encoded HMAC digest

When signed, `/portal/export?page=1` returns all 403 meters in a single JSON payload (~232 KB), complete with nameplate attributes, GPS coordinates, and full 7-level network ancestry.

---

## 5. Consumption Readings

Readings are fetched from `/portal/meters/{id}/energy`.

### Data Shape:
```json
{
  "data": [
    {
      "timestamp": "23/06/2026 23:30",
      "kwh": "48438.74",
      "kvah": "52313.84",
      "voltR": "226"
    }
  ]
}
```

### Quirks:
- **String values**: All numeric values (`kwh`, `kvah`, `voltR`) are returned as strings instead of numbers.
- **Date format**: Dates use the Indian standard `DD/MM/YYYY HH:MM`. Our service parses them into standard ISO-8601 datetimes.
- **Intervals**: Records are taken every 30 minutes, with about 337 entries per meter (~7 days of data).

---

## 6. Network Hierarchy

The portal organizes meters into a 7-level electrical distribution tree:
1. **Zone**: Jaipur Zone 1 (`Z-01`)
2. **Circle**: Circle 1 (`C-01`)
3. **Division**: Division 1 (`D-01`)
4. **Subdivision**: Subdivision 1 (`SD-01`)
5. **Substation**: Substation 1 (`SS-01`)
6. **Feeder**: Feeder 1 (`F-001`) through `F-020`
7. **DT (Distribution Transformer)**: `DT-001` through `DT-040` (capacities: 63 to 400 kVA)
8. **Meters**: `J100000` to `J100402` (averaging ~10 meters per DT)

The hierarchy is present in the breadcrumbs on meter detail pages and is also embedded in the bulk export payload under the `hierarchy` key.
