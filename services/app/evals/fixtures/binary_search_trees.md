# CSIT101 — Week 4: Binary Search Trees

## Overview

A binary search tree orders keys so search and insertion follow a single root-to-leaf path. The lecture shows the code and the one way it fails: a degenerate tree.

## Key Concepts

### The invariant

Every key in the left subtree is smaller than the node and every key in the right subtree is larger. Search and insert follow one path from the root, so their cost is the height of the tree.

### Cost depends on shape

A balanced tree has height about log n, so search is O(log n). Inserting keys in sorted order builds a degenerate tree, effectively a linked list, with height n and O(n) search.

### Traversal

In-order traversal visits the left subtree, the node, then the right subtree, and yields the keys in sorted order.

## Definitions

| Term | Definition |
|---|---|
| BST invariant | Left subtree keys are smaller, right subtree keys larger |
| Height | Length of the longest root-to-leaf path |
| Degenerate tree | A tree shaped like a linked list, height n |
| In-order traversal | Left, node, right: visits keys in sorted order |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

```python
def insert(node, key):
    if node is None:  # empty spot found: create the node
        return Node(key)
    if key < node.key:  # smaller keys go left
        node.left = insert(node.left, key)
    else:  # larger keys go right
        node.right = insert(node.right, key)
    return node


def search(node, key):
    while node and node.key != key:  # follow one path down
        node = node.left if key < node.key else node.right
    return node
```
Insert recurses to the empty position; search loops down one path, so both cost the tree height.

## Formulas & Algorithms

Balanced: height ~ log n, search O(log n). Degenerate: height n, search O(n).

## Key Takeaways

- Every BST operation costs the height.
- Sorted-order inserts give a degenerate tree with O(n) search.
- In-order traversal returns sorted keys.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: binary_search_trees.pdf. Version: 1.*
