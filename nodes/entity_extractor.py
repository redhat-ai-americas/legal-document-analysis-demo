import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import dateutil.parser

class EntityExtractor:
    """
    Deterministic extraction of dates, company names, and entities from contract text.
    Reduces LLM calls by using regex patterns and NLP techniques.
    """
    
    def __init__(self):
        # Common date patterns
        self.date_patterns = [
            # YYYY-MM-DD format
            r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
            # MM/DD/YYYY or MM-DD-YYYY format
            r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',
            # Month DD, YYYY format
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            # Mon DD, YYYY format (abbreviated)
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b',
            # DD Month YYYY format
            r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',
            # DD Mon YYYY format (abbreviated)
            r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b'
        ]
        
        # Legal entity suffixes for company identification
        self.company_suffixes = [
            r'\b\w+\s+(Inc\.?|Corporation|Corp\.?|LLC|L\.L\.C\.?|Limited|Ltd\.?|LLP|L\.L\.P\.?|LP|L\.P\.?)\b',
            r'\b\w+\s+(Company|Co\.?|Group|Enterprises|Holdings|Partners)\b',
            r'\b\w+\s+(Technologies|Tech|Systems|Solutions|Services)\b'
        ]
        
        # Contract start indicators
        self.contract_start_indicators = [
            r'entered into on\s+([^,]+)',
            r'effective\s+(?:as of\s+)?([^,\n]+)',
            r'commence(?:s|d)?\s+on\s+([^,\n]+)',
            r'agreement\s+shall\s+commence\s+on\s+([^,\n]+)',
            r'term\s+(?:shall\s+)?(?:begin|start|commence)(?:s)?\s+on\s+([^,\n]+)',
            r'this\s+agreement\s+is\s+entered\s+into\s+on\s+([^,\n]+)'
        ]
        
        # Party identification patterns
        self.party_patterns = [
            r'between\s+([^("]+)(?:\s*\([^)]*\))?\s+(?:and|&)',
            r'Agreement.*between\s+([^("]+)(?:\s*\([^)]*\))?\s+(?:and|&)',
            r'entered into.*between\s+([^("]+)(?:\s*\([^)]*\))?\s+(?:and|&)',
            r'"([^"]*)",?\s*(?:a\s+[^,]*)?(?:,\s*)?(?:and|&)',
        ]

    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract dates from contract text with confidence scoring.
        Returns list of found dates with metadata.
        """
        found_dates = []
        
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                
                try:
                    # Parse date using dateutil for flexible parsing
                    parsed_date = dateutil.parser.parse(date_str, fuzzy=True)
                    standardized_date = parsed_date.strftime('%Y-%m-%d')
                    
                    # Calculate confidence based on pattern type and context
                    confidence = self._calculate_date_confidence(match, text, pattern)
                    
                    found_dates.append({
                        'raw_text': date_str,
                        'standardized_date': standardized_date,
                        'confidence': confidence,
                        'start_pos': match.start(),
                        'end_pos': match.end(),
                        'context': text[max(0, match.start()-50):match.end()+50],
                        'pattern_used': pattern
                    })
                    
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue
        
        # Sort by confidence and remove duplicates
        found_dates.sort(key=lambda x: x['confidence'], reverse=True)
        return self._deduplicate_dates(found_dates)

    def extract_contract_start_date(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract the contract start/effective date specifically.
        Uses context-aware patterns for higher accuracy.
        """
        for pattern in self.contract_start_indicators:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_candidate = match.group(1).strip()
                
                # Extract date from the candidate text
                dates = self.extract_dates(date_candidate)
                if dates:
                    best_date = dates[0]
                    best_date['extraction_method'] = 'context_aware_start_date'
                    best_date['confidence'] = min(best_date['confidence'] + 20, 100)  # Boost confidence
                    return best_date
        
        # Fallback: find dates near "term" or "agreement" keywords
        return self._find_dates_near_keywords(text, ['term', 'agreement', 'effective'])

    def extract_company_names(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract company names using legal entity patterns.
        """
        companies = []
        
        for pattern in self.company_suffixes:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                company_name = match.group(0).strip()
                
                # Clean up common artifacts
                company_name = self._clean_company_name(company_name)
                
                if len(company_name) > 3:  # Minimum length check
                    companies.append({
                        'name': company_name,
                        'confidence': self._calculate_company_confidence(match, text),
                        'start_pos': match.start(),
                        'end_pos': match.end(),
                        'context': text[max(0, match.start()-30):match.end()+30],
                        'extraction_method': 'legal_suffix_pattern'
                    })
        
        # Sort by confidence and deduplicate
        companies.sort(key=lambda x: x['confidence'], reverse=True)
        return self._deduplicate_companies(companies)

    def extract_contracting_parties(self, text: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Extract the two main contracting parties from agreement text.
        Returns (party1, party2) or (None, None) if not found.
        """
        for pattern in self.party_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Look for the full context around "between X and Y"
                context_start = max(0, match.start() - 100)
                context_end = min(len(text), match.end() + 200)
                context = text[context_start:context_end]
                
                # Find "between X and Y" pattern in context
                between_pattern = r'between\s+([^("]+?)(?:\s*\([^)]*\))?\s+(?:and|&)\s+([^("]+?)(?:\s*\([^)]*\))?(?:\s|\.|\n)'
                between_match = re.search(between_pattern, context, re.IGNORECASE | re.DOTALL)
                
                if between_match:
                    party1_raw = between_match.group(1).strip()
                    party2_raw = between_match.group(2).strip()
                    
                    party1 = {
                        'name': self._clean_party_name(party1_raw),
                        'raw_name': party1_raw,
                        'confidence': 85,
                        'extraction_method': 'between_and_pattern'
                    }
                    
                    party2 = {
                        'name': self._clean_party_name(party2_raw),
                        'raw_name': party2_raw,
                        'confidence': 85,
                        'extraction_method': 'between_and_pattern'
                    }
                    
                    return party1, party2
        
        return None, None

    def _calculate_date_confidence(self, match, text: str, pattern: str) -> int:
        """Calculate confidence score for date extraction (0-100)."""
        confidence = 50  # Base confidence
        
        # Boost confidence for certain contexts
        context = text[max(0, match.start()-50):match.end()+50].lower()
        
        if any(keyword in context for keyword in ['entered into', 'effective', 'commence', 'term']):
            confidence += 30
        if any(keyword in context for keyword in ['agreement', 'contract']):
            confidence += 15
        if re.search(r'\d{4}', match.group(0)):  # Has 4-digit year
            confidence += 10
        
        return min(confidence, 100)

    def _calculate_company_confidence(self, match, text: str) -> int:
        """Calculate confidence score for company name extraction."""
        confidence = 60  # Base confidence
        
        context = text[max(0, match.start()-30):match.end()+30].lower()
        
        if any(keyword in context for keyword in ['between', 'party', 'client', 'customer', 'provider']):
            confidence += 20
        if 'inc' in match.group(0).lower() or 'corp' in match.group(0).lower():
            confidence += 15
        
        return min(confidence, 100)

    def _find_dates_near_keywords(self, text: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Find dates near specific keywords."""
        for keyword in keywords:
            pattern = rf'\b{keyword}\b.{{0,100}}'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                section = match.group(0)
                dates = self.extract_dates(section)
                if dates:
                    best_date = dates[0]
                    best_date['extraction_method'] = f'keyword_proximity_{keyword}'
                    return best_date
        
        return None

    def _clean_company_name(self, name: str) -> str:
        """Clean up extracted company name."""
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name.strip())
        
        # Remove common prefixes that might be captured
        name = re.sub(r'^(the|a|an)\s+', '', name, flags=re.IGNORECASE)
        
        return name

    def _clean_party_name(self, name: str) -> str:
        """Clean up extracted party name."""
        # Remove quotes and extra whitespace
        name = re.sub(r'["""\']', '', name)
        name = re.sub(r'\s+', ' ', name.strip())
        
        # Remove trailing punctuation
        name = re.sub(r'[,\.\s]+$', '', name)
        
        return name

    def _deduplicate_dates(self, dates: List[Dict]) -> List[Dict]:
        """Remove duplicate dates, keeping highest confidence."""
        seen_dates = {}
        for date_info in dates:
            date_key = date_info['standardized_date']
            if date_key not in seen_dates or date_info['confidence'] > seen_dates[date_key]['confidence']:
                seen_dates[date_key] = date_info
        
        return list(seen_dates.values())

    def _deduplicate_companies(self, companies: List[Dict]) -> List[Dict]:
        """Remove duplicate company names, keeping highest confidence."""
        seen_companies = {}
        for company in companies:
            name_key = company['name'].lower()
            if name_key not in seen_companies or company['confidence'] > seen_companies[name_key]['confidence']:
                seen_companies[name_key] = company
        
        return list(seen_companies.values())


def extract_entities_from_document(state) -> Dict[str, Any]:
    """
    Main node function to extract entities from document text.
    Updates state with extracted dates, company names, and parties.
    """
    print("--- EXTRACTING ENTITIES ---")
    
    document_text = state.get('document_text', '')
    if not document_text:
        print("  No document text available for entity extraction")
        return {'extracted_entities': {}}
    
    extractor = EntityExtractor()
    
    # Extract contract start date
    print("  Extracting contract start date...")
    start_date = extractor.extract_contract_start_date(document_text)
    
    # Extract all dates for reference
    print("  Extracting all dates...")
    all_dates = extractor.extract_dates(document_text)
    
    # Extract company names
    print("  Extracting company names...")
    companies = extractor.extract_company_names(document_text)
    
    # Extract contracting parties
    print("  Extracting contracting parties...")
    party1, party2 = extractor.extract_contracting_parties(document_text)
    
    extracted_entities = {
        'contract_start_date': start_date,
        'all_dates': all_dates[:5],  # Limit to top 5 dates
        'companies': companies[:10],  # Limit to top 10 companies
        'party1': party1,
        'party2': party2,
        'extraction_timestamp': datetime.now().isoformat()
    }
    
    # Print summary
    print(f"  Contract start date: {start_date['standardized_date'] if start_date else 'Not found'}")
    print(f"  Total dates found: {len(all_dates)}")
    print(f"  Companies found: {len(companies)}")
    print(f"  Party 1: {party1['name'] if party1 else 'Not found'}")
    print(f"  Party 2: {party2['name'] if party2 else 'Not found'}")
    
    return {'extracted_entities': extracted_entities}