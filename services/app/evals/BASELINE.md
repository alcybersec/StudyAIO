# Offline eval baseline

`baseline.json` is the measured starting point for the offline summary gate
(`python -m evals --offline --check`, a required CI job).

## How it was produced

The 21 fixtures in `fixtures/` are real model output, not hand-written text.
They are the **run 1** outputs of a two-run live eval (post footer normaliser,
i.e. what users get):

```
python -m evals --live --no-judge --temperature 0.2 -n 2 --save-fixtures   # into a scratch dir
python -m evals --offline --write-baseline --model glm-5.3-flash --date 2026-10-12 --no-judge \
    --provenance "prompt=summarize v2.5" --provenance temperature=0.2 \
    --provenance runs=2 --provenance chosen_run=1
```

- model id: `glm-5.3-flash`
- date: 2026-10-12
- prompt: summarize v2.5, summary temperature 0.2
- judge: off (`--no-judge`); 2 runs per case, run 1 committed
- scoring: deterministic (`evals/offline.py`), so the numbers below are exact and repeatable

Run 1 was committed rather than the better run on purpose: it is the honest
sample, and it includes the `dp_knapsack` slip described below. Provenance is
recorded in the `provenance` block of `baseline.json`, not in the fixtures.

Committed (run 1) aggregate: faithfulness 0.967, coverage 100%, structure 100%,
Key Concepts citation coverage 90.2%.

## Gate semantics (regression, not perfection)

`--check` fails when:

- a case's structure is broken now but was OK in the baseline (a break the
  baseline already records is a `WARN`);
- aggregate faithfulness is below baseline minus `threshold` (0.02);
- Key Concepts citation coverage (mean over cases) is below
  `max(0.90, baseline - 0.05)`. The 0.90 is the GL#34 bar; the relative term
  stops a quiet slide from a higher baseline. With the current baseline (0.9025)
  the absolute 0.90 is the binding floor, which leaves almost no headroom: a
  prompt change that costs citations must be fixed or the baseline consciously
  refreshed. A baseline without a citation figure skips this check;
- a fixture or case is missing or stale.

When a fix lands, refresh the fixtures live and rewrite the baseline so the
improvement becomes the new floor.

## Known exception: dp_knapsack (GL#34 closed with it)

Run 1 of `dp_knapsack` scores faithfulness 0.50: the Overview
brings up a "greedy" strategy by name, which the lecture never does. It
disclaims it ("that greedy idea is not part of this lecture's solution"), but
the term is outside material the source does not contain, and the check counts
the mention. Run 2 of the same case scores
1.00, so this is sampling variance at temperature 0.2, not a fixed prompt
defect; across the two runs the case mean is 0.75, under the 0.80 per-target
bar. The slip is a bridge phrase to a topic the source does not contain, the
class v2.5 bans by name; it reduced the rate but did not remove it.

Decision (docs/decisions.md, 2026-10-12): GL#34 is closed with this recorded as
a known exception and the case stays in the eval. It stays visible on purpose:
the committed fixture is the failing run, `dp_knapsack` keeps its 0.50 entry in
`baseline.json`, and every offline report prints it as `WARN ... forbidden claim:
greedy`. It is not excluded, relaxed or hidden. A later prompt or model change
that removes it will show as an improvement when the baseline is refreshed.

## Per-case results (v2.5 @ 0.2, glm-5.3-flash, 2026-10-12)

Committed run 1, plus the two-run view. "cited" is Key Concepts citation
coverage.

| case | faithfulness (run1) | runs | mean | coverage | structure | cited (run1) | cited (mean) |
|---|---|---|---|---|---|---|---|
| acid_transactions | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 100% |
| big_o_notation | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 93% | 87% |
| binary_search_trees | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 70% | 85% |
| deadlock | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 80% | 90% |
| dijkstra_shortest_paths | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 100% |
| dns_resolution | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 100% |
| dp_knapsack | 0.50 | 0.50, 1.00 | 0.75 | 100% | ok | 71% | 85% |
| finite_automata | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 88% | 69% |
| git_branching | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 89% | 94% |
| graph_traversal | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 100% |
| hash_tables | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 90% | 89% |
| http_caching | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 92% | 89% |
| memory_hierarchy | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 83% | 86% |
| normalisation | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 95% |
| process_scheduling | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 82% | 91% |
| rsa_public_key | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 90% | 84% |
| sorting_algorithms | 0.80 | 0.80, 1.00 | 0.90 | 100% | ok | 94% | 91% |
| sql_joins | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 100% | 100% |
| stacks_queues | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 94% | 85% |
| tcp_congestion | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 93% | 93% |
| virtual_memory | 1.00 | 1.00, 1.00 | 1.00 | 100% | ok | 88% | 90% |
| **aggregate** | **0.967** | per-run 0.967, 1.000 | **0.983** | 100% | 100% | **90.2%** | **91%** |

Two cases lost a point in run 1: `dp_knapsack` (the exception above) and
`sorting_algorithms` (0.80, the quicksort average/worst/stability fact missing;
present in run 2). No run has a broken footer.

## History (GL#34)

All on `glm-5.3-flash`, no judge, deterministic scoring.

