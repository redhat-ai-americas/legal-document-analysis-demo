"""
PDF Conversion Quality Critic Agent
Validates PDF to markdown conversion quality and triggers retries with different strategies
"""

import os
import re
from typing import Dict, Any
from workflows.state import ContractAnalysisState
from utils.error_handler import handle_node_errors
import logging

logger = logging.getLogger(__name__)


class PDFConversionCritic:
    """
    Validates PDF conversion quality.
    Checks for:
    - Page anchor presence and distribution
    - Text extraction completeness
    - Image placeholder ratio (OCR failure indicator)
    - Table extraction quality
    - Encoding/garbled text issues
    - Document structure preservation
    """
    
    def __init__(self,
                 min_text_length: int = 1000,
                 max_image_ratio: float = 0.5,
                 require_page_anchors: bool = True,
                 min_pages: int = 1):
        """
        Initialize the PDF conversion critic.
        
        Args:
            min_text_length: Minimum acceptable text length
            max_image_ratio: Maximum ratio of image placeholders to text
            require_page_anchors: Whether page anchors are required
            min_pages: Minimum expected number of pages
        """
        self.min_text_length = min_text_length
        self.max_image_ratio = max_image_ratio
        self.require_page_anchors = require_page_anchors
        self.min_pages = min_pages
        self.validation_results = {}
        self.issues_found = []
    
    def validate_conversion(self, state: ContractAnalysisState) -> Dict[str, Any]:
        """
        Validate PDF conversion quality.
        
        Returns:
            Dict containing validation results and recommendations
        """
        self.validation_results = {
            "text_length": 0,
            "page_count": 0,
            "has_page_anchors": False,
            "page_anchor_count": 0,
            "image_placeholder_count": 0,
            "image_ratio": 0.0,
            "table_count": 0,
            "garbled_text_detected": False,
            "structure_quality": "unknown",
            "validation_passed": True,
            "issues": [],
            "recommendations": [],
            "severity": "none",
            "conversion_metrics": {}
        }
        self.issues_found = []
        
        # Get converted document
        document_text = state.get('document_text', '')
        state.get('processed_document_path', '')
        
        if not document_text:
            self.issues_found.append({
                "type": "no_text",
                "severity": "critical",
                "message": "No text extracted from PDF"
            })
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
            self.validation_results['issues'] = self.issues_found
            return self.validation_results
        
        # Analyze text quality
        self._analyze_text_quality(document_text)
        
        # Check page anchors
        self._check_page_anchors(document_text)
        
        # Analyze image placeholders
        self._analyze_image_placeholders(document_text)
        
        # Check for tables
        self._analyze_tables(document_text)
        
        # Detect garbled text
        self._detect_garbled_text(document_text)
        
        # Analyze document structure
        self._analyze_structure(document_text)
        
        # Check conversion metadata if available
        self._check_conversion_metadata(state)
        
        # Determine severity
        self._determine_severity()
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self.validation_results
    
    def _analyze_text_quality(self, text: str):
        """Analyze basic text quality metrics."""
        # Clean text for measurement
        clean_text = re.sub(r'\s+', ' ', text).strip()
        self.validation_results['text_length'] = len(clean_text)
        
        # Check minimum length
        if len(clean_text) < self.min_text_length:
            self.issues_found.append({
                "type": "insufficient_text",
                "severity": "high",
                "message": f"Only {len(clean_text)} characters extracted (minimum: {self.min_text_length})"
            })
        
        # Check for mostly whitespace
        non_whitespace = len(re.sub(r'\s', '', text))
        if non_whitespace < len(text) * 0.1:
            self.issues_found.append({
                "type": "mostly_whitespace",
                "severity": "high",
                "message": "Document is mostly whitespace"
            })
    
    def _check_page_anchors(self, text: str):
        """Check for page anchor presence and distribution."""
        page_anchors = re.findall(r'\[\[page=(\d+)\]\]', text)
        
        self.validation_results['has_page_anchors'] = len(page_anchors) > 0
        self.validation_results['page_anchor_count'] = len(page_anchors)
        
        if page_anchors:
            # Extract page numbers
            page_numbers = [int(p) for p in page_anchors]
            self.validation_results['page_count'] = max(page_numbers)
            
            # Check for gaps in page numbers
            expected_pages = set(range(1, max(page_numbers) + 1))
            actual_pages = set(page_numbers)
            missing_pages = expected_pages - actual_pages
            
            if missing_pages:
                self.issues_found.append({
                    "type": "missing_pages",
                    "severity": "medium",
                    "message": f"Missing page anchors for pages: {sorted(missing_pages)[:5]}"
                })
        else:
            self.validation_results['page_count'] = 0
            
            if self.require_page_anchors:
                self.issues_found.append({
                    "type": "no_page_anchors",
                    "severity": "high",
                    "message": "No page anchors found in converted document"
                })
        
        # Check minimum pages
        if self.validation_results['page_count'] < self.min_pages:
            self.issues_found.append({
                "type": "too_few_pages",
                "severity": "medium",
                "message": f"Only {self.validation_results['page_count']} pages found (expected >= {self.min_pages})"
            })
    
    def _analyze_image_placeholders(self, text: str):
        """Analyze image placeholder ratio (indicates OCR issues)."""
        # Count image placeholders
        image_placeholders = len(re.findall(r'<!--\s*image\s*-->', text, re.IGNORECASE))
        self.validation_results['image_placeholder_count'] = image_placeholders
        
        # Calculate ratio
        lines = text.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        
        if non_empty_lines:
            image_ratio = image_placeholders / len(non_empty_lines)
            self.validation_results['image_ratio'] = image_ratio
            
            if image_ratio > self.max_image_ratio:
                self.issues_found.append({
                    "type": "too_many_images",
                    "severity": "high",
                    "message": f"High image placeholder ratio ({image_ratio:.1%}) - possible OCR failure"
                })
    
    def _analyze_tables(self, text: str):
        """Check for table extraction."""
        # Simple heuristic: look for pipe-separated content
        table_lines = len(re.findall(r'\|.*\|.*\|', text))
        self.validation_results['table_count'] = table_lines
        
        # Check if tables might be broken
        broken_table_indicators = [
            r'\|\s*\|',  # Empty cells
            r'\|{3,}',   # Multiple consecutive pipes
            r'^\s*\|+\s*$'  # Lines with only pipes
        ]
        
        broken_tables = 0
        for pattern in broken_table_indicators:
            broken_tables += len(re.findall(pattern, text, re.MULTILINE))
        
        if broken_tables > table_lines * 0.3 and table_lines > 0:
            self.issues_found.append({
                "type": "broken_tables",
                "severity": "low",
                "message": "Tables may not be properly extracted"
            })
    
    def _detect_garbled_text(self, text: str):
        """Detect encoding issues and garbled text."""
        # Check for common encoding issues
        garbled_indicators = [
            r'[^\x00-\x7F]{5,}',  # Long sequences of non-ASCII
            r'â€™|â€"|â€œ',  # Common UTF-8 decode errors
            r'Ã¢|Ã©|Ã¨',  # Latin-1 issues
            r'\\x[0-9a-f]{2}',  # Hex escapes
            r'[?]{3,}',  # Multiple question marks
        ]
        
        garbled_count = 0
        for pattern in garbled_indicators:
            matches = re.findall(pattern, text)
            garbled_count += len(matches)
        
        # Check percentage of special characters
        special_chars = len(re.findall(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]]', text))
        special_ratio = special_chars / len(text) if text else 0
        
        if garbled_count > 10 or special_ratio > 0.1:
            self.validation_results['garbled_text_detected'] = True
            self.issues_found.append({
                "type": "garbled_text",
                "severity": "high",
                "message": "Potential encoding issues detected"
            })
    
    def _analyze_structure(self, text: str):
        """Analyze document structure preservation."""
        # Check for headers/sections
        headers = len(re.findall(r'^#+\s+.+', text, re.MULTILINE))
        sections = len(re.findall(r'^\d+\.\s+.+', text, re.MULTILINE))
        
        # Check for paragraphs
        paragraphs = len(re.split(r'\n\n+', text))
        
        # Determine structure quality
        if headers > 3 or sections > 3:
            self.validation_results['structure_quality'] = 'good'
        elif paragraphs > 10:
            self.validation_results['structure_quality'] = 'fair'
        else:
            self.validation_results['structure_quality'] = 'poor'
            self.issues_found.append({
                "type": "poor_structure",
                "severity": "low",
                "message": "Document structure not well preserved"
            })
        
        self.validation_results['conversion_metrics'] = {
            'headers': headers,
            'sections': sections,
            'paragraphs': paragraphs
        }
    
    def _check_conversion_metadata(self, state: ContractAnalysisState):
        """Check conversion metadata for issues."""
        metadata = state.get('conversion_metadata', {})
        
        if metadata:
            # Check for conversion errors
            if metadata.get('errors'):
                self.issues_found.append({
                    "type": "conversion_errors",
                    "severity": "medium",
                    "message": f"Conversion reported errors: {metadata['errors'][:100]}"
                })
            
            # Check conversion method
            if metadata.get('method') == 'fallback':
                self.issues_found.append({
                    "type": "fallback_method",
                    "severity": "low",
                    "message": "Used fallback conversion method"
                })
    
    def _determine_severity(self):
        """Determine overall severity."""
        if not self.issues_found:
            self.validation_results['severity'] = 'none'
            return
        
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for issue in self.issues_found:
            severity_counts[issue['severity']] += 1
        
        # Determine overall severity
        if severity_counts['critical'] > 0:
            self.validation_results['severity'] = 'critical'
            self.validation_results['validation_passed'] = False
        elif severity_counts['high'] > 1:
            self.validation_results['severity'] = 'high'
            self.validation_results['validation_passed'] = False
        elif severity_counts['high'] > 0:
            self.validation_results['severity'] = 'medium'
            self.validation_results['validation_passed'] = False
        elif severity_counts['medium'] > 2:
            self.validation_results['severity'] = 'medium'
            self.validation_results['validation_passed'] = False
        else:
            self.validation_results['severity'] = 'low'
        
        self.validation_results['issues'] = self.issues_found
    
    def _generate_recommendations(self):
        """Generate recommendations for improving conversion."""
        recommendations = []
        
        # Page anchor recommendations
        if not self.validation_results['has_page_anchors']:
            recommendations.append({
                "type": "enable_page_detection",
                "priority": "high",
                "message": "Enable page anchor extraction",
                "action": "Use enhanced page detection in PDF converter"
            })
        
        # OCR recommendations
        if self.validation_results['image_ratio'] > self.max_image_ratio:
            recommendations.append({
                "type": "enable_ocr",
                "priority": "critical",
                "message": "Too many image placeholders - enable OCR",
                "action": "Set enable_ocr=True in PDF converter"
            })
        
        # Text quality recommendations
        if self.validation_results['text_length'] < self.min_text_length:
            recommendations.append({
                "type": "alternative_converter",
                "priority": "high",
                "message": "Insufficient text extracted",
                "action": "Try alternative PDF conversion method"
            })
        
        # Encoding recommendations
        if self.validation_results['garbled_text_detected']:
            recommendations.append({
                "type": "fix_encoding",
                "priority": "high",
                "message": "Fix text encoding issues",
                "action": "Check PDF encoding and use appropriate decoder"
            })
        
        # Structure recommendations
        if self.validation_results['structure_quality'] == 'poor':
            recommendations.append({
                "type": "preserve_structure",
                "priority": "medium",
                "message": "Better preserve document structure",
                "action": "Use structure-aware conversion settings"
            })
        
        self.validation_results['recommendations'] = recommendations


