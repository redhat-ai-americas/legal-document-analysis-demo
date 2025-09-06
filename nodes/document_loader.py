import re
import yaml
import logging
from workflows.state import ContractAnalysisState
from utils.document_metadata_extractor import document_metadata_extractor
from utils.sentence_page_mapper import sentence_page_mapper

def clean_text(text: str) -> str:
    """
    Cleans text while preserving document structure.
    """
    # Replace HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    
    # Normalize quotes
    text = text.replace(' \' ', "'").replace(' " ', '"')
    text = text.replace("' ", "'").replace('" ', '"')
    text = text.replace(" '", "'").replace(' "', '"')
    
    # Preserve paragraph structure but clean extra whitespace
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []
    for p in paragraphs:
        lines = [line.strip() for line in p.splitlines()]
        cleaned_p = ' '.join(line for line in lines if line)
        if cleaned_p:
            cleaned_paragraphs.append(cleaned_p)
    
    return '\n\n'.join(cleaned_paragraphs)

def extract_sentences(document_text: str) -> list[str]:
    """
    Extracts sentences from a document string using improved handling of document structure.
    Handles markdown formatting, lists, and special cases while preserving meaningful content.
    Also extracts page information from [[page=N]] anchors.
    """
    # Store original text to preserve page anchors
    original_text = document_text
    # Clean text while preserving structure
    document_text = clean_text(document_text)
    
    # Split into paragraphs
    paragraphs = document_text.split('\n\n')
    sentences = []
    
    # Track stats for debugging
    total_paragraphs = len(paragraphs)
    processed_paragraphs = 0
    skipped_paragraphs = 0
    
    # Also process original text to extract page anchors
    original_paragraphs = original_text.split('\n\n')
    
    for i, paragraph in enumerate(paragraphs):
        paragraph = paragraph.strip()
        
        # Check for page anchors in the original paragraph
        if i < len(original_paragraphs):
            orig_para = original_paragraphs[i]
            page_match = re.search(r'\[\[page=(\d+)\]\]', orig_para)
            if page_match:
                int(page_match.group(1))
        
        # Skip empty paragraphs
        if not paragraph:
            skipped_paragraphs += 1
            continue
            
        # Handle HTML comments
        if paragraph.startswith('<!--') and paragraph.endswith('-->'):
            skipped_paragraphs += 1
            continue
            
        # Handle markdown headers but keep their content
        if paragraph.startswith('#'):
            content = re.sub(r'^#+\s*', '', paragraph)
            if len(content) > 15:  # Only keep substantial headers
                sentences.append(content)
            processed_paragraphs += 1
            continue
            
        # Handle list items and bullet points
        if re.match(r'^[a-z0-9]\.\s|^\([0-9]+\)\s|^[-*•]\s', paragraph):
            if len(paragraph) > 30:  # Only keep substantial items
                sentences.append(paragraph)
            processed_paragraphs += 1
            continue
            
        # Regular text - split on sentence boundaries
        # Enhanced pattern that better handles legal document formatting
        potential_sentences = re.split(
            r'(?<=[.!?])\s+(?=[A-Z])|(?<=\n)(?=[A-Z])|(?<=\)\.)\s+(?=[A-Z])',
            paragraph
        )
        
        for sentence in potential_sentences:
            sentence = sentence.strip()
            # Enhanced filtering criteria for legal/contract content
            if (len(sentence) > 30 and  # More substantial minimum length
                len(sentence.split()) > 3 and  # At least a few words
                not sentence.startswith(('|', '+-', '=', '_')) and  # Skip table/formatting
                not all(c.isdigit() or c.isspace() for c in sentence) and  # Skip pure numbers
                any(c.isalpha() for c in sentence)):  # Must contain some letters
                sentences.append(sentence)
        
        processed_paragraphs += 1
    
    # Log extraction stats
    print("  📊 Sentence extraction stats:")
    print(f"    Total paragraphs: {total_paragraphs}")
    print(f"    Processed: {processed_paragraphs}")
    print(f"    Skipped: {skipped_paragraphs}")
    print(f"    Extracted sentences: {len(sentences)}")
    
    if not sentences:
        print("  ⚠️  WARNING: No sentences were extracted!")
        print("  🔍 First 200 chars of input:", document_text[:200])
    
    return sentences

