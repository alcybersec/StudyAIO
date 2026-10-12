# CSIT101 — Week 2: Asymptotic Analysis

## Overview

When we compare algorithms, we can't simply time them with a stopwatch — running times depend on the machine, the programming language, and other programs competing for resources. Instead, computer scientists **count steps, not seconds**: we measure how the number of basic operations an algorithm performs grows as the input size *n* grows. This is the essence of asymptotic analysis.

Asymptotic analysis gives us a machine-independent way to answer the question every programmer eventually faces: "Will this program still be fast enough when the input is a million items instead of a hundred?" It also gives us a shared vocabulary — Big-O notation and the standard growth rates — that lets us classify and compare algorithms at a glance. This week's material is foundational: nearly every algorithm you study later in this course will be described by its asymptotic complexity.

## Key Concepts

### Counting Steps, Not Seconds

Measuring runtime in real seconds is unreliable because it entangles the algorithm with the hardware and environment it runs on. The alternative is to count the number of elementary steps an algorithm executes as a function of input size *n*. Two algorithms may take different absolute times on the same machine, but their *step counts* reveal which one scales better as inputs grow. This shift in perspective — from wall-clock time to growth rate — is what makes algorithm comparison meaningful and reproducible.

### Big-O Notation

#### What It Means

Big-O describes the **upper bound** on an algorithm's growth rate. Saying an algorithm is O(f(n)) means that, for large enough inputs, its step count grows no faster than some constant multiple of f(n). It characterizes the worst-case scaling behavior, so we know what to expect as inputs get large.

#### Ignoring Constants and Lower-Order Terms

Big-O deliberately discards details that matter less and less as n grows. Constants and lower-order terms become insignificant compared to the dominant term:

- $3n^2 + 5n + 2$ is **O(n²)**. As n grows, the n² term dwarfs 5n, and both dwarf 2. For n = 1000, 3n² = 3,000,000 while 5n = 5,000 — the lower-order terms are negligible.

Why drop the constant 3? Because a constant factor could be absorbed by a faster machine or a better implementation; what matters fundamentally is the *shape* of the growth curve, not its scaling factor.

### The Common Growth Rates

Growth rates are conventionally listed from **slowest growing to fastest growing**. Slower growth means better scalability:

| Growth rate | Intuition | Feasibility |
|---|---|---|
| O(1) | Constant — doesn't grow with input | Excellent |
| O(log n) | Grows very slowly (e.g., halving) | Excellent |
| O(n) | Linear — proportional to input | Good |
| O(n log n) | Slightly worse than linear | Good for large inputs |
| O(n²) | Quadratic — input squared | Acceptable for moderate n |
| O(2^n) | Exponential — doubles per unit of n | **Infeasible beyond small n** |

The exponential case deserves special attention: an O(2ⁿ) algorithm may be perfectly usable at n = 10 or n = 20, but each increment of n doubles the work. By n = 100, the step count is astronomically large — no speed of hardware can rescue it. This is why the lecture flags O(2ⁿ) as infeasible beyond small inputs: exponential growth overwhelms any constant-factor improvements.

### Recognizing Complexity from Code Structure

Asymptotic analysis connects directly to how code is written. Two patterns from the lecture:

- **Nested loops**: a loop over n items containing another loop over n items performs n × n = n² steps, giving **O(n²)**. Each additional level of nesting adds another factor of n.
- **Halving loops**: a single loop that halves n on each pass (e.g., repeatedly dividing the search space by 2) takes only **O(log n)** iterations, because you can halve n only logarithmically many times before reaching 1. This is why logarithmic algorithms are so efficient — doubling the input adds just one more iteration.

## Definitions

| Term | Definition |
|---|---|
| Asymptotic analysis | Studying algorithm efficiency by counting steps as a function of input size, rather than measuring seconds |
| Big-O notation | A way to express the upper bound on an algorithm's growth rate, ignoring constants and lower-order terms |
| n | The size of the algorithm's input |
| O(1) | Constant time — the step count does not grow with input size |
| O(log n) | Logarithmic time — step count grows very slowly; arises from loops that halve the problem each pass |
| O(n) | Linear time — step count grows in direct proportion to input size |
| O(n log n) | "n log n" time — a common efficient sorting-scale growth rate |
| O(n²) | Quadratic time — step count grows with the square of the input; e.g., nested loops |
| O(2ⁿ) | Exponential time — step count doubles with each unit of input; infeasible beyond small n |
| Growth rate | How quickly an algorithm's step count increases as input size increases |

## Diagrams & Visual Descriptions

Growth-rate hierarchy, slowest to fastest (a smaller slope means better scalability):

```
steps
  ^
  |                                        /  O(2^n)   (infeasible beyond small n)
  |                                      /
  |                              _______/    O(n^2)
  |                         ____/
  |                    ____/                O(n log n)
  |               ____/
  |          ____/                          O(n)
  |      ___/
  |   __/                                   O(log n)
  |__/___________________________________>  O(1)  (flat line)
  +--------------------------------------> n
```

Halving loop → logarithmic behavior:

```
n = 16
  \---> 8          each pass halves n
        \---> 4    (1 extra iteration even if
              \--> 2    n doubles)
                   \--> 1     total passes ≈ log2(n)
```

No diagrams in this lecture beyond these illustrations of the growth rates described.

## Code Examples

Nested loops — quadratic time:

```python
for i in range(n):  # outer loop runs n times
    for j in range(n):  # inner loop runs n times per outer pass
        do_work()  # total: n * n = n^2 steps  ->  O(n^2)
```

*Relevant when:* you need to spot that nesting a loop inside a loop squares the cost — a common source of slow code on large inputs.

Halving loop — logarithmic time:

```python
while n > 1:  # loop continues while the problem is non-trivial
    n = n // 2  # halve n each pass; only log2(n) passes possible
```

*Relevant when:* you want to see why divide-and-halve processes are O(log n) — doubling the input adds just one extra pass.

## Formulas & Algorithms

Dominant-term reduction:

$$3n^2 + 5n + 2 \implies O(n^2)$$

Rule: drop constant coefficients and lower-order terms; keep the fastest-growing term.

Nested loop step count:

$$n \times n = n^2 \;\Rightarrow\; O(n^2)$$

Halving loop iteration count:

$$n \to n/2 \to n/4 \to \dots \to 1 \;\Rightarrow\; \log_2 n \text{ passes} \;\Rightarrow\; O(\log n)$$

## Key Takeaways

- Measure algorithms by counting steps, not seconds — hardware-independent analysis reveals true scalability.
- Big-O gives an upper bound on growth; it deliberately ignores constants and lower-order terms because they fade in significance as n grows.
- The growth-rate ladder O(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ) is the vocabulary for comparing algorithms.
- Exponential O(2ⁿ) algorithms are effectively unusable beyond small inputs — no hardware can compensate for exponential growth.
- You can often read complexity straight off the code: nested loops over n give O(n²); a loop that halves n each pass gives O(log n).

## Connections

The lecture focuses on establishing the analysis toolkit itself — counting steps, Big-O bounds, and the growth-rate hierarchy — and applies it to loop patterns (nested loops as O(n²), halving loops as O(log n)). These analysis techniques are the lens through which any algorithm in the rest of the course will be evaluated: whenever an algorithm is presented later, its cost will be expressible as one of these growth rates. No other weeks were named in this lecture, so no specific forward links can be given.

---
*Sources: CSIT101 Week 2 lecture slides — Asymptotic Analysis. Version: 1.*
