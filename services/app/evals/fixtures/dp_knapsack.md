# CSIT201 — Week 9: Dynamic Programming: Knapsack

## Overview

0/1 knapsack is solved by tabulating the best value for every prefix of items and every capacity. The lecture turns that idea into a recurrence and a cost analysis.

## Key Concepts

### The problem

Given n items with weight w_i and value v_i and a capacity W, choose a subset with total weight at most W and maximum total value. Each item is taken whole or not at all.

### The table

best[i][c] is the maximum value using the first i items with capacity c. The base case is best[0][c] = 0 for all c. If w_i > c the item does not fit; otherwise the two options are to skip item i or to take it and spend w_i of the capacity.

### Worked example and cost

With W = 5 and items (w=2, v=3), (w=3, v=4), (w=4, v=5) the best choice is the first two items: weight 5, value 7. The table has n * W entries filled in constant time each, so time and space are O(nW). This is pseudo-polynomial because W is a number, not a count of input items.

## Definitions

| Term | Definition |
|---|---|
| 0/1 knapsack | Choose whole items under a weight capacity to maximise value |
| Recurrence | Rule defining each table entry from earlier ones |
| Pseudo-polynomial | Polynomial in the numeric value of W rather than the input size |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

```
best[0][c] = 0
best[i][c] = best[i-1][c]                                   if w_i > c
best[i][c] = max(best[i-1][c], best[i-1][c - w_i] + v_i)    otherwise
time, space: O(nW)
```

## Key Takeaways

- Each entry chooses between skipping and taking item i.
- Cost is O(nW), pseudo-polynomial.
- The table fills from the base case upward.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: dp_knapsack.pdf. Version: 1.*
