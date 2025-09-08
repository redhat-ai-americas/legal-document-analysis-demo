"""
Streamlit UI that uses backend API for processing
"""

import streamlit as st
import requests
import os
import time
import tempfile
from pathlib import Path
import json
from typing import Optional, List, Dict, Any

# Get backend URL from environment
BACKEND_URL = os.getenv('BACKEND_URL', 'http://legal-doc-backend:8080')
if not BACKEND_URL.startswith('http'):
    BACKEND_URL = f'http://{BACKEND_URL}'

# For external testing
EXTERNAL_BACKEND_URL = 'https://legal-doc-api-legal-doc-test.apps.cluster-f7p6w.f7p6w.sandbox2014.opentlc.com'

def check_backend_health() -> bool:
    """Check if backend is healthy"""
    try:
        # Try internal URL first, then external
        for url in [BACKEND_URL, EXTERNAL_BACKEND_URL]:
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    st.session_state['backend_url'] = url
                    return True
            except:
                continue
        return False
    except:
        return False

def upload_file_to_backend(file, backend_url: str, document_type: str = "document") -> Optional[str]:
    """Upload file to backend and return file path"""
    try:
        files = {'file': (file.name, file.getvalue(), file.type)}
        data = {'document_type': document_type}
        response = requests.post(f"{backend_url}/api/upload", files=files, data=data)
        if response.status_code == 200:
            return response.json()['file_path']
        else:
            st.error(f"Failed to upload {file.name}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error uploading {file.name}: {str(e)}")
        return None

