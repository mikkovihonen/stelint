"""LLM-powered false positive filter for stelint.

After spaCy checks produce issues, this module sends all filterable issues
to the LLM in a single batched prompt for validation. Issues the LLM identifies
as false positives are suppressed.

This targets the checks known to produce the most false positives:
- VerbForms: flags -ing forms in compound technical nouns (e.g. "running gear")
- ConnectingWords: flags almost every sentence transition regardless of topic
- PartOfSpeech: flags correct verb usage as noun mismatch
- TechnicalVerbAsNoun: flags noun modifiers as verb-as-noun

All functions are no-ops when the LLM is not configured.
"""

import re
import sys
from itertools import islice

from .llm_client import get_llm_client, llm_chat

# Check types that benefit from LLM false positive filtering.
_FILTERABLE_CHECKS = {"VerbForms", "ConnectingWords", "PartOfSpeech", "TechnicalVerbAsNoun"}

# Minimum filterable issues before invoking LLM (avoids call overhead for trivial cases).
_MIN_ISSUES_FOR_LLM = 2

# Maximum total issues across all types in a single prompt.
_MAX_TOTAL_ISSUES = 20


def filter_false_positives(issues: list[dict], doc) -> list[dict]:
    """Filter spaCy check results using LLM validation.

    Combines all filterable issues into a single LLM prompt to minimize
    round-trip latency. Issues the LLM marks as FALSE_POSITIVE are removed.

    Args:
        issues: List of issue dicts from spaCy checks.
        doc: A spaCy Doc object for context lookups.

    Returns:
        Filtered list of issues with false positives removed.
    """
    if get_llm_client() is None:
        return issues

    # Separate filterable and non-filterable issues.
    filterable: list[dict] = []
    non_filterable: list[dict] = []

    for issue in issues:
        if issue["type"] in _FILTERABLE_CHECKS:
            filterable.append(issue)
        else:
            non_filterable.append(issue)

    if len(filterable) < _MIN_ISSUES_FOR_LLM:
        return issues

    # Apply cheap rule-based pre-filters before the LLM call.
    # Returns (pre_confirmed, needs_llm) where:
    #   pre_confirmed = issues confirmed by heuristics (kept without LLM)
    #   needs_llm     = issues that still need LLM validation
    pre_confirmed, needs_llm = _apply_rule_based_prefilters(filterable, doc)

    confirmed_offsets: set[int] = {i["offset"] for i in pre_confirmed}

    if len(needs_llm) >= _MIN_ISSUES_FOR_LLM:
        # Truncate to max to keep the prompt manageable.
        truncated = needs_llm[:_MAX_TOTAL_ISSUES]
        llm_confirmed = _validate_all(truncated, doc)
        confirmed_offsets.update(llm_confirmed)
        # If we truncated, keep all beyond the truncation point (conservative).
        if len(needs_llm) > _MAX_TOTAL_ISSUES:
            for issue in needs_llm[_MAX_TOTAL_ISSUES:]:
                confirmed_offsets.add(issue["offset"])

    # Reconstruct result: non-filterable + filterable issues whose offsets
    # were confirmed by the LLM or pre-filters.
    confirmed: list[dict] = list(non_filterable)
    for issue in filterable:
        if issue["offset"] in confirmed_offsets:
            confirmed.append(issue)

    if len(confirmed) < len(issues):
        suppressed = len(issues) - len(confirmed)
        print(
            f"stelint: LLM filter suppressed {suppressed} false positive(s).",
            file=sys.stderr,
        )

    return confirmed


