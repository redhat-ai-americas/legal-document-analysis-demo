#!/usr/bin/env python3
"""
Test script for Docling PDF Processor Service
This tests the deployed service at OpenShift and shows the permission error
"""

import os
import sys
import requests
import time
import json

def test_docling_processor():
    # Configuration
    service_url = 'https://docling-pdf-processor-legal-doc-test.apps.cluster-f7p6w.f7p6w.sandbox2014.opentlc.com'
    test_pdf = 'sample_documents/target_docs/ai_addendum/AI-Services-Addendum-for-Procurement-Contracts-Aug.pdf'
    
    print(f'Testing Docling processor at: {service_url}')
    print(f'Using PDF: {test_pdf}')
    print('-' * 60)
    
    # Verify the PDF exists
    if not os.path.exists(test_pdf):
        print(f'❌ PDF file not found: {test_pdf}')
        return False
    
    file_size = os.path.getsize(test_pdf)
    print(f'📄 PDF file size: {file_size:,} bytes')
    
    # Step 1: Submit PDF for processing
    print('\n1️⃣ Submitting PDF for processing...')
    try:
        with open(test_pdf, 'rb') as f:
            files = {'file': (os.path.basename(test_pdf), f.read(), 'application/pdf')}
            response = requests.post(
                f'{service_url}/process-pdf/', 
                files=files,
                timeout=30
            )
        
        print(f'   Response status: {response.status_code}')
        
        if response.status_code != 200:
            print(f'❌ Failed to submit: {response.status_code}')
            print(f'   Response: {response.text[:500]}')
            return False
        
        job_data = response.json()
        job_id = job_data.get('job_id')
        
        if not job_id:
            print(f'❌ No job ID in response: {job_data}')
            return False
            
        print(f'✅ Job submitted successfully')
        print(f'   Job ID: {job_id}')
        print(f'   Initial status: {job_data.get("status")}')
        
    except Exception as e:
        print(f'❌ Error submitting PDF: {e}')
        return False
    
    # Step 2: Poll for job completion
    print('\n2️⃣ Polling for job completion...')
    max_attempts = 30  # 30 attempts * 2 seconds = 60 seconds max
    poll_interval = 2
    
    for attempt in range(max_attempts):
        time.sleep(poll_interval)
        
        try:
            status_response = requests.get(
                f'{service_url}/status/{job_id}',
                timeout=10
            )
            
            if status_response.status_code != 200:
                print(f'   Attempt {attempt + 1}: Status check returned {status_response.status_code}')
                continue
            
            status_data = status_response.json()
            status = status_data.get('status')
            
            # Show progress
            if attempt % 5 == 0 or status != 'processing':
                print(f'   Attempt {attempt + 1}: Status = {status}')
            
            if status == 'completed':
                print(f'✅ Processing completed successfully!')
                break
                
            elif status == 'failed':
                print(f'❌ Processing failed!')
                print(f'   Error: {status_data.get("error", "Unknown error")}')
                print(f'   Full response: {json.dumps(status_data, indent=2)}')
                return False
                
        except Exception as e:
            print(f'   Attempt {attempt + 1}: Error checking status: {e}')
            
    else:
        print(f'❌ Timeout: Processing did not complete within {max_attempts * poll_interval} seconds')
        return False
    
    # Step 3: Retrieve the result
    print('\n3️⃣ Retrieving processed result...')
    try:
        result_response = requests.get(
            f'{service_url}/result/{job_id}',
            timeout=30
        )
        
        print(f'   Response status: {result_response.status_code}')
        
        if result_response.status_code != 200:
            print(f'❌ Failed to get result: {result_response.status_code}')
            print(f'   Response: {result_response.text[:500]}')
            return False
        
        result_data = result_response.json()
        markdown_content = result_data.get('markdown_content', '')
        
        if not markdown_content:
            print(f'❌ No markdown content in result')
            print(f'   Result keys: {list(result_data.keys())}')
            return False
        
        content_length = len(markdown_content)
        print(f'✅ Successfully retrieved result!')
        print(f'   Content length: {content_length:,} characters')
        print(f'   Has page anchors: {"[[page=" in markdown_content}')
        
        # Show a preview
        print('\n📝 Content preview (first 500 chars):')
        print('-' * 40)
        print(markdown_content[:500])
        print('-' * 40)
        
        # Save to file for inspection
        output_file = 'test_docling_output.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f'\n💾 Full output saved to: {output_file}')
        
        return True
        
    except Exception as e:
        print(f'❌ Error retrieving result: {e}')
        return False

if __name__ == '__main__':
    print('=' * 60)
    print('DOCLING PDF PROCESSOR SERVICE TEST')
    print('=' * 60)
    
    success = test_docling_processor()
    
    print('\n' + '=' * 60)
    if success:
        print('✅ TEST PASSED: Docling processor is working correctly!')
    else:
        print('❌ TEST FAILED: See errors above')
        print('\n🔧 The main issue appears to be:')
        print('   Permission denied: /opt/app-root/src/.cache/huggingface')
        print('\n   This needs to be fixed in the Docling processor container:')
        print('   1. The container needs write access to ~/.cache/huggingface')
        print('   2. Or set HF_HOME environment variable to a writable directory')
        print('   3. Or pre-download models and set TRANSFORMERS_OFFLINE=1')
    print('=' * 60)
    
    sys.exit(0 if success else 1)