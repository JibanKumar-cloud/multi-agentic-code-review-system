"""
Evaluation script for the Multi-Agent Code Review System.

Runs the system against test cases and calculates precision, recall, and F1 score.

Usage:
    python evaluate.py --input test_cases/buggy_samples/ --expected test_cases/expected_findings.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from starter_code.src.config import config
from starter_code.src.events import EventBus
from starter_code.src.agents.code_review_workflow import CodeReviewWorkflow



@dataclass
class EvaluationResult:
    """Results for a single file evaluation."""
    filename: str
    expected_count: int
    found_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    findings: List[Dict[str, Any]] = field(default_factory=list)
    matches: List[Dict[str, Any]] = field(default_factory=list)
    missed: List[Dict[str, Any]] = field(default_factory=list)
    extras: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OverallMetrics:
    """Overall evaluation metrics."""
    total_files: int
    total_expected: int
    total_found: int
    total_true_positives: int
    total_false_positives: int
    total_false_negatives: int
    precision: float
    recall: float
    f1_score: float
    fixes_proposed: int
    fixes_verified: int
    fix_success_rate: float
    duration_ms: int
    file_results: List[EvaluationResult] = field(default_factory=list)


async def analyze_file(file_path: Path, event_bus: EventBus) -> Dict[str, Any]:
    """Analyze a single file and return results."""
    code = file_path.read_text()
    
   # Run analysis
    results = await code_review.review_code(code, filename={"filename": str(file_path.file_name)})
    
    return results


def match_finding(found: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    """Check if a found finding matches an expected finding."""
    # Match by type/category
    found_type = found.get('type', '').lower().replace('_', ' ')
    expected_cat = expected.get('category', '').lower().replace('_', ' ')
    expected_type = expected.get('type', '').lower() if expected.get('type') else expected_cat
    
    type_match = (
        found_type in expected_cat or
        expected_cat in found_type or
        found_type in expected_type or
        expected_type in found_type
    )
    
    # Match by line number (within tolerance)
    found_line = found.get('location', {}).get('line_start', 0)
    expected_start = expected.get('line_start', 0)
    expected_end = expected.get('line_end', expected_start)
    
    line_match = (
        expected_start - 5 <= found_line <= expected_end + 5
    )
    
    return type_match and line_match


def evaluate_file(
    findings: List[Dict[str, Any]],
    expected: List[Dict[str, Any]],
    filename: str
) -> EvaluationResult:
    """Evaluate findings against expected for a single file."""
    
    true_positives = 0
    matches = []
    matched_expected = set()
    matched_found = set()
    
    # Find matches
    for i, found in enumerate(findings):
        for j, exp in enumerate(expected):
            if j not in matched_expected and match_finding(found, exp):
                true_positives += 1
                matches.append({
                    "found": found,
                    "expected": exp
                })
                matched_expected.add(j)
                matched_found.add(i)
                break
    
    # Calculate metrics
    false_positives = len(findings) - true_positives
    false_negatives = len(expected) - true_positives
    
    precision = true_positives / len(findings) if findings else 0.0
    recall = true_positives / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Identify missed and extra findings
    missed = [expected[j] for j in range(len(expected)) if j not in matched_expected]
    extras = [findings[i] for i in range(len(findings)) if i not in matched_found]
    
    return EvaluationResult(
        filename=filename,
        expected_count=len(expected),
        found_count=len(findings),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1,
        findings=findings,
        matches=matches,
        missed=missed,
        extras=extras
    )


async def run_evaluation(
    input_dir: Path,
    expected_file: Path,
    verbose: bool = False
) -> OverallMetrics:
    """Run full evaluation against test cases."""
    
    # Load expected findings
    with open(expected_file) as f:
        expected_data = json.load(f)
    
    # Validate config
    try:
        config.validate()
    except ValueError as e:
        print(f"⚠️  Configuration warning: {e}")
        print("   Running in demo mode with mock responses...")
        # Continue anyway for testing structure
    
    event_bus = EventBus()
    file_results = []
    total_fixes_proposed = 0
    total_fixes_verified = 0
    start_time = datetime.now()
    
    # Get list of files
    py_files = sorted(input_dir.glob("*.py"))
    
    print(f"\n{'='*60}")
    print(f"Multi-Agent Code Review System - Evaluation")
    print(f"{'='*60}")
    print(f"Input directory: {input_dir}")
    print(f"Expected findings: {expected_file}")
    print(f"Files to analyze: {len(py_files)}")
    print(f"{'='*60}\n")

    code_review = CodeReviewWorkflow(event_bus)

    for file_path in py_files:
        filename = file_path.name
        print(f"📄 Analyzing: {filename}...", end=" ", flush=True)
        
        try:
            # Get expected findings for this file
            file_expected = expected_data.get('files', {}).get(filename, {})
            expected_findings = file_expected.get('expected_findings', [])
            
                
            # Run analysis
            code = file_path.read_text()

            results = await code_review.review_code(code, filename={"filename": str(filename)})
            
            # Get findings
            findings = results.get('findings', [])
            fixes = results.get('fixes', [])
            
            # Count fixes
            total_fixes_proposed += len(fixes)
            total_fixes_verified += len([f for f in fixes if f.get('verified', False)])
            
            # Evaluate
            eval_result = evaluate_file(findings, expected_findings, filename)
            file_results.append(eval_result)
            
            # Print result
            status = "✅" if eval_result.precision >= 0.7 and eval_result.recall >= 0.7 else "⚠️"
            print(f"{status} Found: {eval_result.found_count}, TP: {eval_result.true_positives}, "
                  f"P: {eval_result.precision:.2f}, R: {eval_result.recall:.2f}")
            
            if verbose and eval_result.missed:
                print(f"   Missed: {[m.get('title', m.get('id')) for m in eval_result.missed]}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            file_results.append(EvaluationResult(
                filename=filename,
                expected_count=len(expected_data.get('files', {}).get(filename, {}).get('expected_findings', [])),
                found_count=0,
                true_positives=0,
                false_positives=0,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0
            ))
    
    # Calculate overall metrics
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    total_expected = sum(r.expected_count for r in file_results)
    total_found = sum(r.found_count for r in file_results)
    total_tp = sum(r.true_positives for r in file_results)
    total_fp = sum(r.false_positives for r in file_results)
    total_fn = sum(r.false_negatives for r in file_results)
    
    overall_precision = total_tp / total_found if total_found > 0 else 0.0
    overall_recall = total_tp / total_expected if total_expected > 0 else 0.0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0
    
    fix_rate = total_fixes_verified / total_fixes_proposed if total_fixes_proposed > 0 else 0.0
    
    return OverallMetrics(
        total_files=len(file_results),
        total_expected=total_expected,
        total_found=total_found,
        total_true_positives=total_tp,
        total_false_positives=total_fp,
        total_false_negatives=total_fn,
        precision=overall_precision,
        recall=overall_recall,
        f1_score=overall_f1,
        fixes_proposed=total_fixes_proposed,
        fixes_verified=total_fixes_verified,
        fix_success_rate=fix_rate,
        duration_ms=int(duration),
        file_results=file_results
    )


def print_report(metrics: OverallMetrics) -> None:
    """Print evaluation report."""
    
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*60}")
    
    print(f"\n📊 Overall Metrics:")
    print(f"   Files analyzed:    {metrics.total_files}")
    print(f"   Expected findings: {metrics.total_expected}")
    print(f"   Found findings:    {metrics.total_found}")
    print(f"   True positives:    {metrics.total_true_positives}")
    print(f"   False positives:   {metrics.total_false_positives}")
    print(f"   False negatives:   {metrics.total_false_negatives}")
    
    print(f"\n📈 Quality Metrics:")
    print(f"   Precision:    {metrics.precision:.2%} {'✅' if metrics.precision >= 0.7 else '⚠️'}")
    print(f"   Recall:       {metrics.recall:.2%} {'✅' if metrics.recall >= 0.7 else '⚠️'}")
    print(f"   F1 Score:     {metrics.f1_score:.2%} {'✅' if metrics.f1_score >= 0.7 else '⚠️'}")
    
    print(f"\n🔧 Fix Metrics:")
    print(f"   Fixes proposed: {metrics.fixes_proposed}")
    print(f"   Fixes verified: {metrics.fixes_verified}")
    print(f"   Success rate:   {metrics.fix_success_rate:.2%} {'✅' if metrics.fix_success_rate >= 0.5 else '⚠️'}")
    
    print(f"\n⏱️  Duration: {metrics.duration_ms}ms")
    
    # Per-file breakdown
    print(f"\n📋 Per-File Results:")
    print(f"{'File':<30} {'Expected':>8} {'Found':>8} {'TP':>4} {'P':>6} {'R':>6} {'F1':>6}")
    print("-" * 70)
    
    for result in metrics.file_results:
        print(f"{result.filename:<30} {result.expected_count:>8} {result.found_count:>8} "
              f"{result.true_positives:>4} {result.precision:>6.2f} {result.recall:>6.2f} {result.f1_score:>6.2f}")
    
    # Pass/fail determination
    print(f"\n{'='*60}")
    if metrics.precision >= 0.7 and metrics.recall >= 0.7 and metrics.f1_score >= 0.7:
        print("✅ EVALUATION PASSED - Meets quality thresholds")
    else:
        print("⚠️  EVALUATION NEEDS IMPROVEMENT")
        if metrics.precision < 0.7:
            print("   - Precision below 0.7 (too many false positives)")
        if metrics.recall < 0.7:
            print("   - Recall below 0.7 (missing too many findings)")
    print(f"{'='*60}")


def save_results(metrics: OverallMetrics, output_path: Path) -> None:
    """Save evaluation results to JSON file."""
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_files": metrics.total_files,
            "total_expected": metrics.total_expected,
            "total_found": metrics.total_found,
            "true_positives": metrics.total_true_positives,
            "false_positives": metrics.total_false_positives,
            "false_negatives": metrics.total_false_negatives,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "fixes_proposed": metrics.fixes_proposed,
            "fixes_verified": metrics.fixes_verified,
            "fix_success_rate": metrics.fix_success_rate,
            "duration_ms": metrics.duration_ms
        },
        "file_results": [
            {
                "filename": r.filename,
                "expected_count": r.expected_count,
                "found_count": r.found_count,
                "true_positives": r.true_positives,
                "false_positives": r.false_positives,
                "false_negatives": r.false_negatives,
                "precision": r.precision,
                "recall": r.recall,
                "f1_score": r.f1_score,
                "findings": r.findings,
                "missed": r.missed,
                "extras": r.extras
            }
            for r in metrics.file_results
        ]
    }
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the Multi-Agent Code Review System"
    )
    
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Directory containing test case files"
    )
    
    parser.add_argument(
        "--expected", "-e",
        type=Path,
        required=True,
        help="JSON file with expected findings"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("metrics.json"),
        help="Output file for metrics (default: metrics.json)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input directory not found: {args.input}")
        sys.exit(1)
    
    if not args.expected.exists():
        print(f"Error: Expected findings file not found: {args.expected}")
        sys.exit(1)
    
    # Run evaluation
    metrics = asyncio.run(run_evaluation(args.input, args.expected, args.verbose))
    
    # Print report
    print_report(metrics)
    
    # Save results
    save_results(metrics, args.output)
    
    # Exit with appropriate code
    if metrics.precision >= 0.7 and metrics.recall >= 0.7:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
