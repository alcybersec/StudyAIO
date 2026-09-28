"""Summary quality evaluation.

`tests/golden/` checks that a summary has the right *shape* — deliberately, and
correctly, because `.claude/rules/tests.md` forbids asserting on generated text
that varies between runs. The consequence is that nothing measures whether a
summary is any **good**: a prompt change can be an improvement or a regression
and the suite says the same thing either way.

This closes that gap without breaking the rule. It never asserts exact text.
It asks four questions that have stable answers:

* **Coverage** — are the concepts the lecture actually taught present?
* **Fabrication** — does the summary name things the lecture never mentioned?
* **Structure** — does it still follow the format the prompt specifies?
* **Faithfulness** — does it assert anything the source does not support?

The first three are deterministic and free. Only faithfulness needs a model, and
it is optional for exactly that reason.

Deliberately **not** part of CI: it costs money, it is not deterministic, and a
non-deterministic gate is worse than no gate. Run it by hand when a prompt
changes, and compare against the previous run.
"""
