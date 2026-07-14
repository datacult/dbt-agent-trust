# Building and Evaluating Trusted Data Agents on dbt

A complete, open-source reference for building a governed analytics agent on the dbt semantic layer and evaluating whether its answers are trustworthy before they reach your stakeholders.

Built by [Data Culture](https://www.datacult.com) as part of the inaugural [dbt Champions](https://www.getdbt.com/community/dbt-champions) cohort.

---

## The problem

Teams can stand up AI analytics agents quickly. The hard part is not building one. The hard part is answering two questions before you put it in front of your stakeholders:

1. **Is it getting the right numbers?** Many different SQL queries return the same correct result, so comparing query text tells you nothing. You need to compare actual results, and you need to handle the real-world messiness of column-name differences, ordering differences, and precision differences without penalising genuinely correct answers.

2. **Is its interpretation sound?** Once an agent moves beyond answering individual questions and starts synthesizing, interpreting, and rendering a verdict on what the data means, there is often no single correct answer to compare against. That layer is fundamentally harder to evaluate, and most published benchmarks do not attempt it.

This repo provides a working solution to the first problem and an honest, documented methodology for the second.

## What this repo contains

Two complementary halves, built by two dbt Champions, in one forkable repository:

**The Metric Agent Playbook** [David Effiong](https://www.linkedin.com/in/david-effiong/): How to build a governed data agent on the dbt semantic layer, from semantic model design to connecting an LLM that queries governed metrics. The construction side.

**Trust by Design** [Opeyemi Fabiyi](https://www.linkedin.com/in/opeyemifabiyi/): How to evaluate whether that agent's answers are correct, using layered result comparison and an LLM-as-judge fallback. Plus an honest methodology for the interpretation layer that automated evaluation cannot reach. The verification side.

One teaches how to build. The other teaches how to know it works. Together they cover the full lifecycle a practitioner needs.

A third piece makes both halves runnable end to end: the agent layer connecting an LLM to the dbt semantic layer via MCP, built by [Joseph Ojo](https://www.linkedin.com/in/ojofemijoseph/). Without it, the playbook and the evaluation framework would have nothing to build on and nothing to test.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        PUBLIC DATASET                            │
│                    (DuckDB, public data)                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    1. DATA FOUNDATION                            │
│                                                                  │
│  dbt project: staging models, marts (fact + dimension tables),   │
│  tests, documentation. The governed layer the agent builds on.   │
│                                                                  │
│                                                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    2. SEMANTIC LAYER                              │
│                                                                  │
│  Metric definitions, dimensions, entities, relationships.        │
│  MetricFlow YAML or dbt agent schema. The governed contract      │
│  that defines what the agent is allowed to query and how.        │
│                                                                  │
│                                                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    3. AGENT LAYER                                 │
│                                                                  │
│  Natural language question                                       │
│       │                                                          │
│       ▼                                                          │
│  Claude (or any LLM) + dbt MCP server                            │
│       │                                                          │
│       ▼                                                          │
│  Queries governed metrics via the semantic layer                 │
│       │                                                          │
│       ▼                                                          │
│  Returns: answer + SQL + result                                  │
│                                                                  │
│                                                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    4. EVALUATION LAYER                            │
│                                                                  │
│  Golden questions (curated, validated)                            │
│       │                                                          │
│       ▼                                                          │
│  Run each through the agent, capture output                      │
│       │                                                          │
│       ▼                                                          │
│  LAYER 1: Deterministic comparison                               │
│  ┌─────────────┐   ┌──────────────────┐   ┌───────────────────┐ │
│  │ Strict match │──▶│ Column-tolerant  │──▶│ Approximate match │ │
│  │ (exact)      │   │ (name/order)     │   │ (numeric tol.)    │ │
│  └──────┬───────┘   └───────┬──────────┘   └────────┬──────────┘ │
│         │ pass              │ pass                   │ pass       │
│         ▼                   ▼                        ▼            │
│       PASS                PASS                     PASS           │
│                                                                   │
│  All stages fail?                                                 │
│         │                                                         │
│         ▼                                                         │
│  LAYER 2: LLM-as-judge                                            │
│  ┌─────────────────────────────────────────────┐                  │
│  │ "Do these results answer the same business  │                  │
│  │  question with the same information?"       │                  │
│  │  PASS / FAIL + one sentence justification   │                  │
│  └─────────────────────────────────────────────┘                  │
│         │                                                         │
│         ▼                                                         │
│  SCORECARD (per question + aggregate)                             │
│                                                                   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    5. SYNTHESIS METHODOLOGY                      │
│                    (documentation, not code)                      │
│                                                                  │
│  For interpretation/synthesis evaluation where no single         │
│  correct answer exists:                                          │
│                                                                  │
│  - Decision criteria: when to automate vs. when to keep human    │
│  - Expert-anchored validation: test against the expert's own     │
│    past analyses before rollout                                  │
│  - Correction loop: harvest expert feedback, update framework    │
│  - Honest limits: what this approach catches and what it cannot  │
│                                                                  │
│  Owner: Opeyemi                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Who this is for

- **Data and analytics engineers** who have built (or are building) an agent on dbt and need to know whether to trust it
- **Team leads** deciding whether an agent is ready to put in front of stakeholders
- **Practitioners** looking for a concrete, forkable starting point for evaluation rather than a conceptual framework

## How to use this repo

### Option A: Run the full system

Clone the repo, set up the dbt project, run the agent against the golden questions, and evaluate the results. This gives you a working example of the build-and-evaluate lifecycle on public data.

### Option B: Fork and adapt

Replace the dbt project with your own, write golden questions for your domain, and run the evaluation against your agent. The evaluation framework is designed to work with any dbt project and any agent that produces SQL and results.

### Option C: Read the methodology

If you already have an agent and evaluation in place, the `docs/` directory covers the harder questions: how to craft golden questions that actually test the agent, when to automate evaluation versus when to rely on human judgment, and how to handle the synthesis layer.

## Repo structure

```
dbt-agent-trust/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
│
├── dbt_project/                       THE METRIC AGENT PLAYBOOK (David)
│   ├── models/
│   │   ├── staging/                   Source cleanup and standardisation
│   │   └── marts/                     Business-ready fact and dimension tables
│   ├── semantic_layer/                Governed metrics, dimensions, entities
│   ├── tests/                         Data quality assertions
│   ├── dbt_project.yml
│   └── README.md                      Build guide: decisions, tradeoffs, patterns
│
├── agent/                             AGENT LAYER (Joe)
│   ├── agent.py                       Sends questions to the LLM via dbt MCP
│   ├── run_golden_set.py              Batch runner for all golden questions
│   ├── config.yaml
│   └── README.md                      Setup, output format, architecture notes
│
├── golden_questions/                  GOLDEN QUESTIONS (David + Opeyemi)
│   ├── questions.yaml                 Curated questions with expected SQL and results
│   ├── expected_results/              Pre-computed expected results (one file per question)
│   └── README.md                      How to craft good golden questions
│
├── evaluation/                        TRUST BY DESIGN (Opeyemi)
│   ├── run_eval.py                    Orchestrator: loads outputs, runs comparison, produces results
│   ├── comparison.py                  Layered deterministic comparison
│   ├── judge.py                       LLM-as-judge fallback
│   ├── judge_prompt.txt               Judge prompt template
│   ├── scorecard.py                   Human-readable scorecard generator
│   ├── results/                       Output scorecards (gitignored)
│   └── README.md                      How the evaluation works, scope and limits
│
└── docs/                              METHODOLOGY AND CONTEXT
    ├── synthesis_evaluation.md        The interpretation evaluation methodology
    ├── decision_criteria.md           When to automate vs. when to keep human
    ├── golden_question_guide.md       Detailed guide to writing effective golden questions
    └── prior_work.md                  Positioning vs. Spider 2.0, ADE-bench, Hex, Anthropic
```

## Getting started

### Prerequisites

- Python 3.10+
- [dbt-core](https://docs.getdbt.com/docs/core/installation-overview) with the DuckDB adapter
- An Anthropic API key (for the agent and the LLM judge)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Quick start

```bash
# Clone
git clone https://github.com/datacult/dbt-agent-evaluation.git
cd dbt-agent-evaluation

# Set up environment
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY

# Build the data foundation
cd dbt_project
dbt deps && dbt build
cd ..

# Run golden questions through the agent
python agent/run_golden_set.py

# Evaluate
python evaluation/run_eval.py

# View the scorecard
python evaluation/scorecard.py
```

## How this relates to existing work

Detailed positioning is in `docs/prior_work.md`. The short version:

| Project | What it evaluates | Our relationship |
|---|---|---|
| [Spider 2.0](https://spider2-sql.github.io/) | Whether models can write correct SQL against enterprise databases | We share the result-comparison concept but apply it to governed semantic layers and add the interpretation dimension |
| [ADE-bench](https://github.com/dbt-labs/ade-bench) | Whether coding agents can complete dbt engineering tasks | Complementary: they test the builder, we test the analyst |
| [Hex Shoebox](https://hex.tech/blog/evaluate-data-agents/) | Internal product evaluation with a synthetic business at scale | We provide an open, forkable alternative at practitioner scale |
| [Anthropic analytics](https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude) | Internal analytics agent evaluation and context management | Our synthesis methodology aligns with their human-in-the-loop posture |

## A note on scope

This is an educational reference implementation, not a production evaluation system.

A production system would include additional scoring dimensions, domain-specific calibrated judge prompts, regression detection, monitoring infrastructure, and automated alerting. Those are outside the scope of this reference.

Our goal is to provide a clear, forkable starting point that teaches the approach well enough for a practitioner to understand it, run it on their own data, and build on it.

## Contributors

| Person | Role | Layers |
|---|---|---|
| **David Effiong** | dbt Champion, Data Culture | Data foundation, semantic layer, golden questions |
| **Joseph Ojo** | Engineer, Data Culture | Agent layer, MCP integration |
| **Opeyemi Fabiyi** | dbt Champion, Data Culture | Evaluation framework, synthesis methodology, golden questions |

## Part of the dbt Champions program

This project is the joint Big Project from Data Culture's two members of the inaugural dbt Champions cohort and Joseph, a Senior Data Engineer at Data Culture:

- **David Effiong** — *The Metric Agent Playbook*: building governed data agents on the dbt semantic layer
- **Opeyemi Fabiyi** — *Trust by Design*: evaluating whether those agents are trustworthy

Two halves of one system. Built together, published together.

## License

Apache 2.0

## Contact

- Opeyemi Fabiyi: [LinkedIn](https://linkedin.com/in/opeyemifabiyi)
- David Effiong: [LinkedIn](https://linkedin.com/in/davideffiong) | [YouTube](https://youtube.com/@daviddata)
- Data Culture: [hello@datacult.com](mailto:hello@datacult.com) | [datacult.com](https://www.datacult.com)
