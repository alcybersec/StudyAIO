# CSIT101 — Week 8: Version Control with Git

## Overview

Git models history as commits with parent pointers and branches as movable pointers. The lecture covers merging, rebasing and the rule against rewriting shared history.

## Key Concepts

### Commits and branches

A commit is a snapshot with a pointer to its parent. A branch is just a movable pointer to a commit, so creating one is cheap.

### Merge

git merge joins histories. If main has not moved Git does a fast-forward and simply moves the pointer; otherwise it creates a merge commit with two parents. A conflict arises when both branches changed the same lines: Git marks them with <<<<<<< and >>>>>>>, you resolve by hand, then commit.

### Rebase and stash

git rebase replays the branch's commits on top of main for a linear history. It rewrites commits, so never rebase commits you have already pushed and others use. git stash saves uncommitted changes aside and git stash pop restores them.

## Definitions

| Term | Definition |
|---|---|
| Commit | Snapshot with a pointer to its parent |
| Branch | Movable pointer to a commit |
| Fast-forward | Moving a pointer when no divergence exists |
| Rebase | Replay commits on a new base, rewriting them |

## Diagrams & Visual Descriptions

```
main:     A --- B --- C
                 \
feature:          D --- E
```
Merging creates a commit with two parents; rebasing replays D and E on top of C.

## Code Examples

```
git switch -c feature      # create and move to a new branch
git add file.py            # stage the change
git commit -m 'add parser' # record a snapshot
git switch main            # go back
git merge feature          # fast-forward or merge commit
git rebase main            # replay commits on main (never on pushed commits)
git stash / git stash pop  # set uncommitted work aside and restore it
```

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Branches are cheap pointers.
- Merge preserves history; rebase rewrites it.
- Never rebase commits that are pushed and shared.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: git_branching.pdf. Version: 1.*
