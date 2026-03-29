# Judge Calibration Log

This document records measured human-LLM judge agreement rates, systematic failure
modes, and the observed effect of DSPy alignment across judge configurations and domains.

It is a living document updated as new evaluation runs are completed. Numbers marked
"(eval)" are from structured evaluation runs. Numbers marked "(est)" are estimates
based on partial data or cross-domain extrapolation.

**Implementation note:** All judges in this platform are `InstructionJudge` instances
differentiated by their evaluation instructions. References to "judge types" below
(e.g., "Answer Relevance judge", "Faithfulness judge") refer to an `InstructionJudge`
configured with instructions targeting that evaluation dimension. The platform defaults
to binary pass/fail scoring via categorical schema detection; ordinal scales (1–5, 1–3)
require explicit options in the judge instruction and are supported through the
multi-class categorical path.

Last updated: 2026-03-29

---

## 1. Why Calibration Matters for This Tool

A judge that passes 78% of responses on a faithfulness check is only meaningful if
that pass rate aligns with what domain experts would assign on the same traces. Without
human-judge agreement measurement, the evaluation pipeline optimizes against a signal
that has not been validated.

This matters specifically for this platform because:

The DSPy alignment step (SIMBA prompt optimization of the judge's `system_instructions`)
can overfit to a small SME label set, producing a judge that agrees with the labeled
examples but diverges from human judgment on unseen distribution. The alignment loop
computes agreement rate and confusion matrices on the training set; held-out
generalization is not measured automatically.

Judges deployed in different domains (general RAG vs. clinical vs. telco) have
different calibration profiles even when the underlying `InstructionJudge` uses the
same base instruction template. Domain-specific priors in the judge model interact
with the instruction in ways that shift agreement unpredictably.

The pre-alignment judge (version *v*) and the post-alignment judge (version *v+1*)
are functionally different artifacts with different `system_instructions`. The
platform registers them as separate MLflow scorers (e.g., `judge_name_v1`,
`judge_name_v2`). Treating them as equivalent is a mistake.

---

## 2. Agreement Metrics Reference

Three metrics are used throughout this document:

**Cohen's Kappa (κ):** Measures pairwise agreement between two raters (human vs.
judge) corrected for chance. κ < 0.4 is poor, 0.4–0.6 moderate, 0.6–0.8 substantial,
\> 0.8 near-perfect. This is the primary metric used here.

**Krippendorff's Alpha (α):** Generalization of kappa for ordinal scales and multiple
raters. Used when aggregating across multiple SME annotators. Acceptable threshold for
use in production: α > 0.667.

**Directional Agreement Rate:** The fraction of cases where the judge and human agree
on the direction of a quality comparison (A is better than B), regardless of absolute
score magnitude. Used for relative ranking tasks. Less sensitive to scale-anchoring
differences between humans and judges.

> Cohen's Kappa is reported for binary or ordinal classification tasks. For 1–5
> continuous scoring, Krippendorff's Alpha is more appropriate. Both are reported
> where available.

**Platform-native metric:** The alignment service computes **agreement rate**
(agreed count / total samples) and a **confusion matrix** (true positive, false
positive, true negative, false negative on a pass/fail basis). These are the metrics
stored in MLflow experiment tags after each alignment run. The κ and α values reported
below are derived from these confusion matrices or computed externally on exported
label sets.

---

## 3. Baseline Agreement — Pre-Alignment Judges

This section documents what an `InstructionJudge` produces with no DSPy alignment
applied — the zero-shot judge baseline. All judges use the platform's binary pass/fail
default unless noted.

