# CSIT201 — Week 9: Dynamic Programming and the 0/1 Knapsack Problem

## Overview

The 0/1 knapsack problem is a classic optimisation problem: given n items, each with a weight w_i and a value v_i, and a knapsack with capacity W, we must choose a subset of items whose total weight is at most W while maximising the total value. The "0/1" refers to the restriction that each item must be taken whole or not at all — you cannot take a fraction of an item [p.1].

This problem is the vehicle for this week's introduction to dynamic programming, a technique that solves problems by breaking them into overlapping subproblems and reusing their answers in a table. Rather than trying every subset (an enormous number), dynamic programming fills a table `best[i][c]` that records, for each item index and remaining capacity, the best value achievable — and each entry is computed once from smaller subproblems [p.1][p.2]. By the end of the lecture you will know the recurrence, how to fill the table, a fully worked example, and the complexity analysis — including the important subtlety that the O(nW) running time is pseudo-polynomial [p.3].

## Key Concepts

### The Problem

Picture a courier with a delivery van of fixed load capacity, and a set of packages each weighing some amount and earning some fee. The courier wants the most valuable load the van can legally carry. Formally, given n items with weight w_i and value v_i and a capacity W, we choose a subset with total weight at most W and maximum total value; each item is taken whole or not at all, hence 0/1 [p.1].

The "whole or not at all" restriction is what makes this interesting. If fractions were allowed, a simple strategy (taking the most value-dense items first) would suffice — but that greedy idea is not part of this lecture's solution. Here, every item is an all-or-nothing decision, and the difficulty is that taking a heavy, valuable item may consume capacity needed by two cheaper items that together are worth more [p.1].

### The Dynamic Programming Table

The key idea is to define a table whose entries answer progressively larger versions of the question: let `best[i][c]` be the maximum value using the first i items with capacity c [p.1]. Rather than asking "what is the best subset of all n items?", we ask "what is the best value achievable using only the first i items and a budget of c?" — and answer it for every i from 0 up to n and every c from 0 up to W.

This works because each subproblem's answer depends only on smaller ones. The final answer to the original problem is `best[n][W]`: the best value using all items with the full capacity available.

### The Recurrence: Skip or Take

How do we fill an entry? For item i with capacity c, there are exactly two options: skip item i, or take it and spend w_i of the capacity [p.2]. If we skip it, we keep the best answer without item i, which is `best[i-1][c]`. If we take it, we gain v_i but lose w_i units of capacity, so the remaining problem is the best value using the first i−1 items with capacity reduced to c − w_i.

The recurrence is [p.2]:

```
best[i][c] = best[i-1][c] if w_i > c
best[i][c] = max(best[i-1][c], best[i-1][c - w_i] + v_i) otherwise
```

The first case handles an item that simply cannot fit: if the item's weight w_i exceeds the capacity c, there is no choice — the answer is the same as without it, `best[i][c] = best[i-1][c]` [p.2]. The second case, when the item does fit, takes the maximum of the two options: skip it (`best[i-1][c]`) or take it and spend w_i of the capacity (`best[i-1][c - w_i] + v_i`) [p.2].

Every row i depends only on row i−1, so we can fill the table row by row, and each entry is filled in constant time given the previous row.

### Base Case

Before filling the table we need somewhere to start: the base case is `best[0][c] = 0` for all c [p.2]. With zero items available, the best value you can get is 0, no matter how much capacity you have. This grounds the recursion — every entry ultimately traces back to row 0.

### Worked Example

The lecture works through a concrete instance to make the mechanics tangible. The setup: capacity W = 5, with items (w=2, v=3), (w=3, v=4), (w=4, v=5) [p.3].

Let's reason it through as the table would:

- Taking only the first two items gives total weight 2 + 3 = 5, which fits exactly in capacity 5, with total value 3 + 4 = 7 [p.3].
- Any pair involving the third item: item 3 alone weighs 4, leaving only 1 unit of capacity — neither of the other items (weights 2 and 3) fits alongside it. So item 3 can only pair with items that don't fit with it.
- All three items together weigh 2 + 3 + 4 = 9 > 5, so that's not allowed.

The conclusion: the best is the first two items: weight 5, value 7 [p.3]. Notice this vindicates the table approach — item 3 has the highest individual value, but the table correctly discovers that skipping it yields a better total.

### Complexity: Time, Space, and Pseudo-Polynomial Time

