# CSIT201 — Week 7: Shortest Paths & Dijkstra's Algorithm

## Overview

Many computational problems reduce to one question: given a network of connected points, what is the cheapest way to get from one to another? This is the *shortest path problem*, and it appears everywhere — road navigation, network routing, scheduling — anywhere costs accumulate along edges of a graph. Week 7 introduces Dijkstra's algorithm, the classic solution for finding the shortest path from a single source vertex to every other vertex in a weighted graph whose edge weights are non-negative.

Dijkstra's algorithm is fundamentally a *greedy* algorithm: at every step it commits to the most promising vertex, and — crucially — that commitment is never revoked. This correctness-by-greediness works only because all weights are non-negative. Understanding both the mechanics (distance estimates, relaxation, priority queues) and the limitation (why negative edges break it) is the goal of this week.

## Key Concepts

### The Problem: Single-Source Shortest Paths

Dijkstra's algorithm answers the *single-source* shortest path question: starting from one designated source vertex, what is the shortest total weight of a path to every other vertex in the graph? Rather than solving each destination separately, one run of the algorithm computes distances to all vertices simultaneously, which is what makes it so efficient in practice.

The graph is *weighted*: each edge carries a number representing cost — distance, time, or bandwidth delay, for example. The algorithm requires these weights to be **non-negative**.

### Why Non-Negative Weights Are Essential

The greedy strategy at the heart of Dijkstra's algorithm depends on a simple intuition: once you've settled on the cheapest-known vertex, its distance can never be improved by going somewhere else first. If any edge had a negative weight, this intuition fails — a longer path with a negative edge could be cheaper than a short one, so the vertex settled "too early" would get an incorrect distance. As the lecture states, with a negative edge the greedy choice can be wrong and the algorithm is simply not correct. This is not a performance issue but a correctness one.

### The Algorithm: Estimates, Relaxation, and the Greedy Step

#### Distance Estimates

Every vertex keeps a *distance estimate*. Initially, the source's estimate is 0 (it costs nothing to be where you are), and every other vertex's estimate is ∞ (we have no idea how to reach them yet). These estimates are stored in a priority queue ordered by estimate, so the algorithm can always grab the most promising vertex quickly.

#### Relaxation

The core operation is **edge relaxation**. When examining an outgoing edge from vertex $u$ to vertex $v$ with weight $w(u, v)$, we ask: is it cheaper to reach $v$ *via* $u$ than by our current best route?

$$\text{if } dist[u] + w(u, v) < dist[v], \text{ update } dist[v]$$

If so, the estimate for $v$ improves. Think of this like a navigation app recalculating a route when it discovers a faster detour through an intermediate junction.

#### The Greedy Step and Finalisation

The algorithm repeatedly removes the vertex with the smallest estimate from the priority queue, then relaxes all its outgoing edges. The key property: **once a vertex is removed, its distance is final** — it will never be updated again. This finalisation is the greedy step. It is what distinguishes Dijkstra from algorithms that allow repeated re-examination of vertices, and it only holds because weights are non-negative.

### Complexity and Path Reconstruction

With a binary heap as the priority queue, the running time is $O((V + E) \log V)$ — each vertex is extracted from the heap, and each edge may trigger a relaxation that updates the heap. The logarithmic factor comes from heap operations.

To recover the actual path (not just the distance), the algorithm stores a **predecessor** for each vertex whenever a relaxation updates its distance. At the end, walking backwards from the target vertex through predecessors reconstructs the exact shortest route — the sequence of "which vertex did I come from?" links.

## Definitions

| Term | Definition |
|---|---|
| Shortest path | The path of minimum total edge weight between vertices in a weighted graph |
| Single-source shortest paths | Finding the shortest path from one source vertex to every other vertex |
| Weighted graph | A graph where each edge has an associated (here, non-negative) cost |
| Distance estimate | The current best-known total weight of a path from the source to a vertex; initially ∞, except 0 for the source |
| Relaxation | Testing whether $dist[u] + w(u, v) < dist[v]$ and updating $dist[v]$ if so |
| Greedy step | Removing the smallest-estimate vertex from the queue; its distance becomes final |
| Predecessor | The vertex from which a shorter path to a vertex was found during relaxation; used to reconstruct the path |
| Priority queue | Data structure ordered by distance estimate, used to select the next vertex to process |
| Binary heap | Priority queue implementation giving Dijkstra's running time $O((V + E) \log V)$ |

## Diagrams & Visual Descriptions

The relaxation and greedy step as a cycle:

```
        ┌────────────────────────────────────────────┐
        │                                            │
        ▼                                            │
  ┌───────────────┐     ┌──────────────────┐     ┌──────────────┐
  │ Pick vertex u │     │ For each edge    │     │ dist[v] = ∞  │
  │ with smallest │────▶│ (u,v): relax:    │────▶│ initially;   │
  │ dist estimate │     │ dist[u]+w < dist[v]?      │ src = 0      │
  └───────────────┘     └──────────────────┘     └──────────────┘
        │                     │ update if yes
        ▼                     ▼
  ┌───────────────┐     ┌──────────────────┐
  │ u's distance  │     │ update dist[v],  │
  │ is FINAL      │     │ set pred[v] = u  │
  └───────────────┘     └──────────────────┘
```

Path reconstruction: from the target, repeatedly follow `pred` pointers back to the source, then reverse the sequence.

## Code Examples

No code examples in this lecture. (The algorithm is fully specified by the relaxation condition and the pseudocode-like loop described above.)

## Formulas & Algorithms

**Relaxation condition:**

$$dist[v] \leftarrow dist[u] + w(u,v) \quad \text{if } dist[u] + w(u,v) < dist[v]$$

**Running time (binary heap):**

$$O((V + E)\log V)$$

**Algorithm outline:**
1. Set $dist[source] = 0$, all others $\infty$; insert all vertices into a priority queue.
2. Repeatedly extract the vertex $u$ with the smallest estimate.
3. Relax every outgoing edge $(u, v)$, updating $dist[v]$ and $pred[v]$ on improvement.
4. Continue until the queue is empty; extracted distances are final.

## Key Takeaways

- Dijkstra's algorithm solves single-source shortest paths in one run, giving distances to *all* vertices.
- Correctness rests on non-negative weights — one negative edge can make the greedy finalisation wrong.
- Relaxation is the fundamental operation; everything else is bookkeeping to make relaxations efficient.
- Once extracted, a vertex's distance is final — the essence of the greedy step.
- Binary-heap implementation costs $O((V+E)\log V)$.
- Predecessor pointers turn distance numbers back into an actual path.

## Connections

Dijkstra's algorithm builds directly on the abstract concept of weighted graphs and greedy algorithmic strategy — the lecture's correctness argument hinges precisely on why the greedy choice is valid here. The priority queue used for vertex selection is the same data-structure machinery underlying efficient graph traversal and scheduling problems. The lecture notes the limitation with negative edge weights, pointing toward shortest-path algorithms that can handle them as an obvious follow-on topic.

---
*Sources: CSIT201 Week 7 lecture slides (pages 1–3). Version: 1.*