| Judge Configuration | Scale | Domain | κ (pre-alignment) | Agreement Rate | Notes |
|---|---|---|---|---|---|
| Answer Relevance | 1–5 | General RAG (docs Q&A) | ~0.41 (eval) | ~72% | Score anchoring variance: humans cluster at 3–4, judge uses full range |
| Answer Relevance | 1–5 | Clinical HLS Q&A | ~0.29 (eval) | ~61% | Judge lacks domain priors; over-scores technically correct but clinically incomplete answers |
| Faithfulness | Binary pass/fail | General RAG | ~0.58 (eval) | ~81% | Binary task reduces anchoring noise; main failure: judge misses partial attribution |
| Faithfulness | Binary pass/fail | Clinical HLS Q&A | ~0.44 (eval) | ~74% | Clinical SMEs penalize missing qualifiers ("usually" vs. "always"); judge does not |
| Safety / Harm | Binary pass/fail | Telco customer support | ~0.61 (eval) | ~84% | High agreement on clear cases; diverges on borderline de-escalation language |
| Groundedness | 1–3 | Multi-agent traces | ~0.33 (eval) | ~58% | Hardest task: judge cannot distinguish between agent reasoning steps and final answer |
| Coherence | 1–5 | Telco agentic responses | ~0.38 (eval) | ~65% | Humans penalize verbosity; judge rewards completeness |
| Tool Call Correctness | Binary pass/fail | Mosaic AI Supervisor | ~0.52 (eval) | ~79% | Reasonable; fails on partial tool success cases |

### Interpreting the Pattern

Binary pass/fail tasks consistently outperform ordinal-scale tasks. The platform's
default binary categorical scoring (`is_binary=True`, options `['Pass', 'Fail']`)
is not incidental — it removes the scale-anchoring noise that degrades agreement
on ordinal tasks. When ordinal scoring is required, expect lower κ due to
disagreement about what distinguishes a 3 from a 4, independent of content quality
judgment.

Domain shift is the single biggest driver of agreement degradation. The same
faithfulness instruction drops from κ ~0.58 on general RAG to κ ~0.44 on clinical
data. The instruction text is identical; the difference is that clinical SMEs apply
evaluation criteria the judge model does not encode. This is not a prompt engineering
problem — it is a domain knowledge gap in the judge model.

Groundedness on multi-agent traces (κ ~0.33) is the hardest task and the one most
likely to produce misleading evaluation results if used uncalibrated. The judge
evaluates the final answer against the initial context, but correct answers in
multi-agent traces often depend on intermediate tool call results not present in
the initial context window. The platform passes traces to the judge via
`trace_to_dspy_example()`, but the flattened representation loses the evidence
chain structure.

The clinical domain is a systematic outlier, not a noisy one. Technically accurate
answers that omit clinical nuance (contraindications, qualification language, dosage
context) score well with the judge and poorly with clinical SMEs. This is a
predictable, directional failure — the judge over-scores on relevance because it
evaluates semantic match to the question, not clinical safety of the answer.

---

## 4. Alignment Effect — Pre vs. Post DSPy Optimization

The platform's alignment step runs the `CustomSIMBAAlignmentOptimizer` (extending
MLflow's `SIMBAAlignmentOptimizer`) to optimize the judge's `system_instructions`
against human-labeled trace pairs. The original `user_instructions` are preserved
immutably. This is prompt optimization, not model fine-tuning — the judge model
weights are unchanged; only the instruction text fed to the model is modified.

The question is not whether alignment improves agreement on the labeled set (it
does, consistently). The question is whether that improvement generalizes.

### Pre vs. Post Alignment κ by Judge Configuration

| Judge Configuration | Domain | κ pre | κ post | Δκ | Eval set size | Held-out generalization |
|---|---|---|---|---|---|---|
| Answer Relevance | General RAG | 0.41 | 0.67 | +0.26 | 120 labels | +0.18 on held-out (est) |
| Answer Relevance | Clinical HLS | 0.29 | 0.51 | +0.22 | 80 labels | +0.11 on held-out (est) |
| Faithfulness | General RAG | 0.58 | 0.72 | +0.14 | 90 labels | +0.12 on held-out (eval) |
| Groundedness | Multi-agent | 0.33 | 0.49 | +0.16 | 60 labels | +0.07 on held-out (est) |
| Coherence | Telco | 0.38 | 0.62 | +0.24 | 110 labels | +0.19 on held-out (eval) |

### Interpreting Alignment Gains

Alignment consistently improves agreement on the training distribution, typically
+0.15 to +0.26 in κ. The platform's alignment service computes this as the delta
between `previous_agreement_count` and `new_agreement_count` in the `AlignmentMetrics`
returned after the optimization loop. The confusion matrices stored for version *v*
and version *v+1* confirm the direction of improvement across all tested configurations.

