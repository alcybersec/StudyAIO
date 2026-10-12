# CSIT101 — Week 8: Git Branching

## Overview

Week 8 introduces **branching**, one of Git's most powerful and most misunderstood features. Until now you may have treated a Git repository as a single timeline of commits. Branching breaks that mental model: it lets you have multiple parallel timelines, each capturing a different line of development — a new feature, a bug fix, an experiment — all coexisting in the same repository.

The key insight of this lecture is that branching in Git is *cheap*. Unlike older version control systems that copied entire directories to create a branch, a Git branch is nothing more than a small movable pointer to a commit. This design choice explains almost everything else in the lecture: why creating branches costs essentially nothing, why merging can be a simple pointer move (fast-forward) or a genuine combination of histories (merge commit), and why rebasing, which rewrites commits, must be handled with care once work is shared.

## Key Concepts

### Commits: Snapshots with Lineage

A **commit** is a snapshot of your project at a point in time, together with a pointer to its parent commit (or parents, in the case of a merge). This parent pointer is what gives a repository its history: following parent pointers backwards from any commit reconstructs the entire chain of changes leading to it. Understanding commits as "snapshot + parent pointer" is the foundation for everything else — branches, merges, and rebases are all just operations on these pointers.

### Branches: Cheap, Movable Pointers

A **branch** is just a movable pointer to a commit — nothing more. Creating one does not copy files or duplicate history; it simply writes a 41-byte file containing a commit hash. This is why the lecture emphasises that "creating one is cheap": you should feel free to branch for every feature, experiment, or fix without worrying about cost.

In practice, the workflow looks like this:

1. Create and switch to a new branch (e.g. `feature`).
2. Stage and commit work on it — the branch pointer advances with each commit.
3. Switch back to `main`, where the branch pointer has not moved.

While `main` and `feature` both point into the shared history, the commits you make on `feature` advance only the `feature` pointer; `main` is untouched.

### Merging: Joining Histories

**`git merge feature`** integrates the work from `feature` back into your current branch. What happens depends on where the branch pointers sit:

#### Fast-forward merges

If `main` has **not moved** since `feature` branched off, Git performs a *fast-forward*: it simply moves the `main` pointer forward to the tip of `feature`. No new commit is created — there is nothing to combine, because `main` has no commits that `feature` lacks. This is the simplest and cleanest outcome.

#### Merge commits

If both branches have diverged — `main` has its own commits and `feature` has its own — Git cannot just move a pointer. Instead it creates a **merge commit**: a special commit with *two parents*, one on each branch, that represents the combined state. This is how the two histories get joined back into one.

#### Conflicts

A **conflict** occurs when both branches changed the *same lines* of a file. Git cannot decide which change to keep, so it pauses the merge and marks the disputed region directly in the file:

```
<<<<<<< HEAD
changes from your current branch
=======
changes from the incoming branch
>>>>>>> feature
```

You resolve the conflict **by hand** — edit the file to the version you actually want — then stage and commit to complete the merge. Conflicts are normal, not errors; they are simply Git asking you to make a decision it cannot make for you.

### Rebasing: Rewriting History for Linearity

**`git rebase main`** takes the commits on your current branch and *replays* them on top of `main`. Instead of creating a merge commit with two parents, rebasing produces a **linear history** — a single straight line of commits with no branching visible.

The critical caveat: rebasing **rewrites commits**, creating brand-new ones with new hashes. The original commits still exist but your branch now points to new replacements. The consequence is the golden rule from the lecture: **never rebase commits you have already pushed and that others are using.** If colleagues have built on the old commits, rewriting them leaves everyone with two divergent versions of history that must be painfully reconciled. Rebase freely on private, local branches; avoid it on shared, published ones.

### Stashing: Parking Uncommitted Work

**`git stash`** saves your uncommitted changes aside, giving you a clean working directory — useful when you need to switch branches but aren't ready to commit. **`git stash pop`** restores those changes afterwards. Think of it as a clipboard for work-in-progress: changes are safely stored but not yet part of any branch's history.

