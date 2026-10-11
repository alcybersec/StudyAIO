# CSIT314 — Week 5: HTTP Caching

## Overview

Every request a client sends to an origin server costs time and bandwidth — and on a busy site, the same resources (images, stylesheets, API responses) are requested over and over. HTTP caching is the mechanism that lets an intermediate store — the **cache** — keep a copy of a server's response and serve it directly on repeat requests, without the request ever reaching the origin server. Done well, this dramatically reduces latency, network traffic, and load on the server.

This week covers how caching works, how the server tells caches how long a response is trustworthy (**freshness**), what happens when that freshness expires (**stale responses and revalidation**), and how the **conditional request** mechanism (using `ETag` and `If-None-Match`) lets a cache efficiently confirm whether its stored copy is still valid. The lab reinforces this hands-on: fetching the same resource twice with `curl` and observing the `304 Not Modified` response.

## Key Concepts

### What a Cache Is and Why It Exists

A cache stores a response so that a repeat request need not reach the origin server. Think of it like keeping a photocopy of a frequently-read document at your desk instead of walking to the library every time. The performance win is twofold: the client gets the response faster (shorter path), and the origin server handles fewer requests (less load).

### Freshness: `Cache-Control: max-age=N`

Freshness is the core contract of caching. When the origin server sends a response, it can include:

- `Cache-Control: max-age=N` — the response is **fresh** for N seconds after it was sent.
- `no-store` — the response must **not** be cached at all.

During the freshness window, the cache can serve the stored response to clients directly, with no contact with the origin at all. This is the fastest possible case. After N seconds, the response becomes **stale**.

Why does the distinction matter? Some data (e.g., a stable logo image) is safe to reuse for a long time; other data (e.g., a live price or personal account response) must never be reused, which is what `no-store` protects against.

### Stale Responses and Revalidation

A key insight from the lecture: **a stale response is not necessarily wrong.** The `max-age` simply expired — the content may still be identical on the origin server. Rather than throwing the copy away and re-downloading the full resource, the cache can **revalidate** it: it asks the origin server "has this resource changed?" This avoids wasted bandwidth when the answer is "no."

### Conditional Requests: `ETag` and `If-None-Match`

Revalidation needs a cheap way to compare versions. That's the **ETag**: an identifier the origin server attaches to the response, representing the version of the response content.

The revalidation flow:

1. Origin serves a response with an `ETag`.
2. Later, when the cached copy is stale, the cache/client sends a conditional request including `If-None-Match: <that ETag>`.
3. If the resource is unchanged, the origin replies **`304 Not Modified`** with no body — saving bandwidth, since only headers travel.
4. If it has changed, the origin replies **`200 OK`** with the new body and (typically) a new `ETag`.

The efficiency gain is easy to see: for a large unchanged image, revalidation costs a few hundred bytes of headers instead of megabytes of body.

## Definitions

| Term | Definition |
|---|---|
| Cache | A store of a response so a repeat request need not reach the origin server. |
| Origin server | The server that actually holds the resource, as opposed to the cache serving a copy. |
| Fresh | State of a cached response within its `max-age` window; may be served without contacting the origin. |
| `Cache-Control: max-age=N` | Header declaring the response is fresh for N seconds. |
| `no-store` | Directive forbidding caching of the response altogether. |
| Stale response | A cached response whose freshness period has expired; not necessarily wrong. |
| Revalidation | Asking the origin server whether a stale cached response has changed. |
| ETag | An identifier for the version of a response, sent by the origin server. |
| `If-None-Match` | Request header carrying a previously seen ETag to make a request conditional. |
| `304 Not Modified` | Origin's reply meaning "unchanged" — no body is sent, saving bandwidth. |

## Diagrams & Visual Descriptions

**Fresh-serve vs. revalidation flows:**

```
Within max-age (fresh):                After max-age (revalidation):

Client    Cache        Origin          Client    Cache         Origin
   |--GET-->|              |              |--GET--->|              |
   |        |--(serve     |              |         |--GET         |
   |        |   cached    |              |         |  If-None-Match-->|
   |        |   copy)     |              |         |              | compare
   |<--200--|              |              |         |<--304 (no body)--|  if same
   |        |              |              |<--200---|              |
                                          |         |<--200 + body----|  if changed
```

Left: the origin is never contacted while the response is fresh. Right: the ETag is compared; only headers travel if unchanged.

## Code Examples

```bash
# Lab 5: observe a 304 with curl.

# First fetch — full response with headers; note the ETag value.
curl -v http://example.com/resource

# Second fetch — send the ETag back conditionally.
# If unchanged, the origin replies 304 Not Modified with no body.
curl -v -H "If-None-Match: <etag-from-first-response>" http://example.com/resource
```

This is relevant because the lab task asks you to fetch a resource twice and observe the 304 — doing it yourself makes the revalidation mechanism concrete.

## Formulas & Algorithms

No formulas in this lecture. The closest quantitative relationship: bandwidth saved on revalidation ≈ size of the response body, since a `304` carries no body.

## Key Takeaways

- A cache stores responses so repeat requests never burden the origin — a win for both speed and server load.
- `max-age=N` defines a freshness window during which the cache may serve without checking the origin; `no-store` forbids caching entirely.
- Expiry (staleness) does not mean the content is wrong — revalidation exists to check cheaply.
- `ETag` + `If-None-Match` is the version-comparison mechanism for revalidation.
- `304 Not Modified` sends no body, saving bandwidth; `200` with a body means the content changed.
- Running the curl lab yourself cements the difference between a fresh hit, a 304, and a fresh 200.

## Connections

This lecture's lab, "Conditional requests," shows that the caching concepts here are meant to be exercised practically — the revalidation flow (ETag, If-None-Match, 304) is the material's direct extension into hands-on work. Within the lecture itself, no links to other weeks' material are made, and no other weeks were available to compare against.

---
*Sources: CSIT314 Week 5 lecture slides (HTTP Caching); Lab 5 (Conditional requests). Version: 1.*
