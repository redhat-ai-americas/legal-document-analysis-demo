"""
Document Metadata Extractor

Extracts key metadata from documents including:
- Document title (from filename, headers, or content)
- Document type (License Agreement, MSA, SOW, etc.)
- Key headers and sections
"""

import re
import os
from typing import Dict, List, Optional, Tuple


class DocumentMetadataExtractor:
    """Extract metadata from document text and filename."""
    
    # Common document type patterns
    DOCUMENT_TYPE_PATTERNS = {
        'software_license': [
            r'software\s+license\s+agreement',
            r'end\s+user\s+license\s+agreement',
            r'eula',
            r'software\s+licensing\s+terms'
        ],
        'master_agreement': [
            r'master\s+(?:service|services|subscription)\s+agreement',
            r'msa',
            r'master\s+agreement',
            r'framework\s+agreement'
        ],
        'statement_of_work': [
            r'statement\s+of\s+work',
            r'sow',
            r'work\s+order',
            r'project\s+scope'
        ],
        'saas_agreement': [
            r'saas\s+(?:service|services)?\s*agreement',
            r'software\s+as\s+a\s+service',
            r'cloud\s+services?\s+agreement',
            r'subscription\s+agreement'
        ],
        'purchase_order': [
            r'purchase\s+order',
            r'p\.?o\.?',
            r'order\s+form'
        ],
        'amendment': [
            r'amendment',
            r'addendum',
            r'modification\s+agreement',
            r'change\s+order'
        ],
        'nda': [
            r'non[\-\s]?disclosure\s+agreement',
            r'nda',
            r'confidentiality\s+agreement',
            r'mutual\s+non[\-\s]?disclosure'
        ],
        'service_agreement': [
            r'(?:professional\s+)?services?\s+agreement',
            r'consulting\s+(?:services?\s+)?agreement',
            r'maintenance\s+(?:and\s+support\s+)?agreement'
        ]
    }
    
    def __init__(self):
        self.metadata = {}
    
    def extract_from_filename(self, filepath: str) -> Dict[str, str]:
        """Extract metadata from filename."""
        filename = os.path.basename(filepath)
        base_name = os.path.splitext(filename)[0]
        
        metadata = {
            'filename': filename,
            'base_name': base_name
        }
        
        # Check filename for document type
        filename_lower = base_name.lower()
        for doc_type, patterns in self.DOCUMENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    metadata['filename_document_type'] = doc_type.replace('_', ' ').title()
                    break
            if 'filename_document_type' in metadata:
                break
        
        return metadata
    
    def extract_title_from_content(self, text: str) -> Optional[str]:
        """Extract document title from the first few lines of content."""
        lines = text.split('\n')[:20]  # Check first 20 lines
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and short lines
            if not line or len(line) < 10:
                continue
                
            # Check for title patterns (all caps, centered, or markdown headers)
            if line.startswith('#'):
                # Markdown header
                title = re.sub(r'^#+\s*', '', line)
                if self._is_likely_title(title):
                    return title
            elif line.isupper() and len(line) > 15:
                # All caps title
                return line.title()
            elif self._is_likely_title(line):
                return line
        
        return None
    
    def _is_likely_title(self, text: str) -> bool:
        """Check if text is likely a document title."""
        text_lower = text.lower()
        
        # Check for common title keywords
        title_keywords = [
            'agreement', 'contract', 'terms', 'license', 
            'statement of work', 'sow', 'amendment', 'order'
        ]
        
        for keyword in title_keywords:
            if keyword in text_lower:
                return True
        
        # Check for document type patterns
        for patterns in self.DOCUMENT_TYPE_PATTERNS.values():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return True
        
        return False
    
    def extract_document_type(self, text: str, filename: str = "") -> Tuple[str, float]:
        """
        Extract document type from text and filename.
        Returns (document_type, confidence)
        """
        text_lower = text[:5000].lower()  # Check first 5000 chars
        filename_lower = filename.lower()
        
        # Count matches for each document type
        type_scores = {}
        
        for doc_type, patterns in self.DOCUMENT_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                # Check in filename (higher weight)
                if re.search(pattern, filename_lower):
                    score += 3
                # Check in text
                matches = len(re.findall(pattern, text_lower))
                score += min(matches, 5)  # Cap at 5 to avoid over-weighting
            
            if score > 0:
                type_scores[doc_type] = score
        
        # Get the highest scoring type
        if type_scores:
            best_type = max(type_scores.items(), key=lambda x: x[1])
            # Calculate confidence based on score
            confidence = min(1.0, best_type[1] / 10.0)
            return best_type[0].replace('_', ' ').title(), confidence
        
        return "Unknown", 0.0
    
    def extract_headers(self, text: str, max_headers: int = 10) -> List[str]:
        """Extract section headers from document."""
        headers = []
        
        # Pattern for headers (numbered sections, markdown headers, all caps lines)
        header_patterns = [
            r'^#+\s+(.+)$',  # Markdown headers
            r'^(\d+\.?\d*\.?\s+[A-Z][^.]+)$',  # Numbered sections
            r'^([A-Z][A-Z\s]{10,})$',  # All caps headers
            r'^((?:ARTICLE|SECTION|EXHIBIT)\s+[IVX\d]+[:\.]?\s*.+)$'  # Legal sections
        ]
        
        lines = text.split('\n')
        for line in lines[:200]:  # Check first 200 lines
            line = line.strip()
            if not line:
                continue
                
            for pattern in header_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    header = match.group(1).strip()
                    if len(header) > 10 and header not in headers:
                        headers.append(header)
                        if len(headers) >= max_headers:
                            return headers
                    break
        
        return headers
    
    def extract_all_metadata(self, text: str, filepath: str = "") -> Dict[str, any]:
        """Extract all available metadata from document."""
        metadata = {}
        
        # Extract from filename
        if filepath:
            metadata.update(self.extract_from_filename(filepath))
        
        # Extract title
        title = self.extract_title_from_content(text)
        if title:
            metadata['document_title'] = title
        
        # Extract document type
        doc_type, confidence = self.extract_document_type(text, filepath)
        metadata['document_type'] = doc_type
        metadata['document_type_confidence'] = confidence
        
        # Extract headers
        headers = self.extract_headers(text)
        if headers:
            metadata['section_headers'] = headers[:5]  # Keep top 5
        
        # Create a special "metadata sentence" for classification
        # This ensures document type info is available to the LLM
        metadata_sentence = self._create_metadata_sentence(metadata)
        if metadata_sentence:
            metadata['metadata_sentence'] = metadata_sentence
        
        return metadata
    
    def _create_metadata_sentence(self, metadata: Dict) -> str:
        """Create a sentence summarizing document metadata for classification."""
        parts = []
        
        if metadata.get('document_title'):
            parts.append(f"Document Title: {metadata['document_title']}")
        
        if metadata.get('document_type') and metadata.get('document_type') != 'Unknown':
            confidence = metadata.get('document_type_confidence', 0)
            if confidence > 0.5:
                parts.append(f"Document Type: {metadata['document_type']}")
        
        if metadata.get('filename_document_type'):
            parts.append(f"Filename indicates: {metadata['filename_document_type']}")
        
        if parts:
            return " | ".join(parts)
        return ""


# Global instance
document_metadata_extractor = DocumentMetadataExtractor()