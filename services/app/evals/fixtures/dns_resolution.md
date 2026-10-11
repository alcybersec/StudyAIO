# CSIT314 — Week 3: DNS (Domain Name System)

## Overview

The Domain Name System (DNS) is the internet's "phone book": it translates human-friendly names like `www.example.org` into the IP addresses that machines actually use to route traffic. Without DNS, every application would require users to memorize numeric addresses, and moving a service to a new server would break every client that knew the old address. DNS solves both problems by providing a scalable, distributed naming layer.

What makes DNS particularly elegant is that no single server knows all mappings. Instead, it uses a **hierarchy** of servers and **caching** to handle billions of queries per day efficiently. This week we cover that hierarchy, the step-by-step resolution process for a name like `www.example.org`, how caching with TTLs keeps the system fast, and the record types that make DNS do more than just name-to-address lookups.

## Key Concepts

### Purpose of DNS: Names to Addresses

At its core, DNS performs one fundamental mapping: **name → IP address**. Applications and users work with memorable names, but network-layer routing depends on numeric IP addresses. DNS sits between these two worlds, acting as a distributed lookup service. This indirection also gives flexibility: if the IP address behind `www.example.org` changes, only the DNS record needs updating — clients keep using the same name.

### The DNS Hierarchy

DNS is organized as a tree of servers with three main levels:

- **Root servers** — the entry point of the hierarchy. They don't know final answers, but they know who handles each **top-level domain (TLD)** (e.g., `.org`, `.com`).
- **TLD servers** — responsible for a whole domain suffix (like `.org`). They don't know individual hosts either, but they know which server is **authoritative** for each domain registered under that TLD.
- **Authoritative servers** — hold the actual records for a specific domain (e.g., `example.org`) and can return definitive answers about its hostnames.

This division of labor is what makes DNS scalable: each level only needs to know "who is next in the chain," not every name on the internet.

### The Resolution Process

The lecture walks through resolving `www.example.org` step by step:

1. The **stub resolver** (on the client machine) asks the **recursive resolver** to find the answer.
2. The recursive resolver asks a **root server**, which replies with a **referral** to the `.org` **TLD server**.
3. The TLD server replies with a referral to the **authoritative server** for `example.org`.
4. The authoritative server returns the actual **answer**: the IP address.

Two roles are worth distinguishing here. The *stub resolver* is a lightweight client-side component that simply forwards queries; the *recursive resolver* does the heavy lifting, chasing referrals across the hierarchy on the client's behalf. The client makes only one request and receives the final answer, while the resolver does the multi-step walk.

### Caching and TTL

If every lookup traversed the full hierarchy, root and TLD servers would be overwhelmed. DNS solves this with **caching**: resolvers store answers and reuse them for subsequent queries. Each cached answer carries a **TTL (Time To Live)** specifying how long it remains valid. This creates a trade-off: longer TTLs mean fewer upstream queries and faster responses, but slower propagation when a record changes; shorter TTLs are the opposite.

### Record Types

DNS stores more than just address mappings. The lecture highlights four record types:

| Type | Purpose |
|------|---------|
| **A** | Maps a name to an IPv4 address |
| **AAAA** | Maps a name to an IPv6 address |
| **CNAME** | An alias — points one name to another name |
| **MX** | Identifies the mail server(s) for a domain |

The distinction between A/AAAA (name → address) and CNAME (name → name) matters in practice: a CNAME lets multiple names (e.g., `www` and `web`) refer to one canonical host, so the actual IP only needs to be maintained once. MX records show DNS isn't only for web browsing — it underpins email delivery too.

## Definitions

| Term | Definition |
|------|------------|
| DNS | The Domain Name System; translates names into IP addresses |
| Root server | Top of the DNS hierarchy; refers queries to the appropriate TLD server |
| TLD server | Handles a top-level domain (e.g., `.org`); refers to the domain's authoritative server |
| Authoritative server | Holds the definitive DNS records for a specific domain |
| Stub resolver | Client-side resolver that forwards queries to a recursive resolver |
| Recursive resolver | Resolver that performs the full hierarchy walk on behalf of the client |
| Referral | A response pointing the resolver to the next server in the hierarchy |
| TTL | Time To Live; how long a cached DNS answer remains valid |
| A record | Maps a hostname to an IPv4 address |
| AAAA record | Maps a hostname to an IPv6 address |
| CNAME record | Alias from one domain name to another name |
| MX record | Specifies the mail server for a domain |

## Diagrams & Visual Descriptions

**Resolution flow for `www.example.org`:**

```
 Client (stub resolver)
        |
        | 1. query
        v
 Recursive resolver
        |
        | 2. query ------------> Root server
        |                           |  referral: .org TLD
        | 3. query ------------> .org TLD server
        |                           |  referral: example.org authoritative
        | 4. query ------------> Authoritative server (example.org)
        |                           |
        | <------- answer: IP address
        v
 Client receives the IP address
```

Each arrow to a higher-level server returns a *referral* (a pointer to the next server), until the authoritative server supplies the final answer. Answers may then be cached at the resolver for the TTL duration.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture. (The resolution procedure in the diagram above is the lecture's main algorithmic content.)

## Key Takeaways

- DNS is a distributed hierarchy, not a single database — root, TLD, and authoritative servers each handle only "who's next," which is what makes global scalability possible.
- Resolution is a chain of referrals: stub resolver → recursive resolver → root → TLD → authoritative, ending in the IP address.
- The recursive resolver does the legwork; the client asks once and gets a final answer.
- Caching (bounded by TTL) dramatically reduces load and latency but trades off against how quickly record changes propagate.
- Record types extend DNS beyond web lookups: A/AAAA for IPv4/IPv6 addresses, CNAME for aliases, MX for mail servers.

## Connections

This lecture introduces DNS as core network infrastructure that other networking topics presuppose: any discussion of application-layer communication relies on name-to-address translation happening first. The lecture itself focuses narrowly on resolution, hierarchy, caching, and record types, and does not explicitly point to other weeks.

No other weeks were named in this lecture, so no cross-week links can be drawn beyond DNS's general role as a foundational service in the course.

---
*Sources: CSIT314 Week 3 lecture slides (DNS). Version: 1.*
