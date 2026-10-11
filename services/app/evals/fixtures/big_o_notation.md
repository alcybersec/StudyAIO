# CSIT101 — Week 2: Asymptotic Analysis

## Overview

The slides introduce Big-O as a way to compare algorithms by counting steps rather than measuring seconds.

## Key Concepts

### Counting steps

Analysis counts steps, not seconds. Big-O gives an upper bound and ignores constants and lower-order terms, so 3n^2 + 5n + 2 is O(n^2).

### Growth rates

From slowest growing to fastest: O(1), O(log n), O(n), O(n log n), O(n^2), O(2^n). O(2^n) is infeasible beyond small n.

### Reading code

Nested loops over n items do n * n steps, which is O(n^2). One loop that halves n on each pass is O(log n).

## Definitions

| Term | Definition |
|---|---|
| Big-O | An upper bound on growth that ignores constants and lower-order terms |
| Growth rate | How the step count increases with input size n |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

3n^2 + 5n + 2 = O(n^2). Nested loops: n * n = O(n^2). Halving loop: O(log n).

## Key Takeaways

- Count steps, not seconds.
- Drop constants and lower-order terms.
- O(2^n) is infeasible beyond small n.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: big_o_notation.pdf. Version: 1.*
