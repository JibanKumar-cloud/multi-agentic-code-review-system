"""
Test harness for evaluating the multi-agent code review system.

This module provides tools to:
- Run the system against test cases
- Compare findings against ground truth
- Calculate precision, recall, and F1 scores
- Generate evaluation reports

Run with: python -m tests.test_harness
         or: pytest tests/test_harness.py -v
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class Finding:
    """Represents a code review finding."""
    finding_id: str
    category: str
    severity: str
    title: str
    description: str
    line: Optional[int] = None
    code_snippet: Optional[str] = None
    fix_proposed: Optional[str] = None
    agent: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Finding':
        """Create Finding from dictionary."""
        return cls(
            finding_id=data.get('finding_id', data.get('id', '')),
            category=data.get('category', data.get('type', '')),
            severity=data.get('severity', 'medium'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            line=data.get('line', data.get('location', {}).get('line')),
            code_snippet=data.get('code_snippet', data.get('code', '')),
            fix_proposed=data.get('fix_proposed', data.get('fix', '')),
            agent=data.get('agent', data.get('agent_id', ''))
        )


@dataclass
class EvaluationResult:
    """Result of evaluating findings against ground truth."""
    filename: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    details: List[Dict[str, Any]] = field(default_factory=list)
    expected_count: int = 0
    found_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "expected_count": self.expected_count,
            "found_count": self.found_count,
            "details": self.details
        }


@dataclass 
class AggregateResults:
    """Aggregated results across all files."""
    total_files: int
    total_expected: int
    total_found: int
    total_tp: int
    total_fp: int
    total_fn: int
    precision: float
    recall: float
    f1_score: float
    per_file_results: Dict[str, EvaluationResult] = field(default_factory=dict)
    severity_breakdown: Dict[str, int] = field(default_factory=dict)
    category_breakdown: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_files": self.total_files,
            "total_expected": self.total_expected,
            "total_found": self.total_found,
            "total_tp": self.total_tp,
            "total_fp": self.total_fp,
            "total_fn": self.total_fn,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "severity_breakdown": self.severity_breakdown,
            "category_breakdown": self.category_breakdown,
            "per_file_results": {
                k: v.to_dict() for k, v in self.per_file_results.items()
            }
        }


class TestHarness:
    """
    Test harness for evaluating the multi-agent code review system.

    Usage:
        harness = TestHarness("test_cases/expected_findings.json")
        results = harness.evaluate_file("sql_injection.py", findings)
        harness.print_report(results)
    """

    def __init__(self, ground_truth_path: str):
        """
        Initialize the test harness.

        Args:
            ground_truth_path: Path to the expected findings JSON
        """
        self.ground_truth_path = Path(ground_truth_path)
        self.ground_truth = self._load_ground_truth(ground_truth_path)

    def _load_ground_truth(self, path: str) -> Dict[str, Any]:
        """Load ground truth from JSON file."""
        with open(path, 'r') as f:
            return json.load(f)

    def evaluate_file(
        self,
        filename: str,
        findings: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """
        Evaluate findings against ground truth for a file.

        Args:
            filename: Name of the file that was analyzed (e.g., "sql_injection.py")
            findings: Findings from the multi-agent system

        Returns:
            EvaluationResult with metrics
        """
        # Get expected findings for this file
        file_data = self.ground_truth.get("files", {}).get(filename, {})
        expected_findings = file_data.get("expected_findings", [])
        
        # Convert to Finding objects
        actual = [Finding.from_dict(f) for f in findings]
        expected = [Finding.from_dict(f) for f in expected_findings]
        
        # Match findings
        matched_expected = set()
        matched_actual = set()
        details = []
        
        for i, act in enumerate(actual):
            for j, exp in enumerate(expected):
                if j in matched_expected:
                    continue
                    
                is_match, confidence = self._match_finding(act, exp)
                if is_match:
                    matched_expected.add(j)
                    matched_actual.add(i)
                    details.append({
                        "status": "TP",
                        "title": act.title,
                        "expected_title": exp.title,
                        "confidence": confidence,
                        "severity": act.severity,
                        "line": act.line
                    })
                    break
        
        # False positives (actual findings not matched)
        for i, act in enumerate(actual):
            if i not in matched_actual:
                details.append({
                    "status": "FP",
                    "title": act.title,
                    "severity": act.severity,
                    "line": act.line,
                    "reason": "No matching expected finding"
                })
        
        # False negatives (expected findings not matched)
        for j, exp in enumerate(expected):
            if j not in matched_expected:
                details.append({
                    "status": "FN",
                    "title": exp.title,
                    "severity": exp.severity,
                    "line": exp.line,
                    "reason": "Not detected by system"
                })
        
        tp = len(matched_expected)
        fp = len(actual) - tp
        fn = len(expected) - tp
        
        precision, recall, f1 = calculate_metrics(tp, fp, fn)
        
        return EvaluationResult(
            filename=filename,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            details=details,
            expected_count=len(expected),
            found_count=len(actual)
        )

    def _match_finding(
        self,
        actual: Finding,
        expected: Finding
    ) -> Tuple[bool, float]:
        """
        Check if an actual finding matches an expected one.

        Args:
            actual: Finding from the system
            expected: Expected finding from ground truth

        Returns:
            Tuple of (is_match, confidence_score)
        """
        confidence = 0.0
        
        # Category matching (most important)
        actual_cat = actual.category.lower()
        expected_cat = expected.category.lower()
        
        # Map similar categories
        category_aliases = {
            "sql_injection": ["injection", "sqli", "sql"],
            "xss": ["cross-site scripting", "cross_site_scripting", "xss"],
            "command_injection": ["os_command", "cmd_injection", "shell_injection"],
            "deserialization": ["insecure_deserialization", "pickle", "unsafe_deserialization"],
            "null_reference": ["null_pointer", "none_reference", "attributeerror", "null_deref"],
            "hardcoded_secrets": ["hardcoded_credentials", "secrets", "credentials"],
            "race_condition": ["race", "concurrency", "toctou"],
            "cryptographic": ["crypto", "weak_hash", "md5", "sha1"],
        }
        
        def normalize_category(cat: str) -> str:
            cat = cat.lower().replace("-", "_").replace(" ", "_")
            for main, aliases in category_aliases.items():
                if cat == main or cat in aliases:
                    return main
            return cat
        
        norm_actual = normalize_category(actual_cat)
        norm_expected = normalize_category(expected_cat)
        
        if norm_actual == norm_expected:
            confidence += 0.4
        elif any(norm_actual in alias or norm_expected in alias 
                 for alias in category_aliases.get(norm_actual, []) + category_aliases.get(norm_expected, [])):
            confidence += 0.3
        
        # Line number matching
        if actual.line and expected.line:
            line_diff = abs(actual.line - expected.line)
            if line_diff == 0:
                confidence += 0.3
            elif line_diff <= 2:
                confidence += 0.2
            elif line_diff <= 5:
                confidence += 0.1
        
        # Title/description similarity
        actual_text = (actual.title + " " + actual.description).lower()
        expected_text = (expected.title + " " + expected.description).lower()
        
        # Check for keyword overlap
        actual_words = set(re.findall(r'\w+', actual_text))
        expected_words = set(re.findall(r'\w+', expected_text))
        common_words = actual_words & expected_words
        
        if len(expected_words) > 0:
            word_overlap = len(common_words) / len(expected_words)
            confidence += word_overlap * 0.3
        
        # Consider it a match if confidence > 0.5
        is_match = confidence >= 0.5
        
        return is_match, round(confidence, 2)

    def print_report(self, result: EvaluationResult) -> None:
        """
        Print a formatted evaluation report for a single file.

        Args:
            result: Evaluation result to report
        """
        print("\n" + "=" * 70)
        print(f"EVALUATION REPORT: {result.filename}")
        print("=" * 70)

        print(f"\n📊 Metrics:")
        print(f"   Expected findings: {result.expected_count}")
        print(f"   Found findings:    {result.found_count}")
        print(f"   True Positives:    {result.true_positives}")
        print(f"   False Positives:   {result.false_positives}")
        print(f"   False Negatives:   {result.false_negatives}")
        print(f"\n   Precision: {result.precision:.1%}")
        print(f"   Recall:    {result.recall:.1%}")
        print(f"   F1 Score:  {result.f1_score:.1%}")

        if result.details:
            print(f"\n📋 Details:")
            for detail in result.details:
                status = detail.get("status", "?")
                title = detail.get("title", "Unknown")[:50]
                icon = "✅" if status == "TP" else "❌" if status == "FP" else "⚠️"
                print(f"   {icon} [{status}] {title}")

    def print_aggregate_report(self, results: AggregateResults) -> None:
        """
        Print aggregated evaluation report.

        Args:
            results: Aggregated results across all files
        """
        print("\n" + "=" * 70)
        print("AGGREGATE EVALUATION REPORT")
        print("=" * 70)
        
        print(f"\n📊 Overall Metrics:")
        print(f"   Files analyzed:    {results.total_files}")
        print(f"   Expected findings: {results.total_expected}")
        print(f"   Found findings:    {results.total_found}")
        print(f"   True Positives:    {results.total_tp}")
        print(f"   False Positives:   {results.total_fp}")
        print(f"   False Negatives:   {results.total_fn}")
        print(f"\n   Precision: {results.precision:.1%}")
        print(f"   Recall:    {results.recall:.1%}")
        print(f"   F1 Score:  {results.f1_score:.1%}")
        
        if results.severity_breakdown:
            print(f"\n🎯 Severity Breakdown:")
            for sev, count in sorted(results.severity_breakdown.items()):
                print(f"   {sev.capitalize()}: {count}")
        
        print(f"\n📁 Per-File Results:")
        for filename, file_result in results.per_file_results.items():
            status = "✅" if file_result.f1_score >= 0.8 else "⚠️" if file_result.f1_score >= 0.6 else "❌"
            print(f"   {status} {filename}: P={file_result.precision:.0%} R={file_result.recall:.0%} F1={file_result.f1_score:.0%}")

    def run_full_evaluation(
        self,
        findings_by_file: Dict[str, List[Dict[str, Any]]]
    ) -> AggregateResults:
        """
        Run evaluation on multiple files.

        Args:
            findings_by_file: Dictionary mapping filename to list of findings

        Returns:
            AggregateResults with aggregated metrics
        """
        per_file_results = {}
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_expected = 0
        total_found = 0
        severity_breakdown = {}
        category_breakdown = {}
        
        for filename, findings in findings_by_file.items():
            result = self.evaluate_file(filename, findings)
            per_file_results[filename] = result
            
            total_tp += result.true_positives
            total_fp += result.false_positives
            total_fn += result.false_negatives
            total_expected += result.expected_count
            total_found += result.found_count
            
            # Track severity breakdown
            for finding in findings:
                sev = finding.get("severity", "medium").lower()
                severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
                
                cat = finding.get("category", "unknown").lower()
                category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        precision, recall, f1 = calculate_metrics(total_tp, total_fp, total_fn)
        
        return AggregateResults(
            total_files=len(findings_by_file),
            total_expected=total_expected,
            total_found=total_found,
            total_tp=total_tp,
            total_fp=total_fp,
            total_fn=total_fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            per_file_results=per_file_results,
            severity_breakdown=severity_breakdown,
            category_breakdown=category_breakdown
        )


def calculate_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """
    Calculate precision, recall, and F1 score.

    Args:
        tp: True positives
        fp: False positives
        fn: False negatives

    Returns:
        Tuple of (precision, recall, f1_score)
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return precision, recall, f1