| step | prompt | faithfulness | Key Concepts citation | notes |
|---|---|---|---|---|
| first baseline | v2.2 | 0.878 | not measured | weak: `dp_knapsack` 0.40, `binary_search_trees` 0.50, `rsa_public_key` 0.50, `sorting_algorithms` 0.60; footer missing in `acid_transactions` and `memory_hierarchy` |
| same output, scorer fixed | v2.2 | 0.943 | not measured | the scorer now normalises LaTeX and emphasis markup; no content change |
| live | v2.3 | 0.905 (1.000 with the fixed scorer) | 81% | outside-material leaks gone; `dijkstra_shortest_paths` lost its footer separator |
| live | v2.4 | 0.952 | 89% | formulas and worked examples kept; two bridge-phrase slips returned (`dp_knapsack` "greedy", `binary_search_trees` "self-balancing") |
| live, 2 runs | v2.5 @ temperature 0.2 (prompt v2.5 also repairs the footer and bans bridge phrases) | 0.967 / 1.000 per run, **mean 0.983** | **91%** | this baseline; 0 broken footers; `dp_knapsack` run 1 0.50 |

The scorer fix (v2.2 0.878 -> 0.943) is why early and late numbers must be read
like-for-like: `evals/scoring.py` now normalises LaTeX and emphasis markup
before matching (it never adds or reorders content; `m^d` still does not satisfy
`m^e`), and two phrasing-bound facts in `deadlock` and `finite_automata` accept
the inflections the model actually used.

## Targeted generation (weak-spot engine, M33-S2-AI-021, live baseline M33-S2-AI-056)

`targeted_baseline.json` is the baseline for the offline targeted-generation gate.
`python -m evals --offline --check` (the required CI job) runs it after the summary
gate; `python -m evals --offline --targeted --check` runs it alone.

**Provenance: live.** The 12 stored generations in `targeted_fixtures/` are real
model output from `python -m evals --live --targeted --save-fixtures`, run
2026-10-15 on the production model `glm-5.3-flash` with the targeted prompts
`generate_targeted_quiz.txt` / `generate_targeted_flashcards.txt` (v1.0). The
summary temperature setting does not apply to this run. The baseline's
`provenance` is `{source: live, model: glm-5.3-flash, date: 2026-10-15,
prompt: generate_targeted v1.0}`. This replaces the earlier hand-written fixtures.

The 12 cases in `targeted_cases/` (a synthetic lecture week borrowed from
`cases/`, weak topics, the stems the student already has) are unchanged. Each
live fixture holds five items, and every item carries `expect: keep`: the model
planted no near-duplicate of an existing stem and cited no page the lecture lacks,
so the live run exercises the filter's *keep* path only. Dedup (1.000) and filter
accuracy (1.000) are therefore trivially met on these fixtures; the duplicate and
uncited drop rules are covered by the unit tests in `tests/unit/test_eval_targeted.py`
and `tests/unit/pipeline/`, not by this run.

Live scores (aggregate): on-topic 0.950, citation validity 0.983, dedup 1.000,
filter accuracy 1.000.

| case | kind | kept | on-topic | citation | dedup | filter |
|---|---|---|---|---|---|---|
| acid_isolation_durability | quiz | 5 | 0.80 | 1.00 | 1.00 | 1.00 |
| big_o_growth_loops | flashcards | 5 | 0.80 | 1.00 | 1.00 | 1.00 |
| bst_degenerate_inorder | flashcards | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| deadlock_conditions | flashcards | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| dijkstra_relaxation | quiz | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| dns_resolution_steps | flashcards | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| hash_tables_open_addressing | quiz | 5 | 1.00 | 0.80 | 1.00 | 1.00 |
| process_round_robin_sjf | quiz | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| sql_left_join_group_by | quiz | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| stacks_queues_implementation | flashcards | 5 | 0.80 | 1.00 | 1.00 | 1.00 |
| tcp_slow_start_reno | flashcards | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| virtual_memory_faults_replacement | quiz | 5 | 1.00 | 1.00 | 1.00 | 1.00 |

Three cases have one off-topic item out of five (`acid_isolation_durability`,
`big_o_growth_loops`, `stacks_queues_implementation`): the item mentions no term
of the student's weak topics.

**The one citation miss.** In `hash_tables_open_addressing` the first quiz item
asks why an open addressing table can degrade to O(n) lookup and cites page 1.
Page 1 does state the O(n) worst case for a bad hash function, but it never uses
a weak-topic term (open addressing, probing, clustering, load factor, rehash); the
topic terms live on pages 2 and 3. The scorer requires the cited page to contain a
term the item mentions, so it counts the item as unsupported (4 of 5 supported,
0.80). Whether that is a wrong page or a right page the term check cannot see is a
judgement the scorer does not make; it is reported, not hidden.

**The bars** (`evals/targeted.py`), checked on the aggregate: on-topic >= 0.80,
citation validity >= 0.95, dedup >= 0.95, and no aggregate (on-topic, citation
validity, dedup, filter accuracy) more than 0.02 below this baseline. The citation
bar used to be exactly 1.00. It was relaxed on 2026-10-15 (`docs/decisions.md`)
because the in-lecture page filter (`app/pipeline/targeted_items.py`) already
guarantees that every kept item cites a page that exists in the lecture; whether
that page is the *best* one cannot be enforced by a filter, so a model that is
right about the content but loose about the page is not treated as a defect. A
fixture set at 0.94 fails the gate; at 0.95 it passes.

Refresh the baseline, as an operator:

```
python -m evals --live --targeted --save-fixtures        # costs AI calls; review the `expect` labels
python -m evals --offline --targeted --write-baseline --model <model id> --date <YYYY-MM-DD> \
    --provenance "prompt=generate_targeted v1.0"
```
