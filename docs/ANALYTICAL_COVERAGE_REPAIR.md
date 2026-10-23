# Analytical coverage repair

The prior live rerun was faster but omitted important requested results. Its trace showed metadata focus on a few broad sections, 38 source fragments reaching the writer without budget omissions, and only nine selected passages. Supported quotations were incorrectly treated as sufficient evidence that the whole request was answered.

## Changes

- Broad analytical metadata is a ranking hint. Focus remains available for factual and short single-topic requests, with independent fallback retrieval. Navigation matching now uses only original-query terms that also occur in an obligation; planner expansion alone cannot narrow the search.
- Generic requested-topic patterns (accuracy, speed, costs, limitations, controls, monitoring and validation) copy literal query spans into a checklist. No generated source facts or gold-answer points enter it. Each detected topic gets at most two independent source-page FTS hits under existing global caps. This does not claim complete coverage of all possible question types.
- Source verification labels direct findings, necessary qualifications and general background. Background is excluded. Missing role fields from legacy adapters retain prior behavior. Formal controls are not inferred from loosely related mathematical cautions.
- The extractive writer must examine complementary findings for each requested topic, including detailed quantitative results and source qualifications, without a fixed passage count. It still outputs source IDs, not rewritten prose.
- The existing final semantic-verifier call receives the original query and requested-topic checklist. It checks relevance and topic coverage separately from source support. Missing checks, duplicate checks, empty claim references or references to rejected claims leave a topic unresolved and force partial status. No additional model call is introduced.
- Numeric Markdown punctuation such as an italicized decimal dot is repaired only in displayed answers. Original fragments and quotes remain byte-for-byte unchanged. Units, digits and signs are not rewritten.
- `evaluation.audit.judge_consistency` flags label contradictions and a missing-page judgment when the cited filename/page is actually present. It is diagnostic and never overrides official metrics. The official notebook, its point decomposition and gold inputs remain untouched.

## Validation and limits

181 non-slow tests pass (seven slow model tests deselected), including literal topic extraction, independent topic retrieval, broad-query navigation, background removal, fail-closed topic coverage, numeric display/source fidelity and unchanged-score judge audits.

Topic detection is a bounded generic heuristic, not a semantic coverage guarantee. Relevance and completeness judgments remain model-dependent. Source-only answers cannot invent production recommendations absent from the supplied collection. Partial status is expected when the collection lacks support.

The next live diagnostic uses exactly the same single document and two public development questions, Qwen3.8 Flash with thinking disabled, a 180-second diagnostic deadline and a $0.05 ceiling including judging. Production still defaults to 120 seconds. End-to-end gains must be read from the measured report, not inferred from passing tests.