# ============================================================================
# Tests for the Test Harness
# ============================================================================

import pytest


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""
    
    def test_perfect_scores(self):
        """Test with all correct predictions."""
        p, r, f1 = calculate_metrics(tp=10, fp=0, fn=0)
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0
    
    def test_no_predictions(self):
        """Test with no predictions."""
        p, r, f1 = calculate_metrics(tp=0, fp=0, fn=10)
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0
    
    def test_half_precision(self):
        """Test 50% precision."""
        p, r, f1 = calculate_metrics(tp=5, fp=5, fn=0)
        assert p == 0.5
        assert r == 1.0
    
    def test_half_recall(self):
        """Test 50% recall."""
        p, r, f1 = calculate_metrics(tp=5, fp=0, fn=5)
        assert p == 1.0
        assert r == 0.5


class TestFinding:
    """Tests for Finding dataclass."""
    
    def test_from_dict(self):
        """Test creating Finding from dictionary."""
        data = {
            "finding_id": "f1",
            "category": "sql_injection",
            "severity": "critical",
            "title": "SQL Injection",
            "description": "User input in query",
            "line": 42
        }
        finding = Finding.from_dict(data)
        
        assert finding.finding_id == "f1"
        assert finding.category == "sql_injection"
        assert finding.severity == "critical"
        assert finding.line == 42
    
    def test_from_dict_with_location(self):
        """Test creating Finding with nested location."""
        data = {
            "id": "f2",
            "type": "xss",
            "severity": "high",
            "title": "XSS",
            "description": "...",
            "location": {"line": 100, "file": "test.py"}
        }
        finding = Finding.from_dict(data)
        
        assert finding.finding_id == "f2"
        assert finding.category == "xss"
        assert finding.line == 100


