"""
Citation Manager
Handles citation extraction, validation, and formatting with page anchors
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Represents a citation with page anchor"""
    text: str
    page: int
    start_char: int
    end_char: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def anchor(self) -> str:
        """Get page anchor format"""
        return f"[[page={self.page}]]"
    
    def format(self, max_length: int = 200) -> str:
        """Format citation for display"""
        text = self.text
        if len(text) > max_length:
            text = text[:max_length-3] + "..."
        return f'"{text}" {self.anchor}'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "quote": self.text,
            "page": self.page,
            "anchor": self.anchor,
            "location": {
                "start": self.start_char,
                "end": self.end_char
            },
            "confidence": self.confidence,
            "metadata": self.metadata
        }


@dataclass
class CitationValidation:
    """Result of citation validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    match_score: float = 0.0


class CitationManager:
    """Manages citations and page anchors"""
    
    def __init__(self):
        """Initialize citation manager"""
        self.page_anchor_pattern = re.compile(r'\[\[page=(\d+)\]\]')
        self.stats = {
            "citations_extracted": 0,
            "citations_validated": 0,
            "validation_failures": 0
        }
    
    def extract_citations(
        self,
        text: str,
        document_text: str,
        page_map: Optional[Dict[int, int]] = None,
        min_length: int = 20,
        max_length: int = 500
    ) -> List[Citation]:
        """
        Extract citations from text
        
        Args:
            text: Text containing potential citations
            document_text: Original document text
            page_map: Mapping of character position to page
            min_length: Minimum citation length
            max_length: Maximum citation length
            
        Returns:
            List of extracted citations
        """
        citations = []
        
        # Extract quoted text
        quote_pattern = re.compile(r'"([^"]+)"')
        
        for match in quote_pattern.finditer(text):
            quoted_text = match.group(1)
            
            # Check length constraints
            if len(quoted_text) < min_length or len(quoted_text) > max_length:
                continue
            
            # Find in document
            location = self._find_in_document(quoted_text, document_text)
            
            if location:
                start, end = location
                
                # Get page number
                if page_map and start in page_map:
                    page = page_map[start]
                else:
                    page = self._estimate_page(start, len(document_text))
                
                citation = Citation(
                    text=quoted_text,
                    page=page,
                    start_char=start,
                    end_char=end,
                    confidence=1.0
                )
                
                citations.append(citation)
                self.stats["citations_extracted"] += 1
        
        # Also look for text with page anchors already
        anchor_pattern = re.compile(r'([^"]+)\s*\[\[page=(\d+)\]\]')
        
        for match in anchor_pattern.finditer(text):
            citation_text = match.group(1).strip()
            page = int(match.group(2))
            
            if len(citation_text) < min_length or len(citation_text) > max_length:
                continue
            
            # Find in document
            location = self._find_in_document(citation_text, document_text)
            
            if location:
                start, end = location
                
                citation = Citation(
                    text=citation_text,
                    page=page,
                    start_char=start,
                    end_char=end,
                    confidence=0.9  # Slightly lower confidence for extracted anchors
                )
                
                citations.append(citation)
                self.stats["citations_extracted"] += 1
        
        return citations
    
    def create_citation(
        self,
        text: str,
        document_text: str,
        hint_position: Optional[int] = None,
        page_map: Optional[Dict[int, int]] = None
    ) -> Optional[Citation]:
        """
        Create a citation from text
        
        Args:
            text: Text to cite
            document_text: Original document
            hint_position: Hint for where to look
            page_map: Page mapping
            
        Returns:
            Citation or None if not found
        """
        # Find exact or fuzzy match
        location = self._find_in_document(text, document_text, hint_position)
        
        if not location:
            return None
        
        start, end = location
        
        # Get page
        if page_map and start in page_map:
            page = page_map[start]
        else:
            page = self._estimate_page(start, len(document_text))
        
        return Citation(
            text=text,
            page=page,
            start_char=start,
            end_char=end
        )
    
    def validate_citation(
        self,
        citation: Citation,
        document_text: str,
        page_map: Optional[Dict[int, int]] = None,
        require_exact: bool = True
    ) -> CitationValidation:
        """
        Validate a citation against document
        
        Args:
            citation: Citation to validate
            document_text: Original document
            page_map: Page mapping
            require_exact: Require exact match
            
        Returns:
            Validation result
        """
        validation = CitationValidation(is_valid=True)
        
        # Check if text exists in document
        location = self._find_in_document(
            citation.text,
            document_text,
            fuzzy=not require_exact
        )
        
        if not location:
            validation.is_valid = False
            validation.errors.append("Citation text not found in document")
            validation.match_score = 0.0
        else:
            start, end = location
            
            # Verify page number if we have page map
            if page_map and start in page_map:
                actual_page = page_map[start]
                if actual_page != citation.page:
                    validation.warnings.append(
                        f"Page mismatch: cited page {citation.page}, actual page {actual_page}"
                    )
            
            # Calculate match score
            if require_exact:
                actual_text = document_text[start:end]
                validation.match_score = self._calculate_similarity(
                    citation.text,
                    actual_text
                )
            else:
                validation.match_score = 0.8  # Fuzzy match
        
        # Validate page anchor format
        if not re.match(r'^\[\[page=\d+\]\]$', citation.anchor):
            validation.errors.append(f"Invalid anchor format: {citation.anchor}")
            validation.is_valid = False
        
        self.stats["citations_validated"] += 1
        if not validation.is_valid:
            self.stats["validation_failures"] += 1
        
        return validation
    
    def format_citations(
        self,
        citations: List[Citation],
        style: str = "markdown",
        group_by_page: bool = False
    ) -> str:
        """
        Format citations for output
        
        Args:
            citations: List of citations
            style: Output style (markdown, json, text)
            group_by_page: Group citations by page
            
        Returns:
            Formatted citations
        """
        if not citations:
            return ""
        
        if group_by_page:
            # Group by page number
            by_page = {}
            for citation in citations:
                if citation.page not in by_page:
                    by_page[citation.page] = []
                by_page[citation.page].append(citation)
            
            # Sort by page
            sorted_pages = sorted(by_page.keys())
        else:
            sorted_pages = None
        
        if style == "markdown":
            lines = []
            
            if group_by_page and sorted_pages:
                for page in sorted_pages:
                    lines.append(f"\n**Page {page}:**")
                    for citation in by_page[page]:
                        lines.append(f"- {citation.format()}")
            else:
                for citation in citations:
                    lines.append(f"- {citation.format()}")
            
            return "\n".join(lines)
        
        elif style == "json":
            import json
            citations_data = [c.to_dict() for c in citations]
            return json.dumps(citations_data, indent=2)
        
        else:  # text
            lines = []
            for i, citation in enumerate(citations, 1):
                lines.append(f"{i}. {citation.format()}")
            return "\n".join(lines)
    
    def extract_page_anchors(self, text: str) -> List[Tuple[str, int]]:
        """
        Extract page anchors from text
        
        Args:
            text: Text containing page anchors
            
        Returns:
            List of (text, page) tuples
        """
        results = []
        
        # Pattern for text with anchor
        pattern = re.compile(r'([^[]+)\s*\[\[page=(\d+)\]\]')
        
        for match in pattern.finditer(text):
            text_part = match.group(1).strip()
            page = int(match.group(2))
            results.append((text_part, page))
        
        return results
    
    def add_page_anchors(
        self,
        text: str,
        page_map: Dict[int, int],
        sentences: Optional[List[str]] = None
    ) -> str:
        """
        Add page anchors to text
        
        Args:
            text: Text to annotate
            page_map: Character position to page mapping
            sentences: Optional sentences list
            
        Returns:
            Text with page anchors added
        """
        if not page_map:
            return text
        
        # If we have sentences, add anchors to each
        if sentences:
            annotated = []
            current_pos = 0
            
            for sentence in sentences:
                # Find sentence in text
                sentence_pos = text.find(sentence, current_pos)
                if sentence_pos >= 0:
                    page = page_map.get(sentence_pos, 1)
                    annotated.append(f"{sentence} [[page={page}]]")
                    current_pos = sentence_pos + len(sentence)
                else:
                    annotated.append(sentence)
            
            return " ".join(annotated)
        
        else:
            # Add anchor at end with dominant page
            pages = list(page_map.values())
            if pages:
                most_common_page = max(set(pages), key=pages.count)
                return f"{text} [[page={most_common_page}]]"
            return text
    
    def _find_in_document(
        self,
        text: str,
        document: str,
        hint_position: Optional[int] = None,
        fuzzy: bool = False
    ) -> Optional[Tuple[int, int]]:
        """
        Find text in document
        
        Args:
            text: Text to find
            document: Document to search
            hint_position: Hint for search position
            fuzzy: Allow fuzzy matching
            
        Returns:
            (start, end) positions or None
        """
        # Try exact match first
        if hint_position is not None:
            # Search near hint
            search_start = max(0, hint_position - 1000)
            search_end = min(len(document), hint_position + 1000)
            search_text = document[search_start:search_end]
            
            pos = search_text.find(text)
            if pos >= 0:
                actual_start = search_start + pos
                return (actual_start, actual_start + len(text))
        
        # Search entire document
        pos = document.find(text)
        if pos >= 0:
            return (pos, pos + len(text))
        
        # Try case-insensitive
        pos = document.lower().find(text.lower())
        if pos >= 0:
            return (pos, pos + len(text))
        
        # Try fuzzy matching if allowed
        if fuzzy:
            return self._fuzzy_find(text, document)
        
        return None
    
    def _fuzzy_find(
        self,
        text: str,
        document: str,
        threshold: float = 0.8
    ) -> Optional[Tuple[int, int]]:
        """
        Fuzzy find text in document
        
        Args:
            text: Text to find
            document: Document to search
            threshold: Similarity threshold
            
        Returns:
            (start, end) positions or None
        """
        text_len = len(text)
        best_match = None
        best_score = 0
        
        # Slide window through document
        for i in range(len(document) - text_len + 1):
            window = document[i:i + text_len]
            score = self._calculate_similarity(text, window)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = (i, i + text_len)
        
        return best_match
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _estimate_page(self, position: int, doc_length: int) -> int:
        """Estimate page number from position"""
        # Assume ~3000 characters per page
        chars_per_page = 3000
        page = (position // chars_per_page) + 1
        return page
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get citation statistics"""
        total_validated = self.stats["citations_validated"]
        if total_validated == 0:
            return self.stats
        
        return {
            **self.stats,
            "validation_success_rate": 1 - (self.stats["validation_failures"] / total_validated)
        }


# Global citation manager instance
citation_manager = CitationManager()


def extract_citations(
    text: str,
    document_text: str,
    page_map: Optional[Dict[int, int]] = None
) -> List[Citation]:
    """
    Convenience function to extract citations
    
    Args:
        text: Text containing citations
        document_text: Original document
        page_map: Page mapping
        
    Returns:
        List of citations
    """
    return citation_manager.extract_citations(text, document_text, page_map)


def validate_citations(
    citations: List[Citation],
    document_text: str,
    page_map: Optional[Dict[int, int]] = None
) -> List[CitationValidation]:
    """
    Validate multiple citations
    
    Args:
        citations: Citations to validate
        document_text: Original document
        page_map: Page mapping
        
    Returns:
        List of validation results
    """
    results = []
    for citation in citations:
        validation = citation_manager.validate_citation(
            citation,
            document_text,
            page_map
        )
        results.append(validation)
    return results