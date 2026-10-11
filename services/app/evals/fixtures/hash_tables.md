# CSIT302 — Week 5: Hash Tables and Collision Resolution

## Overview

Hash tables map keys to bucket indices with a hash function. The lecture's central warning is that the average-case O(1) lookup is a claim about the hash function, not about the data structure.

## Key Concepts

### Hashing and the load factor

A hash table maps a key to an index using a hash function, giving average case O(1) lookup. The worst case is O(n): with a bad hash function every key lands in the same bucket and the table degrades to a linear scan. The load factor is the ratio of stored entries to buckets, and performance degrades as it approaches 1.

### Resolving collisions

#### Separate chaining
Each bucket holds a linked list and collisions append to it, so lookup cost is proportional to chain length and stays acceptable while the load factor is low.

#### Open addressing
Everything is stored in the table itself. Linear probing checks the next bucket until a free one is found, which causes primary clustering: occupied runs grow and make further collisions more likely. Quadratic probing checks increasing square offsets, spreading entries out and avoiding primary clustering.

### Resizing
When the load factor crosses a threshold the table is usually doubled and every key is rehashed into the new table. Rehashing is O(n), but amortised over the insertions that caused it the cost per insertion stays constant.

## Definitions

| Term | Definition |
|---|---|
| Hash function | Maps a key to a bucket index |
| Load factor | Stored entries divided by buckets |
| Separate chaining | A linked list per bucket |
| Open addressing | Entries live in the table itself, found by probing |
| Primary clustering | Growing runs of occupied buckets under linear probing |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Average lookup: O(1). Worst case: O(n). Load factor = entries / buckets. Resize cost: O(n), constant when amortised per insertion.

## Key Takeaways

- Average O(1) depends on the hash function; the worst case is O(n).
- Keep the load factor low or resize and rehash.
- Quadratic probing avoids the primary clustering of linear probing.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: hash_tables.pdf. Version: 1.*
