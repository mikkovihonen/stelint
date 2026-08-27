"""Dataset generator for ASD-STE100 False Positive Filtering.

Generates ground-truth datasets with annotated True Positives (genuine violations)
and False Positives (compliant usages) across the target check types:
- VerbForms (Rule 3.1)
- ConnectingWords (Rule 4.4)
- PartOfSpeech (Rule 2.1)
- TechnicalVerbAsNoun (Rule 1.1 / 2.1)
- MissingArticles (Rule 4.5)
"""

from __future__ import annotations

import json
from pathlib import Path

# Curated dataset of ASD-STE100 examples based on the specification and real test cases
DATASET_EXAMPLES: list[dict] = [
    # VerbForms: -ing forms
    {
        "rule": "VerbForms",
        "word": "running",
        "sentence": "The pump is running continuously.",
        "label": 0,  # True Positive (Genuine violation: progressive verb)
        "rationale": "Progressive verb '-ing' after be-verb is not allowed in ASD-STE100.",
    },
    {
        "rule": "VerbForms",
        "word": "cooling",
        "sentence": "The cooling water flows through the heat exchanger.",
        "label": 1,  # False Positive (Compliant: technical noun modifier)
        "rationale": "'cooling water' is an approved technical compound noun.",
    },
    {
        "rule": "VerbForms",
        "word": "running",
        "sentence": "Check the running gear for wear.",
        "label": 1,  # False Positive (Compliant: technical noun modifier)
        "rationale": "'running gear' is an approved multi-word noun.",
    },
    {
        "rule": "VerbForms",
        "word": "connecting",
        "sentence": "The technician is connecting the wires.",
        "label": 0,  # True Positive (Genuine violation)
        "rationale": "Active progressive verb 'is connecting'.",
    },
    # ConnectingWords: transitions
    {
        "rule": "ConnectingWords",
        "word": "",
        "sentence": "The pump runs at full speed. The pump temperature increases rapidly.",
        "label": 0,  # True Positive (Related topics without connecting word)
        "rationale": "Two related sentences discussing the pump operating state need a connecting word.",
    },
    {
        "rule": "ConnectingWords",
        "word": "",
        "sentence": "Clean the filter with solvent. Store tools in the cabinet.",
        "label": 1,  # False Positive (Unrelated topics/steps)
        "rationale": "Independent sequential steps on different topics do not require connecting words.",
    },
    # PartOfSpeech: correct vs incorrect POS
    {
        "rule": "PartOfSpeech",
        "word": "oil",
        "sentence": "Oil the hinges monthly.",
        "label": 0,  # True Positive (oil should be used as noun, not verb)
        "rationale": "In STE, 'oil' is an approved noun; use 'lubricate' as verb.",
    },
    {
        "rule": "PartOfSpeech",
        "word": "run",
        "sentence": "The operator runs the test sequence.",
        "label": 1,  # False Positive (correct verb usage if approved)
        "rationale": "Standard verb usage with direct object.",
    },
    # TechnicalVerbAsNoun
    {
        "rule": "TechnicalVerbAsNoun",
        "word": "test",
        "sentence": "Do a test on the system.",
        "label": 0,  # True Positive (verb used as noun)
        "rationale": "In STE, 'test' is a verb; use 'do a test' or appropriate noun.",
    },
    {
        "rule": "TechnicalVerbAsNoun",
        "word": "test",
        "sentence": "The test results are documented in the report.",
        "label": 1,  # False Positive (noun modifier in technical term)
        "rationale": "'test results' is a valid compound noun.",
    },
    # MissingArticles: Rule 4.5
    {
        "rule": "MissingArticles",
        "word": "valve",
        "sentence": "Open valve.",
        "label": 0,  # True Positive (missing article on singular countable direct object)
        "rationale": "Singular countable noun 'valve' requires an article: 'Open the valve.'",
    },
    {
        "rule": "MissingArticles",
        "word": "port",
        "sentence": "Connect the cable to port.",
        "label": 0,  # True Positive (missing article on prepositional object)
        "rationale": "'port' requires an article: 'Connect the cable to the port.'",
    },
    {
        "rule": "MissingArticles",
        "word": "filters",
        "sentence": "Filters are dirty.",
        "label": 1,  # False Positive (generic plural subject)
        "rationale": "Generic plural subject 'Filters' does not require an article in general statements.",
    },
    {
        "rule": "MissingArticles",
        "word": "minimum",
        "sentence": "Their minimum is 100 psi.",
        "label": 1,  # False Positive (has possessive determiner 'Their')
        "rationale": "Possessive determiner 'Their' fulfills Rule 4.5.",
    },
    {
        "rule": "MissingArticles",
        "word": "Section",
        "sentence": "See Section 6 for instructions.",
        "label": 1,  # False Positive (numbered reference)
        "rationale": "Numbered references ('Section 6') take no article in technical writing.",
    },
    {
        "rule": "MissingArticles",
        "word": "JSON",
        "sentence": "The output is formatted in JSON.",
        "label": 1,  # False Positive (technology acronym / proper noun)
        "rationale": "Technology acronyms and proper nouns take no article.",
    },
    {
        "rule": "MissingArticles",
        "word": "pre",
        "sentence": "Configure pre-filters before running the tool.",
        "label": 1,  # False Positive (hyphen compound fragment)
        "rationale": "'pre' is a prefix fragment of 'pre-filters'.",
    },
    {
        "rule": "MissingArticles",
        "word": "word",
        "sentence": "Select a proper noun, stop word, or single-letter word.",
        "label": 1,  # False Positive (shared determiner in coordinate list)
        "rationale": "The initial determiner 'a' is shared across the coordinate list.",
    },
    {
        "rule": "MissingArticles",
        "word": "data",
        "sentence": "Data is collected from the sensors.",
        "label": 1,  # False Positive (uncountable mass noun)
        "rationale": "'Data' is an uncountable noun in technical English.",
    },
    {
        "rule": "MissingArticles",
        "word": "mood",
        "sentence": "This prevents contradictory flags (e.g., imperative mood being flagged as wrong).",
        "label": 0,  # True Positive (grammatical term needs 'the')
        "rationale": "'the imperative mood' is the standard ASD-STE100 form.",
    },
]


def generate_dataset(output_path: str = "data/fp_dataset.json") -> list[dict]:
    """Export the curated dataset to a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DATASET_EXAMPLES, f, indent=2)
    print(f"Generated dataset with {len(DATASET_EXAMPLES)} examples at {path}")
    return DATASET_EXAMPLES


if __name__ == "__main__":
    generate_dataset()