The table has n × W entries, and each is filled in constant time (just a comparison and possibly one addition), so time and space are O(nW) [p.3].

There is a crucial subtlety here. O(nW) looks polynomial, but W is a number, not a count of input items — the number of bits needed to represent W in the input grows only logarithmically with W. This is why the algorithm is called pseudo-polynomial: it is polynomial in the numeric value of W, not in the length of the input encoding [p.3]. This distinction matters for how we classify the knapsack problem's difficulty, and it is exactly the kind of nuance an exam question might probe.

## Definitions

| Term | Definition |
|---|---|
| 0/1 knapsack problem | Choose a subset of n items (weights w_i, values v_i) with total weight at most capacity W and maximum total value; each item is taken whole or not at all [p.1]. |
| Capacity W | The maximum total weight the knapsack can hold [p.1]. |
| best[i][c] | The maximum value using the first i items with capacity c [p.1]. |
| Dynamic programming | Solving the problem by filling a table of subproblem answers (the best table), each computed once from smaller subproblems [p.1][p.2]. |
| Recurrence | The rule defining best[i][c] in terms of smaller subproblems: skip item i, or take it and spend w_i of the capacity [p.2]. |
| Base case | best[0][c] = 0 for all c: with zero items, best value is 0 [p.2]. |
| Pseudo-polynomial | Describes the O(nW) complexity: polynomial in the number W, which is a value rather than a count of input items [p.3]. |

## Diagrams & Visual Descriptions

The dependency structure of the table — each row built from the previous row:

```
capacity c:   0    1    2   ...   W
           +----+----+----+---+----+
row 0      |  0 |  0 |  0 |...|  0 |      best[0][c] = 0 for all c
           +----+----+----+---+----+
row 1      |    |    | ?  |...|    |      each entry uses row 0 only
           +----+----+----+---+----+
row 2      |    |    |    |...|    |      each entry uses row 1 only
           +----+----+----+---+----+
 ...
row n      |    |    |    |...|ANS |      best[n][W] = final answer
           +----+----+----+---+----+
```

Each cell best[i][c] either copies best[i-1][c] (skip) or reads best[i-1][c - w_i] from the row above and adds v_i (take) [p.1][p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The recurrence, with both cases, is [p.2]:

```
best[i][c] = best[i-1][c]                                if w_i > c
best[i][c] = max(best[i-1][c], best[i-1][c - w_i] + v_i) otherwise
```

Base case [p.2]:

```
best[0][c] = 0 for all c
```

Worked example [p.3]:

```
W = 5
items: (w=2, v=3), (w=3, v=4), (w=4, v=5)
Best is the first two items: weight 5, value 7
```

Complexity and properties [p.3]:

```
Time:  O(nW)  (n * W entries, each filled in constant time)
Space: O(nW)
Pseudo-polynomial: W is a number, not a count of input items
```

Problem statement [p.1]:

```
Given n items with weight w_i and value v_i and capacity W,
choose a subset with total weight at most W and maximum total value.
Each item is taken whole or not at all, hence 0/1.
```

## Key Takeaways

- The 0/1 knapsack problem asks for the maximum-value subset of items within capacity W, with each item taken whole or not at all — the all-or-nothing rule is what makes it nontrivial [p.1].
- Dynamic programming turns the problem into a table: `best[i][c]` is the max value using the first i items with capacity c, and the final answer is built row by row from smaller subproblems [p.1].
- Every entry embodies a simple decision — skip item i, or take it and spend w_i of the capacity — captured by the two-branch recurrence [p.2].
- The base case `best[0][c] = 0` grounds everything: no items means no value [p.2].
- The worked example shows that the highest-value item isn't always in the optimal answer: with W = 5, the best choice is the first two items, value 7, skipping item 3 [p.3].
- The O(nW) time and space is pseudo-polynomial because W is a numeric value, not an input count — a key theoretical distinction, not just a detail [p.3].

## Connections

The lecture frames the 0/1 knapsack as this week's introduction to dynamic programming, a technique of building a table of subproblem answers via a recurrence and base case [p.1][p.2]. That same table-plus-recurrence pattern is the core skill this material develops; the lecture itself notes the pseudo-polynomial nature of the O(nW) bound, flagging how input encoding affects complexity analysis [p.3].

This lecture does not link to other named weeks, and no other weeks were available to compare against.

---
*Sources: CSIT201 Week 9 lecture slides (pages 1–3), "Dynamic Programming: 0/1 Knapsack." Version: 1.*
