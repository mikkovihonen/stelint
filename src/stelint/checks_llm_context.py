"""
LLM-powered context classification for ASD-STE100 documents.

Classifies each sentence as PROCEDURAL, DESCRIPTIVE, or SAFETY,
then suppresses context-inappropriate check issues.
"""

import re
import sys

from .llm_client import get_llm_client, llm_chat

# Check types that should be suppressed based on context.
# Key: sentence type, Value: set of issue types to suppress.
_CONTEXT_SUPPRESSIONS: dict[str, set[str]] = {
    "PROCEDURAL": {
        "ImperativeInDescription",
        "ParagraphStructure",
        "ParagraphLength",
        "ParagraphTopic",
    },
    "DESCRIPTIVE": {
        "NonImperativeInProcedures",
        "SentenceLength",
    },
    "SAFETY": {
        "ForbiddenModals",
    },
}


def classify_sentences(doc) -> dict[int, str]:
    """Classify each sentence as PROCEDURAL, DESCRIPTIVE, or SAFETY.

    Uses the LLM to determine the context type for each sentence.

    Args:
        doc: spaCy Doc object.

    Returns:
        Dict mapping sentence index to context type string.
    """
    sentences = [(i, sent.text.strip()) for i, sent in enumerate(doc.sents)]

    if not sentences:
        return {}

    # No LLM configured — return empty dict (no-op behavior).
    if get_llm_client() is None:
        return {}

    prompt = _build_classification_prompt(sentences)

    try:
        result = llm_chat(
            [{"role": "user", "content": prompt}],
            max_tokens=4000,
        )
    except Exception as e:
        print(f"stelint: LLM context classification failed: {e}", file=sys.stderr)
        return {}

    if not result:
        return {}

    return _parse_classification(result, len(sentences))


def apply_context_suppressions(
    issues: list[dict],
    sentence_types: dict[int, str],
    doc,
) -> list[dict]:
    """Suppress issues that don't apply to the sentence's context.

    Args:
        issues: List of issue dicts with 'type' and 'offset' keys.
        sentence_types: Dict mapping sentence index to context type.
        doc: spaCy Doc object for offset-to-sentence mapping.

    Returns:
        Filtered list of issues.
    """
    if not sentence_types:
        return issues

    filtered = []
    for issue in issues:
        sent_idx = _sentence_index_for_offset(issue["offset"], doc)
        sent_type = sentence_types.get(sent_idx)

        if sent_type and issue["type"] in _CONTEXT_SUPPRESSIONS.get(sent_type, set()):
            continue

        filtered.append(issue)

    suppressed_count = len(issues) - len(filtered)
    if suppressed_count > 0:
        print(f"stelint: Context filter suppressed {suppressed_count} issue(s).", file=sys.stderr)

    return filtered


def _build_classification_prompt(sentences: list[tuple[int, str]]) -> str:
    """Build the prompt for sentence classification.

    Args:
        sentences: List of (index, text) tuples.

    Returns:
        Prompt string for the LLM.
    """
    prompt_parts = [
        "Classify each sentence as PROCEDURAL, DESCRIPTIVE, or SAFETY.",
        "",
        "PROCEDURAL: imperative verb (Remove, Install, Check).",
        "DESCRIPTIVE: states a fact or property.",
        "SAFETY: contains Caution/Danger/Warning or safety constraint with must/shall.",
        "",
        "Output format: just 'NUMBER TYPE' per line, nothing else.",
        "",
        "Examples:",
        "1 PROCEDURAL",
        "2 DESCRIPTIVE",
        "3 SAFETY",
        "",
    ]

    for idx, text in sentences:
        prompt_parts.append(f"{idx + 1} '{text}'")

    prompt_parts.append("\nClassify:")

    return "\n".join(prompt_parts)


def _parse_classification(result: str, expected_count: int) -> dict[int, str]:
    """Parse the LLM classification result.

    Handles multiple output formats:
    - "1:PROCEDURAL 2:DESCRIPTIVE 3:SAFETY"
    - "1. 'text' → PROCEDURAL"
    - "1 PROCEDURAL"
    - "1: PROCEDURAL"

    Args:
        result: LLM response string.
        expected_count: Number of sentences expected.

    Returns:
        Dict mapping sentence index to context type.
    """
    classification = {}
    valid_types = {"PROCEDURAL", "DESCRIPTIVE", "SAFETY"}

    # Pattern 1: "N:TYPE" or "N: TYPE"
    pattern1 = re.compile(r"\b(\d+)\s*:\s*(\w+)\b")
    # Pattern 2: "N. ... → TYPE" (arrow notation)
    pattern2 = re.compile(r"\b(\d+)\b.*?→\s*(PROCEDURAL|DESCRIPTIVE|SAFETY)", re.IGNORECASE)
    # Pattern 3: "N TYPE" (space-separated, one per line)
    pattern3 = re.compile(
        r"^\s*(\d+)\s+(PROCEDURAL|DESCRIPTIVE|SAFETY)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    for pattern in (pattern1, pattern2, pattern3):
        for match in pattern.finditer(result):
            idx_str = match.group(1)
            sent_type = match.group(2).upper()
            idx = int(idx_str) - 1  # Convert to 0-indexed

            if 0 <= idx < expected_count and sent_type in valid_types:
                classification[idx] = sent_type

    return classification


def _sentence_index_for_offset(offset: int, doc) -> int:
    """Find the sentence index for a given character offset.

    Args:
        offset: Character offset in the document.
        doc: spaCy Doc object.

    Returns:
        Sentence index, or -1 if not found.
    """
    for i, sent in enumerate(doc.sents):
        if sent.start_char <= offset < sent.end_char:
            return i
    return -1