def _apply_rule_based_prefilters(
    issues: list[dict],
    doc,
) -> tuple[list[dict], list[dict]]:
    """Apply cheap heuristic pre-filters to reduce LLM calls.

    Returns:
        (pre_confirmed, needs_llm) where:
        - pre_confirmed: issues confirmed by heuristics (kept without LLM)
        - needs_llm: issues that still need LLM validation

    Issues suppressed by pre-filters are dropped (assumed FALSE_POSITIVE).
    """
    pre_confirmed: list[dict] = []
    needs_llm: list[dict] = []

    for issue in issues:
        ctype = issue["type"]

        if ctype == "ConnectingWords":
            # Unrelated topics → suppress.
            if _connecting_words_unrelated(doc, issue):
                continue

        elif ctype == "VerbForms":
            token = _find_token(doc, issue["offset"])
            if token is not None:
                if _verb_forms_is_modifier(token):
                    continue  # suppressed: valid compound modifier
                if _verb_forms_is_genuine(token):
                    pre_confirmed.append(issue)  # confirmed: progressive verb
                    continue

        elif ctype == "PartOfSpeech":
            token = _find_token(doc, issue["offset"])
            if token is not None and _part_of_speech_is_correct(token):
                pre_confirmed.append(issue)  # confirmed: correct verb usage
                continue

        elif ctype == "TechnicalVerbAsNoun":
            token = _find_token(doc, issue["offset"])
            if token is not None and _tech_verb_is_modifier(token):
                continue  # suppressed: valid noun modifier

        needs_llm.append(issue)

    return pre_confirmed, needs_llm


def _find_token(doc, offset: int):
    """Find the token at the given character offset, or None."""
    for token in doc:
        if token.idx <= offset < token.idx + len(token.text):
            return token
    return None


def _verb_forms_is_modifier(token) -> bool:
    """Check if -ing token is a noun modifier (compound term)."""
    if token.text.lower().endswith("ing") and token.pos_ == "VERB":
        # If the token modifies a noun (amod, compound dep) and the head is a noun.
        if token.head.pos_ == "NOUN" and token.dep_ in ("amod", "compound"):
            return True
    return False


def _verb_forms_is_genuine(token) -> bool:
    """Check if -ing token is a genuine progressive verb (after be-verb)."""
    if token.text.lower().endswith("ing") and token.pos_ == "VERB":
        # If preceded by a be-verb auxiliary.
        if token.i > 0:
            prev = token.doc[token.i - 1]
            if prev.text.lower() in ("is", "are", "am", "was", "were", "be", "been", "being"):
                return True
    return False


def _part_of_speech_is_correct(token) -> bool:
    """Check if dependencies confirm the word is used as a verb."""
    verb_deps = {"dobj", "nsubj", "attr", "ROOT", "xcomp", "ccomp"}
    for child in token.children:
        if child.dep_ in verb_deps:
            return True
    return False


def _tech_verb_is_modifier(token) -> bool:
    """Check if a word modifies a following noun (compound term)."""
    if token.i + 1 < len(token.doc):
        next_token = token.doc[token.i + 1]
        if next_token.pos_ == "NOUN":
            return True
    return False


def _connecting_words_unrelated(doc, issue: dict) -> bool:
    """Heuristic: are the two sentences around this offset unrelated?

    Returns True if the sentences share no content words (lemmas), which
    strongly suggests they discuss different topics and do not need a
    connecting word.
    """
    sentences = list(doc.sents)
    sent_idx = None
    for i, sent in enumerate(sentences):
        if abs(sent.end_char - issue["offset"]) < 5:
            sent_idx = i
            break

    if sent_idx is None or sent_idx + 1 >= len(sentences):
        return False

    words1 = {t.lemma_.lower() for t in sentences[sent_idx] if not t.is_stop and t.pos_ not in ("PUNCT", "X") and len(t.lemma_) > 1}
    words2 = {t.lemma_.lower() for t in sentences[sent_idx + 1] if not t.is_stop and t.pos_ not in ("PUNCT", "X") and len(t.lemma_) > 1}

    # If no content words overlap at all, they are likely unrelated.
    return len(words1.intersection(words2)) == 0


