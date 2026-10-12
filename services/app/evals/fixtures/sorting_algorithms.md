# CSIT101 — Week 5: Sorting

## Overview

Sorting — rearranging a sequence of elements into order — is one of the foundational problems of computer science, and this lecture surveys three classic algorithms: insertion sort, merge sort, and quicksort [p.1][p.2][p.3][p.4]. Each takes a different strategy: one grows a sorted region one element at a time, one divides the problem in half and combines solutions, and one partitions around a chosen pivot [p.2][p.3][p.4]. The lecture also introduces a subtle property called stability, which determines whether equal elements preserve their original order — crucial when you sort records by one field and then by another [p.1].

Beyond how each algorithm works, the lecture develops a comparative analysis: running times (best, average, and worst case), extra memory needs, and whether the sort is stable or in place [p.2][p.3][p.4]. It closes with a powerful theoretical result: any comparison-based sort requires on the order of n log n comparisons in the worst case, which makes merge sort asymptotically optimal among comparison sorts [p.5].

## Key Concepts

### Stability: Why Order Among Equals Matters

A sort is **stable** if equal keys keep their original relative order [p.1]. This may sound like a minor detail, but the lecture explains why it matters: stability matters when sorting by one field after another [p.1]. Imagine sorting a list of students first by name, then by grade. If the sort is stable, students with the same grade still appear alphabetically within each grade group; an unstable sort would scramble that earlier ordering [p.1]. Throughout the lecture, each algorithm's stability (or lack of it) is treated as a first-class property, on par with its running time [p.2][p.3][p.4].

### Insertion Sort: Growing a Sorted Prefix

#### How It Works

Insertion sort grows a sorted prefix: it takes the next element and shifts larger ones right to insert it [p.2]. Conceptually, the array is divided into a sorted portion at the front and an unsorted remainder; each step, the next unsorted element is "inserted" into its correct place in the prefix by shifting bigger elements one slot to the right [p.2]. This mirrors how many people sort a hand of playing cards [p.2].

#### Performance and Properties

The running time depends heavily on the input:

- Worst case is O(n^2), which occurs on reverse-sorted input — every new element must be shifted past the entire sorted prefix [p.2].
- Best case is O(n), on already sorted input — each element needs only a single check before staying put [p.2].
- It uses O(1) extra space, sorting in place with no auxiliary array [p.2].
- It is stable, so equal keys keep their original order [p.2].

The practical lesson from the lecture is that insertion sort is fast on small or nearly sorted inputs [p.2]. Even though its worst case looks bad, real data is often close to sorted, and in those situations its best-case linear behavior shines [p.2].

### Merge Sort: Divide, Sort, Combine

#### How It Works

Merge sort splits the array in half, sorts each half recursively, and merges the two sorted halves [p.3]. The merge step is the clever part: given two already-sorted halves, they can be combined into one fully sorted array efficiently [p.3]. Recursion keeps halving the problem until the pieces are trivial, and merging at each level stitches the results back together [p.3].

#### Performance and Properties

Merge sort's guarantees are remarkably strong: it is always O(n log n), regardless of the input's initial arrangement [p.3]. Unlike insertion sort, whose cost swings between O(n) and O(n^2), merge sort gives consistent, predictable performance [p.2][p.3]. The trade-off is memory: it needs O(n) extra space for the merge [p.3]. It is also stable [p.3].

### Quicksort: Partitioning Around a Pivot

#### How It Works

Quicksort picks a pivot, partitions the array into elements smaller and larger than the pivot, and recurses on both sides [p.4]. Rather than merging results afterward (as merge sort does), quicksort's work happens in the partitioning step, which places the pivot in its final position [p.4].

#### Performance, Pitfalls, and Pivot Choice

Quicksort's average case is O(n log n) — excellent in practice [p.4]. But its worst case is O(n^2), which happens when the pivot is repeatedly the smallest or largest element [p.4]. The lecture gives a concrete example: a sorted array with a first-element pivot triggers this worst case, because every partition is maximally lopsided [p.4]. Quicksort is in place (no O(n) auxiliary array) but not stable [p.4]. The remedy the lecture offers: choosing a random pivot makes the worst case unlikely [p.4].

### The Comparison-Sorting Lower Bound

The lecture closes with a fundamental limit: any sort that works only by comparing elements needs at least on the order of n log n comparisons in the worst case [p.5]. No clever comparison-based algorithm can beat this barrier [p.5]. The consequence is significant: since merge sort always achieves O(n log n), it is asymptotically optimal among comparison sorts [p.3][p.5].

### Comparing the Three Algorithms

