# Prior Work and Positioning

How this project relates to existing evaluation benchmarks and tools.

## Spider 2.0 (Lei et al., ICLR 2025)

Evaluates whether language models can write correct SQL against enterprise databases. 632 tasks, execution-based comparison. Tests model capability at SQL generation across diverse databases.

**Where it stops:** Operates on raw schemas, not governed semantic layers. Does not touch interpretation or synthesis. Tests whether a model *can* write SQL, not whether a deployed agent *does* answer a specific team's questions correctly.

**Our relationship:** We share the result-comparison mechanism but apply it to governed semantic layers and add the interpretation dimension.

## ADE-bench (Stancil, dbt Labs)

Evaluates whether coding agents can complete data engineering tasks in dbt projects, graded by dbt tests.

**Where it stops:** Tests the builder, not the analyst. A coding agent that passes ADE-bench may still power an analytics agent that gives wrong answers.

**Our relationship:** Complementary. They test whether agents can build data infrastructure. We test whether agents answer questions correctly on top of that infrastructure.

## Hex Shoebox / Shorelane Commerce (Miller, Hex)

Internal evaluation lab with a synthetic business, pairwise experiment comparison, and LLM-judged evaluation at product scale.

**Where it stops:** Internal to Hex. Not open-source. Requires dedicated engineering resources to build and maintain a synthetic business.

**Our relationship:** We provide an open, forkable alternative at practitioner scale.

## Anthropic internal analytics

Describes evaluation of their internal analytics agent, including offline evals and correction harvesting. Honest about interpretation validation relying on human judgment.

**Our relationship:** Our synthesis methodology aligns with their human-in-the-loop posture. We apply their principles at consulting scale.

## Where our contribution sits

The structured evaluation (layered result comparison, LLM judge fallback) is conceptually shared with Spider 2.0's execution-based approach, adapted to governed semantic layers and packaged as a practical, forkable tool.

The synthesis evaluation methodology (expert-anchored validation, automate-vs-human criteria, honest treatment of limits) is genuinely novel. No published benchmark addresses it, because it cannot be benchmarked. Documenting the methodology clearly, including its limits, is the contribution.