@handle_node_errors("pdf_conversion_critic")
def pdf_conversion_critic_node(state: ContractAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node for PDF conversion quality validation.
    
    Returns updated state with:
    - pdf_validation_results: Detailed validation results
    - needs_pdf_rerun: Boolean indicating if reconversion is needed
    - pdf_critic_attempts: Number of attempts so far
    - pdf_retry_config: Configuration adjustments for retry
    """
    print("\n--- PDF CONVERSION QUALITY CRITIC ---")
    
    # Get configuration
    min_text_length = int(os.getenv('PDF_MIN_TEXT_LENGTH', '1000'))
    max_image_ratio = float(os.getenv('PDF_MAX_IMAGE_RATIO', '0.5'))
    require_anchors = os.getenv('PDF_REQUIRE_ANCHORS', 'true').lower() == 'true'
    max_reruns = int(os.getenv('PDF_MAX_RERUNS', '2'))
    
    # Track attempts
    attempts = state.get('pdf_critic_attempts', 0) + 1
    
    print(f"  Running PDF conversion critic (attempt {attempts})")
    print("  Configuration:")
    print(f"    - Min text length: {min_text_length}")
    print(f"    - Max image ratio: {max_image_ratio:.1%}")
    print(f"    - Require page anchors: {require_anchors}")
    
    # Create and run critic
    critic = PDFConversionCritic(
        min_text_length=min_text_length,
        max_image_ratio=max_image_ratio,
        require_page_anchors=require_anchors
    )
    
    validation_results = critic.validate_conversion(state)
    
    # Print summary
    print("\n  Validation Results:")
    print(f"    - Text length: {validation_results['text_length']} chars")
    print(f"    - Page count: {validation_results['page_count']}")
    print(f"    - Has page anchors: {validation_results['has_page_anchors']}")
    print(f"    - Image ratio: {validation_results['image_ratio']:.1%}")
    print(f"    - Structure quality: {validation_results['structure_quality']}")
    print(f"    - Severity: {validation_results['severity']}")
    print(f"    - Validation passed: {validation_results['validation_passed']}")
    
    # Determine if rerun is needed
    needs_rerun = (
        not validation_results['validation_passed'] and
        attempts < max_reruns and
        validation_results['severity'] in ['high', 'critical']
    )
    
    # Prepare retry configuration
    retry_config = {}
    if needs_rerun:
        print("\n  ⚠️ PDF conversion issues - preparing retry configuration")
        
        if validation_results['image_ratio'] > max_image_ratio:
            retry_config['enable_ocr'] = True
            print("    - Enabling OCR for image-heavy PDF")
        
        if not validation_results['has_page_anchors']:
            retry_config['extract_page_anchors'] = True
            print("    - Enabling page anchor extraction")
        
        if validation_results['garbled_text_detected']:
            retry_config['fix_encoding'] = True
            print("    - Attempting to fix encoding issues")
        
        if attempts == 1:
            retry_config['conversion_method'] = 'docling'
        else:
            retry_config['conversion_method'] = 'fallback'
        print(f"    - Using {retry_config['conversion_method']} conversion method")
        
        state['pdf_retry_config'] = retry_config
    else:
        if validation_results['validation_passed']:
            print("\n  ✅ PDF conversion validation PASSED")
        else:
            print("\n  ❌ PDF conversion validation FAILED but max reruns reached")
    
    return {
        'pdf_validation_results': validation_results,
        'needs_pdf_rerun': needs_rerun,
        'pdf_critic_attempts': attempts,
        'pdf_retry_config': retry_config
    }


def should_rerun_pdf_conversion(state: ContractAnalysisState) -> str:
    """
    Conditional edge function to determine if PDF should be reconverted.
    
    Returns:
        "retry_conversion" if reconversion is needed
        "continue" if validation passed or max attempts reached
    """
    needs_rerun = state.get('needs_pdf_rerun', False)
    
    if needs_rerun:
        # Apply retry configuration
        retry_config = state.get('pdf_retry_config', {})
        print(f"\n  Applying PDF retry configuration: {retry_config}")
        
        # These would be used by the PDF converter on retry
        for key, value in retry_config.items():
            state[f'pdf_{key}'] = value
        
        return "retry_conversion"
    
    return "continue"