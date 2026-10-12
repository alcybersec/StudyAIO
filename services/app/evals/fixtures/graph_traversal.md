# CSIT201 — Week 6: Graph Traversal

## Overview

Graphs are one of the most fundamental data structures in computer science: a set of **vertices** (nodes) connected by **edges** (links). Almost any relational data can be modeled this way — road networks, social networks, web pages and hyperlinks, course prerequisites. But representing a graph is only half the story; the real power comes from *traversing* it, i.e., systematically visiting its vertices to answer questions like "is X reachable from Y?" or "what is the shortest path from A to B?"

This week introduces the two canonical traversal strategies: **breadth-first search (BFS)** and **depth-first search (DFS)**. They explore the exact same graph, visit the exact same vertices, and even run in the same time complexity — yet they differ in one crucial design choice (a queue vs. a stack), and that single difference changes the *order* of exploration and makes each suitable for different problems. Understanding *why* that one structural choice changes everything is the key insight of this lecture.

## Key Concepts

### Representing Graphs: The Adjacency List

Before we can traverse a graph, we must store it. The lecture uses an **adjacency list**: for each vertex, we keep a list of its neighbours. For the small square graph used throughout the lecture:

- A's neighbours: B, C
- B's neighbours: A, D
- C's neighbours: A, D
- D's neighbours: B, C

The lecture emphasizes that **memory use is proportional to vertices plus edges** — i.e., $O(V + E)$. This is a key practical property: we only store edges that actually exist, unlike an adjacency *matrix* which would reserve space for every possible pair. For large, sparse graphs (where $E \ll V^2$), this makes adjacency lists the natural choice, and it also directly enables the traversal algorithms below to run in $O(V + E)$ time.

### Breadth-First Search (BFS)

#### The Mechanism: A Queue

BFS uses a **queue** (first-in, first-out). We start at a source vertex, mark it visited, and enqueue it. Then we repeatedly dequeue a vertex and enqueue all of its unvisited neighbours.

Tracing the lecture's example on the square graph, starting at A:

1. Queue: `[A]` — visit A, enqueue its neighbours B and C → `[B, C]`
2. Visit B, enqueue its unvisited neighbour D → `[C, D]`
3. Visit C (no new neighbours to enqueue)
4. Visit D
5. **Visit order: A B C D**

#### Why BFS Matters: Shortest Paths

The lecture's central claim about BFS is that it **visits vertices in order of distance from the start** — first everything at distance 1, then distance 2, and so on. This is a direct consequence of the queue: vertices discovered earlier are processed earlier, so the "frontier" expands outward layer by layer.

The payoff: **in an unweighted graph, BFS finds the fewest-edge path** between the start vertex and every other vertex. If the square graph represented a road map where every road costs the same, BFS from A would immediately give the minimum number of roads to reach every destination. This is why BFS is the go-to algorithm whenever "fewest hops" is the goal.

### Depth-First Search (DFS)

#### The Mechanism: A Stack (or Recursion)

DFS uses a **stack** (last-in, first-out), which can be implemented explicitly or implicitly through **recursion** — each recursive call is effectively a stack frame. Instead of exploring layer by layer, DFS commits to one path and follows it **as deep as possible before backing up** (backtracking).

Tracing the lecture's example from A:

1. From A, go to B
2. From B, go to D
3. From D, go to C
4. **Visit order: A B D C**

Notice this differs from BFS's `A B C D` on the *same graph* — the algorithm, not the graph, determines the order.

#### Intuition: Exploring a Maze

A helpful mental model is maze exploration: DFS is the strategy of "keep walking forward until you hit a dead end, then retrace your steps to the last junction and try another route." The backtracking behaviour falls naturally out of the stack: the most recently discovered vertex is always the next one explored.

### Shared Properties: Visited Marks and Complexity

Both algorithms share two essential properties highlighted in the lecture.

#### Marking Visited Vertices

Both BFS and DFS **mark vertices as visited** so a **cycle cannot cause an infinite loop**. This is critical: our example graph contains a cycle (A–B–D–C–A). Without visited marks, both algorithms would revisit A from C (or D) forever. The visited set is what guarantees termination and ensures each vertex is processed exactly once.

