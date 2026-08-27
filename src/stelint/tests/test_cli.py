"""Tests for stelint CLI, argument parsing, formatters, and linting engine."""

import json

from stelint.formatters import (
    FormattedIssue,
    format_github,
    format_issues,
    format_json,
    format_sarif,
    format_summary,
    format_vale,
)
from stelint.stelint import LintConfig, lint_text, parse_args


class TestFormatters:
    """Tests for formatters module."""

    def test_format_vale(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=1,
                column=5,
                rule="STE100.ShortSentences",
                rule_type="ShortSentences",
                message="Sentence is too long.",
            )
        ]
        output = format_vale(issues)
        assert "test.md:1:5 STE100.ShortSentences: Sentence is too long." in output

    def test_format_vale_with_region(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=2,
                column=1,
                rule="STE100.MissingArticles",
                rule_type="MissingArticles",
                message="Missing article.",
                region_type="table_row",
            )
        ]
        output = format_vale(issues)
        assert "test.md:2:1 STE100.MissingArticles: [table_row] Missing article." in output

    def test_format_json(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=1,
                column=1,
                rule="STE100.PassiveVoice",
                rule_type="PassiveVoice",
                message="Passive voice detected.",
            )
        ]
        output = format_json(issues)
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["rule_type"] == "PassiveVoice"
        assert data[0]["file"] == "test.md"

    def test_format_github(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=5,
                column=10,
                rule="STE100.Hyphens",
                rule_type="Hyphens",
                message="Too many hyphens.",
            )
        ]
        output = format_github(issues)
        assert "::warning file=test.md,line=5,col=10,title=STE100.Hyphens::Too many hyphens." in output

    def test_format_sarif(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=3,
                column=4,
                rule="STE100.Semicolons",
                rule_type="Semicolons",
                message="Do not use a semicolon.",
            )
        ]
        output = format_sarif(issues)
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert len(data["runs"][0]["results"]) == 1
        assert data["runs"][0]["results"][0]["ruleId"] == "STE100.Semicolons"

    def test_format_summary(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=1,
                column=1,
                rule="STE100.Semicolons",
                rule_type="Semicolons",
                message="Do not use a semicolon.",
            ),
            FormattedIssue(
                file="test.md",
                line=2,
                column=1,
                rule="STE100.Semicolons",
                rule_type="Semicolons",
                message="Do not use a semicolon.",
            ),
        ]
        output = format_summary(issues)
        assert "ASD-STE100 Lint Summary: 2 issue(s)" in output
        assert "STE100.Semicolons: 2" in output

    def test_format_issues_dispatcher(self):
        issues = [
            FormattedIssue(
                file="test.md",
                line=1,
                column=1,
                rule="STE100.Semicolons",
                rule_type="Semicolons",
                message="Do not use a semicolon.",
            )
        ]
        assert "{" in format_issues(issues, format_name="json")
        assert "::warning" in format_issues(issues, format_name="github")
        assert "STE100.Semicolons:" in format_issues(issues, format_name="vale")


class TestCLIOptions:
    """Tests for parse_args and lint_text with options."""

    def test_parse_args_defaults(self):
        args = parse_args(["file.md"])
        assert args.files == ["file.md"]
        assert args.format == "vale"
        assert not args.include_all
        assert args.disable is None

    def test_parse_args_custom(self):
        args = parse_args(["--format", "json", "--include-all", "--disable", "ShortSentences,Hyphens", "test.md"])
        assert args.format == "json"
        assert args.include_all is True
        assert args.disable == "ShortSentences,Hyphens"
        assert args.files == ["test.md"]

    def test_lint_text_disabled_rule(self, nlp_model):
        md = "This sentence contains a semicolon; it should be separated."
        # Without disable, should find Semicolons issue
        issues = lint_text(md, filepath="test.md", nlp=nlp_model)
        has_semi = any(i.rule_type == "Semicolons" for i in issues)
        assert has_semi

        # With disable, Semicolons should be filtered out
        config = LintConfig(disabled_rules={"Semicolons"})
        issues_disabled = lint_text(md, filepath="test.md", config=config, nlp=nlp_model)
        assert not any(i.rule_type == "Semicolons" for i in issues_disabled)

    def test_lint_text_enabled_rules_only(self, nlp_model):
        md = "This sentence contains a semicolon; it should be separated."
        # Enable only a different rule
        config = LintConfig(enabled_rules={"Contractions"})
        issues = lint_text(md, filepath="test.md", config=config, nlp=nlp_model)
        # Semicolons should not be included
        assert not any(i.rule_type == "Semicolons" for i in issues)


class TestGlossaryReload:
    """Tests for in-place glossary mutation."""

    def test_in_place_reload(self):
        import stelint.glossary as glossary_mod
        from stelint.glossary import NON_APPROVED_WORDS

        # NON_APPROVED_WORDS is imported directly
        original_len = len(NON_APPROVED_WORDS)
        assert original_len > 0

        # Reload constants without config
        glossary_mod.reload_constants()

        # The directly-imported NON_APPROVED_WORDS reference must still be populated
        assert len(NON_APPROVED_WORDS) == original_len
