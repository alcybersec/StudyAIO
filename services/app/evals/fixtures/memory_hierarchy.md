# CSIT203 — Week 9: Memory Hierarchy and Caches

## Overview

This week has two files: slides explaining why a memory hierarchy works (locality) and a problem sheet that quantifies it with average memory access time.

## Key Concepts

### The hierarchy (slides)

Faster memory is smaller and more expensive: registers, then cache, then main memory, then disk. It works because of locality: temporal locality means recently used data is likely to be used again, and spatial locality means data near recently used data is likely to be used soon.

### Hits and misses (slides)

A cache hit finds the data in the cache; a miss goes to the next level. The hit rate is the fraction of accesses that hit. A cache holds blocks (lines) rather than single bytes, which exploits spatial locality.

### Average access time (problem sheet)

AMAT = hit time + miss rate * miss penalty. With hit time 1 ns, miss rate 5% and miss penalty 100 ns, AMAT = 1 + 0.05 * 100 = 6 ns. Halving the miss rate to 2.5% gives AMAT = 1 + 0.025 * 100 = 3.5 ns.

## Definitions

| Term | Definition |
|---|---|
| Temporal locality | Recently used data is likely used again |
| Spatial locality | Data near recently used data is likely used soon |
| Hit rate | Fraction of accesses that hit |
| AMAT | Average memory access time |
| Miss penalty | Extra time when an access misses |

## Diagrams & Visual Descriptions

```
registers -> cache -> main memory -> disk
 (fastest, smallest, dearest)  ...  (slowest, largest, cheapest)
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

```
AMAT = hit time + miss rate * miss penalty
Q1: 1 + 0.05 * 100   = 6 ns
Q2: 1 + 0.025 * 100  = 3.5 ns
```

## Key Takeaways

- Locality is why the hierarchy works.
- AMAT = hit time + miss rate * miss penalty.
- Lowering the miss rate cut AMAT from 6 ns to 3.5 ns.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: slides.pdf, problems.pdf. Version: 1.*