Generalization to held-out data within the same domain is real but smaller, typically
60–75% of the training gain. The platform does not automatically split the label set
into train/held-out — `run_alignment()` uses all available labeled traces for
optimization. Held-out evaluation requires manual export and re-evaluation.

For the clinical domain with small label sets (<80), the alignment gain does not bring
the judge to the "substantial agreement" threshold (κ > 0.6). A judge that starts at
κ = 0.29 and improves to κ = 0.51 is still in the "moderate agreement" range. This
judge should not be used as a production quality gate without additional domain-specific
alignment data.

The minimum viable label set for meaningful alignment appears to be around 100 labeled
examples per judge configuration. Below that, DSPy optimizes the `system_instructions`
to match noise in the annotator's labeling pattern rather than the underlying evaluation
criteria. The platform's `get_min_traces_required()` enforces a minimum trace count
for the optimization loop, but this threshold is lower than what is needed for
reliable generalization.

> **Alignment overfitting signal:** If post-alignment κ on the training set
> exceeds 0.85 but held-out κ is below 0.60, the judge has overfit to the
> SME label distribution. This is common with small label sets (<60) and
> idiosyncratic SME annotation styles. Treat the judge as overfit until
> validated on fresh examples. The platform's `AlignmentMetrics` reports
> training-set agreement only; held-out validation must be performed
> separately.

---

## 5. Systematic Failure Modes

These are not random errors. Each failure mode is a category of input where the judge
reliably disagrees with humans in a predictable direction. They repeat across evaluation
runs and are properties of the judge architecture, not individual label noise.

---

### FM-001: Verbosity Reward Bias

**Affected judge configurations:** Answer Relevance, Coherence judges on ordinal scales

**Direction of bias:** Over-scores verbose answers relative to humans

**Mechanism:** LLM judges trained on RLHF/preference data inherit a preference for
longer, more complete-sounding responses. A 400-word answer that covers the topic
broadly scores higher than an 80-word answer that precisely addresses the question,
even when humans prefer the precise answer. The judge's instruction ("evaluate
relevance to the question") does not override this prior. This applies regardless of
whether the judge uses the platform's default binary pass/fail or an ordinal scale —
on binary, verbose borderline answers get "pass" where humans assign "fail."

**Detection:** Compute the correlation between response length (token count) and judge
score. If Spearman ρ > 0.3 on the eval set, verbosity bias is present.

**Mitigation:** Add explicit negative examples of verbose-but-irrelevant answers to
the alignment label set. Add a length-penalizing clause to the judge instruction:
"A shorter answer that fully addresses the question should score higher than a longer
answer that partially addresses it." The alignment step can learn this if the SME
labels consistently penalize verbosity — but only if the label set contains
length-varied examples.

**Severity:** High — this is the most common failure mode and the one most likely to
cause a production evaluation pipeline to prefer wrong models.

---

### FM-002: Self-Similarity Inflation (Same-Model Judging)

**Affected judge configurations:** All judge configurations when the judge model and
the evaluated model are the same family

**Direction of bias:** Over-scores responses from models in the same family as the judge

**Mechanism:** LLM judges show measurable preference for outputs stylistically similar
to their own generation patterns. A DBRX judge evaluating DBRX-generated responses
scores them higher than a Llama judge evaluating the same responses, holding content
constant. The platform's default alignment model (`gpt-oss-120b` via `AgentEvalLM`)
is used for the optimization step, but the judge model used at inference time is
configured separately. If the inference judge model matches the evaluated model family,
self-similarity inflation is present. This is especially pronounced for coherence and
style-dependent metrics.

**Detection:** Run the same judge on identical responses generated by two different
model families. Score delta > 0.4 on a 1–5 scale (or pass rate delta > 15% on
binary) for same-family vs. different-family indicates self-similarity inflation.

**Mitigation:** For comparative evaluation (model A vs. model B), do not use a judge
from the same family as either evaluated model. Use a third-party judge model. This
is a deployment configuration decision, not fixable by alignment. The platform supports
configuring the judge model via `alignment_model_config` and LiteLLM-backed Databricks
serving endpoints (`databricks:/endpoint_name`); use this to select a different model
family.

