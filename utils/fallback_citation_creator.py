"""
Fallback Citation Creator
Creates citations for questions when no classified sentences match
"""

from typing import List, Dict, Any, Optional
from utils.citation_tracker import citation_tracker, CitationType


class FallbackCitationCreator:
    """
    Creates fallback citations when no exact matches are found.
    """
    
    def __init__(self):
        self.keyword_patterns = {
            'limitation_of_liability': ['limitation', 'liability', 'damages', 'loss'],
            'indemnity': ['indemnif', 'defend', 'hold harmless'],
            'ip_rights': ['intellectual property', 'ownership', 'proprietary'],
            'assignment_coc': ['assignment', 'change of control', 'transfer'],
            'exclusivity_non_competes': ['exclusive', 'non-compete', 'competition'],
            'forced_pricing_adjustments': ['pricing', 'most favored', 'price adjustment'],
            'source_code_access': ['source code', 'escrow', 'code access'],
            'contract_start_date': ['effective date', 'commencement', 'start date', 'term'],
        }
    
    def find_relevant_sentences(
        self,
        question_id: str,
        all_sentences: List[Dict[str, Any]],
        max_sentences: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find relevant sentences using keyword search when classification fails.
        
        Args:
            question_id: Question identifier
            all_sentences: All classified sentences
            max_sentences: Maximum sentences to return
            
        Returns:
            List of relevant sentence dictionaries
        """
        keywords = self.keyword_patterns.get(question_id, [])
        if not keywords:
            return []
        
        relevant = []
        
        for sentence_data in all_sentences:
            sentence_text = sentence_data.get('sentence', '').lower()
            
            # Check if any keyword appears in sentence
            for keyword in keywords:
                if keyword.lower() in sentence_text:
                    # Prioritize sentences with page info
                    if sentence_data.get('page') or sentence_data.get('page_number'):
                        relevant.insert(0, sentence_data)  # Add to front
                    else:
                        relevant.append(sentence_data)  # Add to end
                    break
            
            if len(relevant) >= max_sentences:
                break
        
        return relevant[:max_sentences]
    
    def create_fallback_citation(
        self,
        question_id: str,
        question_text: str,
        all_sentences: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a fallback citation when no classified sentences match.
        
        Args:
            question_id: Question identifier
            question_text: Question prompt text
            all_sentences: All classified sentences
            
        Returns:
            Citation dictionary or None
        """
        # Find relevant sentences using keywords
        relevant = self.find_relevant_sentences(question_id, all_sentences)
        
        if not relevant:
            # No relevant sentences found at all
            return None
        
        # Use the most relevant sentence (first one, which has page priority)
        best_sentence = relevant[0]
        
        # Extract page and section info
        page_number = (best_sentence.get('page') or 
                      best_sentence.get('page_number') or 
                      best_sentence.get('page_num'))
        section_name = best_sentence.get('section') or best_sentence.get('section_name')
        
        # Create citation
        citation = citation_tracker.create_citation(
            source_text=best_sentence.get('sentence', ''),
            citation_type=CitationType.INFERENCE,
            sentence_id=best_sentence.get('sentence_id'),
            page_number=page_number,
            section_name=section_name,
            confidence=0.4  # Lower confidence for fallback
        )
        
        return {
            'citation': citation,
            'source_sentences': relevant,
            'method': 'fallback_keyword_search'
        }
    
    def enhance_citations_with_context(
        self,
        citations: List[Any],
        all_sentences: List[Dict[str, Any]],
        window_size: int = 2
    ) -> List[Any]:
        """
        Enhance existing citations by adding context from surrounding sentences.
        
        Args:
            citations: Existing citations
            all_sentences: All classified sentences
            window_size: Number of sentences before/after to consider
            
        Returns:
            Enhanced citations
        """
        if not citations or not all_sentences:
            return citations
        
        # Create sentence index for fast lookup
        sentence_index = {s.get('sentence_id'): i for i, s in enumerate(all_sentences)}
        
        enhanced = []
        for citation in citations:
            # If citation has a sentence_id, find surrounding context
            if hasattr(citation, 'sentence_id') and citation.sentence_id:
                idx = sentence_index.get(citation.sentence_id)
                if idx is not None:
                    # Get surrounding sentences
                    start_idx = max(0, idx - window_size)
                    end_idx = min(len(all_sentences), idx + window_size + 1)
                    
                    # Check if any surrounding sentence has better page info
                    for i in range(start_idx, end_idx):
                        neighbor = all_sentences[i]
                        neighbor_page = (neighbor.get('page') or 
                                       neighbor.get('page_number'))
                        
                        # If citation lacks page but neighbor has it, update
                        if not citation.page_number and neighbor_page:
                            citation.page_number = neighbor_page
                            # Update location with page anchor
                            if citation.section_name:
                                citation.location = f"Section {citation.section_name} [[page={neighbor_page}]]"
                            else:
                                citation.location = f"[[page={neighbor_page}]]"
                            break
            
            enhanced.append(citation)
        
        return enhanced


# Global instance
fallback_citation_creator = FallbackCitationCreator()