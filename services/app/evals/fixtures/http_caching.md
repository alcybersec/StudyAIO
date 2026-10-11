# CSIT314 — Week 5: HTTP Caching

## Overview

This week combines two files: slides on freshness and Cache-Control, and a lab on conditional requests with ETags. Together they describe how a cache decides to reuse a response.

## Key Concepts

### Freshness (slides)

A cache stores a response so a repeat request need not reach the origin server. Cache-Control: max-age=N says the response is fresh for N seconds, during which the cache serves it without contacting the origin. no-store forbids caching altogether.

### Staleness and revalidation (slides)

A stale response is not necessarily wrong. The cache can revalidate it by asking the origin whether it changed.

### Conditional requests (lab)

The origin sends an ETag identifying the version of the response. On revalidation the client sends If-None-Match with that ETag. If the resource is unchanged the origin replies 304 Not Modified with no body, saving bandwidth; otherwise it replies 200 with the new body. The lab task is to fetch a resource twice with curl and observe the 304.

## Definitions

| Term | Definition |
|---|---|
| max-age | Seconds a response stays fresh |
| no-store | Forbids caching |
| ETag | Identifier for a response version |
| If-None-Match | Request header carrying a stored ETag |
| 304 Not Modified | Unchanged: reply with no body |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

```
curl -i https://host/resource                      # first fetch: 200 plus an ETag header
curl -i -H 'If-None-Match: "<etag>"' https://host/resource   # revalidation: expect 304
```
Run it twice to observe the 304 described in the lab.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- max-age sets freshness; no-store forbids caching.
- Stale is not wrong: revalidate.
- ETag plus If-None-Match turns an unchanged resource into a bodyless 304.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: slides.pdf, lab.pdf. Version: 1.*
