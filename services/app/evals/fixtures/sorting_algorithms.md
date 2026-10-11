# CSIT101 — Week 5: Sorting Algorithms

## Overview

The lecture compares three comparison sorts on time, space and stability, then states the lower bound that makes merge sort asymptotically optimal.

## Key Concepts

### Stability

A sort is stable if equal keys keep their original relative order, which matters when sorting by one field after another.

### Insertion sort

Insertion sort grows a sorted prefix, shifting larger elements right to insert the next one. Worst case O(n^2) on reverse-sorted input, best case O(n) when already sorted, O(1) extra space, stable. It is fast on small or nearly sorted inputs.

### Merge sort

Merge sort splits the array in half, sorts each half recursively and merges them. It is always O(n log n), needs O(n) extra space, and is stable.

### Quicksort

Quicksort picks a pivot, partitions into smaller and larger elements and recurses on both sides. Average O(n log n); worst case O(n^2) when the pivot is repeatedly the smallest or largest, as with a sorted array and a first-element pivot. It sorts in place and is not stable. A random pivot makes the worst case unlikely.

### A lower bound

Any sort that works only by comparing elements needs on the order of n log n comparisons in the worst case, so merge sort is asymptotically optimal among comparison sorts.

## Definitions

| Term | Definition |
|---|---|
| Stable sort | Equal keys keep their relative order |
| Pivot | Element quicksort partitions around |
| Partition | Split into smaller and larger than the pivot |
| Comparison sort | A sort that only compares elements |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

| Sort | Best | Worst | Extra space | Stable |
|---|---|---|---|---|
| Insertion | O(n) | O(n^2) | O(1) | Yes |
| Merge | O(n log n) | O(n log n) | O(n) | Yes |
| Quick | O(n log n) average | O(n^2) | in place | No |

## Key Takeaways

- Pick by stability, space and input shape.
- Quicksort's worst case is real; randomise the pivot.
- n log n is the comparison-sort floor.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: sorting_algorithms.pdf. Version: 1.*
