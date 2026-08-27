# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

- Multi-tier false positive filter: rule-based pre-filters, then an optional local ONNX cross-encoder classifier (sub-10ms per issue), then LLM validation as fallback.
- Deterministic context classifier: marks sentences as procedural, descriptive, or safety from Markdown structure and syntax patterns. No LLM endpoint required.
- Output formatters: `--format` supports json, vale, github (GitHub Actions commands), and sarif (SARIF v2.1.0).
- Add `MissingArticles` to the false positive filter. Batch interleaving across check types keeps prompt truncation from starving later check types.
- Evaluation tooling: ground-truth false positive / true positive dataset generator and precision, recall, and F1 benchmark (`scripts/dataset_generator.py`, `scripts/eval_fp_filter.py`, `data/fp_dataset.json`).
- Add `onnxruntime` dependency for the local false positive classifier.
- MissingArticles: reduce false positives for plural nouns in general statements, uncountable and process nouns, proper nouns and acronyms, hyphenated compounds, numbered references, coordinate lists with a shared determiner, quoted terms, possessive determiners, and misparsed verbs. Italic example words are no longer flagged.
- MissingArticles: bound the coordinate-list fallback to nearby conjuncts so long spaCy pseudo-sentences in Markdown do not suppress genuine missing articles.
- NonApprovedWords: remove self-mapping glossary entries (`check`, `cover`, `damage`, `test`, `complete`) that produced messages such as "Use 'test' instead of 'test'".
- NonApprovedWords: warn at load time on self-mapping replacement entries and skip them in the check.
- PartOfSpeech: skip words already handled by the TechnicalNounAsVerb check to remove duplicate warnings on `check`, `cover`, and `test`.
- Fix syntax errors in the LLM filter prompt builder and response parser that broke the LLM code path.
- Replace `/prosecco-add-to-glossary` references in issue messages with the real `python -m stelint.add_to_glossary` CLI.
- LLM polysemy check: local candidate preprocessing before any LLM call. Words are pre-filtered by occurrence count, POS consistency, and (with the optional sense2vec model) monosemy. Candidates are processed in compact batches (5 words per call, at most 4 context windows of 80 characters per word, capped token budget) to reduce latency and token usage.
- LLM polysemy check: context windows are cut around the word itself, so the word stays visible in long sentences.
- LLM polysemy check: parse verdicts from echoed "Word: x" headers, a format some reasoning models use.
- Add `STELINT_LLM_TIMEOUT` env var for the LLM request timeout in seconds (default: 60, was 30).
- Cap context classification token budget at 1500 to bound call duration on reasoning models.
- Add `STELINT_LLM_TYPE` env var to disable LLM reasoning output. Maps backend type (deepseek, vllm, qwen, openrouter) to the request body each backend expects. Verified with llama.cpp-served thinking models (Qwen3, Gemma 3) via the `vllm` type.
- Add `STELINT_LLM_THINKING` env var to keep LLM reasoning (thinking) output on or off. Overrides the `STELINT_LLM_TYPE` default. Accepts on/off, true/false, 1/0, yes/no.
- Fix runbook: glossary config is passed via the `--glossaries` flag, not a `STELINT_GLOSSARIES` env var

## [0.1.5] - 2026-08-10

- Fix sense2vec installation: use STELINT_S2V_PATH env var with manual extraction
- Rename SENSE2VEC_PATH to STELINT_S2V_PATH for namespacing
- Remove noisy progress messages from spaCy model loading
- Add spaCy model info to --help output
- Add sense2vec instructions to --help output
- Add specific download URL and extraction instructions to --help

## [0.1.4] - 2026-08-10

### Breaking changes

- Stdin reading now requires explicit `-` argument. Running `stelint` without arguments shows usage instead of hanging.

### What's new

- `--help` flag shows usage information

## [0.1.3] - 2026-08-10

- Add sense2vec dependency and make model loading optional

## [0.1.2] - 2026-08-10

- Fixes to NLP model loading with stelint module (python -m spacy download en_core_web_sm)

## [0.1.1] - 2026-08-10

- Cosmetic fixes

## [0.1.0] - 2026-08-10

- Proof-of-concept version for evaluation of further development
