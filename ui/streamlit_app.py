import os
import tempfile
import sys
from typing import List, Optional, Dict, Any, Deque
import yaml
from pathlib import Path

# Ensure project root is on sys.path for module imports when run via Streamlit
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)  # agentic-process
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from dotenv import load_dotenv
from collections import deque

from workflows.graph_builder import build_graph  # noqa: F401 (will be re-imported after env setup)
from nodes.base_node import ProgressReporter, ProgressUpdate, NodeStatus


def load_document_sets() -> Dict[str, Any]:
    """Load document sets configuration from YAML file"""
    config_path = Path(_PROJECT_ROOT) / "config" / "document_sets.yaml"
    
    # Check if only AI addendum files exist (fallback mode)
    if not config_path.exists():
        # Create a minimal configuration with just AI addendum
        ai_addendum_target = Path(_PROJECT_ROOT) / "sample_documents/target_docs/ai_addendum/AI-Services-Addendum-for-Procurement-Contracts-Aug.pdf"
        ai_addendum_ref = Path(_PROJECT_ROOT) / "sample_documents/standard_docs/ai_addendum/AI-Addendum.md"
        ai_addendum_rules = Path(_PROJECT_ROOT) / "sample_documents/standard_docs/ai_addendum/ai_addendum_rules.json"
        
        # Only include AI addendum if files actually exist
        if ai_addendum_target.exists() and ai_addendum_ref.exists():
            return {
                "document_sets": {
                    "ai_addendum": {
                        "name": "AI Services Addendum",
                        "description": "AI services agreement templates and compliance rules",
                        "reference_document": str(ai_addendum_ref),
                        "rules_file": str(ai_addendum_rules) if ai_addendum_rules.exists() else None,
                        "target_documents": [
                            {
                                "name": "AI Services Addendum (August)",
                                "path": str(ai_addendum_target),
                                "description": "Vendor AI services addendum"
                            }
                        ]
                    }
                }
            }
        return {"document_sets": {}}
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate that referenced files exist
        validated_sets = {}
        for set_id, set_config in config.get("document_sets", {}).items():
            # Check if reference document exists
            ref_path = Path(_PROJECT_ROOT) / set_config.get("reference_document", "")
            if not ref_path.exists():
                continue
            
            # Check if at least one target document exists
            valid_targets = []
            for target in set_config.get("target_documents", []):
                target_path = Path(_PROJECT_ROOT) / target.get("path", "")
                if target_path.exists():
                    valid_targets.append(target)
            
            if valid_targets:
                set_config["target_documents"] = valid_targets
                
                # Check if rules file exists (optional)
                rules_path = Path(_PROJECT_ROOT) / set_config.get("rules_file", "")
                if not rules_path.exists():
                    set_config["rules_file"] = None
                    
                validated_sets[set_id] = set_config
        
        config["document_sets"] = validated_sets
        return config
        
    except Exception as e:
        st.error(f"Error loading document sets: {e}")
        return {"document_sets": {}}


def save_uploaded_file(upload, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, upload.name)
    with open(path, 'wb') as f:
        f.write(upload.getbuffer())
    return path


def display_progress_update(update: ProgressUpdate, container):
    """Display a progress update in the Streamlit UI"""
    status_icons = {
        NodeStatus.RUNNING: "🔄",
        NodeStatus.COMPLETED: "✅",
        NodeStatus.FAILED: "❌",
        NodeStatus.SKIPPED: "⏭️",
        NodeStatus.RETRYING: "🔁",
        NodeStatus.PENDING: "⏳"
    }
    
    icon = status_icons.get(update.status, "⏳")
    
    # Format progress bar if available
    if update.progress is not None:
        progress_text = f"{update.progress * 100:.0f}%"
        container.progress(update.progress, text=f"{icon} {update.node_name}: {update.message} ({progress_text})")
    else:
        container.info(f"{icon} **{update.node_name}**: {update.message}")
    
    # Show error details if failed
    if update.status == NodeStatus.FAILED and update.details.get('error'):
        container.error(f"Error: {update.details['error']}")