def start_analysis(
    backend_url: str,
    reference_path: str,
    target_paths: List[str],
    rules_path: Optional[str] = None
) -> Optional[str]:
    """Start analysis job on backend"""
    try:
        payload = {
            "reference_document_path": reference_path,
            "target_document_paths": target_paths,
            "rules_path": rules_path,
            "options": {}
        }
        
        response = requests.post(
            f"{backend_url}/api/analyze",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()['job_id']
        else:
            st.error(f"Failed to start analysis: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error starting analysis: {str(e)}")
        return None

def check_job_status(backend_url: str, job_id: str) -> Dict[str, Any]:
    """Check job status"""
    try:
        response = requests.get(f"{backend_url}/api/jobs/{job_id}")
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "error": response.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def download_results(backend_url: str, job_id: str, file_type: str) -> Optional[bytes]:
    """Download results from backend"""
    try:
        response = requests.get(f"{backend_url}/api/jobs/{job_id}/download/{file_type}")
        if response.status_code == 200:
            return response.content
        else:
            return None
    except:
        return None

def main():
    st.set_page_config(
        page_title="Legal Document Analysis",
        page_icon="⚖️",
        layout="wide"
    )
    
    st.title("⚖️ Legal Document Analysis Platform")
    st.caption("AI-powered contract review and compliance checking")
    
    # Check backend health
    if not check_backend_health():
        st.error("❌ Backend service is not available. Please contact support.")
        st.stop()
    
    backend_url = st.session_state.get('backend_url', BACKEND_URL)
    st.success(f"✅ Connected to backend")
    
    # Document upload section
    st.header("📄 Document Upload")
    
    # Sample documents section
    with st.expander("📚 Load Sample Documents"):
        st.write("Choose a pre-configured document set for testing:")
        
        sample_sets = {
            "AI Services Addendum": {
                "reference": "/app/sample_documents/standard_docs/ai_addendum/AI-Addendum.md",
                "target": "/app/sample_documents/target_docs/ai_addendum/AI-Services-Addendum-for-Procurement-Contracts-Aug.pdf",
                "description": "AI services contract analysis"
            },
            "Software License Agreement": {
                "reference": "/app/sample_documents/standard_docs/software_license_agreement/Software-License-Agreement.md",
                "target": "/app/sample_documents/target_docs/software_license_agreement/Form of Software License Agreement.pdf",
                "description": "Software license review"
            },
            "Business Associate Agreement": {
                "reference": "/app/sample_documents/standard_docs/baa/BAA.md",
                "target": "/app/sample_documents/target_docs/baa/model-business-associate-agreement.pdf",
                "description": "HIPAA BAA compliance check"
            }
        }
        
        cols = st.columns(len(sample_sets))
        for idx, (name, info) in enumerate(sample_sets.items()):
            with cols[idx]:
                if st.button(name, key=f"sample_{idx}", use_container_width=True):
                    st.session_state['use_sample'] = True
                    st.session_state['sample_reference'] = info['reference']
                    st.session_state['sample_target'] = info['target']
                    st.session_state['sample_name'] = name
                    st.success(f"✅ Loaded {name} sample documents")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Reference Document")
        st.caption("📂 Drag and drop or click to browse")
        reference_file = st.file_uploader(
            "Upload reference contract",
            type=['pdf', 'md', 'txt'],
            key="reference",
            help="Upload your standard reference contract (PDF, Markdown, or Text)"
        )
        if reference_file:
            st.success(f"✅ {reference_file.name}")
    
    with col2:
        st.subheader("Target Documents")
        st.caption("📂 Drag and drop or click to browse")
        target_files = st.file_uploader(
            "Upload contracts to analyze",
            type=['pdf', 'md', 'txt'],
            accept_multiple_files=True,
            key="targets",
            help="Upload one or more contracts to analyze against the reference"
        )
        if target_files:
            for f in target_files:
                st.success(f"✅ {f.name}")
    
    with col3:
        st.subheader("Rules File (Optional)")
        st.caption("📂 Drag and drop or click to browse")
        rules_file = st.file_uploader(
            "Upload compliance rules",
            type=['yaml', 'yml', 'json'],
            key="rules",
            help="Upload YAML or JSON rules file for compliance checking"
        )
        if rules_file:
            st.success(f"✅ {rules_file.name}")
    
    # Analysis button
    if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
        # Check if using sample documents or uploaded files
        use_sample = st.session_state.get('use_sample', False)
        
        if use_sample:
            # Use sample documents
            reference_path = st.session_state.get('sample_reference')
            target_paths = [st.session_state.get('sample_target')]
            rules_path = None
            st.info(f"Using sample documents: {st.session_state.get('sample_name', 'Unknown')}")
        elif not reference_file or not target_files:
            st.error("Please upload at least a reference document and one target document, or select sample documents")
            st.stop()
        else:
            with st.spinner("Uploading files..."):
                # Upload files
                reference_path = upload_file_to_backend(reference_file, backend_url, "reference")
                if not reference_path:
                    st.stop()
                
                target_paths = []
                for target_file in target_files:
                    path = upload_file_to_backend(target_file, backend_url, "target")
                    if path:
                        target_paths.append(path)
                
                rules_path = None
                if rules_file:
                    rules_path = upload_file_to_backend(rules_file, backend_url, "rules")
        
        # Start analysis (for both sample and uploaded documents)
        if reference_path and target_paths:
            with st.spinner("Starting analysis..."):
                job_id = start_analysis(backend_url, reference_path, target_paths, rules_path)
                
                if job_id:
                    st.success(f"Analysis started! Job ID: {job_id}")
                    st.session_state['current_job_id'] = job_id
                    # Clear sample flag after use
                    if 'use_sample' in st.session_state:
                        del st.session_state['use_sample']
                else:
                    st.error("Failed to start analysis")
                    st.stop()
    
    # Job monitoring section
    if 'current_job_id' in st.session_state:
        st.header("📊 Analysis Progress")
        
        job_id = st.session_state['current_job_id']
        
        # Create placeholders for different sections
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        llm_output_placeholder = st.empty()
        history_placeholder = st.empty()
        result_placeholder = st.empty()
        
        # Poll for status
        while True:
            status = check_job_status(backend_url, job_id)
            
            if status['status'] == 'error':
                status_placeholder.error(f"Error: {status.get('error', 'Unknown error')}")
                break
            elif status['status'] == 'failed':
                status_placeholder.error(f"Analysis failed: {status.get('error', 'Unknown error')}")
                break
            elif status['status'] == 'completed':
                with result_placeholder.container():
                    st.success("✅ Analysis completed!")
                    
                    # Download buttons
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        excel_data = download_results(backend_url, job_id, 'excel')
                        if excel_data:
                            st.download_button(
                                label="📊 Download Excel Results",
                                data=excel_data,
                                file_name="analysis_results.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    
                    with col2:
                        yaml_data = download_results(backend_url, job_id, 'yaml')
                        if yaml_data:
                            st.download_button(
                                label="📄 Download YAML Results",
                                data=yaml_data,
                                file_name="analysis_results.yaml",
                                mime="text/yaml"
                            )
                    
                    with col3:
                        md_data = download_results(backend_url, job_id, 'markdown')
                        if md_data:
                            st.download_button(
                                label="📝 Download Report",
                                data=md_data,
                                file_name="analysis_report.md",
                                mime="text/markdown"
                            )
                break
            else:
                # Show progress bar
                progress = status.get('progress', 0.0)
                progress_placeholder.progress(progress, text=f"Overall Progress: {int(progress * 100)}%")
                
                # Show current status
                with status_placeholder.container():
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.metric("Status", status['status'].upper())
                    with col2:
                        current_node = status.get('current_node', 'Unknown')
                        current_message = status.get('current_message', '')
                        st.info(f"**{current_node}**: {current_message}")
                
                # Show LLM output if available
                llm_output = status.get('llm_output')
                if llm_output:
                    with llm_output_placeholder.expander("🤖 LLM Output", expanded=True):
                        st.code(llm_output, language="text")
                
                # Show progress history
                history = status.get('progress_history', [])
                if history:
                    with history_placeholder.expander("📜 Progress History", expanded=False):
                        for entry in history[-5:]:  # Show last 5 entries
                            timestamp = entry.get('timestamp', '')
                            node = entry.get('node', '')
                            message = entry.get('message', '')
                            st.text(f"[{timestamp.split('T')[1][:8] if timestamp else ''}] {node}: {message}")
                
                time.sleep(1)  # Poll every second for more responsive updates

if __name__ == "__main__":
    main()