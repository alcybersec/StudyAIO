# CSIT201 — Week 7: Shortest Paths

## Overview

Dijkstra's algorithm computes single-source shortest paths, but only when edge weights are non-negative.

## Key Concepts

### Precondition

Dijkstra's algorithm finds the shortest path from one source to every other vertex in a weighted graph. It requires non-negative edge weights; with a negative edge the greedy choice can be wrong and the algorithm is not correct.

### The procedure

Keep a distance estimate for each vertex, infinity except the source at 0, and a priority queue ordered by estimate. Repeatedly remove the vertex with the smallest estimate and relax each outgoing edge: if dist[u] + w(u, v) < dist[v], update dist[v]. Once a vertex is removed its distance is final; this is the greedy step.

### Cost and paths

With a binary heap the running time is O((V + E) log V). Storing a predecessor on each relaxation lets you walk back from the target to recover the path.

## Definitions

| Term | Definition |
|---|---|
| Relaxation | Update dist[v] if dist[u] + w(u, v) is smaller |
| Distance estimate | Current best known distance to a vertex |
| Predecessor | The vertex before v on its best known path |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

```
relax(u, v): if dist[u] + w(u, v) < dist[v]: dist[v] = dist[u] + w(u, v)
time with binary heap: O((V + E) log V)
```

## Key Takeaways

- Non-negative weights are a hard precondition.
- A removed vertex is final: the greedy step.
- Predecessors rebuild the path.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: dijkstra_shortest_paths.pdf. Version: 1.*