def run_workflow_for_documents(doc_paths: List[str], reference_path: str, rules_path: str | None) -> None:
    # Ensure Granite-only env before imports are resolved
    # Always use template master for consistency
    os.environ['USE_TEMPLATE_EXCEL'] = 'true'
    if rules_path:
        os.environ['RULES_MODE_ENABLED'] = 'true'
    else:
        os.environ.pop('RULES_MODE_ENABLED', None)
    # Force Granite-only
    os.environ['FORCE_GRANITE'] = 'true'
    os.environ['USE_TUNED_MODEL'] = 'false'
    os.environ['DUAL_MODEL_ENABLED'] = 'false'
    os.environ['COMPARISON_ENABLED'] = 'false'
    load_dotenv(override=True)

    # Reload config modules so flags take effect, then import build_graph
    import importlib
    import utils.model_config as mc
    mc = importlib.reload(mc)
    import workflows.graph_builder as gb
    gb = importlib.reload(gb)
    app = gb.build_graph()

    for doc in doc_paths:
        state = {
            "target_document_path": os.path.abspath(doc),
            "reference_document_path": os.path.abspath(reference_path),
            "terminology_path": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'terminology', 'terms.yaml'),
            "baseline_summary": {},
            "spreadsheet_template_path": '',
            "output_path": '',
            "rules_path": rules_path,
            # Required placeholders
            "processed_document_path": "",
            "document_text": "",
            "document_sentences": [],
            "reference_document_text": "",
            "reference_document_sentences": [],
            "terminology_data": [],
            "classified_sentences": [],
            "reference_classified_sentences": [],
            "extracted_data": {},
            "extracted_entities": {},
            "red_flag_analysis": "",
            "questionnaire_responses": {},
            "questionnaire_responses_granite": {},
            "questionnaire_responses_ollama": {},
            "model_comparison": {},
            "active_model_branch": "both",
            "final_spreadsheet_row": {},
            "processing_errors": [],
            "quality_metrics": {},
            "overall_quality_score": None,
            "manual_review_required": False,
            "processing_warnings": [],
            "workflow_status": "running",
            "last_successful_node": None,
            "current_processing_node": None,
            "checkpoints": [],
            "processing_start_time": "",
            "processing_metadata": {},
            "conversion_metadata": None,
            "fallback_strategies_used": [],
            "api_call_metrics": None,
            "classification_metrics": None,
        }
        with st.status(f"Processing {os.path.basename(doc)}", expanded=True) as status:
            # Set up progress reporting
            reporter = ProgressReporter()
            reporter.clear_callbacks()
            
            # Create containers for different types of updates
            main_progress_bar = status.progress(0.0, text="Starting analysis...")
            progress_container = status.container()
            current_node_container = progress_container.empty()
            llm_container = progress_container.container()  # For LLM streaming output
            rules_container = progress_container.container()
            details_container = progress_container.container()
            
            # Track recent updates and processed rules
            recent_updates: Deque[ProgressUpdate] = deque(maxlen=3)
            processed_rules: Dict[str, Any] = {}
            current_llm_output: Optional[Any] = None  # Track current LLM streaming
            accumulated_response: str = ""  # Accumulate the streaming response
            overall_progress: float = 0.0  # Track overall progress
            
            def update_callback(update: ProgressUpdate):
                """Callback to display progress updates in Streamlit"""
                nonlocal current_llm_output, accumulated_response, overall_progress
                
                # Special handling for RuleComplianceEvaluator updates
                if update.node_name == "RuleComplianceEvaluator":
                    # Check for LLM streaming phases
                    if update.details and 'phase' in update.details:
                        phase = update.details['phase']
                        rule_name = update.details.get('rule', '')
                        model_name = update.details.get('model', 'LLM')
                        
                        # Handle different LLM phases
                        if phase == 'llm_start':
                            # Starting LLM analysis - just show a message
                            with llm_container:
                                llm_container.empty()
                                st.info(f"🤖 **{model_name}** analyzing rule: {rule_name}")
                        
                        elif phase == 'llm_complete':
                            # LLM analysis complete - show the full response
                            full_response = update.details.get('full_response', '')
                            with llm_container:
                                # Don't clear - accumulate all responses
                                # llm_container.empty()  # REMOVED to keep history
                                
                                # Create a nice display of the LLM response
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.success(f"✅ **{model_name}** completed: {rule_name}")
                                
                                # Show the formatted JSON response
                                try:
                                    import json
                                    parsed = json.loads(full_response)
                                    
                                    # Display key information prominently
                                    status = parsed.get('status', 'unknown')
                                    confidence = parsed.get('confidence', 0)
                                    
                                    # Color-code the status
                                    status_color = {
                                        'compliant': '🟢',
                                        'non_compliant': '🔴',
                                        'partially_compliant': '🟡',
                                        'not_applicable': '⚪',
                                        'requires_review': '🔵'
                                    }.get(status, '⚫')
                                    
                                    st.markdown(f"### {status_color} LLM Decision: **{status.replace('_', ' ').title()}** (Confidence: {confidence*100:.0f}%)")
                                    
                                    # Show rationale
                                    if 'rationale' in parsed:
                                        st.markdown("**Rationale:**")
                                        st.write(parsed['rationale'])
                                    
                                    # Show issues if non-compliant
                                    if status == 'non_compliant' and 'specific_issues' in parsed:
                                        st.markdown("**Specific Issues Found:**")
                                        for issue in parsed['specific_issues']:
                                            st.write(f"• {issue}")
                                    
                                    # Show the full JSON in an expander
                                    with st.expander("📄 View Full JSON Response", expanded=False):
                                        st.code(json.dumps(parsed, indent=2), language='json')
                                    
                                except Exception as e:
                                    # If JSON parsing fails, show the raw response
                                    st.error(f"Error parsing response: {e}")
                                    st.code(full_response, language='text')
                    
                    # Check if this is a detailed rule analysis result
                    elif update.details and 'rule_name' in update.details:
                        rule_name = update.details['rule_name']
                        
                        # Skip duplicate updates for the same rule
                        if rule_name not in processed_rules:
                            processed_rules[rule_name] = update.details
                            
                            # Display rule analysis in a clean format
                            with rules_container:
                                status_emoji = {
                                    'compliant': '✅',
                                    'non_compliant': '❌',
                                    'partially_compliant': '⚠️',
                                    'not_applicable': '➖',
                                    'requires_review': '🔍'
                                }.get(update.details['status'], '❓')
                                
                                # Create a nicely formatted rule result
                                confidence = update.details.get('confidence', 0) * 100
                                severity = update.details.get('severity', 'medium')
                                
                                # Build the display message
                                msg = f"{status_emoji} **{rule_name}**: {update.details['status'].replace('_', ' ').title()}"
                                if confidence > 0:
                                    msg += f" ({confidence:.0f}% confidence)"
                                
                                # Color code based on status
                                if update.details['status'] == 'non_compliant':
                                    if severity == 'critical':
                                        st.error(f"🔴 {msg} - CRITICAL")
                                    elif severity == 'high':
                                        st.warning(f"🟠 {msg} - HIGH PRIORITY")
                                    else:
                                        st.warning(msg)
                                elif update.details['status'] == 'compliant':
                                    st.success(msg)
                                elif update.details['status'] == 'not_applicable':
                                    st.info(msg)
                                else:
                                    st.warning(msg)
                        
                        # Update overall progress for rule analysis
                        if update.progress is not None:
                            overall_progress = update.progress
                            main_progress_bar.progress(overall_progress, text=f"Analyzing Rules: {int(overall_progress*100)}% complete")
                    
                    # Skip general RuleComplianceEvaluator status updates to reduce clutter
                    return
                
                # Handle other node updates
                if update.status == NodeStatus.RUNNING:
                    current_node_container.info(f"🔄 **Current Step**: {update.node_name}")
                    if update.progress is not None:
                        overall_progress = update.progress
                        # Update the main progress bar with appropriate text
                        if update.node_name == "RuleComplianceEvaluator":
                            progress_text = f"Analyzing Rules: {int(overall_progress*100)}% complete"
                        else:
                            progress_text = f"{update.node_name}: {int(overall_progress*100)}% complete"
                        main_progress_bar.progress(overall_progress, text=progress_text)
                
                # Only show completed nodes (not running status)
                if update.status == NodeStatus.COMPLETED:
                    recent_updates.append(update)
                    
                    # Display completed nodes
                    with details_container:
                        details_container.empty()  # Clear previous updates
                        for recent_update in recent_updates:
                            st.success(f"✅ Completed: {recent_update.node_name}")
            
            # Register the callback
            reporter.register_callback(update_callback)
            
            # Run the workflow
            status.update(label=f"Processing {os.path.basename(doc)}...", state="running")
            
            try:
                result = app.invoke(state)
                status.update(label=f"✅ Completed: {os.path.basename(doc)}", state="complete", expanded=False)
                
                # Show summary
                if 'rule_compliance_summary' in result:
                    summary = result['rule_compliance_summary']
                    score = summary.get('compliance_score', 0) * 100
                    st.metric(
                        label="Compliance Score",
                        value=f"{score:.1f}%",
                        delta=f"{summary.get('compliant', 0)} compliant, {summary.get('non_compliant', 0)} non-compliant"
                    )
            
            except Exception as e:
                status.update(label=f"❌ Failed: {os.path.basename(doc)}", state="error")
                st.error(f"Error processing document: {str(e)}")
            
            finally:
                # Clear callbacks to avoid memory leaks
                reporter.clear_callbacks()


