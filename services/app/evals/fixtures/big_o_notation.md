# CSIT101 — Week 2: Asymptotic Analysis

## Overview

When we compare algorithms, we should not measure how long a program takes in seconds — that depends on the machine, the compiler and the workload. Instead, we count steps: the number of basic operations an algorithm performs as the input size n grows. Asymptotic analysis is the technique of describing that step count as a growth rate, so two algorithms can be compared fairly no matter what hardware they run on [p.1].

The central tool is Big-O notation, which gives an upper bound on growth. In Big-O we ignore constant factors and lower-order terms, because as n gets large only the fastest-growing term matters. This is why a function like 3n^2 + 5n + 2 is O(n^2) — the constants 3, 5 and 2, and the smaller terms, do not change the shape of the growth curve [p.1]. This week builds the vocabulary of growth rates you will use to classify every algorithm you meet.

## Key Concepts

### Counting Steps, Not Seconds

The first principle of the week is that we count steps, not seconds. Timing an algorithm with a stopwatch tells you about a particular machine as much as about the algorithm itself; a step count is machine-independent and grows in a predictable way with input size [p.1]. Focusing on how the step count grows as n grows is exactly what lets us say one approach scales better than another.

### Big-O Notation

#### What Big-O Means

Big-O gives an upper bound on an algorithm's growth rate. Saying an algorithm is O(f(n)) means its step count grows no faster than f(n), up to constants [p.1].

#### Ignoring Constants and Lower-Order Terms

The rule of Big-O is to ignore constants and lower-order terms. Consider the function 3n^2 + 5n + 2: the n^2 term dominates as n grows, so 3n^2 + 5n + 2 is O(n^2) [p.1]. This is the standard worked example of the week: constants in front (the 3) and smaller terms (5n and 2) are dropped, leaving the dominant growth rate.

### The Common Growth Rates

The lecture orders the common growth rates from slowest growing to fastest [p.2]:

- O(1)
- O(log n)
- O(n)
- O(n log n)
- O(n^2)
- O(2^n) [p.2]

Placed in a table, slowest first:

| Growth rate | Position in the ordering |
|---|---|
| O(1) | slowest growing [p.2] |
| O(log n) | second [p.2] |
| O(n) | third [p.2] |
| O(n log n) | fourth [p.2] |
| O(n^2) | fifth [p.2] |
| O(2^n) | fastest growing [p.2] |

#### Why Exponential Growth Is Infeasible

At the top of the ordering sits O(2^n), and the lecture's warning is direct: O(2^n) is infeasible beyond small n [p.2]. Because the step count doubles with each extra unit of input, an exponential algorithm quickly becomes unusable as n grows, even though it might work fine for a handful of items. This is the practical payoff of the growth-rate ordering: an algorithm's place in that list tells you whether it can scale.

### Recognizing Growth Rates from Code Structure

#### Nested Loops Give Quadratic Time

The first structural pattern: nested loops over n items = n * n = O(n^2) [p.3]. If an outer loop runs n times and an inner loop also runs n times, the body executes n * n times, and n * n = O(n^2) [p.3]. Spotting nested loops in code is therefore a quick way to predict a quadratic running time.

#### Halving Loops Give Logarithmic Time

The second pattern: one loop that halves n each pass = O(log n) [p.3]. Instead of shrinking the problem by one each iteration, the loop cuts the remaining input in half, so the number of passes is only logarithmic in n — dramatically fewer steps than a linear scan [p.3].

## Definitions

| Term | Definition |
|---|---|
| Asymptotic analysis | Comparing algorithms by counting steps, not seconds [p.1] |
| Big-O | Upper bound on growth rate, ignoring constants and lower-order terms [p.1] |
| O(1) | Slowest-growing common rate in the ordering [p.2] |
| O(log n) | Growth of a loop that halves n each pass [p.3][p.2] |
| O(n) | Linear growth [p.2] |
| O(n log n) | Growth rate between linear and quadratic [p.2] |
| O(n^2) | Growth of nested loops over n items [p.3][p.2] |
| O(2^n) | Fastest common growth rate; infeasible beyond small n [p.2] |

## Diagrams & Visual Descriptions

The growth-rate ladder, slowest at the top, fastest at the bottom — the further down an algorithm sits, the harder it scales [p.2]:

```
        slowest  →  fastest
        O(1)
          ↓
       O(log n)
          ↓
         O(n)
          ↓
      O(n log n)
          ↓
        O(n^2)
          ↓
       O(2^n)      ← infeasible beyond small n
```

## Code Examples

Structural patterns of the lecture, expressed as loop skeletons [p.3]:

```
# Pattern 1: nested loops over n items = n * n = O(n^2)
for i in range(n):
    for j in range(n):   # runs n times per outer pass → n * n total

# Pattern 2: one loop that halves n each pass = O(log n)
while n > 1:
    n = n / 2            # problem halves each pass → logarithmic passes
```

These examples matter because they let you read ordinary loop code and predict its growth rate without running anything [p.3].

## Formulas & Algorithms

```
Big-O rule: ignore constants and lower-order terms
3n^2 + 5n + 2 is O(n^2)
```
[p.1]

Common growth rates, slowest growing first [p.2]:

```
O(1)
O(log n)
O(n)
O(n log n)
O(n^2)
O(2^n)
```

Feasibility bound: O(2^n) is infeasible beyond small n [p.2].

Worked structural examples [p.3]:

```
nested loops over n items = n * n = O(n^2)
one loop that halves n each pass = O(log n)
```

## Key Takeaways

- Measuring algorithms in seconds confuses the machine with the method; counting steps isolates the algorithm's own cost [p.1].
- Big-O is an upper bound, and its simplification rule — drop constants and lower-order terms — is what makes 3n^2 + 5n + 2 simply O(n^2) [p.1].
- The six common rates form a strict ordering from O(1) up to O(2^n); knowing an algorithm's place in that order tells you how it scales [p.2].
- Exponential time is a practical dead end: O(2^n) is infeasible beyond small n [p.2].
- You can often read the growth rate straight off the code: nested loops over n items = n * n = O(n^2), while one loop that halves n each pass = O(log n) [p.3].

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: CSIT101 Week 2 lecture slides, pages 1–3. Version: 1.*
