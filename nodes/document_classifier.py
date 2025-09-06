"""
Unified document classifier for both target and reference documents.
Includes caching support with semantic versioning.

This module consolidates the functionality of target_sentence_classifier.py and
reference_classifier.py into a single parameterized function.
"""

import json
import re
from typing import Dict, Any, List, cast
from workflows.state import ClassifiedSentence
from utils.granite_client import granite_client, GraniteAPIError
from utils.mixtral_adapter import mixtral_client
from utils.error_handler import handle_node_errors
from utils.classification_utils import (
    load_terminology_yaml,
    load_prompt_template,
    format_terminology_for_prompt,
    get_cache_stats,
    get_terminology_hash,
    get_cached_classification,
    cache_classification_result
)
from utils.term_aliases import alias_to_canonical
from utils.model_calling import call_with_schema_retry
from utils.classification_output_writer import save_classification_results

# ===== EFFICIENT CLASSIFICATION FUNCTIONS (merged from document_classifier_efficient.py) =====

def smart_filter_sentences(sentences: List[str], min_length: int = 40) -> List[str]:
    """Filter sentences to only those likely to contain contract terms."""
    
    # Legal keywords that indicate contract-relevant content
    legal_keywords = [
        'shall', 'agree', 'contract', 'agreement', 'party', 'parties',
        'terminate', 'termination', 'liable', 'liability', 'rights', 'obligations',
        'payment', 'fee', 'confidential', 'intellectual', 'property',
        'indemnify', 'damages', 'breach', 'notice', 'governing', 'law',
        'amendment', 'modify', 'assign', 'transfer', 'expire', 'renew'
    ]
    
    filtered_sentences = []
    
    for sentence in sentences:
        sentence_clean = sentence.strip()
        
        # Skip very short sentences
        if len(sentence_clean) < min_length:
            continue
            
        # Skip sentences that are just numbers or bullets
        if re.match(r'^[\d\.\)\(\-\s]+$', sentence_clean):
            continue
            
        # Include if contains legal keywords
        sentence_lower = sentence_clean.lower()
        if any(keyword in sentence_lower for keyword in legal_keywords):
            filtered_sentences.append(sentence_clean)
            continue
            
        # Include sentences with capitalized terms (likely defined terms)
        if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence_clean):
            filtered_sentences.append(sentence_clean)
    
    return filtered_sentences

