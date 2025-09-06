"""
Citation tracking utility for linking extracted information back to source text.
Provides traceability and verification support for contract analysis results.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CitationType(Enum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    INFERENCE = "inference"
    NOT_FOUND = "not_found"


@dataclass
class Citation:
    """
    Represents a citation linking back to source text.
    """
    citation_id: str
    type: CitationType
    source_text: str
    location: str
    sentence_id: Optional[str] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    confidence: float = 0.0
    word_start: Optional[int] = None
    word_end: Optional[int] = None


class CitationTracker:
    """
    Tracks citations and provides linking between extracted information and source text.
    """
    
    def __init__(self):
        self.citations = {}
        self.sentence_registry = {}
        self.next_citation_id = 1
    
    def register_sentence(self, sentence: str, sentence_index: int, 
                         page_number: Optional[int] = None, 
                         section_name: Optional[str] = None) -> str:
        """
        Register a sentence in the citation system and return its ID.
        """
        sentence_id = f"sent_{sentence_index:04d}"
        self.sentence_registry[sentence_id] = {
            "text": sentence,
            "index": sentence_index,
            "page_number": page_number,
            "section_name": section_name,
            "citations": []
        }
        return sentence_id
    
    def create_citation(self, source_text: str, citation_type: CitationType,
                       sentence_id: Optional[str] = None,
                       page_number: Optional[int] = None,
                       section_name: Optional[str] = None,
                       confidence: float = 1.0) -> Citation:
        """
        Create a new citation entry.
        """
        citation_id = f"cite_{self.next_citation_id:04d}"
        self.next_citation_id += 1
        
        # Determine location string with page anchor format
        location_parts = []
        if section_name:
            location_parts.append(f"Section {section_name}")
        if page_number:
            # Use page anchor format for consistency
            location_parts.append(f"[[page={page_number}]]")
        elif sentence_id:
            # Only add sentence if no page number
            location_parts.append(f"sentence {sentence_id}")
        
        location = " ".join(location_parts) if location_parts else "Unknown location"
        
        citation = Citation(
            citation_id=citation_id,
            type=citation_type,
            source_text=source_text,
            location=location,
            sentence_id=sentence_id,
            page_number=page_number,
            section_name=section_name,
            confidence=confidence
        )
        
        self.citations[citation_id] = citation
        
        # Link to sentence if provided
        if sentence_id and sentence_id in self.sentence_registry:
            self.sentence_registry[sentence_id]["citations"].append(citation_id)
        
        return citation
    
    def find_text_match(self, target_text: str, search_text: str, 
                       fuzzy_threshold: float = 0.8) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """
        Find if target text appears in search text, with fuzzy matching support.
        Returns (found, confidence, (start_pos, end_pos)).
        """
        if not target_text or not search_text:
            return False, 0.0, None
            
        target_clean = self._clean_text_for_matching(target_text)
        search_clean = self._clean_text_for_matching(search_text)
        
        # Exact match first
        if target_clean in search_clean:
            start_pos = search_clean.find(target_clean)
            end_pos = start_pos + len(target_clean)
            return True, 1.0, (start_pos, end_pos)
        
        # Fuzzy matching for partial matches
        target_words = target_clean.split()
        search_words = search_clean.split()
        
        if len(target_words) < 3:  # Too short for reliable fuzzy matching
            return False, 0.0, None
        
        # Find best matching subsequence
        best_match_ratio = 0.0
        best_position = None
        
        for i in range(len(search_words) - len(target_words) + 1):
            window = search_words[i:i + len(target_words)]
            match_count = sum(1 for t, w in zip(target_words, window) if t == w)
            match_ratio = match_count / len(target_words)
            
            if match_ratio > best_match_ratio:
                best_match_ratio = match_ratio
                best_position = (i, i + len(target_words))
        
        if best_match_ratio >= fuzzy_threshold:
            return True, best_match_ratio, best_position
        
        return False, best_match_ratio, None
    
    def _clean_text_for_matching(self, text: str) -> str:
        """Clean text for more reliable matching."""
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\;\:\!\?]', '', text)
        return text.lower()
    
    def create_citation_from_match(self, question: str, answer: str, 
                                 source_sentences: List[Dict[str, Any]],
                                 min_confidence: float = 0.6) -> List[Citation]:
        """
        Create citations by finding the best source matches for an answer.
        Prioritizes citations with page anchors.
        """
        citations = []
        
        if not answer or answer in ["Not specified", "Not found", "DETERMINISTIC_FIELD"]:
            # For deterministic fields, don't create empty citations
            if answer == "DETERMINISTIC_FIELD":
                return []  # Return empty list for deterministic fields
            
            # For truly not found cases, create a not_found citation
            citation = self.create_citation(
                source_text="",
                citation_type=CitationType.NOT_FOUND,
                confidence=1.0
            )
            citations.append(citation)
            return citations
        
        # Sort source sentences to prioritize those with page numbers
        source_sentences_sorted = sorted(
            source_sentences,
            key=lambda s: (
                # First priority: has page number
                1 if (s.get("page") or s.get("page_number") or s.get("page_num")) else 0,
                # Second priority: has section
                1 if (s.get("section") or s.get("section_name")) else 0
            ),
            reverse=True
        )
        
        # Clean answer for matching
        answer_parts = self._extract_key_phrases(answer)
        
        for sentence_data in source_sentences_sorted:
            sentence_text = sentence_data.get("sentence", "")
            sentence_id = sentence_data.get("sentence_id")
            # Extract page information from various possible fields
            page_number = (sentence_data.get("page") or 
                          sentence_data.get("page_number") or 
                          sentence_data.get("page_num"))
            # Extract section name if available
            section_name = sentence_data.get("section") or sentence_data.get("section_name")
            
            for phrase in answer_parts:
                found, confidence, position = self.find_text_match(phrase, sentence_text)
                
                if found and confidence >= min_confidence:
                    # Determine citation type based on match quality
                    if confidence >= 0.95:
                        citation_type = CitationType.DIRECT_QUOTE
                    elif confidence >= 0.8:
                        citation_type = CitationType.PARAPHRASE
                    else:
                        citation_type = CitationType.INFERENCE
                    
                    citation = self.create_citation(
                        source_text=sentence_text,
                        citation_type=citation_type,
                        sentence_id=sentence_id,
                        page_number=page_number,
                        section_name=section_name,
                        confidence=confidence
                    )
                    
                    # Add word position if available
                    if position:
                        citation.word_start, citation.word_end = position
                    
                    citations.append(citation)
                    break  # One citation per sentence
        
        # If no citations found, create inference citation with best matching sentence
        if not citations and source_sentences_sorted:
            best_sentence = source_sentences_sorted[0]  # Use first sorted (has page priority)
            # Extract page and section info for fallback citation
            page_number = (best_sentence.get("page") or 
                          best_sentence.get("page_number") or 
                          best_sentence.get("page_num"))
            section_name = best_sentence.get("section") or best_sentence.get("section_name")
            
            citation = self.create_citation(
                source_text=best_sentence.get("sentence", ""),
                citation_type=CitationType.INFERENCE,
                sentence_id=best_sentence.get("sentence_id"),
                page_number=page_number,
                section_name=section_name,
                confidence=0.3
            )
            citations.append(citation)
        
        return citations
    
    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Extract key phrases from text for citation matching."""
        if not text:
            return []
        
        # Split into sentences first
        sentences = re.split(r'[.!?]+', text)
        phrases = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue
                
            # Extract noun phrases and meaningful segments
            words = sentence.split()
            if len(words) >= 3:
                # Take first few words and last few words as potential phrases
                if len(words) >= 6:
                    phrases.append(' '.join(words[:4]))  # First 4 words
                    phrases.append(' '.join(words[-4:]))  # Last 4 words
                else:
                    phrases.append(sentence)
        
        # Remove duplicates and return top phrases
        unique_phrases = list(dict.fromkeys(phrases))
        return unique_phrases[:max_phrases]
    
    def get_citation_summary(self, citation_ids: List[str]) -> Dict[str, Any]:
        """
        Generate a summary of citations for reporting.
        """
        if not citation_ids:
            return {
                "total_citations": 0,
                "citation_types": {},
                "confidence_stats": {},
                "sources": []
            }
        
        citations = [self.citations[cid] for cid in citation_ids if cid in self.citations]
        
        # Count by type
        type_counts = {}
        for citation in citations:
            type_name = citation.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Confidence statistics
        confidences = [c.confidence for c in citations if c.confidence > 0]
        confidence_stats = {}
        if confidences:
            confidence_stats = {
                "average": sum(confidences) / len(confidences),
                "min": min(confidences),
                "max": max(confidences),
                "count": len(confidences)
            }
        
        # Source summary
        sources = []
        for citation in citations:
            if citation.source_text:
                sources.append({
                    "citation_id": citation.citation_id,
                    "type": citation.type.value,
                    "text_preview": citation.source_text[:100] + "..." if len(citation.source_text) > 100 else citation.source_text,
                    "location": citation.location,
                    "confidence": citation.confidence
                })
        
        return {
            "total_citations": len(citations),
            "citation_types": type_counts,
            "confidence_stats": confidence_stats,
            "sources": sources
        }
    
    def format_citations_for_yaml(self, citation_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Format citations for inclusion in YAML output.
        Includes page anchors in [[page=N]] format when available.
        """
        formatted_citations = []
        
        for citation_id in citation_ids:
            if citation_id in self.citations:
                citation = self.citations[citation_id]
                citation_dict = {
                    "type": citation.type.value,
                    "source_text": citation.source_text,
                    "location": citation.location,
                    "confidence": round(citation.confidence, 2),
                    "citation_id": citation.citation_id
                }
                
                # Add page anchor if page number is available
                if citation.page_number:
                    citation_dict["page_anchor"] = f"[[page={citation.page_number}]]"
                
                formatted_citations.append(citation_dict)
        
        return formatted_citations


# Global instance for easy import
citation_tracker = CitationTracker()