#### Time Complexity

Both run in **O(V + E)** with an adjacency list. The reasoning: every vertex is enqueued/pushed (and dequeued/popped) at most once, and every edge is examined at most twice (once from each endpoint). Since we touch each vertex and each edge a bounded number of times, the total work is linear in the graph's size — the same bound as the adjacency list's memory footprint.

### BFS vs. DFS at a Glance

| Aspect | BFS | DFS |
|---|---|---|
| Data structure | Queue (FIFO) | Stack (LIFO) or recursion |
| Exploration pattern | Layer by layer, by distance from start | As deep as possible, then backtrack |
| Example order from A | A B C D | A B D C |
| Path property | Fewest-edge path in unweighted graphs | Not guaranteed shortest |
| Time complexity | $O(V + E)$ | $O(V + E)$ |
| Visited marks | Required (cycles) | Required (cycles) |

## Definitions

| Term | Definition |
|---|---|
| Graph | A structure of vertices connected by edges. |
| Vertex | A node of the graph; the entities being related. |
| Edge | A connection between two vertices. |
| Adjacency list | Storage where each vertex holds the list of its neighbours; memory proportional to vertices plus edges. |
| Traversal | Systematically visiting the vertices of a graph. |
| BFS | Breadth-first search; queue-based traversal visiting vertices in order of distance from the start; finds fewest-edge paths in unweighted graphs. |
| DFS | Depth-first search; stack/recursion-based traversal that goes as deep as possible before backing up. |
| Queue | FIFO data structure driving BFS. |
| Stack | LIFO data structure driving DFS; recursion provides it implicitly. |
| Visited mark | A flag ensuring each vertex is processed once, preventing infinite loops on cycles. |
| Cycle | A path that returns to its starting vertex; the reason visited marks are needed. |
| O(V + E) | Time complexity of both traversals using an adjacency list. |

## Diagrams & Visual Descriptions

The lecture's example graph — a square with four vertices and four edges, containing a cycle:

```
    A --- B
    |     |
    C --- D
```

Traversal orders from A on this same graph:

```
BFS (queue):            DFS (stack):
level 0:  A             A
level 1:  B, C            -> B
level 2:  D                 -> D
                              -> C
order: A B C D         order: A B D C
```

The cycle A→B→D→C→A is exactly why both algorithms must mark vertices as visited.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

**Memory (adjacency list):**

$$\text{memory} \propto V + E$$

**Time complexity (both BFS and DFS):**

$$O(V + E)$$

**BFS algorithm sketch:**

```text
put start in queue; mark start visited
while queue not empty:
    v = dequeue
    for each neighbour of v:
        if not visited: mark visited, enqueue
```

**DFS algorithm sketch:**

```text
visit(v):
    mark v visited
    for each neighbour of v:
        if not visited: visit(neighbour)   # recursion = implicit stack
```

## Key Takeaways

- An adjacency list stores a graph in space proportional to $V + E$ — efficient for sparse graphs, and the reason traversals can be linear-time.
- BFS and DFS differ only in the container used (queue vs. stack), yet that one choice completely changes the exploration order.
- BFS visits vertices in increasing distance from the start, so in an unweighted graph it yields the fewest-edge path.
- DFS dives as deep as possible before backtracking — natural to express recursively.
- Visited marks are mandatory in both: without them, a cycle causes an infinite loop.
- Both traversals run in $O(V + E)$ — optimal, since you must at least look at every vertex and edge.

## Connections

The lecture notes that BFS finds the fewest-edge path in unweighted graphs — pointing toward shortest-path problems, where weighted graphs would require going beyond this week's simple traversal. The adjacency-list representation and the $O(V + E)$ bound are presented as the enabling foundation for both algorithms, and the lecture's emphasis on cycles motivating visited marks highlights graph structure as central to algorithm correctness.

---

*Sources: CSIT201 Week 6 lecture slides (Graph Traversal). Version: 1.*