def classify_sentences_batch(
    sentences_batch: List[str], 
    terminology_data: List[Dict[str, Any]], 
    prompt_template: Dict[str, Any],
    batch_size: int = 5
) -> List[Dict[str, Any]]:
    """Multi-label classification for a batch with schema enforcement.

    Returns JSON list of objects: {"sentence_id": int, "classes": [..], "subsection": str}
    """
    if not sentences_batch:
        return []

    # Load batch classification prompt template
    batch_prompt = load_prompt_template('classifier_batch')
    
    # Allowed canonical labels + none
    allowed_canonical = [t.get("name") for t in terminology_data if t.get("name")]
    allowed_canonical = [str(x) for x in allowed_canonical] + ["none"]

    # Build messages
    sentences_text = ""
    for i, sentence in enumerate(sentences_batch, 1):
        sentences_text += f"{i}. {sentence}\n"

    term_list_display = "\n".join(f"- {t}" for t in allowed_canonical if t != "none")

    # Use template from YAML
    system = batch_prompt.get('system_message', '').strip()
    user = batch_prompt.get('user_message_template', '').format(
        term_list=term_list_display,
        sentences_text=sentences_text
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # Try up to 3 attempts with corrective hint on failure
    response_str: str = ""
    for attempt in range(3):
        try:
            response = granite_client.call_api_with_messages(messages, max_tokens=2048, temperature=0.0, return_metadata=False)
            response_str = str(response).strip()
            parsed = json.loads(response_str)
            if isinstance(parsed, list):
                # Basic schema validation
                ok = True
                for item in parsed:
                    if not isinstance(item, dict):
                        ok = False
                        break
                    # Handle both normal keys and string-escaped keys
                    has_sentence_id = "sentence_id" in item or '"sentence_id"' in item
                    has_classes = "classes" in item or '"classes"' in item
                    if not (has_sentence_id and has_classes):
                        ok = False
                        break
                    # Get classes value handling both key formats
                    classes_val = item.get("classes", item.get('"classes"', []))
                    if not isinstance(classes_val, list):
                        ok = False
                        break
                if ok:
                    return parsed
        except Exception:
            pass

        # Use error correction message from template
        error_msg = batch_prompt.get('error_correction_message', 
            "Reminder: Return ONLY JSON list with objects containing sentence_id, classes (array), and subsection.\n"
            "Classes must be from allowed labels; if none apply, use [\"none\"].")
        messages.append({
            "role": "user",
            "content": error_msg.strip()
        })

    # Final attempt to parse; otherwise empty list
    try:
        parsed = json.loads(response_str)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

@handle_node_errors("document_classifier_efficient")
def classify_document_sentences_efficient(
    state: Dict[str, Any],
    document_type: str = "target",
    batch_size: int = 5,
    enable_filtering: bool = True,
    confidence_threshold: float = 0.7
) -> dict:
    """
    Efficient document classification using batch processing and smart filtering.
    Reduces API calls by 5-10x compared to the original approach.
    """
    
    print(f"  🚀 Using efficient classification (batch_size={batch_size})")
    
    # Load document data
    sentences, output_key_prefix = load_document_data(state, document_type)
    if not sentences:
        return {}
    
    # Check if we have sentences with page information
    sentences_with_pages = state.get('sentences_with_pages', [])
    page_map = {}
    if sentences_with_pages:
        # Create a mapping from sentence text to page number
        # Use stripped text for better matching
        for item in sentences_with_pages:
            sentence_text = item.get('sentence', '').strip()
            page_num = item.get('page', 1)
            page_map[sentence_text] = page_num
        print(f"  📍 Page mapping available for {len(page_map)} sentences")
    
    print(f"  📄 Initial sentence count: {len(sentences)}")
    
    # Smart filtering to reduce sentence count
    if enable_filtering:
        sentences = smart_filter_sentences(sentences)
        print(f"  🔍 Filtered to {len(sentences)} relevant sentences ({(len(sentences)/len(state.get('document_sentences', sentences)))*100:.1f}% of original)")
    
    if not sentences:
        print("  ⚠️  No sentences remaining after filtering")
        return {}
    
    # Check if this is an amendment document
    document_text = state.get('document_text', '')
    is_amendment = is_amendment_document(document_text)
    if is_amendment:
        print("  📝 Detected amendment document - using relaxed classification")
    
    # Load terminology and prompt template
    try:
        terminology_yaml = load_terminology_yaml(state['terminology_path'])
        prompt_template = load_prompt_template('classifier')
        
        # Extract terms list from YAML structure
        if isinstance(terminology_yaml, dict) and 'terms' in terminology_yaml:
            terminology_data = terminology_yaml.get('terms', [])
        else:
            print("  ERROR: Invalid terminology structure")
            return {}
            
    except Exception as e:
        print(f"  ERROR loading terminology or prompt: {e}")
        return {}
    
    # Process sentences in batches
    classified_sentences = []
    total_api_calls = 0
    
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(sentences) + batch_size - 1) // batch_size
        
        print(f"  🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} sentences)")
        
        # Classify batch
        batch_results = classify_sentences_batch(batch, terminology_data, prompt_template, batch_size)
        total_api_calls += 1
        
        # Process batch results
        # Compute allowed set once per batch
        allowed_canonical = [t.get("name") for t in terminology_data if t.get("name")]
        allowed_canonical = [str(x) for x in allowed_canonical] + ["none"]

        for result in batch_results:
            # Handle both normal keys and string-escaped keys
            sentence_id = result.get('sentence_id', result.get('"sentence_id"', 0))
            classes = result.get('classes', result.get('"classes"', []))
            subsection = result.get('subsection', result.get('"subsection"', ''))

            # Validate sentence_id
            if sentence_id < 1 or sentence_id > len(batch):
                continue
            sentence_text = batch[sentence_id - 1]

            # Normalize and filter labels
            canonical_classes: List[str] = []
            if isinstance(classes, list):
                for c in classes:
                    canonical = alias_to_canonical(str(c))
                    if canonical in allowed_canonical or canonical == "none":
                        canonical_classes.append(canonical)
            if not canonical_classes:
                canonical_classes = ["none"]

            # Extract page number from page_map or sentence text
            # Use stripped text for better matching
            page_number = page_map.get(sentence_text.strip())
            
            # If not in map, check if sentence has page anchor in text
            if page_number is None:
                page_match = re.search(r'\[\[page=(\d+)\]\]', sentence_text)
                if page_match:
                    page_number = int(page_match.group(1))
                    # Clean the anchor from the sentence text
                    sentence_text = re.sub(r'\[\[page=\d+\]\]', '', sentence_text).strip()
            
            # Create classified sentence object (multi-label)
            classified_sentences.append({
                "sentence": sentence_text,
                "classes": canonical_classes,
                "confidence": confidence_threshold,
                "classification_confidence": confidence_threshold,
                "validation_confidence": None,
                "needs_manual_review": False,
                "review_reason": None,
                "error": None,
                "processing_metadata": {
                    "subsection": subsection,
                    "raw_labels": classes,
                },
                "sentence_id": None,
                "page": page_number,  # Use 'page' field for consistency
                "page_number": page_number,  # Also keep page_number for backward compatibility
                "section_name": None,
                "location_info": {},
                "citations": []
            })
    
    # Print efficiency stats
    original_calls = len(sentences) * 2  # Original approach: 2 calls per sentence
    efficiency_gain = original_calls / total_api_calls if total_api_calls > 0 else 1
    
    # Handle edge case where no sentences were processed
    if len(sentences) == 0:
        efficiency_gain = 1  # No efficiency gain if no work to do
    
    print("  📊 Efficiency stats:")
    print(f"    - API calls made: {total_api_calls}")
    print(f"    - Original approach would use: {original_calls}")
    print(f"    - Efficiency gain: {efficiency_gain:.1f}x faster")
    print(f"    - Classifications found: {len(classified_sentences)}")
    
    # Save classification results to JSONL for inspection
    try:
        run_id = state.get('run_id') or state.get('processing_start_time', '').replace('-', '').replace('T', '_').replace(':', '')[:15]
        doc_name = state.get('target_document_path', '').split('/')[-1] if document_type == "target" else state.get('reference_document_path', '').split('/')[-1]
        save_classification_results(
            classified_sentences,
            run_id=run_id,
            document_name=f"{document_type}_{doc_name}"
        )
    except Exception as e:
        print(f"  ⚠️ Could not save classification results: {e}")
    
    return {
        f"{output_key_prefix}classified_sentences": classified_sentences,
        f"{output_key_prefix}classification_stats": {
            "total_sentences": len(sentences),
            "classified_sentences": len(classified_sentences),
            "api_calls_made": total_api_calls,
            "efficiency_gain": efficiency_gain,
            "batch_size": batch_size
        }
    }

