# CSIT201 — Week 6: Graph Traversal

## Overview

Graph traversal visits every reachable vertex. BFS and DFS differ only in the data structure that holds the frontier, and that choice changes the visiting order.

## Key Concepts

### Representing a graph

A graph has vertices and edges. An adjacency list stores each vertex's neighbours, using memory proportional to vertices plus edges.

### Breadth-first search

BFS uses a queue. From A the queue starts [A]; visiting A enqueues B and C, visiting B enqueues D, giving the order A B C D. Because vertices are visited in order of distance from the start, BFS finds the fewest-edge path in an unweighted graph.

### Depth-first search

DFS uses a stack, or recursion, and goes as deep as possible before backing up: A B D C on the same graph.

### Both

Both mark vertices as visited so a cycle cannot cause an infinite loop, and both run in O(V + E) with an adjacency list.

## Definitions

| Term | Definition |
|---|---|
| Adjacency list | For each vertex, the list of its neighbours |
| BFS | Traversal using a queue, by distance from the start |
| DFS | Traversal using a stack or recursion, deep first |
| Visited mark | Flag preventing revisits and infinite loops on cycles |

## Diagrams & Visual Descriptions

```
    A --- B
    |     |
    C --- D

BFS from A (queue):  A B C D
DFS from A (stack):  A B D C
```
The square graph shows how the same start gives two different visiting orders.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Both BFS and DFS: O(V + E) time with an adjacency list.

## Key Takeaways

- BFS = queue, DFS = stack or recursion.
- BFS gives fewest-edge paths when edges are unweighted.
- Mark vertices visited to survive cycles.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: graph_traversal.pdf. Version: 1.*
