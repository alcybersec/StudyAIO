# CSIT302 — Week 5: Hash Tables

## Overview

A hash table is one of the most important data structures in computer science because it promises something remarkable: lookup of a key in **O(1) average time**. Instead of searching through data sequentially or navigating a tree, a hash table uses a *hash function* to compute, directly from the key, the index of the bucket where the value is stored. Want to find `"student_id=12345"` in a table of a million records? You don't scan a million entries — you compute a number and jump straight to the answer.

This week's lecture focuses on the mechanics behind that promise and, crucially, on when the promise breaks. The average O(1) is **a claim about the quality of the hash function, not a guarantee built into the structure itself**: with a bad hash function, every key can land in the same bucket, and the table degenerates into an O(n) linear scan. The lecture therefore examines collision handling (separate chaining, linear probing, quadratic probing), the *load factor* as the key performance indicator, and *rehashing* as the mechanism that restores performance — with an amortised analysis explaining why the occasional O(n) rebuild doesn't ruin overall efficiency.

## Key Concepts

### The Hash Table Model

A hash table maintains an array of *buckets*. When you insert or look up a key–value pair, a hash function maps the key to an integer index into that array. The "O(1)" behaviour comes from this direct address calculation: the amount of work is independent of how many entries are stored.

The critical subtlety the lecture emphasises: the average case is a *probabilistic* claim that depends on the hash function distributing keys well across buckets. If the hash function is poor (for example, mapping many keys to the same index), every key collides and lookup degrades to O(n) — the hash table becomes no better than a plain list. So when you analyse a hash table, you are really analysing two things: the structure (buckets, collisions, probing) and the assumption about hash quality.

### Load Factor

The **load factor** is the ratio:

$$\alpha = \frac{\text{number of stored entries}}{\text{number of buckets}}$$

It measures how "full" the table is, and it is the single best predictor of hash table performance. As α approaches 1, collisions become frequent, chains (or probe sequences) grow long, and lookup slows noticeably. This is why well-designed hash tables resize themselves *before* the table fills completely — performance is managed by keeping the load factor low, not by choosing a better probe sequence after the fact.

### Collision Resolution Strategies

Two keys hashing to the same bucket is inevitable (there are far more possible keys than buckets), so how we handle collisions defines each hash table variant.

#### Separate Chaining

Each bucket holds a **linked list**. Colliding keys simply append to that bucket's list, so the table can hold arbitrarily many entries per bucket. Lookup cost is proportional to the *length of the chain* at the hashed bucket. With a good hash function and a low load factor, chains are short (around α entries on average), so lookups remain effectively constant time. Chaining's virtue is its simplicity and robustness — it degrades gracefully as the table fills.

#### Open Addressing and Linear Probing

**Open addressing** stores all entries directly in the table array itself — there are no auxiliary lists. On a collision, we search for another free bucket. **Linear probing** is the simplest approach: check the next bucket, then the next, until an empty slot is found.

Its weakness is **primary clustering**: collisions form contiguous runs of occupied buckets. Once a run exists, a key hashing anywhere into that run must probe past the *entire* run — and every insertion extends the run, making future collisions even more likely. Runs snowball, and performance degrades faster than the load factor alone would suggest.

#### Quadratic Probing

Quadratic probing combats clustering by probing at **increasing square offsets** — index + 1², + 2², + 3², ... — instead of stepping one slot at a time. Because successive probes jump further and further across the table, entries are spread out rather than packed into contiguous runs, so primary clustering is avoided. This is the lecture's example of how a small change in probe strategy can materially improve behaviour at the same load factor.

| Strategy | Where entries live | Collision handling | Main weakness |
|---|---|---|---|
| Separate chaining | Linked list per bucket | Append to the chain | Chain length grows with load factor |
| Linear probing | In the table itself | Probe next slot, then next | Primary clustering |
| Quadratic probing | In the table itself | Probe at 1², 2², 3², ... offsets | Avoids primary clustering; still sensitive to load factor |

### Resizing and Rehashing

When the load factor crosses a chosen threshold, the table is **resized** — typically doubled — and **every key is rehashed** into the new table (keys must be rehashed because their indices depend on the table size). This rebuild is an O(n) operation, which sounds alarming for a structure built on O(1) promises.

