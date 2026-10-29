# Reflection

### What assumptions did you make?
- **Read-only interface**: I treated the legacy portal as strictly read-only, matching the instructions. I didn't attempt or implement any write or mutation operations.
- **Dataset scale**: Because the entire system has 403 meters and 40 distribution transformers, the full dataset easily fits into process memory (~500 KB). I assumed that keeping the parsed dataset in an in-memory TTL cache is the right choice for a local take-home assignment, rather than bringing in PostgreSQL or Redis.
- **Data volatility**: I assumed network topology and meter installations change rarely, so I cached them for 5 minutes. In contrast, consumption readings are periodic (30-minute intervals), so I gave them a 1-minute TTL.
- **Single operator account**: I assumed this service is the primary consumer of the provided credentials (`operator@urja.local`), so keeping a single authenticated session token in an HTTP client with transparent re-auth is sufficient.

---

### Which part was the most difficult, and how did you get unstuck?
The trickiest part was figuring out how `/portal/export` worked. 

When I first called `GET /portal/export?page=1` with an active session cookie, the server returned `401 Unauthorized` with `{"error": "signature_invalid", "message": "Missing or invalid request signature."}`. Standard API token headers (`Authorization: Bearer`, `X-Api-Key`) didn't work.

I got unstuck by digging into the browser's network tab and inspecting the compiled SvelteKit JavaScript chunks. I searched the scripts loaded on the `/transformers` page and found the compiled event handler for the "Export all meters" button in `4.2Bgc2kUI.js`. De-obfuscating that function showed that:
1. It fetched a secret key from `/portal/keys`.
2. It constructed a string of `[method, path, query, timestamp].join("\n")`.
3. It generated an HMAC-SHA256 signature using the browser's `crypto.subtle` API.
4. It sent the signature and timestamp in `x-signature` and `x-timestamp` headers.

Once I mirrored that exact signing algorithm in Python, the bulk export returned the full 403-meter dataset immediately.

---

### If you had another day, what would you improve?
- **Background synchronization**: Instead of fetching from the portal on demand, I would set up a lightweight background worker that periodically polls for updated consumption readings and populates a local store. That way, queries never block on legacy portal latency.
- **Downstream authentication**: Add API keys or JWT bearer tokens to our wrapper API so that different internal teams or services can be authenticated, tracked, and rate-limited.
- **Persistent storage for larger scale**: If the dataset scaled to hundreds of thousands of meters, holding records in memory wouldn't be sustainable. I would store them in SQLite or PostgreSQL with spatial indexing.
- **Frontend explorer**: Build a simple web dashboard with map visualization and consumption charts to let operations staff explore the data visually.

---

### What mistake did you make while solving this (there's always one)?
Early on during network recon, I misread the network initiator and assumed the meter search endpoint was `/portal/search?q=...` instead of `/portal/meters/search?q=...`. When my script returned a 404, I spent 10 minutes checking if the portal had cookie or header restrictions before realizing I simply had the wrong URL path. Checking the full request URL in the DevTools Headers tab cleared it up.

---

### If you were reviewing your own submission, what would you criticise?
- **Lack of auth on our wrapper API**: The service handles upstream auth cleanly, but the wrapper's own endpoints are currently unauthenticated. In a real utility environment, this would need an API gateway or token validation.
- **Reliance on the bulk export for single meter lookups**: While fetching the bulk export is fast and gives the full hierarchy for 403 meters, in a utility with hundreds of thousands of meters, downloading the whole inventory to find one meter would be impractical. A production version would need a persistent local index maintained by an ingestion pipeline.
