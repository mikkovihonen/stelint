# Model Upgrade Plan: False Positive Filtering for ASD-STE100

This document outlines the research, comparative analysis, architecture, and phased implementation plan for upgrading stelint's false-positive (FP) filtering subsystem from an external generative LLM prompt to a fast, calibrated, local ONNX cross-encoder classifier.

---

## 1. Problem Statement & Root Cause Analysis

Stelint's generative LLM false-positive filter (`checks_llm_fp.py`) was designed to reduce false alarms from spaCy heuristic checks (such as `VerbForms`, `ConnectingWords`, `PartOfSpeech`, `TechnicalVerbAsNoun`, and `MissingArticles`). However, live runs and empirical testing revealed that the filter frequently collapses into classifying almost everything as a false positive.

### Root Causes:

1. **Sycophancy & Asymmetric Prompt Framing**:
   The prompt instructions in `_build_unified_prompt` heavily emphasize `FALSE_POSITIVE` criteria across all rules while providing minimal explanation for `CONFIRM`. Instruction-tuned and smaller local LLMs (e.g. Gemma, LLaMA) suffer from acquiescence bias, defaulting to the prompted majority class (`FALSE_POSITIVE`).

2. **Negative Confirmation Bias in Rejection Logic**:
   The filter operates on strict opt-in logic: an issue is preserved only if the LLM output strictly matches `CONFIRM`. If the model outputs conversational explanations, formats lines differently, or expresses uncertainty, the regex parser fails to match `CONFIRM`, silently suppressing the issue.

3. **Information Starvation via Truncation**:
   Sentence context was truncated to 60 characters (`sent.text[:60]`), stripping the right half of sentences and depriving the model of grammatical clauses, coordinate conjunctions, and multi-word noun context.

4. **Operational & Latency Overhead**:
   Generative LLM inference requires an external server (vLLM, llama.cpp, or cloud API) and incurs 1–10 seconds of round-trip latency, making offline or fast CI/CD integration impractical.

---

## 2. Model Architecture Comparison

To determine the optimal architecture for false-positive filtering in technical grammar linting, we evaluated four paradigms:

| Dimension | Generative LLM (Current) | Sentence Bi-Encoder (e.g. MiniLM / BGE) | Contextual Token Embeddings (ModernBERT / DeBERTa) | Cross-Encoder Classifier (Target Architecture) |
|---|---|---|---|---|
| **Syntactic & Grammar Sensitivity** | Low (starved by 60-char truncation) | ❌ **Very Low** (semantic topic similarity only; invariant to articles/tenses) | 🟡 **High** (captures token-level syntax & POS context) | 🟢 **Very High** (joint cross-attention over rule + token + full sentence) |
| **Output Calibration** | ❌ Uncalibrated binary tokens | 🟡 Cosine similarity score | 🟢 Continuous probability $[0, 1]$ | 🟢 **Calibrated softmax probability $[P(\text{TP}), P(\text{FP})]$** |
| **Susceptibility to Bias** | ❌ Severe (sycophancy / prompt drift) | 🟢 None | 🟢 Low | 🟢 **Low** |
| **Inference Latency (CPU)** | ❌ 1,000–10,000 ms (GPU preferred) | 🟢 1–3 ms | 🟢 2–5 ms | 🟢 **5–10 ms** |
| **External Dependencies** | ❌ Requires external LLM endpoint/server | 🟢 Self-contained local model | 🟢 Self-contained local model | 🟢 **Self-contained local ONNX model** |
| **Best Role in stelint** | Discourse-level tone & open-ended advice | Document deduplication & topic grouping | Word sense disambiguation & polysemy | **General False Positive filter across all rules** |

### Key Findings:
- **Sentence-level Bi-Encoders are unsuitable** for grammar validation because sentence embeddings are designed to be invariant to minor grammatical variations (e.g. *"Open the valve"* and *"Open valve"* have $\sim 0.98$ cosine similarity).
- **Cross-Encoders provide the ideal trade-off**: They evaluate full cross-attention between the rule description and the sentence context, generating a calibrated probability distribution without generative hallucination or parsing fragility.

---

## 3. Target Architecture: Tiered Local Filtering

```
                         FLAGGED ISSUES FROM SPACY CHECKS
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │  Tier 1: Deterministic spaCy Heuristics │
                   │  - Generic plurals, numbered references │
                   │  - Proper nouns, possessives, compounds │
                   │  - Latency: < 0.1 ms                    │
                   └────────────────────┬────────────────────┘
                                        │ (Ambiguous / Borderline)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │  Tier 2: Local ONNX Cross-Encoder       │
                   │  - Sequence classifier (~25M params)    │
                   │  - Quantized INT8 ONNX (< 30 MB)        │
                   │  - Latency: 2–8 ms on CPU               │
                   │  - Zero external server requirement     │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │  Calibrated Decision Thresholding       │
                   │  - Suppress only if P(FP) > τ_rule      │
                   │  - Retain issue if confidence is low    │
                   └────────────────────┬────────────────────┘
                                        │ (Optional / Document-wide)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │  Tier 3: Optional Generative LLM        │
                   │  - Global polysemy across full document │
                   │  - Only active when STELINT_LLM_BASE_URL│
                   └─────────────────────────────────────────┘
```

---

## 4. Technical Specifications

- **Runtime Engine**: `onnxruntime` (CPU execution provider).
- **Model Size**: $\le 30 \text{ MB}$ (INT8 quantized).
- **Latency**: $\le 8 \text{ ms}$ per issue on standard CPU.
- **Input Schema**: `[CLS] Rule: {rule_name} | Word: {target_word} [SEP] {sentence_text} [SEP]`
- **Output Schema**: Softmax probability $[P(\text{True Positive}), P(\text{False Positive})]$.
- **Threshold Policy**: Per-rule rejection threshold $\tau_{\text{rule}}$ (e.g. $\tau = 0.85$). An issue is suppressed only if $P(\text{FP}) > \tau$; otherwise, it is safely retained.

---

## 5. Implementation Roadmap

### Phase 1: Benchmark & Dataset Generation
1. Extract positive/negative pairs from ASD-STE100 Issue 9 specification examples.
2. Build synthetic data generators for technical grammar rules.
3. Ingest real-world annotated regression cases (`docs/runbook.md`, `docs/missingarticles_analysis.md`).
4. Implement evaluation harness (`scripts/eval_fp_filter.py`).

### Phase 2: Model Training & ONNX INT8 Quantization
1. Fine-tune sequence classifier on the curated dataset.
2. Export model to ONNX with dynamic batching.
3. Apply dynamic INT8 quantization via `onnxruntime.quantization`.
4. Tune per-rule confidence thresholds against precision-recall validation curves.

### Phase 3: Runtime Integration in `stelint`
1. Implement `src/stelint/classifier/` subsystem:
   - `onnx_runner.py`: Minimal, dependency-light ONNX Runtime runner.
   - `tokenizer.py`: Fast tokenizer for encoding input pairs.
   - `model_loader.py`: Model discovery, caching (`~/.cache/stelint/`), and SHA-256 verification.
2. Refactor `checks_llm_fp.py` into a unified tiered filter:
   - Tier 1: Deterministic spaCy heuristics.
   - Tier 2: Local ONNX Classifier.
   - Tier 3: Optional external LLM fallback.
3. Update `pyproject.toml` dependencies.

### Phase 4: Validation & Benchmarking
1. Comprehensive automated unit tests for tokenizer, ONNX runner, and filter fallback.
2. Integration verification on `docs/runbook.md`.
3. Benchmark suite regression testing.

