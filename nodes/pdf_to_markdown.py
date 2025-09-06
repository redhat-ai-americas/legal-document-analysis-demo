import os
from workflows.state import ContractAnalysisState
from utils.error_handler import handle_node_errors, error_handler
import logging

@handle_node_errors("pdf_converter")
def convert_pdf_to_markdown(state: ContractAnalysisState) -> dict:
    """
    Converts PDF file to markdown using multiple fallback libraries for robustness.
    """
    print("--- 0. CONVERTING PDF TO MARKDOWN ---")
    
    pdf_path = state["target_document_path"]
    
    # Check if file is actually a PDF
    if not pdf_path.lower().endswith('.pdf'):
        print(f"  File {pdf_path} is not a PDF, skipping conversion")
        return {}
    
    # Validate PDF file exists and is accessible
    if not os.path.exists(pdf_path):
        error_msg = f"PDF file not found: {pdf_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    if not os.access(pdf_path, os.R_OK):
        error_msg = f"Cannot read PDF file: {pdf_path}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    
    print(f"  Converting PDF using multi-library approach: {pdf_path}")
    
    # Try primary method (Docling) first
    result = _try_docling_conversion(pdf_path)
    if result.get("success"):
        print(f"  Successfully converted PDF using Docling: {result['processed_path']}")
        return {"processed_document_path": result["processed_path"]}
    else:
        print(f"  Docling conversion failed: {result.get('error')}")
    
    # If primary method fails, try fallback methods
    try:
        # Try alternative PDF libraries through error handler
        fallback_result = error_handler.handle_error(
            Exception("Primary PDF conversion failed"),
            "pdf_converter", 
            context_data={
                "pdf_path": pdf_path,
                "primary_error": result.get('error')
            },
            pdf_path=pdf_path
        )
        
        if fallback_result and fallback_result.get("success") and fallback_result.get("result", {}).get("success"):
            # Process fallback result
            content = fallback_result["result"]["content"]
            method = fallback_result["result"]["method"]
            quality_score = fallback_result["result"].get("quality_score", 0.0)
            
            print(f"  PDF converted using fallback method: {method} (quality: {quality_score:.2f})")
            
            # Save processed content
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            processed_path = f"data/output/{base_name}_processed.md"
            
            os.makedirs(os.path.dirname(processed_path), exist_ok=True)
            
            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Add quality metadata
            metadata = {
                "conversion_method": method,
                "quality_score": quality_score,
                "fallback_used": True,
                "original_error": result.get('error')
            }
            
            # Save metadata
            metadata_path = f"data/output/{base_name}_metadata.json"
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"  PDF converted and saved to: {processed_path}")
            print(f"  Conversion metadata saved to: {metadata_path}")
            
            return {
                "processed_document_path": processed_path,
                "conversion_metadata": metadata
            }
        else:
            # All conversion methods failed
            error_msg = f"All PDF conversion methods failed. Primary error: {result.get('error')}, Fallback error: {fallback_result.get('message', 'Unknown error')}"
            logging.error(error_msg)
            raise Exception(error_msg)
    except Exception as e:
        error_msg = f"PDF conversion failed with error: {str(e)}"
        logging.error(error_msg)
        raise Exception(error_msg)

def _try_docling_conversion(pdf_path: str) -> dict:
    """
    Try primary PDF conversion using Docling library.
    Uses simple approach that handles images with placeholders.
    """
    try:
        from docling.document_converter import DocumentConverter
        
        print("  Using Docling for PDF conversion (ignoring images)...")
        
        # Initialize the converter with basic settings
        converter = DocumentConverter()
        
        # Convert the PDF to markdown
        result = converter.convert(pdf_path)
        
        # Get the markdown content and inject page anchors
        markdown_content = result.document.export_to_markdown()
        
        # Always add page anchors - start with page 1
        pg_annotated = ["[[page=1]]"]  # Start with page 1 anchor
        current_page = 1
        lines_since_page = 0
        
        for line in markdown_content.splitlines():
            # Check for explicit page markers
            if line.strip().lower().startswith("page ") and " of " in line.lower():
                current_page += 1
                pg_annotated.append(f"[[page={current_page}]]")
                lines_since_page = 0
                continue
            
            # Also add page anchors every ~50 lines as a fallback
            # This ensures we have some page anchors even if no explicit markers
            lines_since_page += 1
            if lines_since_page >= 50:
                current_page += 1
                pg_annotated.append(f"[[page={current_page}]]")
                lines_since_page = 0
            
            pg_annotated.append(line)
        
        markdown_content = "\n".join(pg_annotated)
        print(f"  Added {current_page} page anchors to document")
        
        # Quality check
        if len(markdown_content.strip()) < 100:
            error_msg = f"Insufficient content extracted by Docling (length: {len(markdown_content)})"
            logging.warning(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "content_length": len(markdown_content)
            }
        
        # Create output path for processed document
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        processed_path = f"data/output/{base_name}_processed.md"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)
        
        # Write processed content
        with open(processed_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"  Successfully converted PDF to markdown ({len(markdown_content)} chars)")
        print("  Sentence extraction will filter out image placeholders and noise")
        
        return {
            "success": True,
            "processed_path": processed_path,
            "method": "docling_simple",
            "content": markdown_content,
            "content_length": len(markdown_content)
        }
        
    except ImportError as e:
        error_msg = f"Docling not available: {e}. Install with: pip install docling"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "Install with: pip install docling"
        }
    except Exception as e:
        error_msg = f"Docling conversion failed: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }