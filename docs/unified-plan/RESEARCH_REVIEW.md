# Unified research record and decisions

This file retains the earlier 28-entry review, with strict-profile corrections, followed by the additional primary-source checks made during merging. The first review was performed earlier on 23 October 2026; it is not a claim that every linked implementation was rerun during this merge. The newly refreshed records are identified below. No published result is a local result, and no source was independently reproduced here. Use ARCHITECTURE.md and reference-config.json for the selected default; older optional experiment suggestions do not override disabled training or recursive retrieval.

# Industry retrieval and research review

Research cutoff: **23 October 2026**. This is a targeted multi-pass review, not a claim to enumerate every retrieval paper. Searches covered production search systems, financial long-document QA, hierarchy and association, visual/late-interaction retrieval, long-context processing, and evidence evaluation. Primary papers, author repositories/model cards, and official engineering documentation were prioritized. Exa failed earlier in the session; the review used the available web-search tool plus Context7 documentation retrieval. No private benchmarks or paid inference calls were used.

Evidence labels: **published paper** means a venue/proceedings record was reviewed; **preprint** means an arXiv record was reviewed without assuming peer-review; **engineering evidence** describes the vendor/author's system and experiments; **implementation documentation** supports API behavior, not empirical superiority. Results measured elsewhere are not results for this corpus. Recency alone is not evidence of quality.

**Competition boundary:** research relevance is not permission to ship a listed baseline or to train models. Read COMPLIANCE.md. Model adaptation and recursive-reader experiments remain disabled in the strict submission profile until the corresponding organizer ruling; the pretrained inference/source-engineering core proceeds without them.

## 1. What production systems actually do

Industrial retrieval is usually staged. Content preparation preserves identity, permissions, structure, and freshness; relatively cheap candidate generators optimize recall; more expensive rankers operate on a smaller candidate set; downstream context selection controls relevance and cost. Production systems also need observable failure modes, cache/version discipline, and evaluation tied to real questions. The papers and documents below support parts of this pattern; they do not establish one universally best system.

This contradicts a simplistic reading of the brief's “advanced methods stop at 0.6” assertion. Those methods are still useful building blocks. The hackathon requirement is to contribute mechanisms addressing its specific failure modes beyond merely stacking standard retrieval techniques.

### R01. Elastic: multi-stage ranking

