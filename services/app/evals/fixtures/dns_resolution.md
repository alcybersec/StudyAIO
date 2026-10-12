# CSIT314 — Week 3: DNS (Domain Name System)

## Overview

This week introduces DNS, the system that translates names into IP addresses: `name -> IP address` [p.1]. Every time you visit a website, your computer must first find out which IP address corresponds to the hostname you typed. DNS answers that question, and it does so using a hierarchy of servers: the root, top-level domain (TLD) servers, and authoritative servers [p.1].

The lecture covers how a lookup actually happens — the resolution steps a query travels through — and how caching makes the system efficient by storing answers for a limited lifetime (their TTL) [p.2][p.3]. It also introduces the main record types you will encounter: A, AAAA, CNAME, and MX [p.3].

## Key Concepts

### What DNS Does

The core job of DNS is one mapping: `name -> IP address` [p.1]. Humans use names like `www.example.org`; machines on a network are reached by IP addresses. DNS is the service standing between the two, resolving a human-readable name into the numeric address needed to communicate.

### The DNS Hierarchy

DNS is organized as a hierarchy with three tiers: the root, top-level domain (TLD), and authoritative server [p.1]. This structure matters because no single server needs to know every name on the internet. Each tier knows only enough to point a query one level down:

- The **root** sits at the top and directs queries toward the right TLD [p.1].
- The **TLD** server handles a top-level domain such as `.org` [p.2].
- The **authoritative** server holds the actual answer for a specific name like `example.org` [p.2].

### Resolution: Looking Up www.example.org

The lecture walks through the resolution steps for `www.example.org`, which show the hierarchy in action [p.2]:

1. The stub resolver asks the recursive resolver [p.2].
2. The recursive resolver asks a root server -> referral to the .org TLD server [p.2].
3. The TLD server -> referral to the authoritative server for example.org [p.2].
4. The authoritative server -> answer: the IP address [p.2].

Two roles are worth noticing here. The **stub resolver** is the client-side piece that starts the process by asking the **recursive resolver**, which does the legwork of walking the hierarchy on the client's behalf [p.2]. Each tier of the hierarchy doesn't answer the full question — it returns a **referral**, a pointer to the next server that is one step closer to the final answer, until the authoritative server finally supplies the IP address [p.2].

### Caching and TTL

Looking up `www.example.org` from scratch every time would involve multiple servers, so DNS uses caching: answers are cached for their TTL (time to live) [p.3]. The TTL bounds how long a cached answer stays valid, balancing efficiency (fewer repeated lookups) against freshness (names can change addresses, so cached answers must eventually expire) [p.3].

### Record Types

DNS answers come in different record types, each serving a different purpose [p.3]:

| Type | Purpose |
|---|---|
| A | IPv4 address [p.3] |
| AAAA | IPv6 address [p.3] |
| CNAME | alias [p.3] |
| MX | mail server [p.3] |

An A record maps a name to an IPv4 address, AAAA does the same for IPv6, CNAME provides an alias pointing one name at another, and MX records identify the mail server for a domain [p.3].

## Definitions

| Term | Definition |
|---|---|
| DNS | The system that maps `name -> IP address` [p.1] |
| Root server | Top of the hierarchy; refers queries to TLD servers [p.1][p.2] |
| TLD server | Handles a top-level domain (e.g. `.org`); refers to authoritative servers [p.1][p.2] |
| Authoritative server | Holds the actual answer (the IP address) for a name [p.1][p.2] |
| Stub resolver | Client-side resolver that asks the recursive resolver [p.2] |
| Recursive resolver | Performs the full lookup walk through the hierarchy on behalf of the stub resolver [p.2] |
| Referral | A pointer from one server to the next in the hierarchy [p.2] |
| TTL | The duration for which a cached DNS answer remains valid [p.3] |
| A record | Record holding an IPv4 address [p.3] |
| AAAA record | Record holding an IPv6 address [p.3] |
| CNAME record | Record providing an alias [p.3] |
| MX record | Record identifying a mail server [p.3] |

## Diagrams & Visual Descriptions

The resolution flow for `www.example.org` as a chain of referrals [p.2]:

```
Stub resolver
     |
     | asks
     v
Recursive resolver
     |
     | asks
     v
Root server --------- referral to .org TLD server
     |
     v
.org TLD server ----- referral to authoritative server for example.org
     |
     v
Authoritative server - answer: the IP address
     |
     v
(answer cached for its TTL) [p.3]
```

Each server except the last returns only a referral — a pointer deeper into the hierarchy — until the authoritative server produces the actual IP address [p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Resolution algorithm for a hostname (worked example: `www.example.org`) [p.2]:

```
1. Stub resolver asks the recursive resolver
2. Recursive resolver asks a root server -> referral to .org TLD server
3. TLD server -> referral to authoritative server for example.org
4. Authoritative server -> answer: the IP address
```

Core mapping and caching rules [p.1][p.3]:

```
name -> IP address
answers are cached for their TTL
```

Record types [p.3]:

```
A    (IPv4 address)
AAAA (IPv6 address)
CNAME (alias)
MX   (mail server)
```

## Key Takeaways

- DNS exists for one reason: turning `name -> IP address` [p.1].
- The hierarchy (root, TLD, authoritative) lets lookups be distributed — each tier only knows where to send you next [p.1].
- Resolution is a chain of referrals: the recursive resolver does the walking, from root to TLD to authoritative server, which alone holds the answer [p.2].
- Caching (bounded by TTL) avoids repeating the full multi-server lookup on every request [p.3].
- The record type matters: A vs AAAA for address family, CNAME for aliases, MX for mail routing [p.3].

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: CSIT314 Week 3 lecture slides on DNS (pp. 1–3). Version: 1.*