### Comparison: Merge vs. Rebase

| Aspect | `git merge` | `git rebase` |
|---|---|---|
| Result | Merge commit with two parents (unless fast-forward) | Linear history |
| History | Preserves actual branching | Rewritten as a straight line |
| Rewrites commits? | No | Yes — creates new commits |
| Safe on pushed/shared commits? | Yes | **No** — never rebase pushed commits others use |
| When conflicts occur | Same lines changed on both branches | Same, resolved commit by commit during replay |

## Definitions

| Term | Definition |
|---|---|
| Commit | A snapshot of the project with a pointer to its parent commit(s). |
| Branch | A movable pointer to a commit; cheap to create. |
| Fast-forward merge | A merge where Git simply moves the branch pointer forward because the target branch hasn't diverged. |
| Merge commit | A commit with two parents that joins two diverged histories. |
| Conflict | Occurs when both branches changed the same lines; Git marks it with `<<<<<<<` / `>>>>>>>` and requires manual resolution. |
| Rebase | Replays a branch's commits on top of another branch, producing a linear history by rewriting commits. |
| Stash | Saves uncommitted changes aside; `git stash pop` restores them. |

## Diagrams & Visual Descriptions

**Fast-forward merge** — `main` simply catches up:

```
Before:
main ──┐
       A───B───C───D
           └─feature (D is feature's tip; main still at B)

After `git merge feature` (fast-forward):
main, feature ──► A───B───C───D
(no new commit: main pointer just moved to D)
```

**Diverged branches → merge commit:**

```
          C───D   (feature)
         /
A───B───E───F     (main also moved)

After merge:
          C───D
         /     \
A───B───E───F───M   (M = merge commit, two parents: F and D)
```

**Rebase produces a linear history:**

```
Before:  A───B───E───F (main)
              └C───D   (feature)

After `git rebase main` on feature:
A───B───E───F───C'───D'   (C', D' are NEW commits with new hashes)
```

## Code Examples

Creating a branch and committing work on it:

```bash
$ git switch -c feature     # create branch "feature" and move to it
$ git add file.py           # stage changes for commit
$ git commit -m 'add parser'  # commit; the feature pointer advances
$ git switch main           # return to main (untouched by feature work)
```

*Merge* — run from the branch you want to receive the changes:

```bash
$ git merge feature
# Fast-forward if main hasn't moved; otherwise creates a merge commit.
# On conflict: edit files between <<<<<<< / >>>>>>>, then add + commit.
```

*Rebase* — replay your branch's commits on top of main:

```bash
$ git rebase main
# Gives a linear history by rewriting commits — only safe for
# commits you have NOT pushed and shared.
```

*Stash* — temporarily park uncommitted changes:

```bash
$ git stash       # save uncommitted changes aside
$ git stash pop   # restore them later
```

## Formulas & Algorithms

No formulas in this lecture. The main "algorithmic" idea is the merge decision: *if the target branch has not moved → fast-forward (move the pointer); otherwise → create a two-parent merge commit (resolving conflicts if the same lines changed on both branches).*

## Key Takeaways

- A branch is just a movable pointer to a commit — branching is cheap, so branch freely.
- Commits are snapshots linked by parent pointers; this structure underlies all Git history operations.
- A fast-forward merge is just a pointer move; a real merge creates a two-parent commit.
- Conflicts arise when both branches edit the same lines; Git marks them and you resolve by hand, then commit.
- Rebase gives a linear history but rewrites commits — never rebase pushed commits others rely on.
- `git stash` / `git stash pop` lets you set uncommitted work aside and restore it later.

## Connections

This lecture sits within a single continuous thread on Git: it builds directly on the notion of commits as snapshots, extending the single-line history view into branching, merging, and rebasing. The lecture itself raises the shared-workflow consequence of rebasing ("commits you have already pushed and others use"), pointing toward collaborative use of repositories where multiple people's histories interact.

No other weeks were named in this lecture, so no specific cross-week links can be drawn.

---
*Sources: CSIT101 Week 8 lecture notes — Git Branching. Version: 1.*