class TestTestHarness:
    """Tests for TestHarness class."""
    
    @pytest.fixture
    def sample_ground_truth(self, tmp_path):
        """Create sample ground truth file."""
        ground_truth = {
            "files": {
                "test.py": {
                    "expected_findings": [
                        {
                            "id": "e1",
                            "category": "sql_injection",
                            "severity": "critical",
                            "title": "SQL Injection in authenticate",
                            "description": "User input concatenated into query",
                            "line": 10
                        },
                        {
                            "id": "e2",
                            "category": "null_reference",
                            "severity": "medium",
                            "title": "Potential None access",
                            "description": "user.name accessed without check",
                            "line": 25
                        }
                    ]
                }
            }
        }
        
        path = tmp_path / "expected.json"
        path.write_text(json.dumps(ground_truth))
        return str(path)
    
    def test_perfect_match(self, sample_ground_truth):
        """Test evaluation with perfect matches."""
        harness = TestHarness(sample_ground_truth)
        
        findings = [
            {
                "finding_id": "a1",
                "category": "sql_injection",
                "severity": "critical",
                "title": "SQL Injection vulnerability",
                "description": "Query uses string concatenation",
                "line": 10
            },
            {
                "finding_id": "a2",
                "category": "null_reference",
                "severity": "medium",
                "title": "NoneType error possible",
                "description": "Accessing .name on potentially None",
                "line": 25
            }
        ]
        
        result = harness.evaluate_file("test.py", findings)
        
        assert result.true_positives == 2
        assert result.false_positives == 0
        assert result.false_negatives == 0
        assert result.precision == 1.0
        assert result.recall == 1.0
    
    def test_partial_match(self, sample_ground_truth):
        """Test evaluation with partial matches."""
        harness = TestHarness(sample_ground_truth)
        
        findings = [
            {
                "finding_id": "a1",
                "category": "sql_injection",
                "severity": "critical",
                "title": "SQL Injection",
                "description": "...",
                "line": 10
            }
        ]
        
        result = harness.evaluate_file("test.py", findings)
        
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 1
        assert result.recall == 0.5
    
    def test_false_positives(self, sample_ground_truth):
        """Test evaluation with false positives."""
        harness = TestHarness(sample_ground_truth)
        
        findings = [
            {
                "finding_id": "a1",
                "category": "sql_injection",
                "severity": "critical",
                "title": "SQL Injection",
                "description": "...",
                "line": 10
            },
            {
                "finding_id": "a2",
                "category": "null_reference",
                "severity": "medium",
                "title": "None check",
                "description": "...",
                "line": 25
            },
            {
                "finding_id": "a3",
                "category": "xss",
                "severity": "high",
                "title": "False positive XSS",
                "description": "This doesn't exist in ground truth",
                "line": 50
            }
        ]
        
        result = harness.evaluate_file("test.py", findings)
        
        assert result.true_positives == 2
        assert result.false_positives == 1
        assert result.precision < 1.0


