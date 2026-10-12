# CSIT203 — Week 9: The Memory Hierarchy

## Overview

Modern computers need memory that is simultaneously fast and large — but these two goals pull in opposite directions. Week 9 introduces the memory hierarchy, the layered arrangement of storage technologies that resolves this tension. The fundamental trade-off is stark: faster memory is smaller and more expensive, so systems stack several levels — registers, then cache, then main memory, then disk — and rely on the fast upper levels to serve most accesses [D1 p.1].

What makes this layering work is a predictable pattern in how programs access data, called locality. Because programs repeatedly touch the same small region of memory, a small, fast cache can act as a stand-in for the much larger and slower levels below it. This week also introduces the key performance metric for evaluating the hierarchy: average memory access time (AMAT), which combines hit time, miss rate and miss penalty into a single number you can compute and optimize [D2 p.1].

## Key Concepts

### The Levels of the Memory Hierarchy

The hierarchy is ordered by speed and cost. At the top sit the registers — the fastest and most expensive storage, closest to the CPU. Below them is the cache, then main memory, and finally disk at the bottom, which is the slowest but largest and cheapest per byte [D1 p.1]. The design principle to internalize is the pairing of these properties: as you move down a level, you gain capacity but lose speed.

This matters because if programs accessed memory randomly, a fast-but-small cache would be nearly useless. The hierarchy succeeds precisely because of locality — the tendency of programs to reuse recently accessed data and to access data near what they just accessed [D1 p.1].

### Locality: Why the Hierarchy Works

#### Temporal Locality

Temporal locality is the principle that recently used data is likely to be used again [D1 p.1]. A concrete mental model: when a loop iterates, the loop's instructions and the variables it touches are fetched once and then reused on every iteration — keeping them in cache pays off immediately.

#### Spatial Locality

Spatial locality is the principle that data near recently used data is likely to be used soon [D1 p.1]. Arrays illustrate this well: reading element 0 makes it very likely that element 1 will be read next, so fetching a neighbourhood of bytes at once serves future accesses for free.

### Hits, Misses and Blocks

When the processor requests data, the two possible outcomes are:

- A cache hit — the data is found in the cache [D1 p.2].
- A cache miss — the data is not there, and the request must go to the next level down [D1 p.2].

The hit rate is the fraction of accesses that hit [D1 p.2] — for example, a hit rate of 95% corresponds to the 5% miss rate used in this week's AMAT exercise [D2 p.1].

A crucial design detail: a cache does not hold individual bytes. It holds blocks (also called lines) rather than single bytes, which exploits spatial locality [D1 p.2]. By transferring an entire block on a miss, the cache bets that neighbouring data will be needed soon — turning one slow trip to a lower level into service for several future accesses.

### Measuring Performance: AMAT

The single-number metric for cache performance is:

`Average memory access time (AMAT) = hit time + miss rate * miss penalty` [D2 p.1]

The three ingredients each play a distinct role: the hit time is what you pay on every access, while the miss rate and miss penalty combine into the expected extra cost of taking the slow path. AMAT is the tool for evaluating design changes — as the problem sheet shows, reducing the miss rate has a direct, computable payoff [D2 p.1].

## Definitions

| Term | Definition |
|---|---|
| Memory hierarchy | The layered arrangement of registers, cache, main memory and disk, where faster memory is smaller and more expensive [D1 p.1] |
| Temporal locality | Recently used data is likely to be used again [D1 p.1] |
| Spatial locality | Data near recently used data is likely to be used soon [D1 p.1] |
| Cache hit | An access that finds the data in the cache [D1 p.2] |
| Cache miss | An access that does not find the data, so the request goes to the next level [D1 p.2] |
| Hit rate | The fraction of accesses that hit [D1 p.2] |
| Block (line) | The unit a cache holds, rather than single bytes — this exploits spatial locality [D1 p.2] |
| AMAT | Average memory access time = hit time + miss rate * miss penalty [D2 p.1] |

## Diagrams & Visual Descriptions

The hierarchy as an inverted pyramid — fast and small at the top, slow and large at the bottom:

```
        +-----------+   fastest, smallest, most expensive
        | Registers |                [D1 p.1]
        +-----------+
        |   Cache   |   holds blocks/lines, not single bytes [D1 p.2]
        +-----------+
        |  Memory   |
        +-----------+
        |   Disk    |   slowest, largest, cheapest [D1 p.1]
        +-----------+
```

On a hit, the cache answers; on a miss, the request falls through to the next level [D1 p.2]:

```
CPU -> [ Cache ] --hit--> data returned fast      [D1 p.2]
             |
            miss
             v
         [ Memory ] (next level supplies the data) [D1 p.2]
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The core performance formula [D2 p.1]:

```
AMAT = hit time + miss rate * miss penalty
```

Worked example Q1 [D2 p.1]:

```
Given: hit time 1 ns, miss rate 5%, miss penalty 100 ns
AMAT = 1 + 0.05 * 100 = 6 ns
```

Worked example Q2 — halving the miss rate to 2.5% [D2 p.1]:

```
AMAT = 1 + 0.025 * 100 = 3.5 ns
```

## Key Takeaways

- Faster memory is always smaller and more expensive, so no single technology can be both fast and large — the hierarchy stacks levels instead [D1 p.1].
- Locality is the entire reason the hierarchy works: without temporal and spatial locality, a small cache could not stand in for a large memory [D1 p.1].
- Caches move whole blocks, not bytes — this design choice is what converts spatial locality into real performance gains [D1 p.2].
- AMAT gives you a concrete way to evaluate design changes: halving the miss rate in the problem sheet cut average access time from 6 ns to 3.5 ns — nearly a 2× improvement from one parameter [D2 p.1].

## Connections

This week's material builds a performance model (AMAT) on top of the hierarchy it introduces — registers, cache, main memory and disk — and leaves open how the miss rate itself can be reduced, a question the problem sheet quantifies directly [D2 p.1]. Within the lecture's own scope, locality and the block-based structure of the cache are the concepts the AMAT calculations depend on [D1 p.1][D1 p.2].

---
*Sources: Week 9 lecture slides (D1), Problem sheet 9 (D2). Version: 1.*
