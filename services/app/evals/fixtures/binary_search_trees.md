# CSIT101 — Week 4: Binary Search Trees

## Overview

A binary search tree (BST) is a data structure that organizes keys in a tree so that searching behaves like a highly efficient guessing game: at each node, you compare the key you want with the node's key and eliminate half of the remaining possibilities. The tree maintains a simple but powerful invariant — every key in the left subtree of a node is smaller than that node, and every key in the right subtree is larger. This single rule is what makes the BST useful.

Why does this matter? Data structures are all about trade-offs between storage and speed, and the BST promises logarithmic-time search and insertion — *provided* the tree stays balanced. This week's material also exposes the fragility of that promise: insert the same keys in a different order (specifically, in sorted order) and the "tree" collapses into a linear chain, destroying performance. Understanding both the invariant and its limitations is the heart of this lecture, and it sets up the motivation for self-balancing structures later in a data structures course.

## Key Concepts

### The BST Invariant

The defining property of a binary search tree is a local rule with global consequences. For **every** node in the tree:

- All keys in its **left subtree** are **smaller** than the node's key.
- All keys in its **right subtree** are **larger** than the node's key.

It's crucial to understand that this applies recursively — not just to immediate children. If a node holds key 50, then every single key anywhere in its left subtree must be less than 50, even three levels down. Because the invariant holds at every node simultaneously, it acts as a roadmap: when searching for a key, the comparison at each node tells you definitively which subtree to descend into, and you never need to consider the other one again.

### Search: Following One Path

Because of the invariant, searching doesn't require examining the whole tree — it traces a single path from the root downward. At each node, compare the target key to the node's key:

- If the target is smaller, go left.
- If it's larger, go right.
- If equal, you found it.
- If you fall off the tree (reach `None`), the key isn't present.

The number of comparisons equals the length of this path, which is at most the **height** of the tree. This is the key cost model: **search cost = height**, not total size.

### Insertion: Searching for a Missing Spot

Insertion works almost identically to search — you follow the same one-path descent, using comparisons to decide left or right, until you reach an empty spot (`None`). That's exactly where the new key belongs, preserving the invariant. The recursive `insert` function in the lecture expresses this elegantly: the base case creates a new node when it reaches `None`; otherwise it recurses into the correct subtree and reattaches the (possibly new) subtree root.

Notice the implication: **insertion cost is also the height of the tree**, since inserting is just an unsuccessful search plus one node creation.

### Height, Balance, and the Worst Case

Here is the critical insight — and the caveat — of this lecture:

- A **balanced** tree has height about $\log_2 n$, so search and insert run in **O(log n)**. Doubling the number of keys adds only one comparison, which is why balanced trees scale so well.
- But the BST does not guarantee balance. If you insert keys in **sorted order** (e.g., 1, 2, 3, 4, 5...), each new key always goes right of the previous one. The result is a **degenerate tree** — structurally a linked list — with height $n$ and **O(n)** search.

This means BST performance is order-dependent. The same set of keys can produce an efficient tree or a pathological one depending purely on insertion sequence. This weakness motivates the study of balanced tree variants, where rotations or other mechanisms maintain the $\log n$ height guarantee automatically.

### In-Order Traversal: Free Sorting

The last concept ties the tree structure to ordering. An **in-order traversal** visits nodes in the order: left subtree, then the node itself, then the right subtree. Applied recursively to a BST, this produces the keys in **sorted order**.

Why? Consider the root: in-order visits everything smaller than the root first, then the root, then everything larger. By induction, the whole traversal is sorted. This gives BSTs a second superpower beyond search — they can enumerate their contents in order in linear time, effectively sorting data by building a tree and traversing it.

### Complexity Summary

| Operation | Balanced BST | Degenerate BST (sorted inserts) |
|---|---|---|
| Search | O(log n) | O(n) |
| Insert | O(log n) | O(n) |
| In-order traversal | O(n) | O(n) |