def main():
    st.set_page_config(page_title="Contract Analysis Platform", layout="wide")
    st.title("Contract Analysis Platform")
    st.caption("Automated legal document compliance review powered by Granite 3.3. Upload rules and documents to analyze contract compliance.")

    # Load available document sets
    config = load_document_sets()
    document_sets = config.get("document_sets", {})
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📚 Use Predefined Document Set", "📤 Upload Custom Documents"])
    
    with tab1:
        if document_sets:
            st.info("Select a predefined document set for quick analysis. These sets include reference documents, rules, and sample target documents.")
            
            # Document set selector
            selected_set = st.selectbox(
                "Choose a document set:",
                options=[""] + list(document_sets.keys()),
                format_func=lambda x: document_sets[x]["name"] if x else "-- Select a document set --",
                help="Select from available document sets"
            )
            
            if selected_set:
                set_config = document_sets[selected_set]
                
                # Display set information
                st.markdown(f"**Description:** {set_config.get('description', 'No description available')}")
                
                # Show what's included
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**📄 Reference Document:**")
                    ref_name = Path(set_config["reference_document"]).name
                    st.write(f"✓ {ref_name}")
                
                with col2:
                    st.markdown("**📋 Rules File:**")
                    if set_config.get("rules_file"):
                        rules_name = Path(set_config["rules_file"]).name
                        st.write(f"✓ {rules_name}")
                    else:
                        st.write("❌ No rules file")
                
                with col3:
                    st.markdown("**📁 Target Documents:**")
                    st.write(f"✓ {len(set_config['target_documents'])} document(s) available")
                
                # Target document selector
                st.markdown("---")
                st.markdown("### Select Target Documents to Analyze")
                
                selected_targets = []
                for target in set_config["target_documents"]:
                    if st.checkbox(
                        f"{target['name']}",
                        value=True,
                        key=f"target_{selected_set}_{target['name']}",
                        help=target.get('description', '')
                    ):
                        selected_targets.append(target['path'])
                
                # Optional: Allow adding custom target documents to the set
                st.markdown("---")
                additional_docs = st.file_uploader(
                    "📎 Add additional target documents (optional)",
                    type=["md", "txt", "pdf"],
                    accept_multiple_files=True,
                    key="additional_docs_tab1",
                    help="Optionally upload additional documents to analyze with this set"
                )
                
                # Store selections in session state
                if selected_set and selected_targets:
                    st.session_state['selected_reference'] = set_config["reference_document"]
                    st.session_state['selected_rules'] = set_config.get("rules_file")
                    st.session_state['selected_targets'] = selected_targets
                    st.session_state['additional_docs'] = additional_docs
                    st.session_state['input_method'] = 'preset'
        else:
            st.warning("No document sets configured. Please use the 'Upload Custom Documents' tab or check your configuration.")
    
    with tab2:
        st.info("Upload your own documents for analysis. You can provide a reference document, optional rules file, and one or more target documents.")
        
        # Custom upload interface (existing functionality)
        rules_file = st.file_uploader(
            "📋 Rules file (CSV/XLSX/YAML/JSON)",
            type=["csv", "xlsx", "xlsm", "yml", "yaml", "json"],
            accept_multiple_files=False,
            key="custom_rules",
            help="Upload a rules file to enable compliance checking against specific requirements"
        )
        
        reference_doc = st.file_uploader(
            "📄 Reference document (MD/TXT/PDF)", 
            type=["md", "txt", "pdf"], 
            accept_multiple_files=False,
            key="custom_reference",
            help="Upload a reference document for comparison"
        )
        
        docs = st.file_uploader(
            "📁 Target documents (multiple)", 
            type=["md", "txt", "pdf"], 
            accept_multiple_files=True,
            key="custom_targets",
            help="Upload one or more target documents to analyze"
        )
        
        # Store custom uploads in session state
        if reference_doc and docs:
            st.session_state['custom_reference'] = reference_doc
            st.session_state['custom_rules'] = rules_file
            st.session_state['custom_targets'] = docs
            st.session_state['input_method'] = 'custom'
    
    # Options
    with st.expander("⚙️ Options"):
        clear_history = st.checkbox("Clear main spreadsheet before run", value=False, help="Reset the main spreadsheet to start fresh")

    # Run button with better styling
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run = st.button("🚀 Analyze Documents", type="primary", use_container_width=True)

    if run:
        # Determine which input method was used
        input_method = st.session_state.get('input_method', None)
        
        if input_method == 'preset':
            # Use predefined document set
            reference_path = st.session_state.get('selected_reference')
            rules_path = st.session_state.get('selected_rules')
            target_paths = st.session_state.get('selected_targets', [])
            additional_docs = st.session_state.get('additional_docs', [])
            
            if not reference_path or not target_paths:
                st.error("Please select a document set and at least one target document.")
                return
            
            # Handle additional uploaded documents
            if additional_docs:
                with tempfile.TemporaryDirectory() as tmpdir:
                    additional_paths = [save_uploaded_file(f, tmpdir) for f in additional_docs]
                    target_paths.extend(additional_paths)
            
            # Convert paths to absolute paths
            reference_path = str(Path(_PROJECT_ROOT) / reference_path)
            if rules_path:
                rules_path = str(Path(_PROJECT_ROOT) / rules_path)
            target_paths = [str(Path(_PROJECT_ROOT) / p) if not Path(p).is_absolute() else p for p in target_paths]
            
        elif input_method == 'custom':
            # Use custom uploaded documents
            reference_doc = st.session_state.get('custom_reference')
            rules_file = st.session_state.get('custom_rules')
            docs = st.session_state.get('custom_targets')
            
            if not docs or not reference_doc:
                st.error("Please upload at least one target document and a reference document.")
                return
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Save uploads
                reference_path = save_uploaded_file(reference_doc, tmpdir)
                rules_path = save_uploaded_file(rules_file, tmpdir) if rules_file else None
                target_paths = [save_uploaded_file(f, tmpdir) for f in docs]
        else:
            st.error("Please select a document set or upload custom documents.")
            return

        # Clear master if requested
        if clear_history:
            # Prefer resetting the template master to preserve headers
            try:
                from utils.template_excel_writer import reset_master_template_excel
                comparisons_dir = os.path.join(_PROJECT_ROOT, 'data', 'output', 'comparisons')
                master_template = os.path.join(comparisons_dir, 'contract_analysis_template_master.xlsx')
                reset_master_template_excel(master_template, preserve_headers=True)
            except Exception:
                # Fallback: delete files
                comparisons_dir = os.path.join(_PROJECT_ROOT, 'data', 'output', 'comparisons')
                for fname in [
                    'contract_analysis_template_master.xlsx',
                    'contract_analysis_master.xlsx'
                ]:
                    fpath = os.path.join(comparisons_dir, fname)
                    try:
                        if os.path.exists(fpath):
                            os.remove(fpath)
                    except Exception:
                        pass

        # Run the workflow with selected documents
        run_workflow_for_documents(target_paths, reference_path, rules_path)

        st.success("Completed.")

        # Provide download options for different Excel formats
        col1, col2 = st.columns(2)
        
        # Original analysis results
        with col1:
            master_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'output', 'comparisons', 'contract_analysis_template_master.xlsx')
            if os.path.exists(master_path):
                with open(master_path, 'rb') as f:
                    st.download_button(
                        label="📊 Download Analysis Results",
                        data=f.read(),
                        file_name="contract_analysis_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            else:
                st.info("Analysis results not found yet.")
        
        # Rule compliance results
        with col2:
            compliance_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'output', 'comparisons', 'rule_compliance_master.xlsx')
            if os.path.exists(compliance_path):
                with open(compliance_path, 'rb') as f:
                    st.download_button(
                        label="⚖️ Download Compliance Report",
                        data=f.read(),
                        file_name="rule_compliance_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            else:
                st.info("Compliance report not available (requires rules file).")

        st.markdown("""
        Symbols:
        - LLM: Answered using Granite
        - Deterministic: Answered by deterministic code (entities/metadata)
        Confidence is reported per-question in the spreadsheet under the `Confidence` column.
        """)


if __name__ == "__main__":
    main()