The resolution is **amortised analysis**: rehashing happens only after many insertions have occurred (since the table doubled, it takes roughly as many insertions again to trigger the next resize). Spreading the O(n) rebuild cost across those insertions, the *amortised cost per insertion stays constant*. The lesson generalises: occasional expensive operations can be acceptable if they are rare enough relative to the cheap operations between them.

## Definitions

| Term | Definition |
|---|---|
| Hash table | A data structure mapping keys to array indices via a hash function, giving O(1) average-case lookup. |
| Hash function | A function that maps a key to a bucket index in the table. |
| Load factor | Ratio of stored entries to buckets; performance degrades as it approaches 1. |
| Collision | The event of two keys hashing to the same bucket. |
| Separate chaining | Collision resolution storing a linked list at each bucket; lookups cost the chain length. |
| Open addressing | Collision resolution storing all entries in the table itself and probing for free slots. |
| Linear probing | Open addressing variant that checks successive buckets one at a time. |
| Primary clustering | Tendency of linear probing to form growing runs of occupied buckets that increase collision likelihood. |
| Quadratic probing | Probing at increasing square offsets (1², 2², ...), spreading entries and avoiding primary clustering. |
| Rehashing | Recomputing every key's index after resizing, usually doubling, the table. |
| Amortised cost | The average per-operation cost when an occasional expensive operation is spread across many cheap ones. |

## Diagrams & Visual Descriptions

**Separate chaining** — each bucket points to a linked list of colliding entries:

```
Index      Bucket (linked list)
 0    →   (empty)
 1    →   [K7] → [K12] → null      ← collision chain
 2    →   [K3] → null
 3    →   (empty)
```

**Linear probing vs. quadratic probing** — how collisions walk through the table:

```
Linear probing (step of 1):           Quadratic probing (offsets 1², 2², ...):

slot:  4   5   6   7   8              slot:  4   5   6   7   8
      [X][X][X][X][ ]                     [X][ ][ ][ ][X]
        ← cluster forms; any key          hash→4, try +1²=5, +2²=8
        hitting 4–7 probes all of it      (jumps over cluster)
```

**Rehashing / resize flow:**

```
insert → load factor ≥ threshold? ──no──→ place in bucket
                │yes
                ▼
        allocate table (double size)
                ▼
        rehash every key into new table
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

**Load factor:**

$$\alpha = \frac{\text{number of stored entries}}{\text{number of buckets}}$$

**Complexity summary:**

- Average-case lookup: $O(1)$ (depends on hash function quality)
- Worst-case lookup: $O(n)$ (bad hash function → all keys in one bucket)
- Rehashing: $O(n)$ per resize, but amortised $O(1)$ per insertion

**Quadratic probing sequence:** probe offsets $1^2, 2^2, 3^2, \dots$ from the home slot.

## Key Takeaways

- O(1) hash table lookup is an *average-case* claim about the hash function, not a guarantee — a bad hash function collapses the table to O(n).
- The load factor is the performance dial: as it approaches 1, collisions dominate and lookups slow.
- Separate chaining is simple and robust but pays chain-walking costs; open addressing keeps everything in one array.
- Linear probing's primary clustering is a feedback loop: runs grow, which causes more collisions, which grows runs further.
- Quadratic probing's square offsets break up clusters by spreading entries across the table.
- Resizing (doubling) plus rehashing costs O(n) once, but amortised across the insertions that triggered it, insertion stays O(1).

## Connections

Within this lecture, the analysis of hash tables leans on two ideas that recur across data-structures study: probabilistic performance (the O(1) bound depends on an assumption about hash behaviour, echoing how average-case analysis rests on distributional assumptions) and amortised analysis (justifying dynamic resizing by spreading the O(n) rebuild across insertions). Both are techniques you will reuse whenever evaluating adaptive data structures.

The lecture notes that hash tables provide average O(1) lookup, positioning them as the go-to structure whenever fast key-based access is needed — a claim worth testing against alternatives like tree-based maps, which offer worst-case guarantees instead.

---

*Sources: CSIT302 Week 5 lecture notes (Hash Tables). Version: 1.*
