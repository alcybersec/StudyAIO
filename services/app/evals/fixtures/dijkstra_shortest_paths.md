# CSIT201 — Week 7: Shortest Paths

## Overview

This week studies the shortest path problem: in a weighted graph, finding the shortest path from one source vertex to every other vertex [p.1]. The tool of the week is Dijkstra's algorithm, which solves this single-source problem efficiently — but only under one crucial restriction: it requires non-negative edge weights. With a negative edge, the greedy choice the algorithm relies on can be wrong, and the algorithm is simply not correct [p.1].

This matters because shortest paths appear everywhere: road networks, communication routing, any setting where you must move through a network at minimum cost. The lecture walks through the algorithm's mechanics — distance estimates, a priority queue, and edge relaxation — explains the greedy step that makes it correct, and gives its running time with a binary heap, along with how to recover the actual path, not just its length [p.1][p.2][p.3].

## Key Concepts

### The Problem: Single-Source Shortest Paths

We are given a weighted graph and want the shortest path from one source to every other vertex [p.1]. "Weighted" means each edge carries a cost, and "shortest" means minimizing the total weight along a route. The output is not just distances: as we'll see, we can also recover the path itself [p.3].

### The Critical Restriction: Non-Negative Weights

Dijkstra's algorithm requires non-negative edge weights [p.1]. This is not a technicality — with a negative edge, the greedy choice made at each step can be wrong, and the algorithm is not correct [p.1]. Intuitively, the algorithm commits to a vertex's distance once it becomes the smallest estimate; a negative edge elsewhere could later offer a shorter route that the algorithm will never revisit.

### How the Algorithm Works

#### Step 1: Initialize the Estimates

Keep a distance estimate for each vertex. Initially every estimate is infinity, except the source, which is 0 [p.2]. This encodes "we know nothing yet, except that the source is at distance 0 from itself."

Alongside the estimates, maintain a priority queue ordered by estimate [p.2]. The queue is what lets the algorithm efficiently find the most promising vertex to process next.

#### Step 2: Extract and Relax

The main loop does two things [p.2]:

1. Repeatedly remove the vertex with the smallest estimate from the priority queue [p.2].
2. Relax each outgoing edge of that vertex: if `dist[u] + w(u, v) < dist[v]`, update `dist[v]` [p.2].

Relaxation is the heart of the algorithm. When processing vertex `u`, we check whether travelling to `u` and then along edge `(u, v)` beats the best known route to `v`. If so, we improve `v`'s estimate. Each vertex's outgoing edges are examined once, when the vertex is extracted [p.2].

#### The Greedy Step: Why It's Correct

Once a vertex is removed from the queue, its distance is final [p.2]. This is the greedy step [p.2]. The algorithm bets that the smallest current estimate cannot be improved later — a bet that is safe exactly because all weights are non-negative: any path still in the queue must leave the settled region via an edge of weight at least 0, so it cannot undercut the smallest settled distance. With negative edges this bet fails, which is precisely the correctness restriction discussed above [p.1].

### Running Time and Path Recovery

With a binary heap as the priority queue, the running time is `O((V + E) log V)` [p.3]. Each queue operation costs `O(log V)`, and every vertex and edge is touched a bounded number of times, giving the combined bound [p.3].

The algorithm as described gives distances only. To recover the path itself, store a predecessor for each vertex when relaxing, and walk back from the target [p.3]. Each time a relaxation succeeds, record which vertex `u` caused the update; following predecessors from any target therefore retraces the shortest route back to the source [p.3].

## Definitions

| Term | Definition |
|---|---|
| Shortest path | The minimum-total-weight route in a weighted graph; the lecture solves it from one source to every other vertex [p.1] |
| Dijkstra's algorithm | Algorithm finding shortest paths from one source to all vertices; requires non-negative edge weights [p.1] |
| Distance estimate | A current best-known distance per vertex; initially infinity, except the source at 0 [p.2] |
| Priority queue | A structure ordered by estimate, from which the smallest-estimate vertex is repeatedly removed [p.2] |
| Relaxation | The update rule: if `dist[u] + w(u, v) < dist[v]`, update `dist[v]` [p.2] |
| Greedy step | The property that once a vertex is removed from the queue, its distance is final [p.2] |
| Predecessor | Stored when relaxing; walking back from the target recovers the path itself [p.3] |

## Diagrams & Visual Descriptions

The overall flow of one iteration of Dijkstra's algorithm [p.2]:

```
            ┌──────────────────────────────┐
 dist[v]=∞ ──► dist[src]=0 , PQ ordered ──► LOOP:
 by estimate                     remove smallest-estimate vertex u
            └──────────────────────────────┘
                                 │
                                 ▼
                    for each outgoing edge (u,v):
                    if dist[u] + w(u,v) < dist[v]:
                        dist[v] = dist[u] + w(u,v)
                        predecessor[v] = u
                                 │
                                 ▼
              u's distance is FINAL (greedy step)
```

Text description: initialization sets all estimates to infinity except the source at 0; the loop extracts the minimum vertex and relaxes its edges; extraction freezes the vertex's distance [p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The relaxation update applied to each outgoing edge of the extracted vertex `u` is [p.2]:

```
if dist[u] + w(u, v) < dist[v]: update dist[v]
```

Initial condition for the distance estimates [p.2]:

```
dist[v] = infinity for every vertex except the source
dist[source] = 0
```

Running time with a binary heap [p.3]:

```
O((V + E) log V)
```

The must-keep item, in full [p.3]: with a binary heap the running time is `O((V + E) log V)`; to recover the path itself, store a predecessor for each vertex when relaxing and walk back from the target.

## Key Takeaways

- Dijkstra's algorithm solves shortest paths from one source to every other vertex, but only when all edge weights are non-negative — with a negative edge the greedy choice can be wrong and the algorithm is not correct [p.1].
- The algorithm's three ingredients are distance estimates (infinity everywhere, 0 at the source), a priority queue ordered by estimate, and edge relaxation [p.2].
- Relaxation is the engine: `if dist[u] + w(u, v) < dist[v]`, update `dist[v]` — applied to every outgoing edge of each extracted vertex [p.2].
- Once a vertex is removed from the queue, its distance is final — this greedy step is what makes the algorithm both efficient and (with non-negative weights) correct [p.2].
- With a binary heap the total cost is `O((V + E) log V)` [p.3].
- Distances alone aren't the whole answer: storing a predecessor at each relaxation lets you walk back from the target to recover the actual path [p.3].

## Connections

This lecture sits within the broader study of graph algorithms and the algorithms course around it, but the text itself points nowhere beyond its own pages: it does not name a next topic, a prior week, or other applications [p.1][p.2][p.3]. The priority queue used here is the structure that carries the algorithm's efficiency — ordered by estimate, it delivers the smallest-estimate vertex cheaply — and the running time `O((V + E) log V)` is stated specifically for the binary-heap implementation [p.2][p.3]. The lecture leaves open what to do when edge weights can be negative, noting only that Dijkstra's greedy approach then fails [p.1].

---
*Sources: CSIT201 Week 7 lecture slides (pp. 1–3). Version: 1.*
