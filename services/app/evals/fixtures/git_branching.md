# CSIT101 — Week 8: Git Branching

## Overview

This week covers Git branching: how Git models history as commits, and how branches let you work on multiple lines of development at once. The core mental model is simple but powerful: a commit is a snapshot with a pointer to its parent, and a branch is just a movable pointer to a commit — which is why creating one is cheap [p.1]. Understanding this makes everything else in the lecture click: merging, rebasing, and stashing are all operations on pointers and commit chains.

Branching matters because real projects need parallel work — you develop a feature on its own branch, then bring it back into the main line. This week explains the mechanics of that workflow: creating and switching branches, merging histories (fast-forward vs. merge commits), resolving conflicts, rewriting history with rebase, and temporarily setting work aside with stash [p.1][p.2][p.3].

## Key Concepts

### The Commit Model

A commit is a snapshot with a pointer to its parent [p.1]. This is the foundation of everything in Git: each commit records the state of the project and links backward to the commit that came before it, forming a chain of history. Because a branch is just a movable pointer to a commit, creating a branch costs almost nothing — Git doesn't copy files, it just creates a new pointer [p.1].

### Creating and Using Branches

The typical workflow is to create a branch, switch to it, commit work, and switch back:

```bash
$ git switch -c feature     # create and move to a new branch
$ git add file.py
$ git commit -m 'add parser'
$ git switch main
```

`git switch -c feature` creates the branch and moves you onto it in one step; you then stage and commit as normal, and `git switch main` returns you to the main line [p.1].

### Merging

`git merge feature` joins the histories of the two branches [p.2]. What happens depends on whether main has moved since the branch was created:

- If main has not moved, Git performs a **fast-forward**: it simply moves the main pointer forward to the branch's latest commit [p.2].
- Otherwise, Git creates a **merge commit with two parents**, tying both lines of history together [p.2].

#### Conflicts

Conflicts happen when both branches changed the same lines. Git marks them with `<<<<<<<` and `>>>>>>>`, and you resolve them by hand, then commit [p.2].

### Rebasing

`git rebase main` replays the branch's commits on top of main, giving a linear history [p.3]. Because it rewrites commits — creating new ones — you should **never rebase commits you have already pushed and others use** [p.3].

### Stashing

`git stash` saves uncommitted changes aside; `git stash pop` restores them [p.3]. This is useful when you need a clean working directory temporarily without committing half-finished work.

## Definitions

| Term | Definition |
|---|---|
| Commit | A snapshot with a pointer to its parent [p.1] |
| Branch | A movable pointer to a commit; creating one is cheap [p.1] |
| Fast-forward merge | When main has not moved, merging just moves the main pointer [p.2] |
| Merge commit | A commit with two parents created when histories have diverged [p.2] |
| Conflict | Occurs when both branches changed the same lines; marked with `<<<<<<<` and `>>>>>>>` [p.2] |
| Rebase | Replays the branch's commits on top of main, giving a linear history [p.3] |
| Stash | Saves uncommitted changes aside; `git stash pop` restores them [p.3] |

## Diagrams & Visual Descriptions

A fast-forward merge — main simply moves its pointer:

```
before:   main
            |
            v
   A <-- B <-- C   (feature)
                ^
                |
              (after fast-forward) main
```

A diverged merge — the merge commit has two parents [p.2]:

```
   A <-- B <-- D   (main)
          \      ^
           \     |
            C <--M   (merge commit, parents B and D)
```

## Code Examples

Creating a branch and committing work on it, then returning to main — the standard branching workflow [p.1]:

```bash
$ git switch -c feature     # create and move to a new branch
$ git add file.py           # stage the changed file
$ git commit -m 'add parser'  # commit a snapshot on the feature branch
$ git switch main           # return to the main branch
```

Conflict markers as Git presents them during a merge [p.2]:

```text
<<<<<<<
your branch's version of the line
=======
```

Relevant whenever you develop a feature in isolation and need to integrate it back into main [p.1][p.2].

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- A commit is a snapshot with a parent pointer; a branch is just a movable pointer to a commit, so branching is cheap [p.1].
- `git merge` fast-forwards if main hasn't moved; otherwise it creates a merge commit with two parents [p.2].
- Conflicts arise when both branches change the same lines — resolve the `<<<<<<<`/`>>>>>>>` markers by hand, then commit [p.2].
- Rebase gives a linear history but rewrites commits, so never rebase pushed commits others use [p.3].
- `git stash` / `git stash pop` let you set uncommitted changes aside and restore them [p.3].

## Connections

This lecture builds directly on Git's commit-based model of history introduced with version control: the parent-pointer structure of commits is what makes fast-forward merges and merge commits possible [p.1][p.2]. The lecture also implicitly connects branching to collaborative workflows — the warning against rebasing pushed commits only makes sense in a setting where multiple people share a repository [p.3].

This lecture does not name any specific other weeks.

---
*Sources: Week 8 lecture slides (pp. 1–3). Version: 1.*