def load_and_prep_document(state: ContractAnalysisState) -> dict:
    """
    Loads terminology and document text, then splits text into sentences.
    """
    print("--- 1. LOADING AND PREPPING DOCUMENTS ---")
    
    # Load terminology from YAML file
    try:
        with open(state['terminology_path'], 'r') as f:
            terminology_data = yaml.safe_load(f)
        print(f"  Loaded {len(terminology_data['terms'])} terms from {state['terminology_path']}")
    except Exception as e:
        error_msg = f"Failed to load terminology from {state['terminology_path']}: {e}"
        logging.error(error_msg)
        terminology_data = {"terms": []}

    # Determine which file to load text from
    source_path = state.get("processed_document_path") or state["target_document_path"]
    print(f"  Loading document text from: {source_path}")
    
    # Check if we have a PDF file that hasn't been processed
    if source_path.lower().endswith('.pdf') and not state.get("processed_document_path"):
        error_msg = "Cannot process PDF directly. PDF must be converted to markdown first."
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Try UTF-8 first
        with open(source_path, 'r', encoding='utf-8') as f:
            document_text = f.read()
            print("  Successfully loaded document with UTF-8 encoding")
    except UnicodeDecodeError:
        try:
            # Try with different encoding
            with open(source_path, 'r', encoding='latin-1') as f:
                document_text = f.read()
                print("  Successfully loaded document with Latin-1 encoding")
        except Exception as e:
            error_msg = f"Failed to read file {source_path} with Latin-1 encoding: {e}"
            logging.error(error_msg)
            raise IOError(error_msg)
    except Exception as e:
        error_msg = f"Failed to read file {source_path}: {e}"
        logging.error(error_msg)
        raise IOError(error_msg)

    # Extract document metadata BEFORE sentence extraction
    print("  Extracting document metadata...")
    metadata = document_metadata_extractor.extract_all_metadata(
        document_text, 
        state.get("target_document_path", "")
    )
    
    if metadata.get('document_type'):
        print(f"    Document Type: {metadata['document_type']} (confidence: {metadata.get('document_type_confidence', 0):.1%})")
    if metadata.get('document_title'):
        print(f"    Document Title: {metadata['document_title']}")
    
    # Store original text with page anchors for mapping
    original_document_text = document_text
    
    # Extract sentences with improved handling
    sentences = extract_sentences(document_text)
    
    # Map sentences to pages if document contains page anchors
    sentences_with_pages = None
    if '[[page=' in original_document_text:
        print("  Mapping sentences to pages...")
        sentences_with_pages = sentence_page_mapper.map_sentences_to_pages(
            sentences, original_document_text
        )
        print(f"    Mapped {len(sentences_with_pages)} sentences to pages")
        
        # Extract unique page numbers
        page_numbers = set(s['page'] for s in sentences_with_pages)
        print(f"    Found pages: {sorted(page_numbers)}")
    
    # IMPORTANT: Add metadata as the first "sentence" to ensure it's available for classification
    if metadata.get('metadata_sentence'):
        sentences.insert(0, f"[DOCUMENT METADATA] {metadata['metadata_sentence']}")
        print("  Added metadata sentence for classification")
    
    print(f"  Split document into {len(sentences)} sentences (including metadata)")
    
    # Enhanced validation with more details
    if not sentences:
        error_msg = f"No valid sentences extracted from document: {source_path}"
        logging.warning(error_msg)
        print(f"  WARNING: {error_msg}")
        print(f"  Document text length: {len(document_text)} chars")
        print(f"  First 100 chars: {document_text[:100]}")
    else:
        print(f"  First sentence preview: {sentences[0][:100]}...")
    
    result = {
        "terminology_data": terminology_data,
        "document_text": original_document_text,  # Use original with page anchors
        "document_sentences": sentences,
        "document_metadata": metadata  # Add metadata to state
    }
    
    # Add sentences_with_pages if available
    if sentences_with_pages:
        result["sentences_with_pages"] = sentences_with_pages
    
    return result