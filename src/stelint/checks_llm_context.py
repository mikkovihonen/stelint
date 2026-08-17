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
            max_tokens=500,
        )
    except Exception as e:
        print(f"stelint: LLM context classification failed: {e}", file=sys.stderr)
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
    example_sentences = (
        "1. 'Remove the cap.' → PROCEDURAL\n"
        "2. 'The cap is made of rubber.' → DESCRIPTIVE\n"
        "3. 'Caution: Hot surface.' → SAFETY\n"
        "4. 'Install the bolt and tighten to 5 Nm.' → PROCEDURAL\n"
        "5. 'The system must operate between -20°C and 80°C.' → SAFETY\n"
        "6. 'Water flows through the heat exchanger.' → DESCRIPTIVE\n"
    )

    prompt_parts = [
        "You are an ASD-STE100 technical writing expert.",
        "",
        "Classify each sentence as one of: PROCEDURAL, DESCRIPTIVE, or SAFETY.",
        "",
        "Definitions:",
        "- PROCEDURAL: gives an instruction or work step. Usually starts with an",
        "  imperative verb (Remove, Install, Check, Verify). Describes actions.",
        "- DESCRIPTIVE: states a fact, property, condition, or relationship.",
        "  Describes what something IS or HOW something WORKS.",
        "- SAFETY: contains safety signal words (Caution, Danger, Warning, Note)",
        "  or describes safety-critical constraints.",
        "",
        "Rules:",
        "- A sentence starting with 'Caution:', 'Danger:', or 'Warning:' is SAFETY.",
        "- A sentence with 'must' or 'shall' about a safety constraint is SAFETY.",
        "- An imperative sentence is PROCEDURAL unless it's a safety instruction.",
        "- A declarative sentence describing properties is DESCRIPTIVE.",
        "",
        "Examples:",
        example_sentences,
        "Return your answers as: '1:TYPE 2:TYPE 3:TYPE ...'",
        "",
        "Now classify these sentences from the document:",
    ]

    for idx, text in sentences:
        prompt_parts.append(f"{idx + 1}. '{text}'")

    return "\n".join(prompt_parts)


def _parse_classification(result: str, expected_count: int) -> dict[int, str]:
    """Parse the LLM classification result.

    Args:
        result: LLM response string.
        expected_count: Number of sentences expected.

    Returns:
        Dict mapping sentence index to context type.
    """
    classification = {}

    # Match patterns like "1:PROCEDURAL", "2:DESCRIPTIVE", etc.
    pattern = re.compile(r"\b(\d+):(\w+)\b")
    matches = pattern.findall(result)

    for match in matches:
        idx_str, sent_type = match
        idx = int(idx_str) - 1  # Convert to 0-indexed

        if 0 <= idx < expected_count:
            sent_type_upper = sent_type.upper()
            if sent_type_upper in _CONTEXT_SUPPRESSIONS:
                classification[idx] = sent_type_upper
            elif sent_type_upper == "SAFETY":
                classification[idx] = "SAFETY"
            elif sent_type_upper == "PROCEDURAL":
                classification[idx] = "PROCEDURAL"
            elif sent_type_upper == "DESCRIPTIVE":
                classification[idx] = "DESCRIPTIVE"

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