| Algorithm | Best | Average | Worst | Extra space | Stable? |
|---|---|---|---|---|---|
| Insertion sort | O(n) (already sorted) | — | O(n^2) (reverse-sorted input) | O(1) | Yes [p.2] |
| Merge sort | — | — | Always O(n log n) | O(n) | Yes [p.3] |
| Quicksort | — | O(n log n) | O(n^2) (pivot repeatedly smallest/largest, e.g. sorted array + first-element pivot) | In place | No [p.4] |

## Definitions

| Term | Definition |
|---|---|
| Stable sort | A sort in which equal keys keep their original relative order [p.1] |
| Insertion sort | Sort that grows a sorted prefix: take the next element and shift larger ones right to insert it [p.2] |
| Merge sort | Sort that splits the array in half, sorts each half recursively, and merges the two sorted halves [p.3] |
| Quicksort | Sort that picks a pivot, partitions into smaller and larger elements, and recurses on both sides [p.4] |
| Pivot | The element quicksort picks; partitions the array into smaller and larger elements [p.4] |
| In place | Uses no significant extra memory beyond the input array (quicksort has this property; merge sort does not, needing O(n) extra space) [p.3][p.4] |
| Comparison sort | A sort that works only by comparing elements; needs at least on the order of n log n comparisons in the worst case [p.5] |
| Asymptotically optimal | Achieving the best possible growth rate for the problem class; merge sort is this among comparison sorts [p.5] |

## Diagrams & Visual Descriptions

Conceptual structure of merge sort (split, recurse, merge) [p.3]:

```
        [ 8 3 5 1 ]
        /         \
   [8 3]           [5 1]        split in half [p.3]
   /   \           /   \
 [8]   [3]       [5]   [1]      recurse [p.3]
   \   /           \   /
   [3 8]           [1 5]        sort each half [p.3]
        \         /
        [ 1 3 5 8 ]              merge the two sorted halves [p.3]
```

Quicksort partitioning around a pivot: elements smaller go left, larger go right, then recursion continues on both sides [p.4].

```
array -> [ < pivot ] [ pivot ] [ > pivot ]
              |                    |
          recurse              recurse          [p.4]
```

Insertion sort grows a sorted prefix left to right, shifting larger elements right to insert each new element [p.2]:

```
[ sorted prefix | unsorted ... ]
        ^--- next element is inserted here,
             larger prefix elements shift right [p.2]
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Complexities and properties of insertion sort [p.2]:

```
Worst case: O(n^2)  (reverse-sorted input)
Best case:  O(n)    (already sorted)
Extra space: O(1)
Stable: yes
```

Complexities and properties of merge sort [p.3]:

```
Time: always O(n log n)
Extra space: O(n) (for the merge)
Stable: yes
```

Complexities and properties of quicksort [p.4]:

```
Average case: O(n log n)
Worst case:   O(n^2)  (pivot repeatedly the smallest or largest,
                       e.g. sorted array with a first-element pivot)
In place: yes
Stable: no
Fix: choosing a random pivot makes the worst case unlikely
```

Comparison-sorting lower bound [p.5]:

```
Any comparison-based sort needs at least order of n log n
comparisons in the worst case
=> merge sort is asymptotically optimal among comparison sorts
```

## Key Takeaways

- Stability — equal keys keeping their original relative order — matters when sorting by one field after another, so it should factor into algorithm choice alongside speed [p.1].
- Insertion sort's simplicity hides a useful strength: despite an O(n^2) worst case, it is the fastest choice on small or nearly sorted inputs, running in O(n) best case with O(1) extra space [p.2].
- Merge sort trades O(n) extra memory for a guaranteed O(n log n) every time, making it the predictable, stable option [p.3].
- Quicksort averages O(n log n) in place, but a poor pivot strategy (like first-element pivot on sorted input) degrades it to O(n^2); randomizing the pivot makes the worst case unlikely [p.4].
- The order of n log n lower bound for comparison sorts means no comparison-based algorithm can do better asymptotically — merge sort already meets that bound [p.5].

## Connections

This lecture's analysis connects naturally to the broader theme of algorithm analysis: running times (O(n^2), O(n log n), O(n)) and space usage (O(1) vs O(n)) are the same cost measures used to evaluate any algorithm, here applied to sorting [p.2][p.3][p.4]. The lower-bound result also shows how theory informs practice — it explains why merge sort's O(n log n) is not just good but optimal among comparison sorts [p.5].

Within the lecture itself, the algorithms illuminate each other: insertion sort's best case on nearly sorted data contrasts with its O(n^2) worst case, while quicksort's random pivot strategy is a design lesson about avoiding predictable worst-case inputs, the very inputs that hurt it [p.2][p.4]. Stability separates the field: insertion sort and merge sort preserve the order of equal keys, while quicksort does not, which matters for multi-field sorting [p.1][p.2][p.3][p.4].

---
*Sources: CSIT101 Week 5 lecture slides (pages 1–5). Version: 1.*
