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

## Quick start

Lint a file:

```bash
uv run python -m stelint path/to/file.md
```

Lint from stdin:

```bash
cat path/to/file.md | uv run python -m stelint
```

## Usage

```
uv run python -m stelint [OPTIONS] [FILE]
```

| Argument | Description |
|---|---|
| `FILE` | Path to a `.md` file to lint. If omitted, stelint reads from stdin. |
| `--include-all` | Show all warnings, including those inside metadata regions such as headers, bold labels, tables, and code blocks. Without this flag, warnings inside metadata regions are suppressed. |

## How it works

1. The input text (Markdown) is preprocessed to strip non-prose elements such as code blocks, links, images, HTML blocks, table rows, and headers.
2. The cleaned text is processed by a spaCy pipeline.
3. All ASD-STE100 check functions run against the spaCy document.
4. Issues are mapped back to their original positions in the input file.
5. Issues inside metadata regions (headers, bold markers, links, etc.) are suppressed unless `--include-all` is set.
6. Results are printed in Vale-compatible format:

```
filename.md:line:col STE100.CheckName: Issue message
```

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

### Pipe text from another tool

```bash
cat CHANGELOG.md | uv run python -m stelint
```

### Include all warnings (even in headers and metadata)

```bash
uv run python -m stelint --include-all manual.md
```

### Use as a Python library

```python
import spacy
from stelint.stelint import main

# Load the model and run checks programmatically
nlp = spacy.load("en_core_web_sm")

# Import individual check functions
from stelint.checks_section1 import check_approved_words, check_part_of_speech
from stelint.checks_section4 import check_short_sentences, check_contractions
from stelint.checks_gr_recommendations import check_conjunction_that

doc = nlp("Your text here.")
issues = check_approved_words(doc)
```

## Output format

By default, only prose issues are reported. Output follows the Vale format:

```
manual.md:12:5 STE100.ShortSentences: Sentence is too long (52 words). Max 35.
manual.md:28:1 STE100.PassiveVoice: Passive voice detected: "is carried out".
manual.md:45:10 STE100.MissingArticles: Missing article before "safety valve".
```

When `--include-all` is used, issues inside metadata regions are also shown with a region label:

```
table.md:3:1 STE100.MissingArticles: [table_row] Missing article before "pressure".
```

## Configuration

Stelint uses a layered glossary system. Constants are loaded in cardinality order — later layers override earlier ones.

### Base layer (always loaded)

`asd-ste100_base.jsonl` is always loaded first with the lowest cardinality. It contains the full ASD-STE100 specification constants and cannot be removed or reordered via configuration.

### User layer (optional)

Create `glossaries.yaml` anywhere and set `STELINT_GLOSSARIES` to its path (relative to CWD or absolute):

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