# ===== END OF EFFICIENT CLASSIFICATION FUNCTIONS =====

def _extract_sentences_improved(document_text: str) -> List[str]:
    """
    Improved sentence extraction for contract documents and markdown.
    Handles docling PDF-converted markdown content with robust filtering.
    Filters out image placeholders, tables, navigation, and other noise.
    """
    
    # Clean the text but preserve structure
    def clean_text_preserve_structure(text: str) -> str:
        # Replace HTML entities
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        
        # Remove docling artifacts and noise patterns
        noise_patterns = [
            r'<!-- image -->',                    # Image placeholders
            r'<!-- .*? -->',                      # HTML comments
            r'\|.*?\|.*?\|',                      # Table rows
            r'^\s*\|.*?\|\s*$',                   # Table borders
            r'^\s*[-=:]+\s*$',                    # Table separators
            r'^\s*page \d+ of \d+\s*$',           # Page numbers
            r'^\s*\d+\s*$',                       # Standalone numbers
            r'^\s*[A-Z]+\s*$'                     # Standalone acronyms
        ]
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that match noise patterns
            line_stripped = line.strip()
            is_noise = False
            
            for pattern in noise_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_noise = True
                    break
            
            if not is_noise and line_stripped:
                # Normalize quotes and spaces but preserve structure
                line_clean = line.replace(' \' ', "'").replace(' " ', '"')
                line_clean = line_clean.replace("' ", "'").replace('" ', '"')
                line_clean = line_clean.replace(" '", "'").replace(' "', '"')
                # Remove excessive spaces within the line
                line_clean = ' '.join(line_clean.split())
                cleaned_lines.append(line_clean)
        
        return '\n'.join(cleaned_lines)
    
    # Clean the text but preserve structure
    document_text = clean_text_preserve_structure(document_text)
    
    # Additional comprehensive filtering
    def is_noise_content(text: str) -> bool:
        """Check if content should be filtered out as noise."""
        text_lower = text.lower().strip()
        
        # Skip completely empty or very short content
        if len(text_lower) < 15:
            return True
            
        # Skip common noise patterns
        noise_indicators = [
            'table of contents',
            'page break',
            'header',
            'footer',
            'appendix',
            'signature',
            'date:',
            'company identification',
            'contact information',
            'address:',
            'phone:',
            'email:',
            'fax:',
            # Skip tables and data structures
            'price (eur without vat)',
            'item description',
            # Skip document metadata
            'proposal',
            'table 1:',
            'table 2:',
            'table 3:'
        ]
        
        for indicator in noise_indicators:
            if indicator in text_lower:
                return True
                
        # Skip if mostly numbers, special characters, or formatting
        word_count = len(text.split())
        if word_count < 4:
            return True
            
        # Skip if too many special characters (likely formatting)
        special_char_ratio = sum(1 for c in text if c in '|+-=_*#[](){}') / len(text)
        if special_char_ratio > 0.3:
            return True
            
        return False
    
    # Split into paragraphs - preserve meaningful structure
    paragraphs = document_text.split('\n\n')
    sentences = []
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        
        # Skip empty paragraphs and noise content
        if not paragraph or is_noise_content(paragraph):
            continue
        
        # Skip markdown headers but process their content if substantial
        if paragraph.startswith('#'):
            # If it's a substantial header (more than just a title), extract as sentence
            header_content = re.sub(r'^#+\s*', '', paragraph).strip()
            if len(header_content) > 15 and '.' in header_content and not is_noise_content(header_content):
                sentences.append(header_content)
            continue
        
        # Handle different types of content
        if re.match(r'^[a-z]\.\s|^\([0-9]+\)\s|^[0-9]+\.\s', paragraph):
            # List items - treat each as a potential sentence
            if paragraph.endswith(('.', '!', '?', ';', ':')) and not is_noise_content(paragraph):
                sentences.append(paragraph)
        else:
            # Regular text - split on sentence boundaries
            # Enhanced splitting that handles legal text better
            potential_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph)
            
            for sentence in potential_sentences:
                sentence = sentence.strip()
                
                # Enhanced filtering criteria for legal/contract content
                if (len(sentence) > 25 and                    # Meaningful length
                    not sentence[0].isdigit() and            # Not starting with number
                    not sentence.startswith(('-', '*', '•', '|')) and  # Not list/table marker
                    len(sentence.split()) > 5 and            # Has substantial word count
                    not is_noise_content(sentence) and       # Not identified as noise
                    any(char.isalpha() for char in sentence) # Contains actual letters
                ):
                    # Final cleanup: remove any remaining artifacts
                    sentence_clean = re.sub(r'\s+', ' ', sentence)  # Normalize spaces
                    sentence_clean = sentence_clean.strip()
                    
                    if sentence_clean:
                        sentences.append(sentence_clean)
    
    print(f"  📝 Extracted {len(sentences)} sentences from document ({len(document_text)} chars)")
    return sentences

