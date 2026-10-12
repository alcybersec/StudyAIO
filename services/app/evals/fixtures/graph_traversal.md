# CSIT201 — Week 6: Graph Traversal

## Overview

A graph is a structure made of vertices and edges, and this week's lecture introduces both how to store a graph and how to explore it systematically [p.1]. Graph traversal — visiting every vertex in a controlled order — is a foundational technique in computing: it underlies searching, pathfinding, and reachability analysis [p.1][p.2].

The lecture presents two traversal strategies that differ only in the data structure they use: breadth-first search (BFS), which uses a queue, and depth-first search (DFS), which uses a stack or recursion [p.2]. Despite producing different visit orders, both share crucial safeguards and the same efficiency guarantees, which the lecture establishes explicitly [p.3].

## Key Concepts

### Representing Graphs: The Adjacency List

Before any traversal can begin, we need a way to store the graph in memory. The lecture's chosen representation is the **adjacency list**: for each vertex, we keep the list of its neighbours [p.1]. So for a graph like the one below, vertex A's list would contain B and C, and so on.

This representation matters because it determines traversal cost. The lecture states that memory use is proportional to vertices plus edges — that is, proportional to the actual size of the graph rather than to some larger fixed structure [p.1]. This property is exactly what makes the O(V + E) running time of the traversal algorithms possible later in the lecture [p.3].

### Breadth-First Search (BFS)

BFS uses a **queue** to decide which vertex to visit next [p.2]. A queue is first-in, first-out: the earliest vertex discovered is the earliest one explored. This gives BFS its defining characteristic — it explores the graph outward from the start in "rings".

The lecture traces BFS on a four-vertex example. Starting at A, the queue holds [A]. We visit A and enqueue its neighbours B and C; then we visit B and enqueue D. The resulting visit order is **A B C D** [p.2].

The payoff of this queue discipline is significant: BFS visits vertices in order of distance from the start, so in an unweighted graph it finds the fewest-edge path [p.2]. Intuitively, imagine navigating a road network where every road costs the same — BFS is guaranteed to reach your destination by the minimum number of roads.

### Depth-First Search (DFS)

DFS uses a **stack**, or equivalently, recursion, to decide the next vertex to explore [p.2]. A stack is last-in, first-out: the most recently discovered vertex is explored next. This means DFS commits to a direction and goes as deep as possible before backing up [p.2].

Tracing the same graph starting at A: DFS goes to B, then D, then C, giving the order **A B D C** — different from BFS's order on the same graph [p.2]. Where BFS swept outward level by level, DFS plunged along one route to its end and only then retreated to explore alternatives.

### Shared Properties: Visited Marking and Complexity

Both algorithms must guard against a subtle hazard: graphs can contain cycles, and a naive traversal could loop around a cycle forever. The solution is that both mark vertices as visited so a cycle cannot cause an infinite loop [p.3]. Before processing a vertex, you check its mark; if it is already visited, you skip it.

Efficiency is also shared. With the adjacency-list representation from earlier, both BFS and DFS run in O(V + E) [p.3]. This means each vertex and each edge is effectively touched a constant number of times, and the adjacency list is what makes that accounting clean [p.1][p.3].

### Comparing the Two

| Aspect | BFS | DFS |
|---|---|---|
| Data structure | Queue [p.2] | Stack, or recursion [p.2] |
| Visit order from A (example graph) | A B C D [p.2] | A B D C [p.2] |
| Exploration style | In order of distance from the start [p.2] | As deep as possible before backing up [p.2] |
| Cycle handling | Marks vertices as visited [p.3] | Marks vertices as visited [p.3] |
| Time complexity | O(V + E) with adjacency list [p.3] | O(V + E) with adjacency list [p.3] |

## Definitions

| Term | Definition |
|---|---|
| Graph | A structure with vertices and edges [p.1] |
| Adjacency list | A graph storage scheme where, for each vertex, we keep the list of its neighbours [p.1] |
| BFS | Breadth-first search; uses a queue and visits vertices in order of distance from the start [p.2] |
| DFS | Depth-first search; uses a stack or recursion and goes as deep as possible before backing up [p.2] |
| Visited marking | Marking vertices as visited so a cycle cannot cause an infinite loop [p.3] |
| Unweighted graph | A graph where BFS finds the fewest-edge path [p.2] |

## Diagrams & Visual Descriptions

The lecture's example graph, used to trace both BFS and DFS:

```
    A --- B
    |     |
    C --- D
```

From A, BFS's queue produces the order A B C D, while DFS's stack-driven exploration produces A B D C — the same graph, two different traversal disciplines [p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Graph storage [p.1]:
```
Adjacency list: for each vertex, the list of its neighbours.
Memory use is proportional to vertices plus edges.
```

BFS trace starting at A [p.2]:
```
queue [A]
Visit A, enqueue B and C.
Visit B, enqueue D.
Order: A B C D
```

DFS trace starting at A [p.2]:
```
go to B, then D, then C.
Order: A B D C
```

Shared properties of BFS and DFS [p.3]:
```
Both mark vertices as visited so a cycle cannot cause an infinite loop.
Both run in O(V + E) with an adjacency list.
```

## Key Takeaways

- The adjacency list stores a graph using memory proportional to vertices plus edges, which sets up efficient traversal [p.1].
- BFS and DFS differ fundamentally in their data structure — queue versus stack or recursion — and this alone changes the visit order [p.2].
- BFS's distance-ordered exploration means it finds the fewest-edge path in an unweighted graph — a genuinely useful guarantee, not just a curiosity [p.2].
- DFS's depth-first commitment produces a different order (A B D C vs A B C D on the lecture's example) but explores the same graph [p.2].
- Visited marking is not optional: without it, a cycle causes an infinite loop in either algorithm [p.3].
- Both traversals achieve O(V + E) with an adjacency list — linear in the graph's actual size [p.3].

## Connections

The lecture builds on the graph definition and adjacency-list storage introduced at its start, using that representation to achieve the O(V + E) bound for both traversals [p.1][p.3]. Within the lecture itself, BFS's property of finding fewest-edge paths in unweighted graphs is presented as the practical payoff of queue-based traversal [p.2]. The lecture does not point to other weeks of the course.

---
*Sources: CSIT201 Week 6 lecture slides (pages 1–3). Version: 1.*
