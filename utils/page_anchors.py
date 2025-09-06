"""
Page Anchor Infrastructure
Manages page references and anchors throughout the document pipeline
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class PageAnchor:
    """Represents a page anchor reference"""
    page: int
    text: str
    start_pos: int
    end_pos: int
    
    def format(self) -> str:
        """Format as [[page=N]]"""
        return f"[[page={self.page}]]"


class PageAnchorManager:
    """Manages page anchors in documents"""
    
    # Regex patterns for page anchors
    ANCHOR_PATTERN = re.compile(r'\[\[page=(\d+)\]\]')
    PAGE_MARKER_PATTERN = re.compile(r'(?:^|\n)(?:Page|PAGE|page)\s*(\d+)(?:\s|:|$)')
    
    def __init__(self):
        """Initialize page anchor manager"""
        self.page_map: Dict[int, List[str]] = {}
        self.current_page = 1
    
    def add_page_anchors_to_markdown(
        self,
        markdown_content: str,
        page_info: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Add page anchors to markdown content
        
        Args:
            markdown_content: Original markdown content
            page_info: Optional page information from PDF converter
            
        Returns:
            Markdown with page anchors
        """
        if not page_info:
            # Try to detect page breaks in content
            page_info = self._detect_page_breaks(markdown_content)
        
        # If we have page info, add anchors
        if page_info:
            lines = markdown_content.split('\n')
            result_lines = []
            current_page = 1
            line_idx = 0
            
            for page in page_info:
                page_num = page.get('page', current_page)
                start_line = page.get('start_line', line_idx)
                end_line = page.get('end_line', len(lines))
                
                # Add page anchor at start of page
                if start_line < len(lines):
                    anchor = f"[[page={page_num}]]"
                    result_lines.append(anchor)
                
                # Add lines for this page
                for i in range(start_line, min(end_line, len(lines))):
                    result_lines.append(lines[i])
                
                line_idx = end_line
                current_page = page_num + 1
            
            # Add any remaining lines
            if line_idx < len(lines):
                result_lines.extend(lines[line_idx:])
            
            return '\n'.join(result_lines)
        
        else:
            # No page info, add anchors based on heuristics
            return self._add_heuristic_anchors(markdown_content)
    
    def _detect_page_breaks(self, content: str) -> List[Dict[str, Any]]:
        """
        Detect page breaks in content
        
        Args:
            content: Document content
            
        Returns:
            List of page information
        """
        pages = []
        lines = content.split('\n')
        
        # Look for explicit page markers
        for i, line in enumerate(lines):
            match = self.PAGE_MARKER_PATTERN.search(line)
            if match:
                page_num = int(match.group(1))
                pages.append({
                    'page': page_num,
                    'start_line': i
                })
        
        # Add end lines
        for i in range(len(pages) - 1):
            pages[i]['end_line'] = pages[i + 1]['start_line']
        
        if pages:
            pages[-1]['end_line'] = len(lines)
        
        return pages
    
    def _add_heuristic_anchors(self, content: str) -> str:
        """
        Add page anchors using heuristics
        
        Args:
            content: Document content
            
        Returns:
            Content with page anchors
        """
        # Simple heuristic: add page anchor every ~50 lines
        lines = content.split('\n')
        result_lines = []
        page = 1
        
        for i, line in enumerate(lines):
            if i % 50 == 0 and i > 0:
                result_lines.append(f"[[page={page}]]")
                page += 1
            result_lines.append(line)
        
        # Add initial page anchor if not present
        if result_lines and not result_lines[0].startswith('[[page='):
            result_lines.insert(0, '[[page=1]]')
        
        return '\n'.join(result_lines)
    
    def extract_anchors(self, text: str) -> List[PageAnchor]:
        """
        Extract page anchors from text
        
        Args:
            text: Text containing page anchors
            
        Returns:
            List of PageAnchor objects
        """
        anchors = []
        
        for match in self.ANCHOR_PATTERN.finditer(text):
            page_num = int(match.group(1))
            start_pos = match.start()
            end_pos = match.end()
            
            # Extract surrounding text for context
            context_start = max(0, start_pos - 50)
            context_end = min(len(text), end_pos + 50)
            context_text = text[context_start:context_end]
            
            anchors.append(PageAnchor(
                page=page_num,
                text=context_text,
                start_pos=start_pos,
                end_pos=end_pos
            ))
        
        return anchors
    
    def get_page_for_position(self, text: str, position: int) -> Optional[int]:
        """
        Get page number for a text position
        
        Args:
            text: Text with page anchors
            position: Character position in text
            
        Returns:
            Page number or None
        """
        current_page = 1
        
        for match in self.ANCHOR_PATTERN.finditer(text):
            if match.start() > position:
                return current_page
            current_page = int(match.group(1))
        
        return current_page
    
    def add_anchor_to_citation(self, citation: str, page: int) -> str:
        """
        Add page anchor to a citation
        
        Args:
            citation: Citation text
            page: Page number
            
        Returns:
            Citation with page anchor
        """
        # Check if anchor already exists
        if self.ANCHOR_PATTERN.search(citation):
            return citation
        
        # Add anchor at end
        return f'{citation} [[page={page}]]'
    
    def validate_anchors(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate page anchors in text
        
        Args:
            text: Text to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        anchors = self.extract_anchors(text)
        
        if not anchors:
            errors.append("No page anchors found in text")
        
        # Check for duplicate or out-of-order pages
        seen_pages = set()
        last_page = 0
        
        for anchor in anchors:
            if anchor.page in seen_pages:
                errors.append(f"Duplicate page anchor: [[page={anchor.page}]]")
            
            if anchor.page < last_page:
                errors.append(f"Out-of-order page anchor: [[page={anchor.page}]] after [[page={last_page}]]")
            
            seen_pages.add(anchor.page)
            last_page = max(last_page, anchor.page)
        
        return len(errors) == 0, errors
    
    def strip_anchors(self, text: str) -> str:
        """
        Remove all page anchors from text
        
        Args:
            text: Text with anchors
            
        Returns:
            Text without anchors
        """
        return self.ANCHOR_PATTERN.sub('', text).strip()
    
    def map_sentences_to_pages(
        self,
        sentences: List[str],
        document_text: str
    ) -> Dict[int, int]:
        """
        Map sentence indices to page numbers
        
        Args:
            sentences: List of sentences
            document_text: Full document text with anchors
            
        Returns:
            Dictionary mapping sentence index to page number
        """
        sentence_pages = {}
        
        for i, sentence in enumerate(sentences):
            # Find sentence position in document
            pos = document_text.find(sentence)
            if pos >= 0:
                page = self.get_page_for_position(document_text, pos)
                sentence_pages[i] = page or 1
            else:
                # Default to page 1 if not found
                sentence_pages[i] = 1
        
        return sentence_pages
    
    def format_citation_with_anchor(
        self,
        text: str,
        page: int,
        start_char: Optional[int] = None,
        end_char: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Format a citation with page anchor
        
        Args:
            text: Citation text
            page: Page number
            start_char: Optional start character position
            end_char: Optional end character position
            
        Returns:
            Formatted citation dictionary
        """
        return {
            "text": text,
            "page": page,
            "anchor": f"[[page={page}]]",
            "formatted": f'"{text}" [[page={page}]]',
            "location": {
                "start": start_char,
                "end": end_char
            } if start_char is not None else None
        }


# Global instance
page_anchor_manager = PageAnchorManager()


# Convenience functions
def add_page_anchors(content: str, page_info: Optional[List[Dict]] = None) -> str:
    """Add page anchors to content"""
    return page_anchor_manager.add_page_anchors_to_markdown(content, page_info)


def extract_page_anchors(text: str) -> List[PageAnchor]:
    """Extract page anchors from text"""
    return page_anchor_manager.extract_anchors(text)


def get_page_for_text(text: str, position: int) -> Optional[int]:
    """Get page number for text position"""
    return page_anchor_manager.get_page_for_position(text, position)


def validate_page_anchors(text: str) -> Tuple[bool, List[str]]:
    """Validate page anchors in text"""
    return page_anchor_manager.validate_anchors(text)


def extract_page_map(text: str) -> Dict[int, int]:
    """
    Extract a mapping from character position to page number.
    
    Args:
        text: Document text with [[page=N]] anchors
        
    Returns:
        Dictionary mapping character position to page number
    """
    page_map = {}
    current_page = 1
    
    # Find all page anchors
    for match in page_anchor_manager.ANCHOR_PATTERN.finditer(text):
        page_num = int(match.group(1))
        position = match.start()
        
        # Update all positions from last anchor to this one
        if not page_map:
            # First anchor - everything before is page 1
            for i in range(position):
                page_map[i] = 1
        
        # This position and forward get the new page number
        current_page = page_num
        page_map[position] = current_page
    
    # Fill in remaining positions with last page
    text_length = len(text)
    for i in range(len(page_map), text_length):
        page_map[i] = current_page
    
    return page_map