def _get_sentence_at_offset(doc, offset: int):
    """Get the sentence containing the given character offset."""
    for token in doc:
        if token.idx <= offset < token.idx + len(token.text):
            return token.sent
    for token in doc:
        if abs(token.idx - offset) < 5:
            return token.sent
    return None


def _build_unified_prompt(issues: list[dict], doc) -> str:
    """Build a compact single prompt covering all filterable issues."""
    parts: list[str] = []

    for idx, issue in enumerate(issues, 1):
        check_type = issue["type"]
        sent = _get_sentence_at_offset(doc, issue["offset"])
        sent_text = (sent.text.strip().rstrip(".")[:60]) if sent else "?"

        # Minimal token context: word + key dependency.
        token_text = ""
        dep_short = ""
        for token in doc:
            if token.idx == issue["offset"]:
                token_text = token.text
                head = token.head.text if token.head else "?"
                dep_short = f" [{token.dep_}->{head}]"
                break

        if check_type == "VerbForms":
            parts.append(f"{idx}. VerbForms: '{token_text}' in '{sent_text}'{dep_short}")
        elif check_type == "ConnectingWords":
            # Include the next sentence too for context.
            sentences = list(doc.sents)
            next_sent = ""
            sent_idx = None
            for i, s in enumerate(sentences):
                if abs(s.end_char - issue["offset"]) < 5:
                    sent_idx = i
                    break
            if sent_idx is not None and sent_idx + 1 < len(sentences):
                next_sent = sentences[sent_idx + 1].text.strip().rstrip(".")[:60]
            parts.append(f"{idx}. ConnectingWords: '{sent_text}' → '{next_sent}'")
        elif check_type == "PartOfSpeech":
            children_deps = []
            for c in islice(token.children, 3):
                children_deps.append(f"{c.dep_}:{c.text}")
            dep_short = f" [{','.join(children_deps)}]" if children_deps else ""
            parts.append(f"{idx}. PartOfSpeech: '{token_text}' in '{sent_text}'{dep_short}")
        elif check_type == "TechnicalVerbAsNoun":
            parts.append(f"{idx}. TechnicalVerbAsNoun: '{token_text}' in '{sent_text}'{dep_short}")

    return (
        "Answer CONFIRM or FALSE_POSITIVE for each issue.\n\n"
        "Rules:\n"
        "- VerbForms: -ing as compound noun modifier = FALSE_POSITIVE. "
        "-ing after be-verb = CONFIRM.\n"
        "- ConnectingWords: unrelated topics = FALSE_POSITIVE.\n"
        "- PartOfSpeech: has dobj/nsubj/ROOT = FALSE_POSITIVE (correct verb).\n"
        "- TechnicalVerbAsNoun: word before noun = FALSE_POSITIVE (valid modifier).\n\n" + "\n".join(parts)
    )


def _validate_all(issues: list[dict], doc) -> set[int]:
    """Send all issues in one prompt and return offsets to keep."""
    prompt = _build_unified_prompt(issues, doc)
    result = llm_chat([{"role": "user", "content": prompt}], max_tokens=2000)

    if not result:
        # LLM call failed, keep all.
        return {i["offset"] for i in issues}

    kept: set[int] = set()
    # Parse lines like "1. VerbForms: ..." or "1: CONFIRM" or "1: FALSE_POSITIVE"
    for line in result.split("\n"):
        line = line.strip()
        # Match "N: CONFIRM" or "N: FALSE_POSITIVE" at start of line.
        match = re.match(r"^(\d+)\s*[:\-]\s*(CONFIRM|FALSE_POSITIVE)", line, re.IGNORECASE)
        if match:
            issue_num = int(match.group(1))
            verdict = match.group(2).upper()
            if 1 <= issue_num <= len(issues):
                issue = issues[issue_num - 1]
                if verdict == "CONFIRM":
                    kept.add(issue["offset"])

    if not kept and not result.strip():
        return {i["offset"] for i in issues}

    return kept
