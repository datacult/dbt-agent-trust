# Golden Question Curation Guide

## Why this matters

The evaluation pipeline is only as good as the questions it tests. A poorly written golden question produces misleading eval results in two ways: a vague question lets the agent answer differently each time, making failures look like accuracy problems when they're actually ambiguity problems. A wrong expected SQL produces false negatives, making you chase fixes for answers that were already correct.

Every golden question should pass a simple test: if you gave this question to two different analysts on the team, would they write the same SQL to get the required result? If not, the question needs to be more specific.

## What makes a good golden question

A good golden question has four properties:

### 1. Specific enough that only one correct answer exists

Bad: "How is the marketplace doing?" This is open to interpretation. Does "doing" mean GMV? Order volume? Customer growth? Delivery performance? Two analysts would write completely different queries.

Good: "What was total GMV for Q1 2018?" One answer. One query. No ambiguity.

### 2. Uses the same language a real stakeholder would use

Good: "What percentage of orders were delivered late last quarter?" This is how an operations lead would actually ask. The agent should be able to translate this into the right SQL without the user knowing the column names or how "late" is defined in the data model.

### 3. Includes enough context to remove ambiguity without over-specifying

There's a balance. The question should be specific enough that the expected answer is deterministic, yet natural enough to test the agent's ability to interpret business language.

Too vague: "Show me revenue." (Which revenue metric? Which time period? Which segment? GMV or TOV?)

Too specific: "Show me the SUM of gmv_amount from fct_order_items where is_completed is true and purchased_at between 2018-01-01 and 2018-03-31." This is just SQL in English. A golden question should test whether the agent can translate business language into the right query, not whether it can repeat column names back to you.

### 4. Represents a real business need

Every golden question should map to something a stakeholder would actually ask in production. If no one would ever ask it, it doesn't belong in the golden set. The eval pipeline tests the agent's readiness for real usage, not its ability to handle synthetic edge cases.

The exception: graceful failure questions (out-of-scope, trick questions) are designed to test boundaries. These are valid even though no stakeholder would sincerely ask them. An agent that fabricates an answer to "what is the profit margin by category?" (when no cost data exists) is more dangerous than one that gets a real question wrong.

## What makes a good expected SQL

The expected SQL is the verified correct answer to the golden question. It must be:

### 1. Validated against the source data

Run the expected SQL against the database. Look at the results. Confirm with a domain expert or the data owner that the numbers are correct. If you're not sure whether the result is right, it's not ready to be a golden question.

### 2. Written at the right level of specificity

The expected SQL should produce the correct result, but it doesn't need to match the agent's SQL structure exactly. The eval pipeline compares results, not SQL text. Two different queries that return the same numbers both pass. A CTE-based query and a subquery-based query that produce identical results will both be marked correct.

### 3. Deterministic for the time period

Use fixed dates rather than relative ones to avoid results changing between eval runs. The golden set is a fixed benchmark, not a live dashboard. If the underlying data doesn't change between runs (as with a static public dataset), the expected results should be identical every time.

### 4. Minimal but complete

Include only the columns needed to verify the answer. If the question asks for "GMV by region," the expected SQL should return the region and the GMV. It doesn't need to return order count, customer count, and five other supporting columns unless the question asks for them.

Extra columns in the expected SQL cause false negatives in the eval pipeline when the agent returns the correct answer with different supporting columns. The tolerant comparison stage handles some of this, but keeping expected SQL minimal reduces unnecessary noise.

## Curation checklist

Before adding a golden question to the set, confirm each item:

| Check | Question to ask yourself |
|---|---|
| Unambiguous | Would two analysts write the same SQL for this question? |
| Natural language | Would a stakeholder actually phrase it this way? |
| One concept | Does this test exactly one thing? |
| Expected SQL validated | Have I run it and confirmed the results are correct? |
| Expected SQL deterministic | Does it produce the same result on every run? |
| Expected SQL minimal | Does it return only the columns needed to verify? |
| Category assigned | Is it tagged with the right category (Aggregation, Ranking, Ratio, etc.)? |
| Business rule tested | Does it exercise at least one business rule from the context document? |

## Categories

Organize questions by what they test:

| Category | What it tests | Example |
|---|---|---|
| Aggregation | Basic counting, summing, averaging | "What was total GMV for Q1 2018?" |
| Filtered Query | Applying the right WHERE clause | "How many orders were canceled in 2017?" |
| Ranking | ORDER BY + LIMIT with correct aggregation | "Top 10 categories by GMV" |
| Ratio | Computing percentages from filtered subsets | "What was the on-time delivery rate?" |
| Time Series | Date truncation, period comparisons, growth rates | "Month-over-month GMV growth for 2017" |
| Multi-metric | Pulling multiple measures across multiple tables | "CSAT by quarter split by intra/inter-state" |
| Out of Scope | Questions the agent should decline | "What is the profit margin?" (no cost data) |

## Difficulty calibration

| Difficulty | What makes it hard | Example |
|---|---|---|
| Easy | Single table, one aggregation, clear filter | "Total GMV for Q1 2018" |
| Medium | Multiple tables, date logic, regional grouping, or a business rule the agent must apply | "On-time delivery rate for Q1 2018" |
| Hard | Window functions, period comparisons, Pareto analysis, or combining multiple business rules simultaneously | "QoQ GMV growth by region for 2017" |

## Versioning and maintenance

Golden questions are living artifacts. They change as the agent's scope expands.

**When to add questions:** After each enrichment cycle when new capabilities are added. When real users ask questions the golden set didn't cover. When the evaluation reveals a pattern of failures in a specific category.

**When to retire questions:** When the underlying data model changes and the question is no longer valid. When the agent's scope changes and the question is no longer in scope.

**When to update expected SQL:** When business rules change (new exclusion, new metric formula). When the data model changes (column renamed, table restructured). Always re-validate the updated SQL before committing.

## Growing the set over time

Start with 20-40 questions covering the core use cases. Quality matters more than quantity. Thirty well-crafted questions that each test a specific business rule are worth more than two hundred vague ones.

The set should grow as you discover new patterns from real usage, not from trying to imagine every possible question upfront. The monitoring pipeline (in production systems) and user feedback are the best sources for new golden questions, because they represent what people actually ask.