def is_amendment_document(document_text: str) -> bool:
    """
    Check if the document appears to be an amendment or modification.
    """
    amendment_indicators = [
        "amendment",
        "modification",
        "addendum",
        "amended and restated",
        "supplemental agreement",
        "change order"
    ]
    
    lower_text = document_text.lower()
    return any(indicator in lower_text for indicator in amendment_indicators)

def calculate_classification_confidence(response_json: Dict[str, Any]) -> float:
    """
    Calculate classification confidence from Granite API logprobs.
    Returns a confidence score between 0 and 1.
    """
    if not response_json.get('choices') or not response_json['choices'][0].get('logprobs'):
        return 0.5  # Default confidence if no logprobs
        
    logprobs = response_json['choices'][0]['logprobs']['content']
    
    # Find logprobs for the classification term tokens
    classification_logprobs = []
    for token_info in logprobs:
        if token_info.get('token') and not token_info['token'].startswith(('{"', '":', ' "', '",', '}')):
            classification_logprobs.append(token_info['logprob'])
    
    if not classification_logprobs:
        return 0.5
    
    # Calculate average confidence from logprobs
    # Convert from log space and average
    import math
    confidences = [math.exp(logprob) for logprob in classification_logprobs]
    return sum(confidences) / len(confidences)

def call_granite_api_with_validation(prompt: str, max_retries: int = 3, confidence_threshold: float = 0.8, is_amendment: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Call the Granite API with enhanced validation and retry logic.
    Returns structured response with confidence and validation metrics.
    """
    # Lower confidence threshold for amendments since they often use indirect references
    if is_amendment:
        confidence_threshold = 0.6
    
    last_response = ""
    for attempt in range(max_retries):
        try:
            # Make API call with logprobs enabled
            response = granite_client._make_request({
                "model": granite_client.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.0,
                "logprobs": True,
                **kwargs
            })
            
            response_json = response.json()
            last_response = response_json['choices'][0]['message']['content']
            
            # Calculate confidence from logprobs
            confidence = calculate_classification_confidence(response_json)
            
            # Validate response quality
            if last_response and len(last_response.strip()) > 0:
                return {
                    "content": last_response,
                    "attempt": attempt + 1,
                    "success": True,
                    "confidence": confidence,
                    "needs_validation": confidence < confidence_threshold,
                    "raw_response": response_json  # Include full response for debugging
                }
            
        except GraniteAPIError as e:
            last_response = f"API_ERROR_{attempt}: {str(e)}"
            if attempt == max_retries - 1:
                return {
                    "content": last_response,
                    "attempt": attempt + 1,
                    "success": False,
                    "confidence": 0.1,
                    "needs_validation": True,
                    "error": str(e)
                }
    
    return {
        "content": last_response,
        "attempt": max_retries,
        "success": False,
        "confidence": 0.1,
        "needs_validation": True
    }

def call_simple_granite_api(prompt: str, **kwargs) -> str:
    """Simple Granite API call for basic classification."""
    try:
        response = granite_client.call_api(
            prompt=prompt,
            max_tokens=512,
            temperature=0.0,
            **kwargs
        )
        return str(response) if response else "API_ERROR"
    except GraniteAPIError as e:
        print(f"Granite API error: {e}")
        return "API_ERROR"

def validate_with_mixtral(validator_prompt: str, term: str, definition: str, is_amendment: bool = False) -> Dict[str, Any]:
    """
    Validate classification using Mixtral model.
    Uses the validate_findings.yaml prompt template.
    """
    try:
        # Force string return type
        response = mixtral_client.call_api(
            prompt=validator_prompt,
            temperature=0.0,
            max_tokens=256,
            return_metadata=False
        )
        
        # Extract validation result based on Pass/Fail format from prompt
        response_text = str(response).strip().lower()
        is_valid = "pass" in response_text
        
        # Set confidence based on clear Pass/Fail vs ambiguous response
        # For amendments, we're more lenient with validation
        if "pass" in response_text or "fail" in response_text:
            validation_confidence = 0.9 if is_valid else (0.3 if is_amendment else 0.1)
        else:
            validation_confidence = 0.6 if is_amendment else 0.5  # Higher base confidence for amendments
            is_valid = is_amendment  # More permissive for amendments
        
        return {
            "is_valid": is_valid,
            "confidence": validation_confidence,
            "response": response_text,
            "success": True
        }
        
    except GraniteAPIError as e:
        print(f"Mixtral validation error: {e}")
        return {
            "is_valid": False,
            "confidence": 0.1,
            "response": f"VALIDATION_ERROR: {e}",
            "success": False
        }

def load_document_data(state: Dict[str, Any], document_type: str) -> tuple:
    """
    Load document data based on document type.
    Returns (sentences, output_key_prefix)
    """
    if document_type == "target":
        # Target document sentences are already loaded in state
        sentences = state.get('document_sentences', [])
        output_key_prefix = ""
        print(f"  Processing target document with {len(sentences)} sentences")
        return sentences, output_key_prefix
        
    elif document_type == "reference":
        # Reference document needs to be loaded from file
        reference_doc_path = state.get('reference_document_path', '')
        if not reference_doc_path:
            print("  No reference document path provided")
            return [], "reference_"
        
        # Check if it's a PDF file that needs conversion
        if reference_doc_path.lower().endswith('.pdf'):
            print("  Reference document is PDF - converting to text first")
            try:
                # Import here to avoid circular imports
                from nodes.pdf_to_markdown import convert_pdf_to_markdown
                
                # Convert PDF using existing converter
                temp_state = {
                    "target_document_path": reference_doc_path,
                    "processed_document_path": ""
                }
                
                conversion_result = convert_pdf_to_markdown(temp_state)
                
                if not conversion_result.get("processed_document_path"):
                    raise Exception("PDF conversion failed - no processed document path returned")
                
                processed_path = conversion_result["processed_document_path"]
                
                # Read converted content
                with open(processed_path, 'r', encoding='utf-8') as f:
                    reference_document_text = f.read()
                
                # Store in state for future use
                state['reference_document_text'] = reference_document_text
                
                print("  Successfully converted PDF reference document")
                print(f"    - Text length: {len(reference_document_text)} characters")
                
            except Exception as e:
                print(f"  ERROR converting reference PDF: {e}")
                return [], "reference_"
        else:
            # Handle non-PDF files (original logic)
            try:
                # Try UTF-8 first
                with open(reference_doc_path, 'r', encoding='utf-8') as f:
                    reference_document_text = f.read()
            except UnicodeDecodeError:
                try:
                    # Try with different encoding
                    with open(reference_doc_path, 'r', encoding='latin-1') as f:
                        reference_document_text = f.read()
                except Exception as e:
                    print(f"  ERROR reading reference file {reference_doc_path}: {e}")
                    return [], "reference_"
            except Exception as e:
                print(f"  ERROR reading reference file {reference_doc_path}: {e}")
                return [], "reference_"
            
            # Store in state
            state['reference_document_text'] = reference_document_text
        
        # Extract sentences from reference document using improved extraction
        sentences = _extract_sentences_improved(reference_document_text)
        
        # Store sentences in state
        state['reference_document_sentences'] = sentences
        
        print(f"  Processing reference document with {len(sentences)} sentences")
        return sentences, "reference_"
    
    else:
        print(f"  ERROR: Unknown document type: {document_type}")
        return [], ""

def extract_term_from_classification(response_text: str) -> str:
    """Extract the term from a classification response."""
    try:
        classification_json = json.loads(response_text)
        return classification_json.get('term', 'no-class')
    except (json.JSONDecodeError, AttributeError):
        return 'no-class'

def create_classified_sentence(
    text: str,
    term: str,
    subsection: str,
    confidence: float
) -> ClassifiedSentence:
    """Create a ClassifiedSentence dictionary with required fields."""
    sentence_dict = {
        "sentence": text,
        "classes": [term] if term != "no-class" else [],
        "confidence": confidence,
        "classification_confidence": confidence,
        "validation_confidence": None,
        "needs_manual_review": False,
        "review_reason": None,
        "error": None,
        "processing_metadata": {
            "subsection": subsection,
            "raw_term": term
        },
        "sentence_id": None,
        "page_number": None,
        "section_name": None,
        "location_info": {},
        "citations": []
    }
    return sentence_dict  # type: ignore

def get_term_definition(terminology_data: List[Dict[str, Any]], term: str) -> str:
    """Get the definition for a term from the terminology data."""
    for item in terminology_data:
        # Support both old and new data structures
        item_term = item.get('name', item.get('term', ''))
        if item_term == term:
            return item.get('definition', item.get('project_specific_definition', ''))
    return ''

@handle_node_errors("document_classifier")
def classify_document_sentences(
    state: Dict[str, Any],
    document_type: str = "target",
    use_enhanced_validation: bool = False,  # Changed: Disable slow validation by default
    enable_confidence_scoring: bool = True,
    use_dual_model: bool = False,  # Changed: Disable dual model for speed
    enable_retry_logic: bool = True,
    confidence_threshold: float = 0.7,  # Changed: Lower threshold for efficiency
    use_efficient_mode: bool = True,  # Changed: Enable efficient mode by default
    batch_size: int = 8  # Changed: Larger batch size for better efficiency
) -> dict:
    """
    Classify sentences in a document using the Granite API.
    Supports both target and reference documents.
    NOW USES EFFICIENT BATCH PROCESSING BY DEFAULT (5-10x faster).
    """
    # Use efficient batch processing if requested (now integrated into this file)
    if use_efficient_mode:
        print(f"  🚀 Using EFFICIENT BATCH PROCESSING (batch_size={batch_size}) - 5-10x faster!")
        return classify_document_sentences_efficient(
            state,
            document_type=document_type,
            batch_size=batch_size,
            enable_filtering=True,
            confidence_threshold=confidence_threshold
        )
    
    # Load document data
    sentences, output_key_prefix = load_document_data(state, document_type)
    if not sentences:
        return {}

    # Check if this is an amendment document
    document_text = state.get('document_text', '')
    is_amendment = is_amendment_document(document_text)
    if is_amendment:
        print("  Detected amendment document - adjusting classification parameters")
        confidence_threshold = 0.6
    
    # Load terminology and prompt template
    try:
        terminology_yaml = load_terminology_yaml(state['terminology_path'])
        load_prompt_template('classifier')
        
        # Extract terms list from YAML structure
        if isinstance(terminology_yaml, dict) and 'terms' in terminology_yaml:
            terminology_data = terminology_yaml.get('terms', [])
        else:
            print(f"  ERROR: Invalid terminology structure: {terminology_yaml}")
            return {}
            
    except Exception as e:
        print(f"  ERROR loading terminology or prompt: {e}")
        return {}

    # Format terminology for prompt
    format_terminology_for_prompt(terminology_data)
    
    # Track classification results
    classified_sentences: List[ClassifiedSentence] = []
    cache_stats = {"hits": 0, "misses": 0}
    
    # Get terminology hash for caching
    terminology_hash = get_terminology_hash(terminology_data)
    
    # Process each sentence
    for sentence in sentences:
        # Skip very short sentences
        if len(sentence.strip()) < 30:
            continue
            
        # Check cache first
        cached_result = get_cached_classification(sentence, terminology_hash)
        
        if cached_result:
            cache_stats["hits"] += 1
            classified_sentences.append(cast(ClassifiedSentence, cached_result))
            continue
            
        cache_stats["misses"] += 1
        
        # Format prompt for this sentence
        # Build allowed labels from terminology
        allowed_labels = [item.get('name', item.get('term', '')) for item in terminology_data if item.get('name', item.get('term', ''))]
        allowed_labels = [str(x) for x in allowed_labels if x] + ["none"]

        system_message = (
            "You are a contract classification model. For the provided sentence, assign ALL applicable labels from the allowed set."
        )
        user_message = (
            "Respond with ONLY JSON. Schema: {\"class\": [array of strings]}.\n"
            "- Labels must be from the allowed set; if none apply, return {\"class\": [\"none\"]}.\n"
            f"Allowed labels: {', '.join([x for x in allowed_labels if x != 'none'])} \n\n"
            f"Sentence: {sentence}"
        )

        try:
            result_json = call_with_schema_retry(
                system_message=system_message,
                user_message=user_message,
                allowed_classes=allowed_labels,
                max_attempts=3,
            )
        except Exception as e:
            print(f"  WARNING: Classification failed after retries for sentence: {sentence[:100]}... ({e})")
            continue

        raw_classes = result_json.get("class", [])
        canonical_classes: List[str] = []
        if isinstance(raw_classes, list):
            for c in raw_classes:
                canonical = alias_to_canonical(str(c))
                if canonical in allowed_labels or canonical == "none":
                    canonical_classes.append(canonical)
        if not canonical_classes:
            canonical_classes = ["none"]

        # Build multi-label classified sentence (no subsection provided by this path)
        classified_sentences.append({
            "sentence": sentence,
            "classes": canonical_classes,
            "confidence": 0.7,
            "classification_confidence": 0.7,
            "validation_confidence": None,
            "needs_manual_review": False,
            "review_reason": None,
            "error": None,
            "processing_metadata": {
                "subsection": "",
                "raw_labels": raw_classes,
            },
            "sentence_id": None,
            "page_number": None,
            "section_name": None,
            "location_info": {},
            "citations": []
        })

        # Cache the result
        cache_classification_result(sentence, terminology_hash, cast(Dict[str, Any], classified_sentences[-1]))

        # Continue to next sentence
        continue
    
    # Print cache stats
    print(f"  Cache stats: {get_cache_stats()}")
    
    # Save classification results to JSONL for inspection
    try:
        run_id = state.get('run_id') or state.get('processing_start_time', '').replace('-', '').replace('T', '_').replace(':', '')[:15]
        doc_name = state.get('target_document_path', '').split('/')[-1] if document_type == "target" else state.get('reference_document_path', '').split('/')[-1]
        save_classification_results(
            classified_sentences,
            run_id=run_id,
            document_name=f"{document_type}_{doc_name}"
        )
    except Exception as e:
        print(f"  ⚠️ Could not save classification results: {e}")
    
    return {
        f"{output_key_prefix}classified_sentences": classified_sentences,
        f"{output_key_prefix}classification_stats": {
            "total_sentences": len(sentences),
            "classified_sentences": len(classified_sentences),
            "cache_hits": cache_stats["hits"],
            "cache_misses": cache_stats["misses"]
        }
    }

def classify_target_sentences(state: Dict[str, Any]) -> dict:
    """Convenience function to classify target document sentences."""
    return classify_document_sentences(state, document_type="target")

def classify_reference_sentences(state: Dict[str, Any]) -> dict:
    """Convenience function to classify reference document sentences."""
    return classify_document_sentences(state, document_type="reference")

# Aliases for existing function names
classify_and_validate_sentences = classify_target_sentences
classify_reference_document = classify_reference_sentences