class TestAggregateResults:
    """Tests for aggregate evaluation."""
    
    @pytest.fixture
    def multi_file_ground_truth(self, tmp_path):
        """Create ground truth with multiple files."""
        ground_truth = {
            "files": {
                "file1.py": {
                    "expected_findings": [
                        {"id": "1", "category": "sql_injection", "severity": "critical", 
                         "title": "SQLi", "description": "...", "line": 10}
                    ]
                },
                "file2.py": {
                    "expected_findings": [
                        {"id": "2", "category": "xss", "severity": "high",
                         "title": "XSS", "description": "...", "line": 20}
                    ]
                }
            }
        }
        
        path = tmp_path / "expected.json"
        path.write_text(json.dumps(ground_truth))
        return str(path)
    
    def test_aggregate_evaluation(self, multi_file_ground_truth):
        """Test aggregated evaluation across multiple files."""
        harness = TestHarness(multi_file_ground_truth)
        
        findings_by_file = {
            "file1.py": [
                {"finding_id": "f1", "category": "sql_injection", "severity": "critical",
                 "title": "SQL Injection", "description": "...", "line": 10}
            ],
            "file2.py": [
                {"finding_id": "f2", "category": "xss", "severity": "high",
                 "title": "XSS vulnerability", "description": "...", "line": 20}
            ]
        }
        
        results = harness.run_full_evaluation(findings_by_file)
        
        assert results.total_files == 2
        assert results.total_tp == 2
        assert results.total_fp == 0
        assert results.total_fn == 0
        assert results.precision == 1.0
        assert results.recall == 1.0


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Run test harness from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Code Review Test Harness")
    parser.add_argument(
        "--ground-truth",
        default="test_cases/expected_findings.json",
        help="Path to ground truth JSON"
    )
    parser.add_argument(
        "--findings",
        help="Path to findings JSON file"
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run pytest tests"
    )
    
    args = parser.parse_args()
    
    if args.run_tests:
        pytest.main([__file__, "-v"])
        return
    
    if args.findings:
        with open(args.findings) as f:
            data = json.load(f)
        
        harness = TestHarness(args.ground_truth)
        
        if "files" in data:
            # Multiple files
            results = harness.run_full_evaluation(data["files"])
            harness.print_aggregate_report(results)
        else:
            # Single file
            filename = data.get("filename", "unknown.py")
            findings = data.get("findings", [])
            result = harness.evaluate_file(filename, findings)
            harness.print_report(result)
    else:
        print("No findings file provided. Use --findings <path> or --run-tests")


if __name__ == "__main__":
    main()