## Definitions

| Term | Definition |
|---|---|
| Binary search tree (BST) | A binary tree where every key in a node's left subtree is smaller and every key in its right subtree is larger than the node's key. |
| Invariant | A property maintained at every node at all times; here, the left-smaller / right-larger ordering rule. |
| Height | The length of the longest path from the root to a leaf; determines the cost of search and insert. |
| Balanced tree | A tree whose height is approximately log n, yielding O(log n) search. |
| Degenerate tree | A tree with height n formed by inserting keys in sorted order; structurally equivalent to a linked list, with O(n) search. |
| In-order traversal | Visiting the left subtree, then the node, then the right subtree; on a BST this yields keys in sorted order. |

## Diagrams & Visual Descriptions

A balanced BST versus a degenerate one (inserting 1, 2, 3, 4, 5 in order):

```
Balanced:                Degenerate (sorted inserts 1..5):

        3                        1
       / \                        \
      2   4                        2
     /     \                        \
    1       5                        3
                                      \
                                       4
                                        \
                                         5

Height ≈ log n  →  O(log n)       Height = n  →  O(n) search
```

Search path illustration — looking for key 4 in the balanced tree visits 3 → 4, ignoring entire subtrees at each step:

```
search(4):  3 (4 > 3, go right)
              \
               4  ✓ found
```

In-order traversal of the balanced tree: 1, 2, 3, 4, 5 — sorted output for free.

## Code Examples

```python
def insert(node, key):
    if node is None:  # Base case: empty spot found — place key here
        return Node(key)
    if key < node.key:  # Key smaller → belongs in left subtree
        node.left = insert(node.left, key)
    else:  # Key >= node key → right subtree
        node.right = insert(node.right, key)
    return node  # Reattach (possibly new) subtree root
```

```python
def search(node, key):
    while node and node.key != key:  # Stop at the key or at None (absent)
        node = node.left if key < node.key else node.right  # Follow one path
    return node  # Either the found node, or None
```

**When/why relevant:** `insert` shows how the invariant is maintained — recursion descends exactly as a search would, so insertion cost equals tree height. `search` shows the iterative version of the same one-path descent, useful for understanding that no backtracking is ever needed.

## Formulas & Algorithms

- Height of a balanced tree: $h \approx \log_2 n$ → search and insert in $O(\log n)$.
- Height of a degenerate tree (sorted-order inserts): $h = n$ → search in $O(n)$.
- Search cost: proportional to the length of the single root-to-target path, i.e., $O(h)$.
- In-order traversal: recursive algorithm `inorder(node) = inorder(left); visit(node); inorder(right)` — produces sorted output in $O(n)$.

## Key Takeaways

- The BST invariant (left smaller, right larger) is a local rule that globally enables one-path search — you never explore a subtree you've ruled out.
- Search *and* insert both cost $O(h)$: the tree's height, not its size, determines performance.
- Balance is everything: a balanced tree gives $O(\log n)$ operations; sorted-order insertion produces a linked-list-like tree with $O(n)$ search.
- The same keys can yield wildly different tree shapes depending on insertion order — a key limitation of plain BSTs.
- In-order traversal yields keys in sorted order, giving BSTs free ordered enumeration.

## Connections

This lecture builds directly on the general idea of using tree height as the driver of algorithmic cost: search and insert are analyzed in terms of one path from the root, and the lecture explicitly contrasts the balanced $O(\log n)$ case with the degenerate $O(n)$ case. The observation that sorted insertion breaks the balance guarantee is the lecture's open problem — it motivates tree structures that maintain balance automatically, which a data structures course would treat next.

The in-order traversal result also connects tree traversal to sorting: the lecture notes that traversing a BST in order yields sorted keys, linking the tree structure to ordering properties that earlier material on sorted data and comparison-based decisions would have motivated.

---
*Sources: CSIT101 Week 4 lecture notes — Binary Search Trees. Version: 1.*
