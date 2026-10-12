# CSIT201 — Week 9: Dynamic Programming — 0/1 Knapsack

## Overview

Dynamic programming (DP) is a technique for solving optimization problems that would otherwise require checking an exponential number of possibilities. The core idea is to break a problem into overlapping subproblems, solve each once, and record the answers in a table. Week 9 applies this to one of the most famous optimization problems in computer science: the **0/1 Knapsack problem**.

The problem is easy to state. You have `n` items, each with a weight `w_i` and a value `v_i`, and a knapsack with capacity `W`. You must choose a subset of items whose total weight is at most `W`, while maximizing total value. The "0/1" means each item is taken whole or not at all — you cannot take a fraction. This matters in practice: it's like packing a shipping container where you can't cut a machine in half, or choosing which projects to fund with a fixed budget.

Trying every subset is O(2^n), which is hopeless for even moderate `n`. The DP approach turns this into a table-filling exercise running in O(nW) — dramatically better in practice, though with a subtle caveat about its complexity class that we'll examine.

## Key Concepts

### Problem Statement

Given `n` items with weights `w_i` and values `v_i`, and capacity `W`, find the subset with total weight ≤ W and maximum total value. Each item contributes fully (take it, weight `w_i`, value `v_i`) or not at all (weight 0, value 0) — hence "0/1". This distinguishes it from the *fractional* knapsack, where items could be split; the lecture focuses only on the 0/1 case.

Real-world intuition: a delivery truck of fixed capacity, a hiker with a weight limit, a project portfolio with a budget constraint. In each case, greedy "pick the best-looking thing next" can fail — sometimes skipping a high-value item makes room for a better combination. This is exactly why we need DP rather than a simple greedy strategy.

### The DP State: `best[i][c]`

The crucial design step is choosing what a table cell means. Define:

> **`best[i][c]`** = the maximum achievable value using only the **first `i` items** with a knapsack of capacity `c`.

Two things make this a good state. First, it captures everything we need to know: which items are available and how much room remains. Second, larger states can be built from smaller ones — if we know the answers for `i-1` items, we can compute the answer for `i` items. The first row of the table encodes the **base case**: `best[0][c] = 0` for all `c`, because with zero items the best value is zero no matter how much capacity you have.

### The Recurrence

When deciding about item `i` with capacity `c` available, there are exactly two options:

1. **Skip item i.** The answer is whatever was possible with the first `i-1` items and the same capacity: `best[i-1][c]`.
2. **Take item i.** This is only allowed if the item fits (`w_i ≤ c`). It consumes `w_i` capacity and earns `v_i`, leaving capacity `c - w_i` for the first `i-1` items: `best[i-1][c - w_i] + v_i`.

Formally:

