# CSIT314 — Week 5: HTTP Caching and Conditional Requests

## Overview

This week covers HTTP caching: the technique of storing a response close to the client so that a repeat request need not reach the origin server at all [D1 p.1]. Caching matters because it saves the origin server from doing redundant work and saves the client from waiting for a full round trip — within the freshness window, the cache simply serves the stored response without contacting the origin [D1 p.1].

The lecture then addresses the obvious follow-up question: what happens when the freshness period expires? A stale response is not necessarily wrong — the resource may be unchanged — so the cache can *revalidate* it, asking the origin whether it changed [D1 p.2]. Revalidation is done with conditional requests built on the `ETag` mechanism, which lets the origin reply "not modified" (a tiny 304 response) instead of resending the full body [D2 p.1]. Together, `Cache-Control` and `ETag` form a two-tier system: freshness avoids contact entirely, and conditional requests make the contact cheap when it is needed.

## Key Concepts

### Caching Basics

#### What a cache is and why it exists
A cache stores a response so that a repeat request need not reach the origin server [D1 p.1]. The value of this is immediate: instead of every client request travelling all the way to the origin, a repeat request is satisfied from the stored copy. This reduces load on the origin and latency for the client, since the response is served locally [D1 p.1].

#### Freshness with `Cache-Control: max-age=N`
The origin tells caches how long a response may be reused by sending the header `Cache-Control: max-age=N`, which says the response is fresh for N seconds [D1 p.1]. Within that time window, the cache serves the response without contacting the origin at all [D1 p.1]. This is the "happy path" of caching: zero network contact, zero bandwidth, instant response.

#### Opting out: `no-store`
Not everything should be cached. The directive `no-store` forbids caching altogether [D1 p.1]. Use this when a response must never be stored and replayed by any cache along the way.

### Staleness and Revalidation

Once the freshness window of `max-age` has passed, the stored response becomes stale [D1 p.1][D1 p.2]. Crucially, a stale response is not necessarily wrong — the resource on the origin may be exactly the same as when it was cached [D1 p.2]. Rather than discarding the stale copy and refetching the whole body, the cache can *revalidate* it: it asks the origin whether the resource changed [D1 p.2]. If it has not, the expensive full transfer can be avoided.

### Conditional Requests and ETags

#### The ETag
To make revalidation possible, the origin sends an `ETag` along with the response — an identifier for the version of the response [D2 p.1]. Think of it as a fingerprint of the content: if the content changes, the identifier changes.

#### The `If-None-Match` exchange
On revalidation, the client sends `If-None-Match` with that ETag, asking "is this still the current version?" [D2 p.1]. Two outcomes are possible:

- If the resource is unchanged, the origin replies `304 Not Modified` with no body, saving bandwidth [D2 p.1].
- Otherwise, it replies `200` with the new body — a normal full response, which also carries a fresh ETag for future revalidations [D2 p.1].

The elegance of this design is that the cost of a "no change" check is tiny: a status code with no body instead of the full resource.

| Scenario | Origin's reply | Body sent? | Outcome [D2 p.1] |
|---|---|---|---|
| Resource unchanged | `304 Not Modified` | No | Bandwidth saved [D2 p.1] |
| Resource changed | `200` | Yes, the new body | Client gets fresh content [D2 p.1] |

#### Observing it yourself: the lab task
The lab asks you to use `curl` to fetch a resource twice and observe the 304 [D2 p.1]. This makes the mechanism concrete: the first fetch returns the full response with its ETag; the second fetch, sent conditionally, returns the compact `304 Not Modified`.

## Definitions

| Term | Definition |
|---|---|
| Cache | Stores a response so a repeat request need not reach the origin server [D1 p.1] |
| `Cache-Control: max-age=N` | Says the response is fresh for N seconds; within that time the cache serves it without contacting the origin [D1 p.1] |
| `no-store` | Forbids caching altogether [D1 p.1] |
| Stale response | A stored response whose freshness window has passed; not necessarily wrong, and can be revalidated [D1 p.1][D1 p.2] |
| Revalidation | Asking the origin whether the cached (stale) response has changed [D1 p.2] |
| `ETag` | An identifier, sent by the origin, for the version of the response [D2 p.1] |
| `If-None-Match` | Header sent by the client on revalidation, carrying the ETag it holds [D2 p.1] |
| `304 Not Modified` | Origin's reply when the resource is unchanged; carries no body, saving bandwidth [D2 p.1] |
| Conditional request | A request (with `If-None-Match`) whose outcome depends on whether the resource changed [D2 p.1] |

## Diagrams & Visual Descriptions

The life cycle of a cached response, from fresh to revalidated:

```
 Client                    Cache                     Origin
   |                         |                          |
   |------- request -------->|                          |
   |                         | fresh? (max-age=N [D1 p.1])
   |                         |  YES: serve stored response,
   |<------ response --------|  no origin contact [D1 p.1]
   |                         |                          |
   |                         |  NO (stale [D1 p.2]):    |
   |                         |---- If-None-Match: ETag ->| [D2 p.1]
   |                         |                          |
   |                         |   unchanged: 304, no body [D2 p.1]
   |                         |   changed:   200 + new body [D2 p.1]
   |<------ response --------|                          |
```

Read the diagram top to bottom: while the response is fresh (within `max-age=N` seconds), the origin is never contacted [D1 p.1]. Once stale, revalidation via `If-None-Match` either gets a cheap `304` or a full `200` with the new body [D1 p.2][D2 p.1].

## Code Examples

The lab task directs you to use `curl` to fetch a resource twice and observe the 304 [D2 p.1]. This is relevant because seeing the first full response and the second conditional exchange makes the ETag/304 mechanism tangible rather than abstract.

## Formulas & Algorithms

The lecture's quantitative content is its headers and status-code protocol rather than mathematical formulas. The exact mechanisms, in code form:

```
Cache-Control: max-age=N     # response is fresh for N seconds [D1 p.1]
Cache-Control: no-store      # forbids caching altogether [D1 p.1]

Revalidation protocol:
  origin -> client: ETag (identifier for version of the response) [D2 p.1]
  client  -> origin: If-None-Match: <ETag>                       [D2 p.1]
    if resource unchanged:
        reply 304 Not Modified, no body  (saves bandwidth)       [D2 p.1]
    otherwise:
        reply 200 with the new body                              [D2 p.1]
```

Lab exercise: fetch a resource twice with `curl` and observe the 304 [D2 p.1].

## Key Takeaways

- A cache exists to stop repeat requests from reaching the origin server, cutting both load and latency [D1 p.1].
- `max-age=N` is the freshness contract: for N seconds the cache answers alone, with zero origin contact [D1 p.1].
- `no-store` is the opt-out: some responses must never be cached at all [D1 p.1].
- Stale does not mean wrong — revalidation lets a cache check cheaply whether its copy is still valid [D1 p.2].
- ETags turn revalidation into a bandwidth-saving exchange: unchanged content costs only a body-less 304, not a full refetch [D2 p.1].

## Connections

This lecture builds HTTP caching as a self-contained mechanism with two cooperating parts: freshness control via `Cache-Control: max-age=N` and `no-store` [D1 p.1], and correctness checking via ETag-based conditional requests [D2 p.1]. The lab ties the concepts to practice by having you observe a 304 directly [D2 p.1].

This lecture does not name any other weeks or outside topics, so no further links can be drawn.

---
*Sources: Week 5 lecture slides (D1) and Lab 5 document (D2). Version: 1.*
