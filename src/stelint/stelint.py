"""
ASD-STE100 checker using spaCy directly (no HTTP server needed).
Reads from file or stdin, outputs results in Vale, JSON, GitHub Actions, SARIF, or Summary formats.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import check functions from General Recommendations
from .checks_gr_recommendations import (
    check_ambiguous_pronouns,
    check_ambiguous_this,
    check_ambiguous_with,
    check_conjunction_that,
    check_false_friends,
    check_gender_pronouns,
    check_latin_abbreviations,
    check_possessive_form,
)

# Import check functions from Section 1 (Words)
from .checks_section1 import (
    check_approved_forms,
    check_approved_meaning,
    check_approved_words,
    check_british_english,
    check_consistent_technical_nouns,
    check_non_approved_as_technical,
    check_part_of_speech,
    check_regional_slang_jargon,
    check_technical_noun_approval,
    check_technical_noun_as_verb,
    check_technical_noun_category,
    check_technical_verb_as_noun,
    check_technical_verb_category,
    check_too_long_technical_nouns,
)

# Import check functions from Section 2 (Multi-word nouns)
from .checks_section2 import (
    check_multi_word_nouns,
    check_technical_noun_clarity,
)

# Import check functions from Section 3 (Verbs)
from .checks_section3 import (
    check_ing_forms,
    check_noun_as_verb,
    check_passive_voice,
    check_passive_voice_with_agent,
    check_past_participle_as_adjective,
    check_verb_forms,
    check_verb_tenses,
)

# Import check functions from Section 4 (Sentences)
from .checks_section4 import (
    check_article_usage,
    check_connecting_words,
    check_contractions,
    check_forbidden_modals,
    check_missing_articles,
    check_short_sentences,
    check_vertical_lists,
)

# Import check functions from Section 5 (Procedural writing)
from .checks_section5 import (
    check_descriptive_statement_first,
    check_multiple_instructions,
    check_non_imperative_in_procedures,
    check_notes,
    check_sentence_length_procedural,
)

# Import check functions from Section 6 (Descriptive writing)
from .checks_section6 import (
    check_information_structure,
    check_key_words,
    check_paragraph_length,
    check_paragraph_structure,
    check_paragraph_topic,
    check_sentence_length_descriptive,
)

# Import check functions from Section 7 (Safety instructions)
from .checks_section7 import (
    check_safety_instruction_explanation,
    check_safety_instruction_format,
)

# Import check functions from Section 8 (Punctuation and word count)
from .checks_section8 import (
    check_hyphenation_patterns,
    check_hyphens,
    check_parentheses_usage,
    check_semicolons,
    check_vertical_list_colons,
    check_word_count_all,
    check_word_count_with_numbers,
    check_word_count_with_parentheses,
)

# Import check functions from Section 9 (Writing practices)
from .checks_section9 import (
    check_consistent_style,
    check_consistent_terminology,
    check_different_sentence_constructions,
    check_non_approved_words,
    check_phrasal_verbs,
    check_word_for_word_replacement,
    check_word_usage,
)
from .context_classifier import (
    apply_context_suppressions,
    classify_sentence_contexts,
)
from .formatters import FormattedIssue, format_issues
from .preprocess_text import preprocess_markdown

_nlp_cache: Any = None


def _get_nlp():
    """Load spaCy model lazily and cache to avoid slow imports."""
    global _nlp_cache
    if _nlp_cache is not None:
        return _nlp_cache

    try:
        import spacy as spacy_module

        _nlp_cache = spacy_module.load("en_core_web_sm")
        return _nlp_cache
    except OSError as e:
        print(f"Error: Could not load spaCy model 'en_core_web_sm'. {e}", file=sys.stderr)
        print("Install it with: python -m spacy download en_core_web_sm", file=sys.stderr)
        return None


def _check_sense2vec_available() -> bool:
    """Check if sense2vec model is available."""
    try:
        from sense2vec import Sense2Vec

        Sense2Vec().from_disk("en")
        return True
    except (ImportError, OSError, FileNotFoundError, ValueError):
        return False


@dataclass
class LintConfig:
    """Configuration options for stelint."""

    include_all: bool = False
    glossaries: str | None = None
    format: str = "vale"
    disabled_rules: set[str] = field(default_factory=set)
    enabled_rules: set[str] = field(default_factory=set)
    quiet: bool = False


# Suppression mapping for region types
_SUPPRESSION_MAP: dict[str, list[str]] = {
    "bold_marker": ["MissingArticles"],
    "header": ["MissingArticles", "ConnectingWords"],
    "table_delimiter": [],
    "code_inline": [],
    "link_text": [],
    "link_url": [],
    "image": [],
    "html_block": [],
    "code_fence": [],
    "blockquote": [],
    "list_marker": [],
    "footnote_ref": [],
    "footnote_def": [],
    "task_checkbox": [],
    "email_autolink": [],
    "math_delimiter": [],
    "definition_marker": [],
    "horizontal_rule": [],
    "strikethrough": [],
    "italic_marker": [],
}


def _get_suppression_types(region_type: str) -> list[str]:
    """Get the list of issue types that should be suppressed for a region type."""
    return _SUPPRESSION_MAP.get(region_type, [])


def _build_metadata_tree(regions: list[tuple[int, int, str]]) -> list[dict]:
    """Build a tree structure from regions once for efficient suppression traversal."""
    nodes = []
    for start, end, rtype in regions:
        node = {
            "start": start,
            "end": end,
            "type": rtype,
            "children": [],
            "suppress": _get_suppression_types(rtype),
        }
        nodes.append(node)

    # Link parent-child relationships (parent contains child)
    for node in nodes:
        for other in nodes:
            if node is other:
                continue
            if node["start"] <= other["start"] and node["end"] >= other["end"] and (node["start"] != other["start"] or node["end"] != other["end"]):
                node["children"].append(other)

    # Return root nodes (not contained in any other)
    roots = []
    for node in nodes:
        is_child = False
        for other in nodes:
            if other is node:
                continue
            if other["start"] <= node["start"] and other["end"] >= node["end"] and (other["start"] != node["start"] or other["end"] != node["end"]):
                is_child = True
                break
        if not is_child:
            roots.append(node)

    return roots


def _find_node_in_tree(node: dict, cleaned_offset: int):
    """Recursively find the innermost node containing the position."""
    if node["start"] <= cleaned_offset < node["end"]:
        for child in node["children"]:
            child_match = _find_node_in_tree(child, cleaned_offset)
            if child_match:
                return child_match
        return node
    return None


def _find_node_at_position(tree_roots: list, cleaned_offset: int):
    """Find the innermost node containing the given position."""
    best_match = None
    best_size = float("inf")
    for root in tree_roots:
        node = _find_node_in_tree(root, cleaned_offset)
        if node:
            size = node["end"] - node["start"]
            if size < best_size:
                best_match = node
                best_size = size
    return best_match


def _is_suppressed_by_metadata(
    cleaned_offset: int,
    issue_type: str,
    cleaned_text: str,
    regions: list[tuple[int, int, str]],
    tree_roots: list[dict],
) -> bool:
    """Check if an issue is suppressed by metadata (bold labels, headers, etc.)."""
    if issue_type == "MissingArticles":
        # Emphasized example words take no article: pair opening/closing
        # marker regions and suppress the enclosed span (bold and italic).
        for marker_type in ("bold_marker", "italic_marker"):
            marker_regions = sorted([(s, e) for s, e, r in regions if r == marker_type])
            for i in range(0, len(marker_regions) - 1, 2):
                _s1, e1 = marker_regions[i]
                s2, _e2 = marker_regions[i + 1]
                if "\n" not in cleaned_text[e1:s2] and e1 <= cleaned_offset < s2:
                    return True

    node = _find_node_at_position(tree_roots, cleaned_offset)
    return bool(node and issue_type in node.get("suppress", []))


def _is_in_link(cleaned_offset: int, length: int, regions: list[tuple[int, int, str]]) -> bool:
    """Check if an error span overlaps with a link region."""
    error_end = cleaned_offset + length
    for start, end, rtype in regions:
        if rtype == "link" and not (error_end < start or cleaned_offset > end):
            return True
    return False


def _get_region_type(cleaned_offset: int, regions: list[tuple[int, int, str]]) -> str | None:
    """Look up the region type for a cleaned-text position."""
    for start, end, rtype in regions:
        if start <= cleaned_offset < end:
            return rtype
    return None


def lint_text(
    text: str,
    filepath: str = "stdin",
    config: LintConfig | None = None,
    nlp: Any = None,
) -> list[FormattedIssue]:
    """Lint a text string for ASD-STE100 compliance and return structured issues.

    Args:
        text: Input Markdown text to lint.
        filepath: Label or file path for issue reporting.
        config: LintConfig instance with settings.
        nlp: Optional pre-loaded spaCy language model.

    Returns:
        List of FormattedIssue objects.
    """
    if config is None:
        config = LintConfig()

    if not text.strip():
        return []

    cleaned_text, offset_map, regions = preprocess_markdown(text)

    if nlp is None:
        nlp = _get_nlp()
        if nlp is None:
            return []

    doc = nlp(cleaned_text)

    # Pre-build region tree once per document for fast suppression checks
    tree_roots = _build_metadata_tree(regions)

    # Collect issues from all rule sections
    all_issues = []

    # Section 1: Words
    all_issues.extend(check_approved_words(doc))
    all_issues.extend(check_part_of_speech(doc))
    all_issues.extend(check_approved_meaning(doc))
    all_issues.extend(check_approved_forms(doc))
    all_issues.extend(check_technical_noun_category(doc))
    all_issues.extend(check_non_approved_as_technical(doc))
    all_issues.extend(check_technical_noun_as_verb(doc))
    all_issues.extend(check_technical_noun_approval(doc))
    all_issues.extend(check_too_long_technical_nouns(doc))
    all_issues.extend(check_regional_slang_jargon(doc))
    all_issues.extend(check_consistent_technical_nouns(doc))
    all_issues.extend(check_technical_verb_category(doc))
    all_issues.extend(check_technical_verb_as_noun(doc))
    all_issues.extend(check_british_english(doc))

    # Section 2: Multi-word nouns
    all_issues.extend(check_multi_word_nouns(doc))
    all_issues.extend(check_technical_noun_clarity(doc))

    # Section 3: Verbs
    all_issues.extend(check_verb_forms(doc))
    all_issues.extend(check_verb_tenses(doc))
    all_issues.extend(check_past_participle_as_adjective(doc))
    all_issues.extend(check_passive_voice(doc))
    all_issues.extend(check_passive_voice_with_agent(doc))
    all_issues.extend(check_ing_forms(doc))
    all_issues.extend(check_noun_as_verb(doc))

    # Section 4: Sentences
    all_issues.extend(check_short_sentences(doc))
    all_issues.extend(check_contractions(doc))
    all_issues.extend(check_forbidden_modals(doc))
    all_issues.extend(check_vertical_lists(doc))
    all_issues.extend(check_connecting_words(doc))
    all_issues.extend(check_missing_articles(doc))
    all_issues.extend(check_article_usage(doc))

    # Section 5: Procedural writing
    all_issues.extend(check_sentence_length_procedural(doc))
    all_issues.extend(check_multiple_instructions(doc))
    all_issues.extend(check_non_imperative_in_procedures(doc))
    all_issues.extend(check_descriptive_statement_first(doc))
    all_issues.extend(check_notes(doc))

    # Section 6: Descriptive writing
    all_issues.extend(check_information_structure(doc))
    all_issues.extend(check_key_words(doc))
    all_issues.extend(check_sentence_length_descriptive(doc))
    all_issues.extend(check_paragraph_structure(doc))
    all_issues.extend(check_paragraph_topic(doc))
    all_issues.extend(check_paragraph_length(doc))

    # Section 7: Safety instructions
    all_issues.extend(check_safety_instruction_format(doc))
    all_issues.extend(check_safety_instruction_explanation(doc))

    # Section 8: Punctuation and word count
    all_issues.extend(check_semicolons(doc))
    all_issues.extend(check_hyphens(doc))
    all_issues.extend(check_parentheses_usage(doc))
    all_issues.extend(check_word_count_with_parentheses(doc))
    all_issues.extend(check_word_count_with_numbers(doc))
    all_issues.extend(check_hyphenation_patterns(doc))
    all_issues.extend(check_vertical_list_colons(doc))
    all_issues.extend(check_word_count_all(doc))

    # Section 9: Writing practices
    all_issues.extend(check_word_usage(doc))
    all_issues.extend(check_consistent_style(doc))
    all_issues.extend(check_phrasal_verbs(doc))
    all_issues.extend(check_consistent_terminology(doc))
    all_issues.extend(check_different_sentence_constructions(doc))
    all_issues.extend(check_word_for_word_replacement(doc))
    all_issues.extend(check_non_approved_words(doc))

    # General Recommendations (GR-1 to GR-8)
    all_issues.extend(check_conjunction_that(doc))
    all_issues.extend(check_ambiguous_with(doc))
    all_issues.extend(check_ambiguous_pronouns(doc))
    all_issues.extend(check_ambiguous_this(doc))
    all_issues.extend(check_false_friends(doc))
    all_issues.extend(check_latin_abbreviations(doc))
    all_issues.extend(check_gender_pronouns(doc))
    all_issues.extend(check_possessive_form(doc))

    # Deterministic heuristic context classification (resolves Section 5 vs Section 6 rule conflicts)
    sentence_contexts = classify_sentence_contexts(doc, raw_text=text, regions=regions)

    # Optional LLM-powered checks
    try:
        from .checks_llm import check_llm_polysemy

        llm_issues = check_llm_polysemy(doc)
        all_issues.extend(llm_issues)
    except Exception:
        pass

    # Optional LLM context classification & false positive filtering
    try:
        from .checks_llm_context import classify_sentences
        from .checks_llm_fp import filter_false_positives

        llm_contexts = classify_sentences(doc)
        if llm_contexts:
            sentence_contexts.update(llm_contexts)

        all_issues = filter_false_positives(all_issues, doc, sentence_types=sentence_contexts)
    except Exception:
        pass

    # Apply context-based suppression using the sentence contexts
    all_issues = apply_context_suppressions(all_issues, sentence_contexts, doc)

    # Sort by offset
    all_issues.sort(key=lambda x: x["offset"])

    # Deduplicate exact duplicate warnings and resolve rule precedence on same span
    seen_issues = set()
    unique_issues = []
    # Identify spans covered by specific technical POS rules
    specific_pos_spans = {(issue["offset"], issue.get("length", 1)) for issue in all_issues if issue["type"] in ("TechnicalNounAsVerb", "TechnicalVerbAsNoun")}

    for issue in all_issues:
        # If a specific technical POS rule already fired at this exact span, suppress generic PartOfSpeech
        if issue["type"] == "PartOfSpeech" and (issue["offset"], issue.get("length", 1)) in specific_pos_spans:
            continue

        dedup_key = (issue["type"], issue["message"], issue["offset"])
        if dedup_key not in seen_issues:
            seen_issues.add(dedup_key)
            unique_issues.append(issue)
    all_issues = unique_issues

    original_lines = text.split("\n")
    formatted_results: list[FormattedIssue] = []

    for issue in all_issues:
        issue_type = issue["type"]

        # Filter enabled/disabled rules
        if config.disabled_rules:
            if issue_type in config.disabled_rules or f"STE100.{issue_type}" in config.disabled_rules:
                continue

        if config.enabled_rules:
            if issue_type not in config.enabled_rules and f"STE100.{issue_type}" not in config.enabled_rules:
                continue

        cleaned_offset = issue["offset"]
        error_length = issue.get("length", 1)

        # Skip errors in link regions
        if _is_in_link(cleaned_offset, error_length, regions):
            continue

        original_offset = offset_map.get(cleaned_offset, cleaned_offset)
        region_type = _get_region_type(cleaned_offset, regions)

        # Skip errors suppressed by metadata
        if _is_suppressed_by_metadata(cleaned_offset, issue_type, cleaned_text, regions, tree_roots):
            continue

        # Skip errors with metadata annotations unless include_all is set
        if not config.include_all and region_type:
            continue

        # Calculate line and column from original character offset
        line = 1
        col = 1
        current_offset = 0
        for i, line_text in enumerate(original_lines):
            line_end = current_offset + len(line_text) + 1
            if current_offset <= original_offset < line_end:
                line = i + 1
                col = original_offset - current_offset + 1
                break
            current_offset = line_end

        message = " ".join(issue["message"].split())

        formatted_results.append(
            FormattedIssue(
                file=filepath,
                line=line,
                column=col,
                rule=f"STE100.{issue_type}",
                rule_type=issue_type,
                message=message,
                region_type=region_type,
                offset=original_offset,
                length=error_length,
            )
        )

    return formatted_results


def lint_file(
    filepath: Path | str,
    config: LintConfig | None = None,
    nlp: Any = None,
) -> list[FormattedIssue]:
    """Lint a file or stdin."""
    str_path = str(filepath)
    if str_path in ("-", "stdin"):
        text = sys.stdin.read()
        return lint_text(text, filepath="stdin", config=config, nlp=nlp)

    p = Path(filepath)
    if not p.exists():
        print(f"Error: File '{str_path}' not found.", file=sys.stderr)
        return []

    try:
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        return lint_text(text, filepath=str_path, config=config, nlp=nlp)
    except Exception as e:
        print(f"Error reading '{str_path}': {e}", file=sys.stderr)
        return []


def lint_paths(
    paths: list[str | Path],
    config: LintConfig | None = None,
) -> list[FormattedIssue]:
    """Lint multiple files or directories recursively."""
    if config is None:
        config = LintConfig()

    nlp = _get_nlp()
    if nlp is None:
        sys.exit(1)

    all_issues: list[FormattedIssue] = []

    for path_item in paths:
        str_path = str(path_item)
        if str_path in ("-", "stdin"):
            all_issues.extend(lint_file("-", config=config, nlp=nlp))
            continue

        p = Path(path_item)
        if p.is_dir():
            # Recursively find all markdown files in the directory
            md_files = sorted(list(p.glob("**/*.md")))
            for md_file in md_files:
                all_issues.extend(lint_file(md_file, config=config, nlp=nlp))
        else:
            all_issues.extend(lint_file(p, config=config, nlp=nlp))

    return all_issues


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="stelint",
        description="ASD-STE100 Simplified Technical English linter.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        default=[],
        help="Markdown file(s) or directories to lint. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Show all warnings, including those inside metadata regions (headers, tables, bold labels)",
    )
    parser.add_argument(
        "--glossaries",
        type=str,
        default=None,
        help="Path to glossaries.yaml config file",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["vale", "json", "github", "sarif", "summary"],
        default="vale",
        help="Output format (default: vale)",
    )
    parser.add_argument(
        "--disable",
        type=str,
        default=None,
        help="Comma-separated list of rule names to disable (e.g. 'ShortSentences,Hyphens')",
    )
    parser.add_argument(
        "--enable",
        type=str,
        default=None,
        help="Comma-separated list of rule names to enable (all other rules will be disabled)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress informational messages",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    args = parse_args(argv)

    # Determine files/paths to process
    paths = args.files
    if not paths:
        if not sys.stdin.isatty():
            paths = ["-"]
        else:
            parse_args(["--help"])
            sys.exit(0)

    # Load custom glossaries if requested
    if args.glossaries:
        import stelint.glossary as glossary_mod

        cfg = Path(args.glossaries)
        glossary_mod.set_config_path(cfg)
        glossary_mod.reload_constants()

    # Parse disabled/enabled rules
    disabled_set = set()
    if args.disable:
        disabled_set = {r.strip() for r in args.disable.split(",") if r.strip()}

    enabled_set = set()
    if args.enable:
        enabled_set = {r.strip() for r in args.enable.split(",") if r.strip()}

    config = LintConfig(
        include_all=args.include_all,
        glossaries=args.glossaries,
        format=args.format,
        disabled_rules=disabled_set,
        enabled_rules=enabled_set,
        quiet=args.quiet,
    )

    issues = lint_paths(paths, config=config)

    output = format_issues(issues, format_name=config.format)
    if output:
        print(output)

    if issues:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
