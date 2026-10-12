# CSIT302 — Week 5: Hash Tables

## Overview

A hash table maps a key to an index using a hash function, giving average case O(1) lookup [p.1]. This makes hash tables one of the fastest data structures for lookup-heavy workloads, but that speed comes with an important caveat: the worst case is O(n). With a bad hash function, every key lands in the same bucket and the table degrades to a linear scan — no better than searching an unsorted list [p.1].

The lecture makes a subtle but crucial point: the average case is a claim about the hash function, not about the data structure [p.1]. In other words, the O(1) guarantee depends on the hash function spreading keys evenly across buckets. This is why the rest of the lecture is devoted to managing collisions and controlling the *load factor* — the ratio of stored entries to buckets, which degrades performance as it approaches 1 [p.1].

## Key Concepts

### The Hash Table Model

A hash table works by applying a hash function to a key to produce an index into an array of buckets, so lookup avoids scanning the whole structure [p.1]. The central tension is between the ideal O(1) average case and the O(n) worst case that occurs when the hash function is poor and all keys collide into one bucket [p.1]. Because the average case depends entirely on hash quality, good hash table design is largely about (a) keeping the load factor low and (b) handling collisions gracefully.

### Load Factor

The load factor is the ratio of stored entries to buckets [p.1]. As it approaches 1, the table becomes crowded, collisions increase, and performance degrades [p.1]. Monitoring the load factor is what tells us *when* to intervene — either by resizing the table or by choosing a collision strategy that tolerates a fuller table.

### Collision Resolution Strategies

#### Separate Chaining

Separate chaining stores a linked list at each bucket; collisions simply append to the list [p.2]. Lookup cost is proportional to the length of the chain, so it stays acceptable while the load factor is low [p.2]. This makes chaining conceptually simple: the table absorbs collisions by growing lists rather than rearranging entries.

#### Open Addressing and Linear Probing

Open addressing takes the opposite approach: everything is stored in the table itself, with no auxiliary lists [p.2]. On a collision, linear probing checks the next bucket, and the next, until a free one is found [p.2]. The problem is *primary clustering*: occupied runs grow, and growing runs make further collisions more likely — a feedback loop that degrades performance [p.2].

#### Quadratic Probing

Quadratic probing checks buckets at increasing square offsets instead of stepping one bucket at a time [p.3]. Because entries are spread out rather than packed into contiguous runs, it avoids primary clustering [p.3].

The three strategies compare as follows:

| Strategy | Where entries live | Collision handling | Key drawback [p.2][p.3] |
|---|---|---|---|
| Separate chaining | Linked list per bucket | Append to list; lookup cost = chain length [p.2] | Acceptable only while load factor is low [p.2] |
| Open addressing (linear probing) | The table itself | Check next bucket, then next, until free [p.2] | Primary clustering [p.2] |
| Quadratic probing | The table itself | Check buckets at increasing square offsets [p.3] | Avoids primary clustering [p.3] |

### Resizing and Rehashing

When the load factor crosses a threshold the table is resized, usually doubled, and every key is rehashed into the new table [p.3]. A single rehash costs O(n), which sounds expensive — but amortised across the insertions that caused it, the cost per insertion stays constant [p.3]. This amortised analysis is why hash tables can guarantee O(1) insertion on average even though occasional operations are slow: the expensive event happens rarely relative to the number of cheap ones.

## Definitions

| Term | Definition |
|---|---|
| Hash table | Maps a key to an index using a hash function, giving average case O(1) lookup [p.1] |
| Worst case O(n) | With a bad hash function every key lands in the same bucket and the table degrades to a linear scan [p.1] |
| Load factor | The ratio of stored entries to buckets; performance degrades as it approaches 1 [p.1] |
| Separate chaining | Stores a linked list at each bucket; collisions append to the list [p.2] |
| Open addressing | Stores everything in the table itself, resolving collisions by probing [p.2] |
| Linear probing | On a collision, checks the next bucket, and the next, until a free one is found [p.2] |
| Primary clustering | Occupied runs grow and make further collisions more likely [p.2] |
| Quadratic probing | Checks buckets at increasing square offsets, spreading entries out and avoiding primary clustering [p.3] |
| Rehashing | When the load factor crosses a threshold, the table is resized (usually doubled) and every key is rehashed into the new table [p.3] |

## Diagrams & Visual Descriptions

Linear probing's primary clustering, where a growing run of occupied slots keeps attracting new keys [p.2]:

```
Buckets:   [A][B][C][D][ ][ ][ ]
            ^--^--^--^
            occupied run — a new key hashing
            to A, B, C or D all probe past the
            same run, making collisions more likely [p.2]
```

Quadratic probing instead jumps at increasing square offsets (0, 1, 4, 9, ...), scattering entries so runs never form [p.3]:

```
Probe i:    0    1    2    3
Offset:     0    1    4    9     (increasing squares) [p.3]
Table:      [K][ ][ ][X][ ][ ][ ][ ][ ][K] ... [p.3]
```

Rehashing on threshold crossing [p.3]:

```
Load factor crosses threshold
        |
        v
Resize table (usually doubled)
        |
        v
Rehash every key into new table  -- O(n) total,
amortised to O(1) per insertion [p.3]
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Complexities and bounds:

```
Hash table lookup: average case O(1) [p.1]
Hash table lookup: worst case O(n) (all keys in one bucket -> linear scan) [p.1]
Separate chaining lookup: proportional to chain length [p.2]
Rehashing: O(n), amortised to constant cost per insertion [p.3]
```

Load factor:

```
load factor = stored entries / buckets
performance degrades as load factor -> 1 [p.1]
```

Resize policy:

```
if load factor crosses threshold:
    resize table (usually doubled)
    rehash every key into the new table [p.3]
```

Quadratic probing offsets:

```
probe sequence: increasing square offsets (0, 1, 4, 9, ...)
avoids primary clustering [p.3]
```

## Key Takeaways

- Hash tables deliver O(1) average lookup only because of the hash function — the average case is a claim about the hash function, not about the data structure itself [p.1].
- A bad hash function collapses the table to a linear scan with O(n) worst-case behaviour, so hash quality is not optional [p.1].
- Watch the load factor: as it approaches 1, performance degrades regardless of collision strategy [p.1].
- Separate chaining and open addressing embody two philosophies — grow lists vs. probe within the table — each with its own failure mode (chain length vs. primary clustering) [p.2].
- Linear probing's primary clustering is self-reinforcing; quadratic probing breaks the runs by using square offsets [p.2][p.3].
- Rehashing looks expensive at O(n), but amortised across the insertions that triggered it, each insertion costs a constant amount — the key insight behind practical hash table design [p.3].

## Connections

This week's emphasis on comparing data-structure strategies by their average and worst-case costs, and on amortised analysis for resizing, gives a framework that recurs throughout data-structure study in this course: a structure is only as good as the assumptions (here, hash quality) behind its performance claims [p.1][p.3]. The lecture also leaves open what makes a hash function "good" — the guarantee rests entirely on keys spreading evenly across buckets, a condition the lecture identifies but does not itself design for [p.1].

---
*Sources: CSIT302 Week 5 lecture slides (pp. 1–3). Version: 1.*
