"""
Compliance Report Generator
Creates comprehensive compliance reports with evidence
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from utils.evidence_validator import ComplianceResult
from utils.rule_manager import Rule

logger = logging.getLogger(__name__)


@dataclass
class ComplianceSummary:
    """Summary of compliance evaluation"""
    total_rules: int = 0
    compliant: int = 0
    non_compliant: int = 0
    not_applicable: int = 0
    unknown: int = 0
    high_risk_violations: int = 0
    critical_violations: int = 0
    overall_confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_rules": self.total_rules,
            "status_breakdown": {
                "compliant": self.compliant,
                "non_compliant": self.non_compliant,
                "not_applicable": self.not_applicable,
                "unknown": self.unknown
            },
            "risk_summary": {
                "high_risk_violations": self.high_risk_violations,
                "critical_violations": self.critical_violations
            },
            "compliance_rate": self.compliant / self.total_rules if self.total_rules > 0 else 0,
            "overall_confidence": self.overall_confidence
        }


@dataclass
class ComplianceReport:
    """Complete compliance report"""
    report_id: str
    document_name: str
    evaluation_date: str
    summary: ComplianceSummary
    results: List[ComplianceResult]
    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence_pack: Dict[str, Any] = field(default_factory=dict)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "document_name": self.document_name,
            "evaluation_date": self.evaluation_date,
            "summary": self.summary.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
            "evidence_pack": self.evidence_pack,
            "audit_trail": self.audit_trail
        }


class ComplianceReportGenerator:
    """Generates compliance reports"""
    
    def __init__(self, output_dir: str = "data/compliance_reports"):
        """
        Initialize report generator
        
        Args:
            output_dir: Directory for report output
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        results: List[ComplianceResult],
        rules: Dict[str, Rule],
        document_name: str,
        document_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ComplianceReport:
        """
        Generate compliance report
        
        Args:
            results: Compliance results
            rules: Dictionary of rules
            document_name: Document name
            document_text: Document text
            metadata: Optional metadata
            
        Returns:
            Compliance report
        """
        # Generate report ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"CR_{timestamp}_{document_name[:20]}"
        
        # Calculate summary
        summary = self._calculate_summary(results, rules)
        
        # Build evidence pack
        evidence_pack = self._build_evidence_pack(results, document_text)
        
        # Create audit trail
        audit_trail = self._create_audit_trail(results)
        
        # Create report
        report = ComplianceReport(
            report_id=report_id,
            document_name=document_name,
            evaluation_date=datetime.now().isoformat(),
            summary=summary,
            results=results,
            metadata=metadata or {},
            evidence_pack=evidence_pack,
            audit_trail=audit_trail
        )
        
        # Add processing statistics
        report.metadata.update({
            "generator_version": "1.0.0",
            "total_processing_time": sum(
                r.attribution.get("time_seconds", 0) for r in results
            ),
            "deterministic_evaluations": sum(
                1 for r in results if r.deterministic_result and r.deterministic_result.is_conclusive
            ),
            "llm_evaluations": sum(
                1 for r in results if r.llm_judgment
            )
        })
        
        return report
    
    def _calculate_summary(
        self,
        results: List[ComplianceResult],
        rules: Dict[str, Rule]
    ) -> ComplianceSummary:
        """Calculate compliance summary"""
        summary = ComplianceSummary(total_rules=len(results))
        
        confidence_scores = []
        
        for result in results:
            # Count by status
            if result.status == "compliant":
                summary.compliant += 1
            elif result.status == "non_compliant":
                summary.non_compliant += 1
                
                # Check risk level
                rule = rules.get(result.rule_id)
                if rule:
                    if rule.risk_level == "critical":
                        summary.critical_violations += 1
                    elif rule.risk_level == "high":
                        summary.high_risk_violations += 1
                        
            elif result.status == "not_applicable":
                summary.not_applicable += 1
            else:  # unknown
                summary.unknown += 1
            
            # Collect confidence scores
            if result.confidence > 0:
                confidence_scores.append(result.confidence)
        
        # Calculate overall confidence
        if confidence_scores:
            summary.overall_confidence = sum(confidence_scores) / len(confidence_scores)
        
        return summary
    
    def _build_evidence_pack(
        self,
        results: List[ComplianceResult],
        document_text: str
    ) -> Dict[str, Any]:
        """Build evidence pack with citations"""
        evidence_pack = {
            "total_citations": 0,
            "citations_by_rule": {},
            "unique_pages_cited": set(),
            "citation_texts": []
        }
        
        for result in results:
            if result.citations:
                evidence_pack["citations_by_rule"][result.rule_id] = []
                
                for citation in result.citations:
                    citation_data = {
                        "rule_id": result.rule_id,
                        "text": citation.text,
                        "page": citation.page,
                        "anchor": citation.anchor
                    }
                    
                    evidence_pack["citations_by_rule"][result.rule_id].append(citation_data)
                    evidence_pack["citation_texts"].append(citation_data)
                    evidence_pack["unique_pages_cited"].add(citation.page)
                    evidence_pack["total_citations"] += 1
        
        # Convert set to list for JSON serialization
        evidence_pack["unique_pages_cited"] = sorted(list(evidence_pack["unique_pages_cited"]))
        
        # Add document excerpt
        evidence_pack["document_excerpt"] = document_text[:1000] + "..." if len(document_text) > 1000 else document_text
        
        return evidence_pack
    
    def _create_audit_trail(self, results: List[ComplianceResult]) -> List[Dict[str, Any]]:
        """Create audit trail of evaluations"""
        audit_trail = []
        
        for result in results:
            entry = {
                "rule_id": result.rule_id,
                "status": result.status,
                "evaluation_method": result.attribution.get("method", "unknown"),
                "model_used": result.attribution.get("model", "none"),
                "confidence": result.confidence,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add deterministic check info
            if result.deterministic_result:
                entry["deterministic"] = {
                    "was_conclusive": result.deterministic_result.is_conclusive,
                    "confidence": result.deterministic_result.confidence
                }
            
            # Add validation info
            if result.validation:
                entry["validation"] = {
                    "is_valid": result.validation.is_valid,
                    "errors": len(result.validation.errors),
                    "warnings": len(result.validation.warnings)
                }
            
            audit_trail.append(entry)
        
        return audit_trail
    
    def save_report(
        self,
        report: ComplianceReport,
        formats: List[str] = ["json", "yaml", "html"]
    ) -> Dict[str, str]:
        """
        Save report in multiple formats
        
        Args:
            report: Report to save
            formats: Output formats
            
        Returns:
            Dictionary of format to file path
        """
        saved_files = {}
        
        # Create report directory
        report_dir = self.output_dir / report.report_id
        report_dir.mkdir(exist_ok=True)
        
        # Save JSON
        if "json" in formats:
            json_path = report_dir / "report.json"
            with open(json_path, 'w') as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
            saved_files["json"] = str(json_path)
            logger.info(f"Saved JSON report: {json_path}")
        
        # Save YAML
        if "yaml" in formats:
            yaml_path = report_dir / "report.yaml"
            with open(yaml_path, 'w') as f:
                yaml.dump(report.to_dict(), f, default_flow_style=False, default=str)
            saved_files["yaml"] = str(yaml_path)
            logger.info(f"Saved YAML report: {yaml_path}")
        
        # Save HTML
        if "html" in formats:
            html_path = report_dir / "report.html"
            html_content = self._generate_html_report(report)
            with open(html_path, 'w') as f:
                f.write(html_content)
            saved_files["html"] = str(html_path)
            logger.info(f"Saved HTML report: {html_path}")
        
        # Save evidence pack separately
        evidence_path = report_dir / "evidence_pack.json"
        with open(evidence_path, 'w') as f:
            json.dump(report.evidence_pack, f, indent=2, default=str)
        saved_files["evidence"] = str(evidence_path)
        
        # Save audit trail
        audit_path = report_dir / "audit_trail.json"
        with open(audit_path, 'w') as f:
            json.dump(report.audit_trail, f, indent=2, default=str)
        saved_files["audit"] = str(audit_path)
        
        return saved_files
    
    def _generate_html_report(self, report: ComplianceReport) -> str:
        """Generate HTML report"""
        summary = report.summary
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Compliance Report - {report.document_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px; }}
        .summary {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .compliant {{ color: #27ae60; font-weight: bold; }}
        .non-compliant {{ color: #e74c3c; font-weight: bold; }}
        .unknown {{ color: #f39c12; font-weight: bold; }}
        .not-applicable {{ color: #95a5a6; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #34495e; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .citation {{ background: #fffacd; padding: 5px; margin: 5px 0; border-left: 3px solid #f39c12; }}
        .confidence {{ float: right; color: #7f8c8d; }}
    </style>
</head>
<body>
    <h1>Compliance Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Document:</strong> {report.document_name}</p>
        <p><strong>Date:</strong> {report.evaluation_date}</p>
        <p><strong>Report ID:</strong> {report.report_id}</p>
        
        <h3>Compliance Status</h3>
        <ul>
            <li>Total Rules Evaluated: {summary.total_rules}</li>
            <li class="compliant">Compliant: {summary.compliant}</li>
            <li class="non-compliant">Non-Compliant: {summary.non_compliant}</li>
            <li class="not-applicable">Not Applicable: {summary.not_applicable}</li>
            <li class="unknown">Unknown: {summary.unknown}</li>
        </ul>
        
        <h3>Risk Summary</h3>
        <ul>
            <li>Critical Violations: {summary.critical_violations}</li>
            <li>High Risk Violations: {summary.high_risk_violations}</li>
            <li>Overall Confidence: {summary.overall_confidence:.1%}</li>
        </ul>
    </div>
    
    <h2>Detailed Results</h2>
    <table>
        <tr>
            <th>Rule ID</th>
            <th>Status</th>
            <th>Rationale</th>
            <th>Citations</th>
            <th>Confidence</th>
        </tr>
"""
        
        for result in report.results:
            status_class = result.status.replace("_", "-")
            html += f"""
        <tr>
            <td>{result.rule_id}</td>
            <td class="{status_class}">{result.status.upper()}</td>
            <td>{result.rationale}</td>
            <td>
"""
            if result.citations:
                for citation in result.citations:
                    html += f'<div class="citation">"{citation.text[:100]}..." {citation.anchor}</div>'
            else:
                html += "No citations"
            
            html += f"""
            </td>
            <td>{result.confidence:.1%}</td>
        </tr>
"""
        
        html += """
    </table>
    
    <h2>Evidence Summary</h2>
    <ul>
        <li>Total Citations: """ + str(report.evidence_pack.get("total_citations", 0)) + """</li>
        <li>Pages Referenced: """ + str(len(report.evidence_pack.get("unique_pages_cited", []))) + """</li>
    </ul>
    
    <p><em>Generated by Compliance Report Generator v1.0.0</em></p>
</body>
</html>"""
        
        return html
    
    def generate_executive_summary(self, report: ComplianceReport) -> str:
        """Generate executive summary text"""
        summary = report.summary
        
        text = f"""EXECUTIVE SUMMARY
================

Document: {report.document_name}
Date: {report.evaluation_date}

COMPLIANCE OVERVIEW:
- Total Rules Evaluated: {summary.total_rules}
- Compliant: {summary.compliant} ({summary.compliant/summary.total_rules:.1%})
- Non-Compliant: {summary.non_compliant} ({summary.non_compliant/summary.total_rules:.1%})
- Not Applicable: {summary.not_applicable}
- Unable to Determine: {summary.unknown}

RISK ASSESSMENT:
- Critical Issues: {summary.critical_violations}
- High Risk Issues: {summary.high_risk_violations}
- Overall Confidence: {summary.overall_confidence:.1%}

KEY FINDINGS:
"""
        
        # Add top non-compliant findings
        non_compliant = [r for r in report.results if r.status == "non_compliant"]
        for result in non_compliant[:5]:  # Top 5
            text += f"\n• {result.rule_id}: {result.rationale[:100]}..."
        
        text += f"""

EVIDENCE:
- Total Citations: {report.evidence_pack.get('total_citations', 0)}
- Pages Referenced: {len(report.evidence_pack.get('unique_pages_cited', []))}

RECOMMENDATION:
"""
        
        if summary.critical_violations > 0:
            text += "Immediate attention required for critical compliance violations."
        elif summary.high_risk_violations > 0:
            text += "Review and address high-risk compliance issues."
        elif summary.non_compliant > 0:
            text += "Minor compliance issues identified for review."
        else:
            text += "Document appears to be compliant with evaluated rules."
        
        return text


# Global report generator instance
report_generator = ComplianceReportGenerator()


def generate_compliance_report(
    results: List[ComplianceResult],
    rules: Dict[str, Rule],
    document_name: str,
    document_text: str,
    metadata: Optional[Dict[str, Any]] = None
) -> ComplianceReport:
    """
    Convenience function to generate report
    
    Args:
        results: Compliance results
        rules: Rules dictionary
        document_name: Document name
        document_text: Document text
        metadata: Optional metadata
        
    Returns:
        Compliance report
    """
    return report_generator.generate_report(
        results,
        rules,
        document_name,
        document_text,
        metadata
    )