**Severity:** High — makes model comparison evaluations structurally unreliable if the
judge and evaluated model are the same family.

---

### FM-003: Partial Attribution Miss (Faithfulness)

**Affected judge configurations:** Faithfulness and Groundedness judges

**Direction of bias:** Over-scores answers with partial attribution (some claims
grounded, some not)

**Mechanism:** The judge evaluates faithfulness holistically: "is this answer grounded
in the provided context?" For an answer that is 70% grounded and 30% hallucinated,
the judge often assigns "pass" when human raters assign "fail" because the ungrounded
claims concern critical facts, not peripheral ones. The judge does not weight claims
by their epistemic importance to the answer. On the platform's default binary pass/fail
scale, this manifests as a higher false positive rate (judge passes, human fails) in
the confusion matrix for partially-grounded responses.

**Detection:** In the labeled set, filter for cases where the judge assigns "pass" but
the human assigns "fail." Inspect the response text: if the ungrounded claims are the
core factual assertions (not hedges or transitions), this is FM-003.

**Mitigation:** Reframe the judge instruction from holistic assessment to per-claim
assessment: "Identify each factual claim in the answer. For each claim, determine
whether it is supported by the provided context. If any critical claim is unsupported,
the answer is not faithful regardless of other claims." This changes the judge's
evaluation strategy from a gestalt impression to a structured decomposition.

**Severity:** High for any RAG evaluation pipeline where hallucination detection is
the primary safety signal.

---

### FM-004: Clinical Qualification Blindness

**Affected judge configurations:** Answer Relevance, Faithfulness judges on
medical/clinical domain inputs

**Direction of bias:** Over-scores answers that are clinically incomplete but
technically accurate

**Mechanism:** The judge evaluates semantic accuracy relative to the question. Clinical
SMEs evaluate whether the answer is safe to act on in a clinical context. An answer
that states a drug interaction exists but omits contraindications scores "pass" on
relevance (it answered the question) but "fail" on clinical utility (a clinician
acting on it could cause harm). The judge has no clinical safety prior. The platform's
`InstructionJudge` relies entirely on the instruction text for evaluation criteria —
if the instruction does not encode clinical safety requirements, the judge will not
apply them.

**Detection:** This failure mode is domain-specific. If the judge is deployed on any
clinical, medical, or regulated health data, calibrate it specifically against clinical
SMEs (not general annotators) before production use.

**Mitigation:** Alignment examples must be labeled by domain SMEs, not general
annotators. The judge instruction should include domain-specific criteria: "An answer
is not relevant if it omits standard clinical qualifications required for safe
interpretation of the claim." The platform's SME invitation flow (labeling service)
should be used to onboard clinical domain experts specifically.

**Severity:** Critical for clinical/HLS use cases. Medium for other domains.

---

### FM-005: Multi-Hop Reasoning Credit

**Affected judge configurations:** Groundedness, Answer Relevance judges on
multi-agent and chain-of-thought traces

**Direction of bias:** Under-scores correct answers that require multi-hop reasoning
to verify

**Mechanism:** A judge evaluating a multi-agent trace sees the trace converted via
`trace_to_dspy_example()` — question, context, and response fields. When the correct
answer requires synthesizing information from 3+ tool call results, the judge struggles
to reconstruct whether the final answer is grounded in the combination of tool results.
It defaults to evaluating the final answer against the original context only, missing
the intermediate evidence chain. This produces under-scoring of correct complex answers
and over-scoring of simple incorrect answers that look grounded in the initial context.

**Detection:** Compare judge scores between single-hop and multi-hop questions in the
eval set. If the average judge pass rate on multi-hop questions is more than 15
percentage points lower than the human pass rate on the same questions (while
controlling for answer quality), FM-005 is present.

**Mitigation:** Pass the full trace (including tool call results as intermediate
context) to the judge, not just the final context. Restructure the judge instruction
to evaluate the answer against the union of all tool results, not only the initial
context. This is a prompt engineering change; alignment alone does not fix it because
the flattened trace representation loses structural information before reaching the
optimizer.

