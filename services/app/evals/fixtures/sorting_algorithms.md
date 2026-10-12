# CSIT101 — Week 5: Sorting

## Overview

Sorting is one of the foundational problems in computer science: given a collection of items, arrange them in order according to some key. It matters both because sorted data is easier to search and process, and because sorting is a showcase for algorithm analysis — different sorting algorithms can solve the same problem with wildly different performance characteristics.

This lecture compares three classic comparison-based sorts — insertion sort, merge sort, and quicksort — through the lens of time complexity, space usage, and stability. It closes with a fundamental result: no comparison-based sort can beat $O(n \log n)$ in the worst case, which tells us merge sort is asymptotically optimal.

## Key Concepts

### Stability: Why Equal Keys Matter

A sort is **stable** if elements with equal keys keep their original relative order after sorting. This may sound minor, but consider a real workflow: you sort a list of employees by name, then sort again by department. If the second sort is stable, employees within each department remain alphabetically sorted by name. If it is not stable, that earlier ordering is scrambled. Stability is what makes **multi-pass sorting** — sorting by one field after another — work correctly.

### Insertion Sort

Insertion sort builds a **sorted prefix** one element at a time. It takes the next unsorted element and shifts all larger elements in the sorted portion one position to the right, then inserts the new element in its correct spot — much like sorting playing cards in your hand.

Its performance depends heavily on the input:
- **Worst case: O(n²)** — a reverse-sorted input forces every element to be shifted past the entire sorted prefix.
- **Best case: O(n)** — an already-sorted input requires only one comparison per element, with no shifts.
- **Space: O(1)** — it sorts in place with only constant extra memory.
- **Stable: yes** — equal elements are never jumped over, only larger ones are shifted.

Because of its low overhead, insertion sort is fast on **small or nearly sorted inputs**, even though it loses badly to divide-and-conquer sorts on large, random data.

### Merge Sort

Merge sort is a **divide-and-conquer** algorithm: split the array in half, recursively sort each half, then **merge** the two sorted halves by repeatedly taking the smaller front element from each.

Its great strength is predictability: it runs in **O(n log n) in all cases** — best, average, and worst. The trade-off is that merging requires **O(n) extra space** for the temporary output array. It is **stable**, since during a merge ties can be broken in favor of the left half, preserving original order.

### Quicksort

Quicksort also divides the problem, but differently: it picks a **pivot**, **partitions** the array into elements smaller than and larger than the pivot, then recursively sorts each side. Unlike merge sort, all the real work happens during partitioning, and merging is trivial (the halves are already in place).

Its performance profile is the mirror image of merge sort's:
- **Average case: O(n log n)** — typically faster in practice due to in-place partitioning.
- **Worst case: O(n²)** — occurs when the pivot is repeatedly the smallest or largest element. A classic trigger: a **sorted array combined with a first-element pivot**, so each partition is maximally unbalanced.
- **Space: in place** — no auxiliary array needed.
- **Stable: no** — partitioning swaps elements across long distances, destroying relative order.

The practical fix for the worst case is **random pivot selection**, which makes a consistently bad pivot choice extremely unlikely.

### Comparison Sorts: The Lower Bound

Any sort that decides order **only by comparing elements** needs on the order of **$n \log n$ comparisons in the worst case**. This is a lower bound, not an upper one — no cleverer comparison sort can do asymptotically better. The consequence: **merge sort is asymptotically optimal among comparison sorts**. (Note the wording "comparison sorts" — the bound says nothing about sorts that exploit structure of keys, which is beyond this lecture's scope.)

### Side-by-Side Comparison

| Property | Insertion Sort | Merge Sort | Quicksort |
|---|---|---|---|
| Best case | O(n) | O(n log n) | O(n log n) |
| Average case | O(n²) | O(n log n) | O(n log n) |
| Worst case | O(n²) | O(n log n) | O(n²) |
| Extra space | O(1) | O(n) | In place |
| Stable | Yes | Yes | No |

## Definitions

| Term | Definition |
|---|---|
| Sort | Rearranging a collection of items into order according to a key |
| Stable sort | A sort in which equal keys keep their original relative order |
| Sorted prefix | The portion of the array, growing from the left, that insertion sort keeps ordered |
| Pivot | The element quicksort uses to partition the array into smaller and larger groups |
| Partition | The step of splitting the array relative to the pivot |
| Merge | The step of combining two sorted halves into one sorted array |
| In place | Uses only constant extra memory beyond the input |
| Comparison sort | A sort that determines order only by comparing pairs of elements |
| Worst case | The input producing the maximum running time (e.g., reverse-sorted for insertion sort) |

## Diagrams & Visual Descriptions

**Insertion sort — growing a sorted prefix:**

```
[ 4 | 2 8 1 ]        [ 2 4 | 8 1 ]        [ 2 4 8 | 1 ]        [ 1 2 4 8 ]
  sorted ↑                sorted ↑              sorted ↑             fully sorted
```
Each step: take the first element after the `|`, shift larger sorted elements right, insert it.

**Merge sort — divide and merge:**

```
        [4 2 8 1]
        /        \
    [4 2]        [8 1]        split
    /   \        /   \
  [4]   [2]    [8]   [1]
    \   /        \   /
    [2 4]        [1 8]        merge pairs
        \        /
        [1 2 4 8]              final merge
```

**Quicksort — partition around a pivot:**

```
[5 3 8 1 9 2]  pivot = 5
      ↓ partition
[3 1 2]  5  [8 9]      → recurse on both sides
 smaller  pivot  larger
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

- Insertion sort: worst case $O(n^2)$, best case $O(n)$, space $O(1)$.
- Merge sort: $O(n \log n)$ always, space $O(n)$.
- Quicksort: average $O(n \log n)$, worst $O(n^2)$; in place.
- Comparison lower bound: any comparison sort needs $\Omega(n \log n)$ comparisons in the worst case.

## Key Takeaways

- Stability isn't academic pedantry — it's what enables correct multi-pass sorting by different fields.
- No single algorithm wins everywhere: merge sort is predictable, quicksort is usually fastest in place, insertion sort shines on small or nearly sorted inputs.
- Quicksort's worst case is input-dependent (e.g., sorted array + first-element pivot); random pivots make it unlikely.
- $O(n \log n)$ is a hard floor for comparison sorts, so merge sort is asymptotically optimal.
- Space matters too: merge sort's speed costs O(n) extra memory; quicksort and insertion sort sort in place.

## Connections

The lecture's stability discussion connects directly to multi-field sorting scenarios it describes — sorting by one field after another — a pattern you'll encounter whenever sorted data supports further processing. The lower-bound argument, showing merge sort is optimal among comparison sorts, implicitly points beyond comparison-based techniques, which the lecture does not name.

Within this lecture, the three algorithms form a natural comparative framework (time, space, stability) that the rest of an algorithms course typically builds on for analyzing other algorithms the same way.

---
*Sources: CSIT101 Week 5 lecture notes (Sorting). Version: 1.*
