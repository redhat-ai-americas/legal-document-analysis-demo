import os
import requests
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
    Try primary PDF conversion using Docling microservice.
    """
    try:
        # Check for Docling processor URL - can be either internal service or external route
        docling_url = os.getenv('DOCLING_URL')
        
        # If no URL set, check if we're in OpenShift and use internal service
        if not docling_url and os.getenv('KUBERNETES_SERVICE_HOST'):
            # Use internal service name if in cluster
            docling_url = 'http://docling-pdf-processor:8080'
            print(f"  Using internal Docling service at {docling_url}...")
        elif docling_url:
            print(f"  Using configured Docling service at {docling_url}...")
        else:
            # No service configured - this is an error
            error_msg = "Docling processor service not configured. Set DOCLING_URL environment variable."
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Call the microservice
        return _try_docling_microservice(pdf_path, docling_url)
        
    except Exception as e:
        error_msg = f"Docling conversion failed: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

def _try_docling_microservice(pdf_path: str, service_url: str) -> dict:
    """
    Try PDF conversion using Docling microservice.
    """
    try:
        import time
        import json
        
        # Read the PDF file
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # Ensure URL doesn't have trailing slash for consistency
        service_url = service_url.rstrip('/')
        
        # Step 1: Submit PDF for processing
        endpoint = f"{service_url}/process-pdf/"
        files = {'file': (os.path.basename(pdf_path), pdf_content, 'application/pdf')}
        
        print(f"  Submitting PDF to Docling processor...")
        response = requests.post(endpoint, files=files, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"Docling processor returned {response.status_code}: {response.text[:200]}"
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Get job ID from response
        job_data = response.json()
        job_id = job_data.get('job_id')
        
        if not job_id:
            error_msg = "No job_id returned from Docling processor"
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        print(f"  Processing job {job_id}...")
        
        # Step 2: Poll for job completion
        status_endpoint = f"{service_url}/status/{job_id}"
        max_wait = 120  # Maximum 2 minutes
        poll_interval = 2  # Check every 2 seconds
        elapsed = 0
        
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            
            status_response = requests.get(status_endpoint, timeout=10)
            
            if status_response.status_code != 200:
                continue  # Keep polling
            
            status_data = status_response.json()
            status = status_data.get('status')
            
            if status == 'completed':
                print(f"  Job completed successfully")
                break
            elif status == 'failed':
                error_msg = f"Docling processing failed: {status_data.get('error', 'Unknown error')}"
                logging.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
            elif status == 'processing':
                if elapsed % 10 == 0:  # Update every 10 seconds
                    print(f"    Still processing... ({elapsed}s)")
        else:
            error_msg = f"Docling processing timed out after {max_wait} seconds"
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Step 3: Get the result
        result_endpoint = f"{service_url}/result/{job_id}"
        result_response = requests.get(result_endpoint, timeout=30)
        
        if result_response.status_code != 200:
            error_msg = f"Failed to get result: {result_response.status_code}"
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Try to parse as JSON first
        try:
            result_data = result_response.json()
            markdown_content = result_data.get('markdown_content', '')
        except json.JSONDecodeError:
            # If not JSON, the service might be returning raw text or Python repr
            result_text = result_response.text
            
            # Check if it's the raw Docling object representation (a bug in the service)
            if result_text.startswith("schema_name='DoclingDocument'"):
                error_msg = "Docling processor returned raw Python object instead of markdown. Service needs to be fixed to return proper markdown."
                logging.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "details": "The service at /result/{job_id} should return markdown content, not the raw Docling document object."
                }
            
            # Otherwise treat as markdown directly
            markdown_content = result_text
        
        # The microservice already adds page anchors, but verify
        if "[[page=" not in markdown_content:
            # Add page anchors if missing
            lines = markdown_content.splitlines()
            pg_annotated = ["[[page=1]]"]
            current_page = 1
            lines_since_page = 0
            
            for line in lines:
                lines_since_page += 1
                if lines_since_page >= 50:
                    current_page += 1
                    pg_annotated.append(f"[[page={current_page}]]")
                    lines_since_page = 0
                pg_annotated.append(line)
            
            markdown_content = "\n".join(pg_annotated)
        
        # Quality check
        if len(markdown_content.strip()) < 100:
            error_msg = f"Insufficient content from microservice (length: {len(markdown_content)})"
            logging.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Create output path for processed document
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        processed_path = f"data/output/{base_name}_processed.md"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)
        
        # Write processed content
        with open(processed_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"  Successfully converted PDF via microservice ({len(markdown_content)} chars)")
        
        return {
            "success": True,
            "processed_path": processed_path,
            "method": "docling_microservice",
            "content": markdown_content,
            "content_length": len(markdown_content)
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to connect to Docling microservice: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Docling microservice conversion failed: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

def _try_local_docling_conversion_DEPRECATED(pdf_path: str) -> dict:
    """
    DEPRECATED: Local Docling conversion - not used to avoid dependency in deployment.
    This function is kept for reference but should not be called.
    """
    try:
        from docling.document_converter import DocumentConverter
        
        print("  Using local Docling library for PDF conversion...")
        
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
            "method": "docling_local",
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
        error_msg = f"Local Docling conversion failed: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }