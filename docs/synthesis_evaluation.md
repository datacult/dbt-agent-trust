# Synthesis Evaluation: The Layer Automated Testing Cannot Reach

## The boundary this document addresses

The evaluation pipeline in this repo handles a specific type of question: ones with a definitive correct answer. "What was total GMV for Q1 2018?" has one right number. The layered comparison can check whether the agent got it right.

But analytics agents increasingly do more than answer individual questions. They synthesize multiple data points, interpret trends, compare against benchmarks, and render a verdict on what the data means. "How is the product launch performing?" requires pulling revenue, customer acquisition, review scores, and delivery metrics, then weighing them against each other and concluding whether things are on track. There is no single correct answer to compare against. Two experienced analysts might look at the same data and reach different but equally valid conclusions.

This document covers how to evaluate that layer. It does not solve the problem with automation. It documents the methodology we use in practice, including its honest limits, because the alternative (ignoring the problem or pretending LLM-as-judge solves it) is worse than acknowledging what's hard.

## Why synthesis evaluation is fundamentally different

Structured questions (the bottom of the pyramid) fail silently. The agent returns a wrong number and no one notices unless you run the eval. That's why automated evaluation exists: to catch failures that humans would miss.

Synthesis and interpretation (the middle and top of the pyramid) fail visibly. When an agent produces a narrative analysis that's wrong, a domain expert reading it notices. The interpretation is obviously off, the framing misses context, the emphasis is on the wrong metric. These failures don't need automated detection. They need systematic expert review with a structured approach to capturing and fixing what went wrong.

This means the two layers need different assurance mechanisms. Automated comparison for the structured layer, where failures are silent. Expert-anchored validation for the synthesis layer, where failures are visible but the correction process needs to be systematic.

## The expert-anchored validation approach

### Step 1: Extract the expert's judgment

Before asking the agent to produce any synthesis or interpretation, capture how the expert currently does the work. Not the metrics they pull, but the reasoning they apply on top. This is the hardest step because interpretive judgment is usually tacit.

### Step 2: Codify the framework

Turn the extracted judgment into structured instructions the agent can follow. This is not a prompt. It's a document with specific rules, thresholds, and interpretation patterns:


### Step 3: Validate against the expert's own past work

Run the agent's framework against historical cases where you already know what the expert concluded. This is the calibration step. Take three to five past analyses the expert produced, feed the same data to the agent with the codified framework, and compare side by side.

You're looking for:
- Does the agent surface the same key findings the expert did?
- Does it miss anything the expert flagged as important?
- Does it flag things the expert would dismiss as noise?
- Does the overall verdict match the expert's judgment?

This is human comparison, not automated scoring. The expert reads both outputs and judges. If the agent's output would lead a stakeholder to the same decision as the expert's output, it passes. If it would lead to a different decision, the framework needs refinement.

### Step 4: Iterate on the framework

When the agent's output diverges from the expert's judgment, the fix is in the framework, not in the model. Add a rule the expert applied that wasn't captured. Adjust a threshold that was set too high or too low. Add context the agent didn't have.

This is the same enrichment loop as the structured layer (change context, re-run, confirm improvement) but with human judgment as the grading mechanism instead of automated comparison.

### Step 5: Ongoing spot-checks

Once the framework is validated and deployed, the expert reviews a sample of the agent's production outputs on a regular cadence. Not every output, but enough to catch drift. Weekly for a pilot, biweekly once stable.

When a spot-check reveals a problem, it becomes a new case for the validation set (Step 3), and the framework is updated (Step 4). This is the correction loop that keeps the synthesis layer calibrated over time.

## What this approach catches and what it does not

### It catches:
- Framework gaps: rules the expert applies that weren't codified
- Threshold miscalibration: severity labels that don't match the expert's judgment
- Missing context: situations the framework doesn't account for
- Mechanical failures: the agent citing wrong numbers or missing required sections
- Drift over time: the framework becoming stale as the business changes

### It does not catch:
- Novel situations the expert hasn't encountered (no historical case to validate against)
- Subtle judgment errors where the agent's conclusion is plausible but not what the expert would say (requires real-time expert review)
- Cases where the expert's own judgment is inconsistent (the validation is anchored to the expert, so expert inconsistency propagates)

### It does not solve:
- Automated grading of open-ended interpretation at scale 
- Removing the human from the loop for high-stakes analytical judgment (this is the correct posture given the state of the art, not a limitation to engineer around)

## How this relates to what others are doing

Hex (Izzy Miller's team) built an internal evaluation lab with a synthetic business and LLM-judged grading, and they still say "there's no substitute for literally looking at trajectories with your eyeballs" for the interpretation layer. Anthropic's own analytics agent team uses human review and correction harvesting for interpretation validation. 

## Practical requirements

To implement this approach you need:

1. **Access to a domain expert** who currently does the analysis the agent will produce. Without this, you have no ground truth to validate against.
2. **Historical examples** of the expert's past analyses (3-5 minimum for initial calibration). Without these, validation is speculative rather than evidence-based.
3. **A codified framework** capturing the expert's interpretive and judgement of the data. This is the deliverable from Steps 1-2 and the artifact that makes the approach repeatable.
4. **A review cadence** where the expert checks a sample of production outputs. Without this, the framework goes stale and the agent drifts.
5. **A correction mechanism** for feeding expert feedback back into the framework. Without this, the same errors repeat.

If you don't have access to a domain expert or historical examples, the synthesis layer isn't ready for deployment. The structured question-answering layer (automated evaluation via this repo's pipeline) is the right scope until the expert extraction can happen.