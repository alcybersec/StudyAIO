# CSIT314 — Week 3: DNS Resolution

## Overview

DNS maps names to IP addresses through a hierarchy of servers. The slides give the resolution steps, caching and four record types.

## Key Concepts

### The hierarchy

DNS maps a name to an IP address through a hierarchy: root, top-level domain (TLD) and authoritative server.

### Resolving www.example.org

The stub resolver asks the recursive resolver. The recursive resolver asks a root server and receives a referral to the .org TLD server, which refers it to the authoritative server for example.org. The authoritative server returns the answer: the IP address.

### Caching and records

Answers are cached for their TTL. Record types: A (IPv4 address), AAAA (IPv6 address), CNAME (alias) and MX (mail server).

## Definitions

| Term | Definition |
|---|---|
| Recursive resolver | Does the lookup work on the client's behalf |
| Authoritative server | Holds the answer for a domain |
| TTL | How long an answer may be cached |
| CNAME | An alias record |

## Diagrams & Visual Descriptions

```
stub -> recursive -> root -> (referral) TLD -> (referral) authoritative -> IP address
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Resolution follows referrals root, TLD, authoritative.
- Caching is bounded by TTL.
- A, AAAA, CNAME and MX are the record types shown.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: dns_resolution.pdf. Version: 1.*
