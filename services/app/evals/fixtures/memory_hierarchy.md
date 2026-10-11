# CSIT203 — Week 9: The Memory Hierarchy and Cache Performance

## Overview

Modern computers need enormous amounts of memory, but memory that is simultaneously large *and* fast *and* cheap does not exist — physics and economics make these three properties trade off against each other. The memory hierarchy is the solution: rather than choosing one memory technology, a system stacks several technologies in layers, from tiny, extremely fast registers at the top, through cache and main memory, down to large, slow, inexpensive disk storage at the bottom. As you move down this pyramid, capacity and storage density increase, but access speed decreases and cost per bit rises at the top.

What makes this clever arrangement actually *work* — rather than being a slow, complicated compromise — is a deep regularity in how programs behave: **locality of reference**. Programs do not access memory at random. They repeatedly reuse the same data (temporal locality) and tend to touch data physically near what they just touched (spatial locality). This week we formalize these ideas, introduce the cache as the level that exploits them, and learn to quantify performance with the **Average Memory Access Time (AMAT)** — the key equation behind the problem sheet calculations.

## Key Concepts

### The Structure of the Hierarchy

The hierarchy is ordered by speed-versus-cost: registers at the very top (a handful of values, accessed in less than a nanosecond), then cache (kilobytes to megabytes, a few nanoseconds), then main memory (gigabytes, tens to hundreds of nanoseconds), then disk (terabytes, milliseconds). Each level down is larger and slower but cheaper per byte. The whole point is to present the illusion of a single large, fast memory by keeping the data the program is actively using as close to the top as possible.

The practical consequence: most of the time, the processor finds what it needs near the top, and the slow lower levels are visited only rarely. That rarity is what makes the average cost low despite the bottom of the pyramid being orders of magnitude slower than the top.

### Locality: Why the Hierarchy Works

#### Temporal locality
Recently used data is likely to be used again soon. Loop counters, frequently-called function variables, and hot data structures all exhibit this. Caches exploit it by *retaining* data after first use, betting it will be requested again.

#### Spatial locality
Data near recently used data is likely to be used soon. Array traversal and sequential instruction fetch are classic examples. The hierarchy exploits this not by caching single bytes but by moving whole **blocks (cache lines)** between levels: fetching one word drags its neighbours along for free, so the next nearby access is likely to hit.

### Cache Hits, Misses, and Hit Rate

When the processor requests data:

- **Cache hit** — the data is found in the cache; access completes at cache speed.
- **Cache miss** — the data is not there; the request goes to the next level down (and typically the block is then brought into the cache for future reuse).

The **hit rate** is the fraction of all accesses that hit; the **miss rate** is its complement. Because a miss costs dramatically more than a hit, even a small miss rate can dominate total performance — as the AMAT example below shows vividly.

### Quantifying Performance: AMAT

AMAT combines the cost of the common case (a hit) with the frequency-weighted cost of the rare case (a miss):

$$AMAT = \text{hit time} + \text{miss rate} \times \text{miss penalty}$$

**Problem Sheet Q1:** hit time = 1 ns, miss rate = 5%, miss penalty = 100 ns:

$$AMAT = 1 + 0.05 \times 100 = 6\ \text{ns}$$

Notice that although only 1 access in 20 misses, the average access time is **6×** the hit time. The rare case dominates.

**Problem Sheet Q2:** halving the miss rate to 2.5%:

$$AMAT = 1 + 0.025 \times 100 = 3.5\ \text{ns}$$

A seemingly modest miss-rate improvement nearly halves average access time. The lesson: because the miss penalty is so much larger than the hit time, reducing miss rate is a powerful lever — this is exactly why spatial locality (large blocks) and temporal locality (retention policies) are worth engineering around.

## Definitions

| Term | Definition |
|---|---|
| Memory hierarchy | Layered arrangement of storage (registers → cache → main memory → disk) trading size and cost against speed |
| Temporal locality | The tendency of recently used data to be used again soon |
| Spatial locality | The tendency of data near recently used data to be used soon |
| Cache | A small, fast level of memory holding recently/recently-near data from lower levels |
| Cache block (line) | The unit of data transferred between cache and lower levels; multiple bytes, exploiting spatial locality |
| Cache hit | An access where the requested data is found in the cache |
| Cache miss | An access where the data is absent and must be fetched from the next level |
| Hit rate | The fraction of memory accesses that result in hits |
| Miss rate | The fraction of accesses that miss (= 1 − hit rate) |
| Miss penalty | The extra time required to fetch data from the next level on a miss |
| Hit time | The time to complete an access that hits in the cache |
| AMAT | Average Memory Access Time = hit time + miss rate × miss penalty |

## Diagrams & Visual Descriptions

```
        FASTER / SMALLER / MORE EXPENSIVE PER BYTE
                     ▲
                     │   ┌───────────┐
                     │   │ Registers │  ← tiny, nanosecond access
                     │   ├───────────┤
                     │   │   Cache   │  ← blocks (lines), hits are fast
                     │   ├───────────┤
                     │   │   Main    │  ← gigabytes, slower
                     │   │  Memory   │
                     │   ├───────────┤
                     │   │   Disk    │  ← terabytes, milliseconds
                     │   └───────────┘
                     ▼
        SLOWER / LARGER / CHEAPER PER BYTE
```

On each access the CPU checks the top of the pyramid first. A **hit** returns data quickly; a **miss** cascades down the levels until the data is found, with the block then copied upward so locality can serve future accesses.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

$$AMAT = \text{hit time} + (\text{miss rate} \times \text{miss penalty})$$

Worked examples from Problem Sheet 9:

```text
Q1: hit time = 1 ns, miss rate = 5%, miss penalty = 100 ns
    AMAT = 1 + (0.05 × 100) = 6 ns

Q2: miss rate halved to 2.5%
    AMAT = 1 + (0.025 × 100) = 3.5 ns
```

## Key Takeaways

- No single memory technology is fast, large, and cheap — the hierarchy combines many technologies to approximate all three.
- The hierarchy only works because programs exhibit temporal and spatial locality; random access patterns would defeat it.
- Caches move whole blocks, not bytes, so one fetch serves the neighbouring accesses spatial locality predicts.
- Misses are rare but enormously expensive; a 5% miss rate made average access 6× slower than the 1 ns hit time.
- Because miss penalties dwarf hit times, small miss-rate reductions yield large AMAT improvements (6 ns → 3.5 ns) — the key optimization target.

## Connections

This lecture's AMAT formula quantifies the cost of moving between hierarchy levels — a theme central to any later discussion of cache design and memory performance, since the problem sheet explicitly treats hit time, miss rate, and miss penalty as the tunable parameters of system performance. The block-based organization of the cache, introduced here as the mechanism exploiting spatial locality, is the structural foundation the lecture builds on.

*Sources: Week 9 lecture slides (Memory Hierarchy); Problem Sheet 9. Version: 1.*