- If `w_i > c` (item doesn't fit): `best[i][c] = best[i-1][c]`
- Otherwise: `best[i][c] = max(best[i-1][c], best[i-1][c - w_i] + v_i)`

The `max` is what makes this an optimization problem — we compare "skip" against "take" and keep whichever yields more value. Every cell depends only on cells in the row above, which is why we can fill the table row by row.

### Worked Example

Consider W = 5 with three items:

| Item | Weight | Value |
|------|--------|-------|
| 1 | 2 | 3 |
| 2 | 3 | 4 |
| 3 | 4 | 5 |

The optimal choice is items 1 and 2: total weight 5 (exactly fits), total value **7**. Notice item 3 alone has value 5, and item 3 plus item 1 doesn't fit (weight 6). The greedy intuition of "take the most valuable item" would pick item 3 and end up worse — the DP systematically considers all combinations through the table.

### Complexity and Pseudo-Polynomial Time

The table has `n × W` entries, each computed in constant time (one comparison, one addition, one max), so **time and space are both O(nW)**.

The lecture highlights an important subtlety: this is **pseudo-polynomial**, not truly polynomial. Why? The input size isn't `n` and `W` as raw numbers — it's the number of *bits* needed to write them down. Writing `W` takes only log(W) bits, so an algorithm proportional to the *value* of W is exponential in W's input length. Doubling the number of items roughly doubles the work (good); doubling the numeric value of W also doubles the work (potentially bad — W could be a huge number). This distinction matters for understanding what "efficient" means for knapsack-style problems.

## Definitions

| Term | Definition |
|------|------------|
| 0/1 Knapsack problem | Choose a subset of n items (weight w_i, value v_i) with total weight ≤ W maximizing total value; each item is taken whole or not at all. |
| Capacity (W) | The maximum total weight the knapsack can hold. |
| DP state (`best[i][c]`) | The maximum value achievable using the first i items with capacity c. |
| Base case | `best[0][c] = 0` for all c — with no items, best value is zero. |
| Recurrence | The rule computing `best[i][c]` from smaller states: take the max of skipping item i or taking it. |
| Pseudo-polynomial time | Runtime polynomial in the numeric value of inputs (like W), not in the number of bits used to represent them. |

## Diagrams & Visual Descriptions

**Dependency structure of the DP table** — each cell depends on the cell directly above (skip) and the cell above, shifted left by w_i (take):

```
Capacity c →   0   1   2   3   4   5
             ┌───┬───┬───┬───┬───┬───┐
  i = 0      │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │   base case: no items
             ├───┼───┼───┼───┼───┼───┤
  i = 1      │ 0 │ 0 │ 3 │ 3 │ 3 │ 3 │   item (w=2, v=3)
             ├───┼───┼───┼───┼───┼───┤
  i = 2      │ 0 │ 0 │ 3 │ 4 │ 4 │ 7 │   item (w=3, v=4)
             ├───┼───┼───┼───┼───┼───┤
  i = 3      │ 0 │ 0 │ 3 │ 4 │ 5 │ 7 │   item (w=4, v=5) → answer: 7
             └───┴───┴───┴───┴───┴───┘

  best[i][c]  ←── best[i-1][c]        (skip item i)
              ←── best[i-1][c - w_i]  (take item i, if w_i ≤ c)
```

Reading the final cell `best[3][5] = 7` recovers the optimal value for the worked example.

## Code Examples

No code examples in this lecture. (The recurrence is given pseudocode-style; it translates directly to a nested loop filling the table row by row.)

## Formulas & Algorithms

**Recurrence:**

$$
best[i][c] = \begin{cases} best[i-1][c] & \text{if } w_i > c \\ \max\big(best[i-1][c],\; best[i-1][c - w_i] + v_i\big) & \text{otherwise} \end{cases}
$$

**Base case:** $best[0][c] = 0$ for all $c$.

**Complexity:** Time O(nW), space O(nW), with n·W constant-time cell computations. Pseudo-polynomial in the input size.

## Key Takeaways

- The 0/1 constraint (whole item or nothing) is what makes knapsack hard — it rules out simple fractional/greedy solutions.
- A good DP state (`best[i][c]`) encodes exactly what's needed: items considered so far and remaining capacity.
- Every decision is binary: skip or take; the recurrence takes the max of the two outcomes.
- Filling an n × W table gives both time and space O(nW) — vastly better than brute-force 2^n subset enumeration.
- O(nW) is **pseudo-polynomial**: it's polynomial in the *value* of W, but exponential in the number of bits used to write W down.

## Connections

This lecture presents dynamic programming as a general technique (the state-table-recurrence pattern) applied to the knapsack problem; the pattern itself — overlapping subproblems and optimal substructure — is the transferable skill here. The lecture notes the algorithm's complexity is pseudo-polynomial, which frames knapsack as a problem whose difficulty relates to the numeric magnitude of its inputs, a theme in complexity analysis.

The lecture does not explicitly reference other weeks of the course.

---
*Sources: CSIT201 Week 9 lecture notes (Dynamic Programming: 0/1 Knapsack). Version: 1.*
