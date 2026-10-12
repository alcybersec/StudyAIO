# Offline eval baseline

`baseline.json` is the measured starting point for the offline summary gate
(`python -m evals --offline --check`, a required CI job).

## How it was produced

The 21 fixtures in `fixtures/` are real model output, not hand-written text:

```
python -m evals --live --no-judge --save-fixtures
python -m evals --offline --write-baseline --model glm-5.3-flash --date 2026-10-11 --no-judge
```

- model id: `glm-5.3-flash`
- date: 2026-10-11
- judge: off (`--no-judge`); one run per case
- scoring: deterministic (`evals/offline.py`), so the numbers below are exact and repeatable

Provenance is recorded in the `provenance` block of `baseline.json`, not in the fixtures.

Aggregate: faithfulness 0.878, coverage 0.993, structure 90%.

## Gate semantics (regression, not perfection)

`--check` fails when a case's structure is broken now but was OK in the baseline,
when aggregate faithfulness is below baseline minus `threshold` (0.02), or when a
fixture or case is missing or stale. A structure break already recorded in the
baseline is reported as `WARN`. When a fix lands, refresh the fixtures live and
rewrite the baseline so the improvement becomes the new floor.

## Per-case results

| case | faithfulness | coverage | structure |
|---|---|---|---|
| acid_transactions | 1.00 | 100% | BROKEN |
| big_o_notation | 1.00 | 100% | ok |
| binary_search_trees | 0.50 | 100% | ok |
| deadlock | 1.00 | 100% | ok |
| dijkstra_shortest_paths | 0.80 | 100% | ok |
| dns_resolution | 1.00 | 100% | ok |
| dp_knapsack | 0.40 | 100% | ok |
| finite_automata | 0.80 | 100% | ok |
| git_branching | 1.00 | 100% | ok |
| graph_traversal | 1.00 | 100% | ok |
| hash_tables | 1.00 | 100% | ok |
| http_caching | 1.00 | 100% | ok |
| memory_hierarchy | 0.83 | 100% | BROKEN |
| normalisation | 1.00 | 100% | ok |
| process_scheduling | 1.00 | 100% | ok |
| rsa_public_key | 0.50 | 86% | ok |
| sorting_algorithms | 0.60 | 100% | ok |
| sql_joins | 1.00 | 100% | ok |
| stacks_queues | 1.00 | 100% | ok |
| tcp_congestion | 1.00 | 100% | ok |
| virtual_memory | 1.00 | 100% | ok |

## Targets for GL#34 (slide citations / faithfulness)

Weakest faithfulness:

- `dp_knapsack` 0.40: calls the method greedy (forbidden claim) and omits the W=5 worked example.
- `binary_search_trees` 0.50: claims the tree rebalances itself (forbidden claim).
- `rsa_public_key` 0.50: omits the factoring-hardness rationale, the toy example (n=33) and the 4 -> 31 -> 4 round trip.
- `sorting_algorithms` 0.60: omits the merge sort and quicksort complexity/stability facts.

Broken structure (both: the `---` / `*Sources: ... Version: N.*` footer is missing):

- `acid_transactions`
- `memory_hierarchy` (also misses the AMAT formula, faithfulness 0.83)

Also below 1.0: `dijkstra_shortest_paths` 0.80, `finite_automata` 0.80.

## GL#34 iteration 2 (prompt v2.4, scorer normalisation)

The live v2.3 run (21 summaries, production model) scored faithfulness 0.905
and citation coverage 81%. Reading the outputs showed most "dropped" facts were
present but typeset: the recurrence, `c = m^e mod n`, the toy numbers and the
AMAT formula as LaTeX (`$$c = m^e \bmod n$$`), `quicksort is **not** stable`
with emphasis, "breaking any single one" for "any one". `evals/scoring.py`
now normalises LaTeX and emphasis markup before matching (it never adds or
reorders content; `m^d` still does not satisfy `m^e`), and two phrasing-bound
facts in `deadlock` and `finite_automata` accept the inflections the model
actually used. Re-scored with this scorer:

| fixtures | faithfulness |
|---|---|
| committed baseline (v2.2 output) | 0.878 -> 0.943 |
| live v2.3 output | 0.905 -> 1.000 |

So the like-for-like improvement from v2.2 to v2.3 is 0.943 -> 1.000, and the
gaps v2.3 really has are structural: `dijkstra_shortest_paths` lost its `---`
footer separator, and Key Concepts citation coverage is 81% (target 90%; the
uncited lines are lead-ins, numbered steps, table rows, formula and code
bullets). v2.4 targets those two, keeps formulas in plain text (LaTeX does not
render in the UI), and passes a `must_keep` checklist of formula and
worked-example lines detected from the extraction. `baseline.json` is not
rewritten until the v2.4 fixtures are measured live.
