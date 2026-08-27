# Stelint Runbook

## Prerequisites

- Python 3.13 or later
- [uv](https://docs.astral.sh/uv/) for dependency management
- A spaCy English model (`en_core_web_sm`)

### Install stelint

```bash
cd <repo-root>
uv sync
```

`uv sync` installs the `en_core_web_sm` model along with the dev dependencies, so
no separate download step is needed for local development or CI.

### Install the spaCy model

Only needed when installing stelint from PyPI, where the model is not bundled:

```bash
python -m spacy download en_core_web_sm
```

### Optional: sense2vec model

Stelint can use [sense2vec](https://github.com/explosion/sense2vec) for enhanced word sense disambiguation in Section 6 checks. This is optional — stelint works fully without it.

To install the English sense2vec model:

```bash
# 1. Download the model
wget https://github.com/explosion/sense2vec/releases/download/v1.0.0/s2v-reddit-2015-distinct.model.tar.gz

# 2. Extract to a directory
mkdir -p ~/.local/share/s2v
tar -xzf s2v-reddit-2015-distinct.model.tar.gz -C ~/.local/share/s2v

# 3. Set the environment variable
export STELINT_S2V_PATH=~/.local/share/s2v
```

## Quick start

Lint a file:

```bash
uv run python -m stelint path/to/file.md
```

Lint from stdin:

```bash
cat path/to/file.md | uv run python -m stelint -
```

## Usage

```
uv run python -m stelint [OPTIONS] [FILE | DIRECTORY ...]
```

| Option | Description |
|---|---|
| `FILES...` | Path to `.md` file(s) or directories to lint recursively. Use `-` or pipe to read from stdin. |
| `--format`, `-f` | Output format: `vale` (default), `json`, `github` (GitHub Actions annotations), `sarif` (SARIF v2.1.0), or `summary`. |
| `--disable` | Comma-separated list of rule names to disable (e.g. `ShortSentences,Hyphens`). |
| `--enable` | Comma-separated list of rule names to enable (all other rules are disabled). |
| `--include-all` | Show all warnings, including those inside metadata regions such as headers, bold labels, tables, and code blocks. |
| `--glossaries` | Path to `glossaries.yaml` config file. |
| `--quiet`, `-q` | Quiet mode: suppress informational messages. |

## How it works

1. The input text (Markdown) is preprocessed to strip non-prose elements (code blocks, links, images, HTML blocks, table rows, headers) while preserving exact character offsets.
2. The cleaned text is processed by a spaCy pipeline.
3. **Deterministic Context Classification**: Sentences are automatically classified into `PROCEDURAL`, `DESCRIPTIVE`, or `SAFETY` contexts based on Markdown AST structure (numbered steps, bullet lists, procedural headings). This automatically prevents rule conflicts between Section 5 (procedural) and Section 6 (descriptive) without requiring an LLM.
4. All ASD-STE100 check functions run against the spaCy document.
5. Issues are mapped back to their original positions in the input file and deduplicated.
6. Context-inappropriate and metadata-suppressed issues are filtered out.
7. Results are emitted in the chosen `--format` (Vale, JSON, GitHub Actions, SARIF, or Summary).

## Check categories

Stelint covers the following sections of the ASD-STE100 specification:

### Section 1 — Words

- Approved words list
- Part of speech verification
- Approved meaning and forms
- Technical noun categories and approval
- Regional slang and jargon
- British English usage

### Section 2 — Multi-word nouns

- Multi-word noun consistency
- Technical noun clarity

### Section 3 — Verbs

- Verb forms and tenses
- Past participle as adjective
- Passive voice detection
- `-ing` forms
- Noun used as verb

### Section 4 — Sentences

- Short sentences (max 35 words)
- Contractions
- Forbidden modals
- Vertical lists
- Connecting words
- Missing articles
- Article usage

### Section 5 — Procedural writing

- Sentence length in procedures
- Multiple instructions per step
- Imperative mood in procedures
- Descriptive statement first
- Notes formatting

### Section 6 — Descriptive writing

- Information structure
- Key words
- Paragraph topic and length
- Paragraph structure

### Section 7 — Safety instructions

- Safety instruction format
- Safety instruction explanation

### Section 8 — Punctuation and word count

- Semicolons, hyphens, parentheses
- Word count limits (with parentheses and numbers)
- Hyphenation patterns
- Vertical list colons

### Section 9 — Writing practices

- Word usage and consistent terminology
- Phrasal verbs
- Consistent style
- Sentence construction variety

### General Recommendations (GR-1 to GR-8)

- GR-1: Conjunction "that"
- GR-2: Ambiguous "with"
- GR-3: Ambiguous pronouns
- GR-4: Ambiguous "this"
- GR-5: False friends
- GR-6: Latin abbreviations
- GR-7: Gender pronouns
- GR-8: Possessive form

## Examples

### Lint a Markdown file

```bash
uv run python -m stelint docs/manual.md
```

### Lint an entire directory recursively

```bash
uv run python -m stelint docs/
```

### Pipe text from another tool

```bash
cat CHANGELOG.md | uv run python -m stelint -
```

### Output in JSON or SARIF for CI/CD pipelines

```bash
# JSON output
uv run python -m stelint --format json docs/

# SARIF output (for GitHub Code Scanning)
uv run python -m stelint --format sarif docs/ > results.sarif

# GitHub Actions workflow annotations
uv run python -m stelint --format github docs/

# Summary statistics
uv run python -m stelint --format summary docs/
```

### Disable specific rules

```bash
uv run python -m stelint --disable ShortSentences,Hyphens docs/manual.md
```

### Include all warnings (even in headers and metadata)

```bash
uv run python -m stelint --include-all manual.md
```

### Use as a Python library

```python
from stelint.stelint import LintConfig, lint_file, lint_text

# Lint a string
issues = lint_text("Check the filter; it is dirty.")
for issue in issues:
    print(f"{issue.line}:{issue.column} {issue.rule}: {issue.message}")

# Lint a file with custom config
config = LintConfig(disabled_rules={"Semicolons"})
issues = lint_file("docs/manual.md", config=config)
```

## Output formats

### Vale format (default)

```
manual.md:12:5 STE100.ShortSentences: Sentence is too long (52 words). Max 35.
manual.md:28:1 STE100.PassiveVoice: Passive voice detected: "is carried out".
manual.md:45:10 STE100.MissingArticles: Missing article before "safety valve".
```

When `--include-all` is used, issues inside metadata regions are also shown with a region label:

```
table.md:3:1 STE100.MissingArticles: [table_row] Missing article before "pressure".
```

### JSON format

```json
[
  {
    "file": "manual.md",
    "line": 28,
    "column": 1,
    "rule": "STE100.PassiveVoice",
    "rule_type": "PassiveVoice",
    "message": "Passive voice detected: \"is carried out\".",
    "region_type": null,
    "severity": "warning"
  }
]
```

### GitHub Actions format

```
::warning file=manual.md,line=28,col=1,title=STE100.PassiveVoice::Passive voice detected: "is carried out".
```

## Configuration

Stelint uses a layered glossary system. Constants are loaded in cardinality order — later layers override earlier ones.

### Base layer (always loaded)

`asd-ste100_base.jsonl` is always loaded first with the lowest cardinality. It contains the full ASD-STE100 specification constants and cannot be removed or reordered via configuration.

### User layer (optional)

Create `glossaries.yaml` anywhere and pass its path to the `--glossaries` flag (relative to CWD or absolute):

```bash
uv run python -m stelint --glossaries docs/examples/glossaries.yaml file.md
```

Example config at `docs/examples/glossaries.yaml`:

```yaml
glossaries:
  - path: ../../src/stelint/company_glossary.jsonl
    cardinality: 100
  - path: ./project_glossary.jsonl
    cardinality: 200
```

Rules:
- `path` is relative to the directory containing `glossaries.yaml`.
- `cardinality` is an integer. Higher values override lower ones.
- `asd-ste100_base.jsonl` must not appear in this file. It is always loaded first with the lowest cardinality.
- If `--glossaries` is omitted, only the base layer is used.

### JSONL format

Each line is a JSON object:

```json
{"namespace": "words", "name": "NON_APPROVED_WORDS", "type": "mapping", "data": {"word": "replacement"}}
```

To remove a key from the base, use `"__REMOVE__"`:

```json
{"namespace": "words", "name": "NON_APPROVED_WORDS", "type": "mapping", "data": {"unwanted_word": "__REMOVE__"}}
```

### Adding entries programmatically

```python
from stelint.glossary import add_to_project_glossary

add_to_project_glossary(
    namespace="words",
    name="NON_APPROVED_WORDS",
    key="approved_word",
    value="allowed_term",
)
```

## Suppressing specific checks

The preprocessor automatically suppresses certain checks inside specific regions:

| Region | Suppressed checks |
|---|---|
| `header` | MissingArticles, ConnectingWords |
| `bold_marker` | MissingArticles |

Use `--include-all` to disable all metadata-based suppression.

## LLM-powered checks

Stelint can use a large language model to detect issues that spaCy cannot,
such as words used with different meanings in different parts of the document
(same-part-of-speech polysemy).

### Enable LLM checks

Set the following environment variables:

| Variable | Description | Example |
|---|---|---|
| `STELINT_LLM_BASE_URL` | OpenAI-compatible API endpoint | `http://llama:9999/v1` |
| `STELINT_LLM_MODEL` | Model name (default: `local-ornith`) | `local-ornith` |
| `STELINT_LLM_API_KEY` | API key (any non-empty string for local models) | `sk-no-key` |
| `STELINT_LLM_TYPE` | LLM backend type. Selects the request body that disables reasoning output. See below. | `deepseek` |
| `STELINT_LLM_THINKING` | Keep reasoning (thinking) output `on` or `off`. Overrides the type default. | `on` |
| `STELINT_LLM_TIMEOUT` | Request timeout in seconds (default: 60). Raise for slow local models. | `120` |

Example:

```bash
export STELINT_LLM_BASE_URL="http://llama:9999/v1"
export STELINT_LLM_MODEL="local-ornith"
export STELINT_LLM_API_KEY="sk-no-key"
uv run python -m stelint file.md
```

### Disable reasoning output

Reasoning models spend tokens on a thought process before the answer.
Set `STELINT_LLM_TYPE` to the type of your LLM backend to disable reasoning
output. Stelint maps each type to the request body that the backend expects:

| `STELINT_LLM_TYPE` | Backend | Request sent |
|---|---|---|
| `deepseek` | DeepSeek API | `thinking: {"type": "disabled"}` |
| `vllm` | vLLM and llama.cpp (Qwen3, Gemma 3, DeepSeek, and other thinking models) | `chat_template_kwargs: {"enable_thinking": false}` |
| `qwen` | Qwen (DashScope) | `enable_thinking: false` |
| `openrouter` | OpenRouter | `reasoning: {"effort": "none"}` |

The value is case-insensitive. An unset or unknown value leaves the request
unchanged (reasoning stays enabled). OpenAI o-series models do not support
full disabling. Their minimum is `reasoning_effort: low`.

Use `STELINT_LLM_THINKING` to override this. Set it to `on` to keep
reasoning enabled even with a known type, or to `off` to force it off.
Without the variable, a known type disables reasoning. Accepted values:
`on`, `off`, `true`, `false`, `1`, `0`, `yes`, `no` (case-insensitive).
An invalid value is ignored with a warning.

### What the LLM checks

- **LLMPolysemy**: Detects when the same word is used with different meanings
  across the document, even when the part of speech is the same. spaCy can only
  detect polysemy at the POS level (e.g. "light" as NOUN vs ADJ), but the LLM
  can detect subtle meaning differences within the same POS (e.g. "run" meaning
  *execute* vs. *manage*, both as VERB).

  Candidate collection is a local preprocessing step (no LLM calls). A word is
  sent to the LLM only if:

  - it appears at least 3 times,
  - all occurrences have the same part of speech (different POS is handled by
    the spaCy checks),
  - it is not a proper noun, stop word, or single-letter word,
  - if the optional sense2vec model is installed (`STELINT_S2V_PATH`), the
    model does not know the word with exactly one sense. A monosemous word
    cannot be polysemous, so it is skipped without an LLM call.

### Context classification

When LLM checks are enabled, stelint also classifies each sentence as
**PROCEDURAL**, **DESCRIPTIVE**, or **SAFETY**, then suppresses context-
inappropriate issues:

| Sentence type | Suppresses |
|---|---|
| **PROCEDURAL** | `ImperativeInDescription`, `ParagraphStructure`, `ParagraphLength`, `ParagraphTopic` |
| **DESCRIPTIVE** | `NonImperativeInProcedures`, `SentenceLength` |
| **SAFETY** | `ForbiddenModals` |

This prevents contradictory flags (e.g., imperative mood being flagged as wrong
in both procedural and descriptive contexts).

### Performance

- LLM checks are fully optional. Stelint works identically without them.
- Each LLM call has a 60-second timeout by default. Set
  `STELINT_LLM_TIMEOUT` for slower local models.
- LLM failures are non-fatal — stelint continues with spaCy results only.
- Results are cached per document to avoid redundant LLM calls.
- Local pre-filters (occurrence count, POS consistency, optional sense2vec
  monosemy check) skip words that do not need LLM analysis.
- Candidates are processed in batches of 5 words per LLM call. Small batches
  keep each call short on slow and reasoning models.
- Each prompt shows at most 4 context sentences of 80 characters per word.
- Token budgets are capped per call (1000 tokens per polysemy batch, 1500 for
  context classification), which bounds call duration on reasoning models.

## Development workflow

| Task | Command |
|---|---|
| Sync dependencies | `uv sync` |
| Run stelint on a file | `uv run python -m stelint file.md` |
| Run tests | `uv run pytest src/stelint/tests/` |
| Lint the code | `uv run ruff check src/` |
| Build the package | `uv run python -m build` |

## Configuration files

| File | Purpose |
|---|---|
| `pyproject.toml` | Python package metadata, build config, and dependency groups |
| `docs/examples/glossaries.yaml` | User glossary overrides (optional) |
| `src/stelint/asd-ste100_base.jsonl` | Base ASD-STE100 constants (always loaded) |
| `zensical.toml` | Documentation site configuration |
| `.pre-commit-config.yaml` | Pre-commit hooks for CI quality checks |

## License

MIT