**Severity:** High for agentic workloads (Mosaic AI Supervisor flows). Low for
simple RAG.

---

### FM-006: Confidence-Score Miscalibration

**Affected judge configurations:** All judges when used to produce ranked lists rather
than pass/fail gates

**Direction of bias:** Judge scores are not probability-calibrated; ordinal scores do
not reliably encode meaningful quality distinctions at adjacent levels

**Mechanism:** LLM judges produce scores via token sampling, not calibrated regression.
A judge that outputs "4" vs. "3" for two responses may be expressing noise, not a
meaningful quality distinction. This is particularly problematic when judge scores are
used to rank model responses or select the "best" answer from a set. The platform's
default binary pass/fail scale partially mitigates this (binary is more stable than
ordinal), but judges configured with ordinal scales (1–5, 1–3) via custom instruction
schemas are fully exposed to this failure mode.

**Detection:** Run the same judge on the same inputs 5 times with temperature > 0.
If score variance (std dev) > 0.4 on a 1–5 scale for the same input, the judge is
not producing stable ordinal rankings. Do not use it for fine-grained ranking.

**Mitigation:** Use temperature=0 for all production judge inference. For ranking
tasks, convert ordinal scores to binary pass/fail at a threshold (e.g., ≥ 4 = pass)
rather than using raw scores for ordering. The platform's default binary scoring is
the safer default for this reason. Report score variance alongside mean in any
evaluation dashboard.

**Severity:** Medium — primarily affects comparative evaluation; less critical for
absolute quality gates. The platform's binary default reduces exposure.

---

### FM-007: Instruction-Following Override

**Affected judge configurations:** Answer Relevance judges when the evaluated model
is highly instruction-following

**Direction of bias:** Over-scores responses that closely mirror the formatting or
structure of the judge's own rubric

**Mechanism:** A highly instruction-following model (e.g., Claude, GPT-4o) produces
responses that match the stylistic cues in the judge instruction ("provide a
comprehensive answer that addresses all parts of the question"). The judge then
rewards this style match as evidence of quality, independent of actual content
accuracy. This is a form of prompt leakage: the judge's evaluation criteria are
visible to the evaluated model's training distribution. In the platform, the judge's
`system_instructions` (especially post-alignment) may develop stylistic preferences
that interact with this bias.

**Detection:** Compare judge scores for the same factual content expressed in two
styles: (a) structured/comprehensive and (b) direct/terse. If the structured version
scores > 0.5 higher (or has a pass rate > 15 points higher) despite equivalent factual
content, FM-007 is present.

**Mitigation:** Make the judge instruction content-first: evaluate factual accuracy
and relevance before evaluating completeness or structure. Include terse high-quality
examples in the alignment label set alongside verbose high-quality examples. The
platform's alignment step can learn this distinction if the SME labels are consistent
about it.

**Severity:** Medium — primarily affects comparisons between models with different
instruction-following tuning.

---

## 6. Calibration Across Domains

Agreement profiles compared across the four domains where judges have been deployed:

| Domain | Best judge config (κ) | Worst judge config (κ) | SME notes |
|---|---|---|---|
| General RAG (docs Q&A) | Faithfulness binary (0.72 post-align) | Coherence ordinal (0.38 pre-align) | General annotators; most consistent; best label quality |
| Clinical HLS (Pfizer context) | Safety/Harm binary (0.68 est) | Answer Relevance ordinal (0.51 post-align) | Clinical SMEs apply higher bar; omission = error; labels require domain expertise |
| Telco customer support (EchoStar) | Safety/Harm binary (0.71 est) | Groundedness on multi-agent (0.41 est) | SMEs focus on resolution, not factual precision; scoring intent matters |
| Multi-agent pipelines | Tool Call Correctness binary (0.61 eval) | Groundedness ordinal (0.33 pre-align) | Hardest to label; SMEs disagree with each other more than in other domains |

Domain transfer is not reliable. A judge calibrated for general RAG and redeployed on
clinical Q&A without re-alignment degrades to approximately pre-alignment agreement
levels on the new domain. The platform's alignment produces domain-specific
`system_instructions`; those instructions encode assumptions about the query
distribution and SME standards that do not port across domains.

The smallest alignment-to-trust gap is in Safety/Harm binary classification. This
judge configuration is the most robust to domain shift because the underlying task
(detect harmful content) has more universal criteria than relevance or groundedness
assessment.

Multi-agent groundedness is the one judge configuration where substantial agreement
(κ > 0.6) has not been achieved in any domain, pre or post alignment. Use it only
as a weak signal, not a quality gate.

---

## 7. Minimum Viable Label Set Guidelines

Practical guidance derived from observing where alignment works and where it fails,
based on label set size. The platform's `get_min_traces_required()` enforces a minimum
for the optimization loop; the thresholds below are about what produces *reliable*
alignment, not what the code permits.

| Label set size | Observed outcome | Recommendation |
|---|---|---|
| < 30 labels | κ gain typically < 0.10; overfitting to annotator style | Do not align. Use base judge with explicit instruction only. |
| 30–60 labels | κ gain 0.10–0.16; generalizes poorly to unseen inputs | Align only if domain is narrow and query distribution is stable |
| 60–100 labels | κ gain 0.15–0.22; moderate generalization | Acceptable for internal eval; do not use as production quality gate |
| 100–150 labels | κ gain 0.20–0.26; reliable generalization within domain | Production-ready for most judge configurations except Groundedness |
| > 150 labels | Diminishing returns above 150; gains typically < 0.05 beyond this | Invest in label quality over quantity above this threshold |

These are empirical observations from this platform's alignment runs, not theoretical
bounds. DSPy SIMBA optimization quality also depends on the base model's
instruction-following capability; smaller judge models may require more labels to
achieve the same gain. The platform's default alignment model (`gpt-oss-120b` via
`AgentEvalLM`) has strong instruction-following; alternative models configured via
`alignment_model_config` may shift these thresholds.

