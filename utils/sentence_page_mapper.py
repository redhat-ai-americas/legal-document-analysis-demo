"""
Sentence to Page Mapping Utility
Maps sentences to their page numbers based on document page anchors
"""

import re
from typing import List, Dict, Tuple, Any


class SentencePageMapper:
    """Maps sentences to page numbers based on document anchors."""
    
    ANCHOR_PATTERN = re.compile(r'\[\[page=(\d+)\]\]')
    
    def __init__(self):
        self.page_boundaries = []
        self.current_document = None
    
    def extract_page_boundaries(self, document_text: str) -> List[Tuple[int, int]]:
        """
        Extract page boundaries from document text.
        Returns list of (page_number, character_position) tuples.
        """
        boundaries = []
        
        # Find all page anchors
        for match in self.ANCHOR_PATTERN.finditer(document_text):
            page_num = int(match.group(1))
            position = match.start()
            boundaries.append((page_num, position))
        
        # If no anchors found, assume entire document is page 1
        if not boundaries:
            boundaries.append((1, 0))
        
        # Sort by position
        boundaries.sort(key=lambda x: x[1])
        
        self.page_boundaries = boundaries
        return boundaries
    
    def get_page_for_position(self, position: int) -> int:
        """
        Get page number for a character position in the document.
        """
        if not self.page_boundaries:
            return 1
        
        current_page = 1
        for page_num, page_pos in self.page_boundaries:
            if position >= page_pos:
                current_page = page_num
            else:
                break
        
        return current_page
    
    def map_sentences_to_pages(self, 
                               sentences: List[str], 
                               document_text: str) -> List[Dict[str, Any]]:
        """
        Map sentences to their page numbers.
        
        Args:
            sentences: List of sentence strings
            document_text: Full document text with page anchors
            
        Returns:
            List of dictionaries with sentence and page info
        """
        # Extract page boundaries
        self.extract_page_boundaries(document_text)
        
        # Clean document text (remove anchors for matching)
        clean_document = self.ANCHOR_PATTERN.sub('', document_text)
        
        # Map each sentence
        mapped_sentences = []
        
        for sentence in sentences:
            # Find sentence position in clean document
            position = clean_document.find(sentence)
            
            if position >= 0:
                # Map position to original document (accounting for removed anchors)
                original_position = self._map_to_original_position(position, document_text, clean_document)
                page_num = self.get_page_for_position(original_position)
            else:
                # If sentence not found, default to page 1
                page_num = 1
            
            mapped_sentences.append({
                'sentence': sentence,
                'page': page_num,
                'page_number': page_num  # For compatibility
            })
        
        return mapped_sentences
    
    def _map_to_original_position(self, clean_pos: int, 
                                  original_text: str, 
                                  clean_text: str) -> int:
        """
        Map a position in clean text to original text position.
        """
        # Count anchors before this position
        anchors_before = 0
        offset = 0
        
        for match in self.ANCHOR_PATTERN.finditer(original_text):
            anchor_start = match.start() - offset
            if anchor_start <= clean_pos:
                offset += len(match.group(0))
                anchors_before += 1
            else:
                break
        
        return clean_pos + offset
    
    def enhance_sentences_with_pages(self,
                                    sentences: List[Any],
                                    document_text: str) -> List[Dict[str, Any]]:
        """
        Enhance sentence objects with page information.
        
        Args:
            sentences: List of sentence strings or dicts
            document_text: Full document text with page anchors
            
        Returns:
            List of sentence dictionaries with page info
        """
        enhanced = []
        
        # Extract page boundaries
        self.extract_page_boundaries(document_text)
        
        # Clean document text
        clean_document = self.ANCHOR_PATTERN.sub('', document_text)
        
        for item in sentences:
            # Handle both string and dict sentences
            if isinstance(item, str):
                sentence_text = item
                sentence_dict = {'sentence': sentence_text}
            else:
                sentence_text = item.get('sentence', str(item))
                sentence_dict = dict(item)  # Copy existing dict
            
            # Find sentence position
            position = clean_document.find(sentence_text)
            
            if position >= 0:
                original_position = self._map_to_original_position(position, document_text, clean_document)
                page_num = self.get_page_for_position(original_position)
            else:
                page_num = sentence_dict.get('page', sentence_dict.get('page_number', 1))
            
            # Update page info
            sentence_dict['page'] = page_num
            sentence_dict['page_number'] = page_num
            
            enhanced.append(sentence_dict)
        
        return enhanced


# Global instance
sentence_page_mapper = SentencePageMapper()