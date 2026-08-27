"""
Deterministic heuristic context classification for ASD-STE100 documents.

Classifies each sentence as PROCEDURAL, DESCRIPTIVE, or SAFETY based on
Markdown structural indicators (lists, numbered steps, headings) and
syntactic patterns, without requiring an external LLM endpoint.
"""

from __future__ import annotations

import re

# Context-based suppressions mapping
CONTEXT_SUPPRESSIONS: dict[str, set[str]] = {
    "PROCEDURAL": {
        "ImperativeInDescription",
        "ParagraphStructure",
        "ParagraphLength",
        "ParagraphTopic",
        "SentenceLengthDescriptive",
    },
    "DESCRIPTIVE": {
        "NonImperativeInProcedures",
        "SentenceLengthProcedural",
    },
    "SAFETY": {
        "ForbiddenModals",
    },
}

_SAFETY_HEADINGS = {"WARNING", "CAUTION", "DANGER", "NOTE", "SAFETY"}
_PROCEDURAL_HEADINGS = {
    "PROCEDURE",
    "PROCEDURES",
    "STEP",
    "STEPS",
    "INSTRUCTIONS",
    "INSTALLATION",
    "REMOVAL",
    "MAINTENANCE",
    "OPERATION",
    "CHECK",
    "TEST",
    "INSPECTION",
    "REPAIR",
    "REPLACEMENT",
    "DISASSEMBLY",
    "ASSEMBLY",
}
_DESCRIPTIVE_HEADINGS = {
    "DESCRIPTION",
    "DESCRIPTIONS",
    "OVERVIEW",
    "GENERAL",
    "INTRODUCTION",
    "THEORY",
    "SPECIFICATION",
    "SPECIFICATIONS",
    "PURPOSE",
}


def classify_sentence_contexts(
    doc,
    raw_text: str = "",
    regions: list[tuple[int, int, str]] | None = None,
) -> dict[int, str]:
    """Classify each sentence in a spaCy Doc as PROCEDURAL, DESCRIPTIVE, or SAFETY.

    Uses Markdown structure (list markers, task checkboxes, heading sections)
    and sentence syntax (imperative mood, safety labels) to deterministically
    identify the context of each sentence.

    Args:
        doc: spaCy Doc object.
        raw_text: The original Markdown source text.
        regions: List of (start, end, region_type) tuples from preprocessing.

    Returns:
        Dict mapping sentence index (0-based) to 'PROCEDURAL', 'DESCRIPTIVE', or 'SAFETY'.
    """
    sentence_contexts: dict[int, str] = {}
    if not doc or not doc.sents:
        return sentence_contexts

    # Collect list marker spans and task checkbox spans if regions provided
    list_marker_offsets: set[int] = set()
    if regions:
        for start, end, rtype in regions:
            if rtype in ("list_marker", "task_checkbox"):
                for offset in range(start, end + 1):
                    list_marker_offsets.add(offset)

    # Track current active heading section context
    current_section_context = "DESCRIPTIVE"

    # Pre-calculate line-based heading contexts if raw_text is available
    heading_sections: list[tuple[int, str]] = []
    if raw_text:
        lines = raw_text.split("\n")
        current_offset = 0
        for line in lines:
            line_len = len(line) + 1  # include newline
            line_stripped = line.strip()
            if line_stripped.startswith("#"):
                clean_heading = re.sub(r"^#+\s*", "", line_stripped).strip().upper()
                words = set(re.findall(r"\b[A-Z]+\b", clean_heading))
                if words & _SAFETY_HEADINGS:
                    h_context = "SAFETY"
                elif words & _PROCEDURAL_HEADINGS:
                    h_context = "PROCEDURAL"
                elif words & _DESCRIPTIVE_HEADINGS:
                    h_context = "DESCRIPTIVE"
                else:
                    h_context = current_section_context
                heading_sections.append((current_offset, h_context))
            current_offset += line_len

    for i, sent in enumerate(doc.sents):
        sent_start = sent.start_char
        sent_text = sent.text.strip()
        if not sent_text:
            sentence_contexts[i] = "DESCRIPTIVE"
            continue

        # Check section heading context
        if heading_sections:
            for h_offset, h_type in heading_sections:
                if h_offset <= sent_start:
                    current_section_context = h_type
                else:
                    break

        # 1. Check for SAFETY context first
        first_token = next((t for t in sent if t.pos_ != "PUNCT"), None)
        if first_token and first_token.text.upper() in ("WARNING", "CAUTION", "DANGER", "NOTE"):
            sentence_contexts[i] = "SAFETY"
            continue

        # 2. Check for PROCEDURAL context via structure or syntax
        is_list_item = False
        if sent_start in list_marker_offsets or (sent_start > 0 and (sent_start - 1) in list_marker_offsets) or (sent_start - 2) in list_marker_offsets:
            is_list_item = True

        # Check raw text pattern for numbered/bullet items if not captured in regions
        if not is_list_item and raw_text:
            prefix_chunk = raw_text[max(0, sent_start - 10) : sent_start + 5]
            if re.search(r"(?:^|\n)\s*(?:[-*+]|\d+\.|\(\d+\))\s*", prefix_chunk):
                is_list_item = True

        # Check for imperative verb at start of sentence (ROOT verb in VB tag without subject)
        has_imperative = False
        if first_token and first_token.pos_ == "VERB" and first_token.tag_ == "VB":
            has_subject = any(c.dep_ == "nsubj" for c in first_token.children)
            if not has_subject and first_token.dep_ in ("ROOT", "advcl"):
                has_imperative = True

        if is_list_item or (has_imperative and current_section_context == "PROCEDURAL") or (is_list_item and has_imperative):
            sentence_contexts[i] = "PROCEDURAL"
            continue

        # 3. Fallback to current section context or DESCRIPTIVE
        if current_section_context in ("PROCEDURAL", "SAFETY"):
            sentence_contexts[i] = current_section_context
        else:
            sentence_contexts[i] = "DESCRIPTIVE"

    return sentence_contexts


def apply_context_suppressions(
    issues: list[dict],
    sentence_types: dict[int, str],
    doc,
) -> list[dict]:
    """Suppress issues that conflict with the sentence's classified context.

    Args:
        issues: List of issue dicts with 'type' and 'offset' keys.
        sentence_types: Dict mapping sentence index to context type string.
        doc: spaCy Doc object.

    Returns:
        Filtered list of issue dicts.
    """
    if not sentence_types or not doc:
        return issues

    filtered: list[dict] = []
    for issue in issues:
        sent_idx = _sentence_index_for_offset(issue["offset"], doc)
        sent_type = sentence_types.get(sent_idx)

        if sent_type and issue["type"] in CONTEXT_SUPPRESSIONS.get(sent_type, set()):
            continue

        filtered.append(issue)

    return filtered


def _sentence_index_for_offset(offset: int, doc) -> int:
    """Find the sentence index for a given character offset."""
    for i, sent in enumerate(doc.sents):
        if sent.start_char <= offset < sent.end_char:
            return i
    return -1