Source: [Ranking and reranking](https://www.elastic.co/docs/solutions/search/ranking). Type: official implementation/engineering documentation; accessed 23 October 2026.

Elastic describes cheap initial retrieval followed by more costly reranking, and lexical/vector fusion. This supports keeping a strong hybrid baseline and measuring candidate recall separately from reranker quality. It does not support replacing identity resolution or broad evidence coverage with one top-k list. **Decision: core supporting infrastructure.** Use local equivalents rather than introducing an external search cluster for 35 documents. Source score fusion and reranker outputs must retain different meanings.

### R02. Vespa: phased ranking

Source: [Phased ranking](https://docs.vespa.ai/en/ranking/phased-ranking.html). Type: official documentation; accessed 23 October 2026.

Vespa separates ranking phases so expensive functions operate on bounded candidate sets. **Decision: adopt the budget principle**, not a mandatory Vespa dependency. ECR has distinct catalog, page, and unit candidate stages, plus a bounded expensive assessment stage. The transferable lesson is where computation is spent; this does not prove that any fixed candidate budget suffices for a broad credit review.

### R03. Microsoft Azure: structure-aware document preparation

Source: [RAG chunking phase](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-chunking-phase). Type: official architecture guidance; accessed 23 October 2026.

The guidance emphasizes document layout, coherent chunks, table reformatting, metadata, and retaining preprocessed artifacts. **Decision: core ingestion requirements.** Keep source coordinates, table headers, and parsed artifacts reusable across retrieval experiments. Do not introduce a paid cloud document-analysis dependency by default. Extraction quality must be inspected before evaluating retrieval models.

### R04. Anthropic: Contextual Retrieval

Source: [Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval), 2024. Type: first-party engineering experiments.

The method adds document-specific context to chunks before embedding and lexical indexing. **Decision: core deterministic identity/section prefixes, optional generated context.** Store enrichment separately from original text. The reported improvements concern retrieval failure under the author's own setup; they do not establish complete multi-page evidence recovery or this hackathon's answer metrics. Contextualized retrieval alone would not satisfy the brief's innovation requirement.

### R05. Microsoft Research: LazyGraphRAG

Source: [LazyGraphRAG: Setting a new standard for quality and cost](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/), with a 2025 update on the page. Type: first-party research/engineering experiments.

It defers expensive LLM work and exposes a relevance-test budget. **Decision: borrow explicit assessment budgets and delayed expensive extraction; do not copy a full graph/community pipeline.** Its reported evaluation uses news articles and preference-style answer comparisons, which differ from page-cited financial evidence and point-level scoring here. Graph expansion can improve discovery while still missing exceptions or confusing periods.

## 2. Most relevant financial and evidence-retrieval research

### R06. Measuring and Closing the Retrieval Gap in Financial Question Answering (2026)

Source: [PMLR proceedings](https://proceedings.mlr.press/v318/kobeissi26a.html); related [preprint](https://arxiv.org/abs/2602.17981). Authors: Amine Kobeissi and Philippe Langlais. Type: published conference paper plus related preprint; do not count them as independent confirmations.

The work separates document, page, and chunk discovery and uses oracle analysis. A domain-tuned page scorer targets evidence missed inside an otherwise correctly retrieved filing. **Decision: core evaluation decomposition; a pretrained page scorer is optional, weight adaptation remains disabled.** This is especially relevant to our long reports and 39-page median reference spread. FinanceBench questions and evidence budgets differ, so transfer must be tested. Use the proceedings as the primary bibliographic record; avoid claiming identical content between versions without a diff.

### R07. HC-RAG: Evidence-Centric Retrieval-Augmented Generation over Heterogeneous Financial Filings (2026)

Source: [arXiv record](https://arxiv.org/abs/2608.12335), [full text](https://arxiv.org/html/2608.12335v1). Type: preprint; title/abstract and evidence/ablation sections reviewed.

It organizes documents, sections, text, tables, and metadata into typed evidence paths and distinguishes query intents. **Decision: supports testing structured text/table routing, not copying its entire architecture.** Its results remain author-reported and do not promise 0.95 here. The source record displays a June submission date despite an August-style identifier; preserve this metadata discrepancy rather than inventing a precise chronology. The hierarchy is relevant, but ECR still needs its own coverage and provenance ablations.

### R08. Rethinking Reasoning-Intensive Retrieval: Evaluating and Advancing Retrievers in Agentic Search Systems (2026)

Source: [arXiv record](https://arxiv.org/abs/2605.04018), which identifies ACL 2026; [ACL paper](https://aclanthology.org/2026.acl-long.1705.pdf). Type: conference-associated paper; primary abstract reviewed.

BRIGHT-Pro evaluates complementary multi-aspect evidence rather than a narrow single-passage target. **Decision: core aspect-coverage diagnostics; no ranker training in the strict profile.** Do not assume the released training recipe or large retriever is feasible or superior on 100 financial questions. The relevant shift is from ranking individual passages to evaluating an evidence portfolio. Query decomposition alone remains insufficient under this brief.

### R09. Evidence-Unit Fairness and the Limits of Query-Adaptive Sparse-Dense Fusion in Financial Document Retrieval (2026)

Source: [arXiv](https://arxiv.org/abs/2608.00183), v2 dated September 2026. Type: preprint; primary abstract reviewed.

It identifies a comparison confound when dense encoders see only truncated portions of larger labeled evidence units. It also finds no reliable gain from its tested lightweight query-adaptive fusion routers under its protocol. **Decision: mandatory tokenizer-visibility auditing and a simple fixed-fusion control.** Do not add a learned fusion router merely because adaptive sounds innovative. Test with company/query-family controls, and report how much source evidence a model actually saw.

### R10. From BM25 to Corrective RAG: Benchmarking Retrieval Strategies for Text-and-Table Documents (2026)

Source: [arXiv](https://arxiv.org/abs/2604.01733). Type: preprint; primary abstract reviewed.

The authors compare retrieval strategies on financial text/table documents and report a strong hybrid-plus-reranking baseline, with limited benefits from some expansion methods for precise numeric queries. **Decision: retain exact lexical/numeric matching and establish a competitive baseline before complex routing.** Its numbers are not directly comparable to our four official metrics. A baseline can be strong even when it is not sufficient as the final hackathon contribution.

### R11. DocFinQA: A Long-Context Financial Reasoning Dataset (2024)

Source: [ACL proceedings](https://aclanthology.org/2024.acl-short.42.pdf), [arXiv](https://arxiv.org/abs/2401.06915). Type: published paper; introduction/abstract reviewed.

It expands financial QA from short snippets to full filings and exposes long-document reasoning difficulty. **Decision: treat financial evidence localization and numerical reasoning as separate bottlenecks.** It informs stress-case design but is not a substitute benchmark for this competition. Do not mix its numerical-answer accuracy with this notebook's point-level precision/recall.

### R12. FinanceBench (2023)

Source: [paper](https://arxiv.org/abs/2311.11944). Type: research benchmark paper; primary abstract reviewed.

It supplies financial questions and evidence and demonstrates limitations of the model configurations tested at publication. **Decision: useful external sanity-check task if event rules/time permit, never a guarantee based on later vendor claims.** This hackathon includes broader synthesis, multiple regimes, and unavailable-information cases; high FinanceBench performance alone cannot establish success here.

## 3. Structure, association, and long-context approaches

### R13. RAPTOR (2024)

Source: [paper](https://arxiv.org/abs/2401.18059). Type: ICLR-associated published research; abstract reviewed.

RAPTOR builds recursive summaries at multiple abstraction levels. **Decision: optional navigation-only summary experiment.** Summaries may help broad discovery but can lose qualifiers, table scope, or exceptions. Require source-unit recovery before answering. The baseline/proposed system must use the same answer model and budget when comparing. A summary tree alone is not the claimed ECR contribution.

### R14. HippoRAG 2 (2025)

Source: [From RAG to Memory](https://arxiv.org/abs/2502.14802), record identifying ICML 2025. Type: published research; abstract reviewed.

It integrates passages and graph-based association for factual and multi-hop retrieval. **Decision: optional relation expansion after document identity is stable.** Financial relations need time, jurisdiction, accounting scope, and provenance qualifiers. Similar entity mentions are not sufficient evidence that facts can be joined. Do not transplant benchmark gains or install graph infrastructure without a measured local benefit.

### R15. LongRAG: Enhancing Retrieval-Augmented Generation with Long-context LLMs (2024)

Source: [paper](https://arxiv.org/abs/2406.15319). Type: research paper/preprint record reviewed.

It explores longer retrieval units and long-context readers. **Decision: compare complete relevant section bundles with smaller units under matched token budgets.** Avoid sending complete 300–1,982-page reports by default. Long context can reduce fragmentation but does not ensure the right version, correct table interpretation, or exhaustive evidence. This title is distinct from another LongRAG paper; pin the ID in experiment notes.

### R16. Recursive Language Models (2025–2026)

Source: [paper](https://arxiv.org/abs/2512.24601), [v3 full text](https://arxiv.org/html/2512.24601v3). Type: research preprint; method summary and limitations reviewed.

RLMs treat long input as an external environment that a model can inspect and decompose through subcalls. **Decision: experimental bounded source-inspection DSL only.** The paper itself notes complexity and possible exploding subcall cost. Use read-only typed operations and explicit budgets, not unrestricted generated Python. This is a comparator or constrained enhancement, not the sole generic agentic loop the brief excludes.

### R17. PageIndex

Source: [author product description](https://vectify.ai/pageindex), [tree-search documentation](https://docs.pageindex.ai/tutorials/tree-search). Type: vendor engineering/documentation, not independently reproduced proof.

Its document tree and reasoning-based navigation are relevant to long structured PDFs. **Decision: optional tree-navigation comparator, preserving vector/lexical escape routes.** Do not repeat the advertised FinanceBench accuracy as a prediction or independent validation; evaluation protocol, document routing, subset, and answer grading matter. Current tree-search documentation returned sparse content in this review, so no SDK syntax is assumed from that page. A tree can still omit a relevant branch.

### R18. BRIGHT (2024)

Source: [paper](https://arxiv.org/abs/2407.12883). Type: research benchmark paper; primary abstract reviewed.

It shows that retrieval requiring reasoning is meaningfully different from simple topical matching. **Decision: test reasoning-heavy comparisons and misleading lexical matches, while preserving simple-query speed.** Its benchmark and scores do not predict financial answer quality. Use explicit query aspects to define evidence needs, not invented hypothetical answers that may bias retrieval.

## 4. Visual and token-level retrieval

### R19. ColBERTv2 (2021 preprint; 2022 publication family)

Source: [paper](https://arxiv.org/abs/2112.01488). Type: research paper; primary abstract reviewed.

Late interaction keeps token-level representations and uses compression to manage their footprint. **Decision: optional detailed-match reranking experiment.** It may retain distinctions hidden in a single vector, but introduces storage and scoring costs and does not solve entity/version scope automatically. The baseline should first establish whether candidate evidence is missing or only misranked.

### R20. ColPali (2024 preprint; ICLR 2025)

Source: [paper](https://arxiv.org/abs/2407.01449), [proceedings PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/99e9e141aafc314f76b0ca3dd66898b3-Paper-Conference.pdf). Type: published research; abstract/introduction reviewed.

It retrieves page images using vision-language multi-vector representations, preserving visual signals that text extraction can lose. **Decision: targeted visual-page sidecar for scans, tables, and formulas.** It returns relevant pages, not automatically trustworthy numeric cell values. Index size, hardware, and original evidence recovery must be measured; do not assume visual retrieval makes OCR or answer verification unnecessary.

### R21. Docling Technical Report (2024)

Source: [paper](https://arxiv.org/abs/2408.09869), [official documentation](https://docling-project.github.io/docling/). Type: technical report plus implementation docs.

It describes a structured PDF conversion pipeline with layout and table models. **Decision: evaluate as an ingestion adapter on a stratified page sample before full-corpus use.** Preserve page/bounding-box provenance and source tables rather than merely exporting plain Markdown. Check code and model-artifact licenses separately. High-quality parsing is a prerequisite, not a standalone retrieval innovation.

## 5. Sufficiency, verification, and evaluation

### R22. Sufficient Context (2024 preprint; ICLR 2025)

Source: [Google Research paper page](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems/), [paper](https://arxiv.org/abs/2411.06037). Type: published research.

The work distinguishes relevant context from context sufficient to answer. **Decision: track requested slots and explicitly partial answers, with supported claims required.** A sufficiency classifier is fallible and does not prove collection-wide absence. Test missing-year and no-evidence cases alongside answerable questions; do not achieve apparent precision by refusing everything.

### R23. RAGChecker (2024)

Source: [paper](https://arxiv.org/abs/2408.08067). Type: research evaluation framework; primary abstract reviewed.

It advocates finer-grained diagnosis of retrieval and generation rather than one opaque end score. **Decision: independent claim-support, retrieval-coverage, and failure-attribution diagnostics.** These supplement, never replace or modify, the official notebook. The additional evaluator should not quietly feed gold missing points back into the runtime answer pipeline.

### R24. Lost in the Middle (2023; TACL publication family)

Source: [paper](https://arxiv.org/abs/2307.03172). Type: published research; primary abstract reviewed.

It documents positional sensitivity in the evaluated long-context models. **Decision: test evidence ordering and extract a source-backed claim ledger before long synthesis.** Do not assume the exact historical degradation holds for every current model, or that a larger context window guarantees evidence use. Reordering is an experiment, not an excuse to discard hard evidence.

## 6. Model and implementation sources

### R25. Default embedding model

Source: [BAAI/bge-small-en-v1.5 model card](https://huggingface.co/BAAI/bge-small-en-v1.5). Type: author model card; accessed 23 October 2026.

Use as a small English retrieval baseline with its model-specific input instruction, tokenizer window, and revision pinned. License shown: MIT. Similarity is not probability. **Decision: default low-resource candidate generator, not asserted best financial model.** Its input budget motivates canonical units plus indexed windows.

### R26. Default cross-encoder

Source: [ms-marco-MiniLM-L6-v2 model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2). Type: author model card; accessed 23 October 2026.

It is a passage relevance ranker trained on MS MARCO, with Apache-2.0 shown. **Decision: default bounded reranker.** It is not an entailment verifier or a financial-number validator. Published throughput is hardware-specific; do not reuse the card's GPU figures as our CPU latency.

### R27. Qwen3 Embedding and Reranking (2025)

Sources: [paper](https://arxiv.org/abs/2506.05176), [embedding 0.6B card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [reranker 0.6B card](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B). Type: author research/model documentation.

The family provides configurable embedding and reranking models, including 0.6B variants with longer input support. **Decision: accuracy-profile candidates, subject to server throughput and held-out local gains.** Both reviewed cards show Apache-2.0. Follow their task formatting rather than treating every model as an interchangeable pooled encoder. Do not infer a local win from general benchmark leadership.

### R28. Verified implementation documentation

Context7 was used to resolve libraries and retrieve scoped official documentation. Sources checked: [Sentence Transformers retrieval usage](https://github.com/huggingface/sentence-transformers/blob/main/docs/sentence_transformer/usage/usage.rst), [FAISS metric guidance](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances), [FastAPI multipart files/forms](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/), [Langfuse observation lifecycle](https://github.com/langfuse/langfuse-python/blob/main/_autodocs/api-reference/client.md), and [PyMuPDF extraction documentation](https://github.com/pymupdf/pymupdf/blob/main/docs/app1.rst).

Use query/document-specific embedding methods with model-aware prompts; normalized inner product for cosine; multipart file plus form fields for indexing; bounded-lifecycle nested observations and usage/cost dictionaries; and page/block provenance in extraction. These support API correctness, not retrieval superiority. Verify the installed versions at build time. PyMuPDF is optional and has licensing implications; the implementation lead must record chosen parser and model licenses.

## 7. What changed in the proposed design because of this review

1. Page discovery became a first-class stage, with document/page/chunk oracle diagnostics and an optional page scorer (R06).
2. A fixed-fusion baseline remains mandatory; adaptive routing is not assumed to help (R09, R10).
3. Contextual descriptors are separate from immutable source text (R04).
4. Broad question handling evaluates complementary aspects, not only single-passage relevance (R08, R18).
5. Tables and original page images retain their own source structure (R03, R20, R21).
6. The claim ledger checks source sufficiency and separates extraction from final synthesis (R22–R24).
7. Expensive model work is budgeted and deferred where it adds value (R01, R02, R05).
8. Hierarchy, graph association, visual retrieval, are individually ablated experiments; recursive retrieval remains disabled (R13–R20), not an unvalidated mega-stack.

## 8. Experimental contribution versus prior art

No individual ingredient here is claimed to be a new research invention. Hierarchies, query decomposition, graphs, verification, reranking, and set selection all have prior art. The proposed competition contribution is a **source-grounded evidence-obligation executor**: qualified document identities, finite section evidence scans, complementary coverage selection, and traceable reconciliation, tested on unseen source collections.

A useful claim for the write-up would be: “At the same measured token budget, our evidence-coverage executor improves cross-entity/page coverage and reduces wrong-period/regime contamination relative to a strong hybrid/rerank baseline.” Only make that claim after the paired experiment establishes it. If it fails, revise or remove the mechanism. Do not claim novelty merely because the pipeline has a new acronym.

## 9. Ideas deliberately excluded from the core

- Training a large foundation model from scratch: outside scope and unsupported by 100 questions.
- Indexing benchmark answers or benchmark chunks as if they were source documents: contamination.
- Pure tree search, vanilla GraphRAG, or an unrestricted ReAct loop as the whole solution: insufficient under the brief and weakly controlled cost/coverage.
- Full-corpus vision embeddings or LLM fact extraction before measuring ingestion resources: potentially expensive and unnecessary.
- Learned adaptive fusion based only on model confidence: unproven and vulnerable to small-data overfit.
- Quoting a vendor's 98% score as a forecast: incompatible tasks/protocols and no independent local reproduction.
- Filling absent source facts from the answer model's parametric knowledge: violates collection-grounded answering.

## 10. Review limitations and next research work

Not every implementation or appendix was reproduced. Some entries were reviewed at abstract/model-card level; detailed full-text inspection focused on financial retrieval, HC-RAG's ablations, and RLM limitations. The HC-RAG bibliographic date inconsistency is retained explicitly. Private production systems and unpublished models were not audited. No model has been run on the supplied corpus, so all architecture-specific benefit statements are hypotheses.

Before adopting a heavy experimental component, the assigned research agent must inspect its code/license, reproduce a minimal retrieval call, measure its memory and throughput, and run the frozen local ablation. Additional papers should enter the plan only with a concrete failure mechanism and an acceptance test, not just because they are newer.

## 11. Additional checks made during the merge

### R29. HiREC — hierarchical retrieval with evidence curation

[Primary paper record, 2505.20368](https://arxiv.org/abs/2505.20368), ACL-associated 2025 work; abstract refreshed in this merge. It directly addresses near-duplicate standardized financial documents through document-first retrieval and curated passage evidence. Adopt qualified document routing and relevance assessment. Its complementary-query loop is not adopted in the strict fixed DAG. Reported gains and its LOFin benchmark do not establish this competition's metrics.

### R30. HDRR — document routing and scoped retrieval

[Primary preprint record, 2603.26815](https://arxiv.org/abs/2603.26815), v3, refreshed. It studies the robustness/precision trade-off between file routing and chunk retrieval, then scopes chunk search to selected documents. This supports measuring routing contamination and downstream page misses separately. The unified system preserves uncertainty escape and explicit coverage; a two-stage router alone is not our claimed additional architecture. No author-reported score is copied into a local forecast.

### R31. MimirRAG

[Primary preprint record, 2605.25030](https://arxiv.org/abs/2605.25030), refreshed. It combines metadata, structure-preserving parsing, tables and an agentic workflow for financial QA. Adopt the testable metadata/table mechanisms, not its full multi-agent architecture or benchmark score. The evidence reinforces source handling, but does not prove that adding agents improves this system.

### R32. READ / Beyond Top-K

[Primary preprint record, 2608.06305](https://arxiv.org/abs/2608.06305), refreshed. The authors show how table numbers lose units/year context and compare lexical/structural reads against dense retrieval. They explicitly report that BM25 was statistically indistinguishable from READ under their test. Adopt source-header lineage, lexical search and bounded source reads. Do not attribute the result to an agentic loop or ship that loop as the core.

### R33. Ingest-time semantic compilation

[Primary position-paper record, 2608.20845](https://arxiv.org/abs/2608.20845), refreshed. It proposes maintained embeddings and provenance-validated atomic claims, with evidence from broadcast transcripts. Page cards are navigation aids, not equivalent to its claim substrate. The unified core compiles source structure cheaply and extracts claims at query time. Full ingest-time semantic claim compilation remains a separate expensive experiment rather than an assumed ingestion optimization.

### R34. Adaptive Query Routing

[Primary preprint record, 2604.14222](https://arxiv.org/abs/2604.14222), refreshed. Its evaluations compare vector, tree and hybrid approaches by query complexity. Retain the hypothesis that different question types need different evidence scopes; do not present this as a direct PageIndex replication or universal tree-search win. The paper's numerical results are author-reported on different protocols, not our four official metrics.

### R35. AdaRankLLM and listwise filtering

[Primary preprint record, 2604.15621](https://arxiv.org/abs/2604.15621), refreshed. It investigates adaptive listwise reranking and passage dropout, including a distillation recipe. Only the zero-shot ability to reject irrelevant context motivates a bounded selection test. No distillation or model training is adopted. Listwise selection is still a supporting noise filter, not sufficient evidence of a novel complete architecture.

### R36. LLM-specific utility: citation correction

[Primary record, 2510.11358](https://arxiv.org/abs/2510.11358), refreshed; record notes CIKM 2026. Its actual subject is generator-specific evidence utility and the limits of existing utility scoring. The source final_plan grouped it under listwise selection; that attribution is removed. Adopt generator-matched evaluation of context portfolios. Do not assert that this source demonstrates a “none” selection mechanism.

### R37. Parser/chunker evaluation

[Primary preprint record, 2604.12047](https://arxiv.org/abs/2604.12047), refreshed. It evaluates parser/chunker interactions on financial QA, including tables. This supports a stratified parser pilot. The abstract does not justify a universal 0.76-second Docling timing or a parser winner on this Mac. Retain source fidelity and actual target-server measurements instead of copying those timing claims.

### R38. Long-context token tax

[Primary preprint record, 2606.20898](https://arxiv.org/abs/2606.20898), refreshed. It studies an accuracy/token-cost frontier in manufacturing safety, not this financial corpus. Adopt measured context allocation trade-offs, without copying its dollar amounts or treating all-document prompting as always worse. The core retains bounded relevant source evidence and explicit coverage limitations.

### R39. FastEmbed implementation checks

[Official FastEmbed README](https://github.com/qdrant/fastembed/blob/main/README.md) and [supported-model examples](https://github.com/qdrant/fastembed/blob/main/docs/examples/Supported_Models.ipynb), retrieved through Context7 during merging. Supported-model enumeration includes the MiniLM-L6 ONNX ranker; custom models require explicit registration. Inspect actual loaded model/tokenizer/artifacts. Automatic tokenizer truncation is not a substitute for visibility auditing; windows must be prepared and mapped before inference.

### R40. PyMuPDF4LLM implementation checks

[Official README](https://github.com/pymupdf/pymupdf4llm/blob/main/README.md), retrieved through Context7 during merging. Per-page conversion and OCR controls are available, but version-specific output shapes/defaults need runtime checks. Explicit native-first and selective-OCR configuration avoids accidental blanket OCR. This is implementation evidence only, not a parsing-quality guarantee. Retain raw page artifacts and confirm actual page metadata.

## 12. Final adoption discipline

The selected core is the bounded identity/structure/coverage/provenance executor in ARCHITECTURE.md. Research serves mechanisms and acceptance tests. Keep a strong same-model hybrid/rerank control. Treat summary omission, routing errors, lost table headers, source token truncation, inference cost and unsupported claims as separate measurable failure classes. No vendor accuracy headline, unrelated benchmark or collection statistic is evidence that the submission reaches 0.95.
