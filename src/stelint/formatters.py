"""
Output formatters for stelint issues.

Supports:
- vale: Standard Vale-compatible output (file:line:col STE100.Rule: message)
- json: Structured JSON array of issues
- github: GitHub Actions workflow commands (::warning file=...,line=...::...)
- sarif: Static Analysis Results Interchange Format (SARIF v2.1.0)
- summary: Human-readable statistics summary
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class FormattedIssue:
    file: str
    line: int
    column: int
    rule: str
    rule_type: str
    message: str
    region_type: str | None = None
    severity: str = "warning"
    offset: int = 0
    length: int = 1


def format_issues(
    issues: list[FormattedIssue],
    format_name: str = "vale",
) -> str:
    """Format a list of FormattedIssue objects according to the chosen format."""
    format_name = format_name.lower().strip()

    if format_name == "json":
        return format_json(issues)
    elif format_name in ("github", "github-actions"):
        return format_github(issues)
    elif format_name == "sarif":
        return format_sarif(issues)
    elif format_name == "summary":
        return format_summary(issues)
    else:  # default: vale
        return format_vale(issues)


def format_vale(issues: list[FormattedIssue]) -> str:
    """Format issues in Vale-compatible format (file:line:col STE100.Rule: message)."""
    if not issues:
        return "No ASD-STE100 issues found."

    lines = []
    for issue in issues:
        clean_message = " ".join(issue.message.split())
        if issue.region_type:
            lines.append(f"{issue.file}:{issue.line}:{issue.column} STE100.{issue.rule_type}: [{issue.region_type}] {clean_message}")
        else:
            lines.append(f"{issue.file}:{issue.line}:{issue.column} STE100.{issue.rule_type}: {clean_message}")
    return "\n".join(lines)


def format_json(issues: list[FormattedIssue]) -> str:
    """Format issues as a JSON string."""
    data = [asdict(issue) for issue in issues]
    return json.dumps(data, indent=2)


def format_github(issues: list[FormattedIssue]) -> str:
    """Format issues as GitHub Actions workflow annotations."""
    if not issues:
        return ""

    lines = []
    for issue in issues:
        clean_message = " ".join(issue.message.split())
        msg = f"[{issue.region_type}] {clean_message}" if issue.region_type else clean_message
        lines.append(f"::warning file={issue.file},line={issue.line},col={issue.column},title=STE100.{issue.rule_type}::{msg}")
    return "\n".join(lines)


def format_sarif(issues: list[FormattedIssue]) -> str:
    """Format issues as a SARIF v2.1.0 JSON string."""
    rules_dict: dict[str, dict[str, Any]] = {}
    results = []

    for issue in issues:
        rule_id = f"STE100.{issue.rule_type}"
        if rule_id not in rules_dict:
            rules_dict[rule_id] = {
                "id": rule_id,
                "name": issue.rule_type,
                "shortDescription": {
                    "text": f"ASD-STE100 Rule: {issue.rule_type}",
                },
            }

        results.append(
            {
                "ruleId": rule_id,
                "level": "warning",
                "message": {
                    "text": issue.message,
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": issue.file,
                            },
                            "region": {
                                "startLine": max(1, issue.line),
                                "startColumn": max(1, issue.column),
                            },
                        },
                    }
                ],
            }
        )

    sarif_doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "stelint",
                        "informationUri": "https://github.com/mikkovihonen/stelint",
                        "rules": list(rules_dict.values()),
                    },
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif_doc, indent=2)


def format_summary(issues: list[FormattedIssue]) -> str:
    """Format issues as a human-readable summary."""
    if not issues:
        return "No ASD-STE100 issues found."

    rule_counts: dict[str, int] = {}
    file_counts: dict[str, int] = {}

    for issue in issues:
        rule_counts[issue.rule_type] = rule_counts.get(issue.rule_type, 0) + 1
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1

    lines = [
        f"ASD-STE100 Lint Summary: {len(issues)} issue(s) found across {len(file_counts)} file(s).",
        "",
        "Issues by rule:",
    ]
    for rule, count in sorted(rule_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  STE100.{rule}: {count}")

    if len(file_counts) > 1:
        lines.append("")
        lines.append("Issues by file:")
        for fname, count in sorted(file_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {fname}: {count}")

    return "\n".join(lines)