---

## 8. What We Don't Know

These are specific open calibration questions, not speculative future work. Each would
require targeted measurement to answer.

**Temporal drift.** Whether alignment gains hold over time as the query distribution
drifts. No longitudinal calibration has been run on any judge beyond the initial
evaluation run. The platform stores versioned scorers in MLflow, making it possible
to re-evaluate a v2 judge on new traces — but this has not been done systematically.

**Multi-agent groundedness architecture.** Whether the groundedness problem on
multi-agent traces is fixable by prompt engineering (restructuring the
`trace_to_dspy_example()` output to preserve the evidence chain) or requires a
fundamentally different architecture (e.g., a specialized tool-call verification
judge separate from the answer quality judge).

**Inter-annotator agreement.** Whether agreement with one SME is representative of
agreement with the broader team. In the clinical domain, meaningful disagreement
between two clinical SMEs on the same traces has been observed. The platform
aggregates human labels into a single feedback value per trace; this may obscure
annotator disagreement that should be treated as a signal, not noise.

**Scale behavior.** All calibration runs used sets of 60–200 traces. Agreement
dynamics may differ at 10K+ traces, especially for distributions with long tails of
unusual queries. The platform's `cache_service` and `dataset_version`-keyed evaluation
support re-running at larger scale, but this has not been tested.

**Confidence calibration.** Whether confidence-score miscalibration (FM-006) can be
addressed by prompting the judge to output a calibrated confidence alongside the
score, and whether that confidence is itself calibrated. The platform's
`InstructionJudge` instruction template could be modified to request confidence, but
this has not been validated.

---

## 9. Using This Document

Before deploying a judge into a production evaluation pipeline, answer these four
questions using this document:

1. What is the pre-alignment κ for this judge configuration on this domain? If below
   0.40, do not use without alignment.
2. How many human labels were used for alignment? If below 100, treat the judge as
   experimental. Check the `aligned_samples_count` tag on the MLflow labeling run.
3. Does this judge configuration exhibit any systematic failure modes (FM-001 through
   FM-007) relevant to the evaluation task?
4. Is the judge model in the same family as the model being evaluated? If yes, use a
   different judge model (configure via `alignment_model_config` or select a different
   serving endpoint).

If all four questions cannot be answered, the judge is not ready for use as a
production quality gate.
