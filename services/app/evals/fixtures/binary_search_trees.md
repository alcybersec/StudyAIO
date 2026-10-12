# CSIT101 — Week 4: Binary Search Trees

## Overview

A binary search tree (BST) is a data structure that stores keys so that searching and inserting are both fast and simple. The whole structure rests on a single invariant: every key in the left subtree is smaller than the node, and every key in the right subtree is larger [p.1]. Because of this ordering property, both search and insert only need to follow one path from the root down to where the key belongs, so their cost is determined by the height of the tree [p.1].

This makes the BST a powerful tool — but its performance depends critically on the tree's shape. When the tree is balanced, its height is about log n and search runs in O(log n); when keys arrive in sorted order, the tree degenerates into what is effectively a linked list with height n and O(n) search [p.3]. Understanding both the operations and this performance trade-off is the heart of this week's material.

## Key Concepts

### The BST Invariant

The defining property of a binary search tree is its ordering invariant: every key in the left subtree is smaller than the node, and every key in the right subtree is larger [p.1]. This is not just a labeling convention — it is what makes the structure useful. At any node, comparing the target key against that node's key tells you immediately which side the key must be on, letting you discard half of the remaining subtree at every step (in a balanced tree).

This invariant must hold at every node, not just the root: each subtree is itself a BST satisfying the same rule, which is why recursive insertion works naturally.

### Search and Insert Follow One Path

Both fundamental operations work by walking a single root-to-leaf (or root-to-found) path. Their cost is therefore the height of the tree [p.1]. This shared characteristic is why we analyze both operations together: whatever makes one slow makes the other slow too.

#### Insertion

Insertion is expressed recursively. To insert a key, compare it with the current node: if it is smaller, recurse into the left subtree; otherwise, recurse into the right subtree [p.2]. When you reach an empty spot (a `None` node), that is where the new key belongs, and you create the node there. Crucially, the recursion reassigns the child pointer on the way back up, as in these lines [p.2]:

```python
node.left = insert(node.left, key)
node.right = insert(node.right, key)
```

The reassignment (`node.left = ...`) is what links the newly created subtree back into the parent — a common point of confusion when first reading recursive tree code.

#### Search

Search can be written iteratively with a simple loop that continues as long as the current node exists and its key is not the target [p.2]. At each step, the comparison against the current key decides which child to move to [p.2]:

```python
while node and node.key != key:
    node = node.left if key < node.key else node.right
```

This mirrors insertion exactly: go left when the key is smaller, right otherwise, until you either find the key or fall off the tree (in which case the key is absent).

### Tree Shape and Performance: Balanced vs. Degenerate

The height of the tree is the whole performance story. A balanced tree has height about log n, so search is O(log n) — fast, because each comparison eliminates a large fraction of the remaining keys [p.3].

But nothing in the basic BST keeps it balanced. Inserting keys in sorted order builds a degenerate tree: each new key is always larger (or always smaller) than everything before it, so every insert goes down the same side. The result is effectively a linked list, with height n and O(n) search [p.3]. The same data set can therefore produce a tree that is logarithmic in height or one that is linear, purely depending on insertion order.

### In-Order Traversal

The BST structure also gives an elegant way to read out the data: in-order traversal visits the left subtree first, then the node itself, then the right subtree [p.3]. Applied to a BST, this yields the keys in sorted order [p.3]. This is a direct consequence of the invariant — everything smaller than a node lives to its left, everything larger to its right, so left–node–right order is exactly sorted order.

## Definitions

| Term | Definition |
|---|---|
| Binary search tree (BST) | A tree keeping the invariant that every key in the left subtree is smaller than the node and every key in the right subtree is larger [p.1] |
| Height | The depth of the tree; search and insert follow one path from the root, so their cost is the height of the tree [p.1] |
| Balanced tree | A tree with height about log n, giving O(log n) search [p.3] |
| Degenerate tree | A tree built by inserting keys in sorted order; effectively a linked list, with height n and O(n) search [p.3] |
| In-order traversal | Traversal that visits left subtree, then node, then right subtree; on a BST it yields the keys in sorted order [p.3] |

## Diagrams & Visual Descriptions

A balanced tree versus a degenerate tree built from the same sorted keys (illustrative shapes consistent with the lecture):

```
Balanced (height ~ log n):        Degenerate (insert 1,2,3,4 — height n):

          4                          1
        /   \                         \
      2       6                         2
     / \     / \                         \
    1   3   5   7                         3
                                           \
                                            4
```

The balanced shape lets each comparison discard most of the remaining keys, giving O(log n) search; the degenerate shape offers no branching, so search degrades to O(n), like scanning a linked list [p.3].

## Code Examples

Recursive insertion — the key comparison sends the key left or right; the returned node is reattached to the parent, and an empty spot becomes the new node. Relevant whenever we grow a BST one key at a time [p.2]:

```python
def insert(node, key):
    if node is None:  # empty spot found: create the node here
        return Node(key)
    if key < node.key:  # smaller keys go to the left subtree
        node.left = insert(node.left, key)
    else:  # otherwise go to the right subtree
        node.right = insert(node.right, key)
    return node  # reattach this subtree to the parent
```

Iterative search — walks one path from the root, choosing a side by comparison, until the key is found or the tree is exhausted. Relevant for membership tests without recursion overhead [p.2]:

```python
def search(node, key):
    while node and node.key != key:  # stop at a match or a dead end
        node = node.left if key < node.key else node.right  # pick the side
    return node
```

## Formulas & Algorithms

The BST invariant [p.1]:

```
every key in the left subtree is smaller than the node,
every key in the right subtree is larger
```

Insertion logic [p.2]:

```
if node is None: return Node(key)
if key < node.key: node.left = insert(node.left, key)
else:              node.right = insert(node.right, key)
```

Search loop [p.2]:

```
while node and node.key != key:
    node = node.left if key < node.key else node.right
```

Complexities and properties [p.1][p.3]:

```
cost of search and insert = height of the tree
balanced tree: height ≈ log n  →  search is O(log n)
sorted-order insertion: degenerate tree (linked list), height = n  →  search is O(n)
in-order traversal = left subtree, node, right subtree  →  keys in sorted order
```

## Key Takeaways

- One invariant — smaller keys left, larger keys right — powers both search and insert [p.1].
- Search and insert each follow a single path from the root, so their running time is the tree's height [p.1].
- A balanced tree gives O(log n) search; sorted-order insertion degenerates to a linked list with O(n) search — insertion order matters enormously [p.3].
- In-order traversal outputs BST keys in sorted order, a free consequence of the invariant [p.3].

## Connections

This lecture stands on the general idea that a structure's shape determines operation cost: the BST's cost is the height of the tree, whether that is log n (balanced) or n (degenerate) [p.1][p.3]. The lecture leaves open the problem of what happens when sorted input produces a degenerate tree, which motivates the question of how to keep a search tree's height small — though it names no specific follow-up technique here.

The in-order traversal result — that visiting left, node, right yields keys in sorted order [p.3] — also ties trees to ordered data, showing that the same structure supports both fast lookup and sorted output.

---
*Sources: CSIT101 Week 4 lecture slides (pages 1–3). Version: 1.*
