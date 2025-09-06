from langgraph.graph import StateGraph, END
from workflows.state import ContractAnalysisState
from utils.state_logger import initialize_state_logger
from utils.enhanced_state_logger import initialize_enhanced_logger
from utils.selective_state_logger import initialize_selective_logger
from utils.enhanced_node_wrapper import create_enhanced_logged_node
from utils.model_config import get_questionnaire_processor, is_dual_model_enabled
from dotenv import load_dotenv
import os
from datetime import datetime

# Import the node functions directly from the 'nodes' package
from nodes import (
    preflight_check,
    convert_pdf_to_markdown,
    load_and_prep_document,
    classify_and_validate_sentences,
    classify_reference_document,
    questionnaire_yaml_populator_node
)
from nodes.entity_extractor import extract_entities_from_document
from nodes.citation_critic import citation_critic_node, should_rerun_citations
from nodes.pdf_conversion_critic import pdf_conversion_critic_node, should_rerun_pdf_conversion
from nodes.classification_coverage_critic import classification_coverage_critic_node, should_rerun_classification
from nodes.questionnaire_completeness_critic import questionnaire_completeness_critic_node, should_rerun_questionnaire

# Set up initial state
initial_state = {
    # Inputs
    'questionnaire_path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                     "questionnaires", "contract_evaluation.yaml"),
    'target_document_path': '',  # Will be set by input
    'reference_document_path': '',  # Will be set by input
    'terminology_path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "terminology", "terms.yaml"),
    'baseline_summary': {},
    'spreadsheet_template_path': '',
    'output_path': '',
    
    # Processed Paths & Data
    'processed_document_path': '',
    'document_text': '',
    'document_sentences': [],
    'document_metadata': None,
    'reference_document_text': '',
    'reference_document_sentences': [],
    'terminology_data': [],
    'classified_sentences': [],
    'reference_classified_sentences': [],
    'extracted_data': {},
    'extracted_entities': {},
    'red_flag_analysis': '',
    'questionnaire_responses': {},
    
    # Model-specific responses (for future multi-model support)  
    'questionnaire_responses_granite': None,
    'model_metadata': None,
    
    # Final Output
    'final_spreadsheet_row': {},
    
    # Error Tracking & Quality
    'processing_errors': [],
    'quality_metrics': {},
    'overall_quality_score': None,
    'manual_review_required': False,
    'processing_warnings': [],
    
    # Workflow State
    'workflow_status': 'running',
    'last_successful_node': None,
    'current_processing_node': None,
    'checkpoints': [],
    'processing_start_time': datetime.now().isoformat(),
    'processing_metadata': {},
    
    # Conversion Info
    'conversion_metadata': None,
    'fallback_strategies_used': [],
    'api_call_metrics': None,
    
    # Classification
    'classification_metrics': None,
    
    # Preflight Check
    'preflight_results': None,
    'rules_path': '', # Added for rules path
    
    # Citation Critic
    'citation_validation_results': None,
    'citation_issues_found': [],
    'needs_citation_rerun': False,
    'citation_critic_attempts': 0,
    'citation_critic_recommendations': [],
    
    # PDF Conversion Critic
    'pdf_validation_results': None,
    'needs_pdf_rerun': False,
    'pdf_critic_attempts': 0,
    'pdf_retry_config': {},
    
    # Classification Coverage Critic
    'classification_validation_results': None,
    'needs_classification_rerun': False,
    'classification_critic_attempts': 0,
    'classification_retry_config': {},
    
    # Questionnaire Completeness Critic
    'questionnaire_validation_results': None,
    'needs_questionnaire_rerun': False,
    'questionnaire_critic_attempts': 0,
    'questionnaire_retry_config': {}
}

def decide_to_convert(state: ContractAnalysisState) -> str:
    """Determines the starting point of the graph based on file extension."""
    # Initialize state if not already done
    if not state.get('processing_start_time'):
        # Initialize with default values
        state.update({
            'questionnaire_path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                         "questionnaires", "contract_evaluation.yaml"),
            'target_document_path': state['target_document_path'],  # Preserve input path
            'reference_document_path': state.get('reference_document_path', ''),
            'terminology_path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "terminology", "terms.yaml"),
            'baseline_summary': {},
            'spreadsheet_template_path': '',
            'output_path': '',
            'processed_document_path': '',
            'document_text': '',
            'document_sentences': [],
            'document_metadata': None,
            'reference_document_text': '',
            'reference_document_sentences': [],
            'terminology_data': [],
            'classified_sentences': [],
            'reference_classified_sentences': [],
            'extracted_data': {},
            'extracted_entities': {},
            'red_flag_analysis': '',
            'questionnaire_responses': {},
            'questionnaire_responses_granite': None,
            'model_metadata': None,
            'final_spreadsheet_row': {},
            'processing_errors': [],
            'quality_metrics': {},
            'overall_quality_score': None,
            'manual_review_required': False,
            'processing_warnings': [],
            'workflow_status': 'running',
            'last_successful_node': None,
            'current_processing_node': None,
            'checkpoints': [],
            'processing_start_time': datetime.now().isoformat(),
            'processing_metadata': {},
            'conversion_metadata': None,
            'fallback_strategies_used': [],
            'api_call_metrics': None,
            'classification_metrics': None,
            'preflight_results': None,
            'rules_path': '' # Added for rules path
        })
        # Propagate rules path from environment if provided
        rules_path_env = os.getenv('RULES_PATH', '')
        if rules_path_env:
            state['rules_path'] = rules_path_env
    
    # Return the next node based on file extension
    return "pdf_converter" if state['target_document_path'].lower().endswith('.pdf') else "loader"

def decide_rules_processing(state: ContractAnalysisState) -> str:
    """Determines whether to process rules based on configuration."""
    rules_enabled = os.getenv('RULES_MODE_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
    
    # Check if rules are enabled AND a rules path exists
    if rules_enabled and (state.get('rules_path') or os.getenv('RULES_PATH')):
        print("Rules processing ENABLED - routing to rules_loader")
        return "rules_loader"
    else:
        print("Rules processing DISABLED or no rules path - skipping to reference_classifier")
        return "reference_classifier"

def build_graph():
    """Builds and compiles the LangGraph workflow with enhanced state logging."""
    # Initialize state logging
    # Load only the agent-local .env (monorepo-safe)
    agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agent_env_path = os.path.join(agent_dir, ".env")
    
    # Store the current RULES_MODE_ENABLED value if it was explicitly set
    rules_mode_override = os.environ.get('RULES_MODE_ENABLED')
    
    if os.path.exists(agent_env_path):
        load_dotenv(agent_env_path, override=True)
    
    # If RULES_MODE_ENABLED was explicitly set before loading .env, restore it
    if rules_mode_override is not None:
        os.environ['RULES_MODE_ENABLED'] = rules_mode_override
    
    # Use selective logging to reduce file count
    use_selective = os.getenv('USE_SELECTIVE_LOGGING', 'true').lower() in ('1', 'true', 'yes', 'on')
    
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(app_root, "logs")
    if use_selective:
        initialize_selective_logger(logs_dir=logs_dir)
        print("Using SELECTIVE state logging (milestones only)")
    else:
        initialize_state_logger(logs_dir=logs_dir)
        initialize_enhanced_logger(logs_dir=logs_dir)
        print("Using FULL state logging (all nodes)")
    
    workflow = StateGraph(ContractAnalysisState)

    # Get the appropriate questionnaire processor based on configuration
    questionnaire_processor_func = get_questionnaire_processor()
    
    # Determine processor type for logging
    from utils.model_config import model_config
    if os.getenv('USE_ENHANCED_ATTRIBUTION', '').lower() in ('1', 'true', 'yes', 'on'):
        processor_name = "questionnaire_processor_enhanced"
    elif model_config.use_tuned_model:
        processor_name = "questionnaire_processor_tuned"
    elif is_dual_model_enabled():
        processor_name = "questionnaire_processor_dual"
    else:
        processor_name = "questionnaire_processor"
    print(f"Using processor: {processor_name}")

    # Wrap nodes with enhanced logging functionality
    # Use enhanced logging for better state tracking
    logged_preflight_check = create_enhanced_logged_node(preflight_check, "preflight_check")
    logged_pdf_converter = create_enhanced_logged_node(convert_pdf_to_markdown, "pdf_converter")
    logged_loader = create_enhanced_logged_node(load_and_prep_document, "loader")
    logged_entity_extractor = create_enhanced_logged_node(extract_entities_from_document, "entity_extractor")
    logged_target_classifier = create_enhanced_logged_node(classify_and_validate_sentences, "target_classifier")
    logged_reference_classifier = create_enhanced_logged_node(classify_reference_document, "reference_classifier")
    logged_questionnaire_processor = create_enhanced_logged_node(questionnaire_processor_func, processor_name)
    logged_yaml_populator = create_enhanced_logged_node(questionnaire_yaml_populator_node, "yaml_populator")
    
    # Critic nodes
    logged_pdf_critic = create_enhanced_logged_node(pdf_conversion_critic_node, "pdf_critic")
    logged_classification_critic = create_enhanced_logged_node(classification_coverage_critic_node, "classification_critic")
    logged_questionnaire_critic = create_enhanced_logged_node(questionnaire_completeness_critic_node, "questionnaire_critic")
    logged_citation_critic = create_enhanced_logged_node(citation_critic_node, "citation_critic")

    # Rules mode: conditional based on RULES_MODE_ENABLED
    # Check if rules should be loaded
    rules_enabled = os.getenv('RULES_MODE_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
    
    if rules_enabled:
        print("Rules mode ENABLED - loading rules nodes")
        from nodes import rules_loader
        from nodes.rule_compliance_evaluator import evaluate_document_compliance
        logged_rules_loader = create_enhanced_logged_node(rules_loader, "rules_loader")
        logged_rule_compliance_evaluator = create_enhanced_logged_node(evaluate_document_compliance, "rule_compliance_evaluator")
    else:
        print("Rules mode DISABLED - rules nodes will not be loaded")
        logged_rules_loader = None
        logged_rule_compliance_evaluator = None

    # Add logged nodes to workflow
    workflow.add_node("preflight_check", logged_preflight_check)
    workflow.add_node("pdf_converter", logged_pdf_converter)
    workflow.add_node("loader", logged_loader)
    workflow.add_node("entity_extractor", logged_entity_extractor)
    workflow.add_node("target_classifier", logged_target_classifier)
    workflow.add_node("reference_classifier", logged_reference_classifier)
    workflow.add_node("questionnaire_processor", logged_questionnaire_processor)
    
    # Add all critic nodes
    workflow.add_node("pdf_critic", logged_pdf_critic)
    workflow.add_node("classification_critic", logged_classification_critic)
    workflow.add_node("questionnaire_critic", logged_questionnaire_critic)
    workflow.add_node("citation_critic", logged_citation_critic)
    
    workflow.add_node("yaml_populator", logged_yaml_populator)
    
    # Only add rules nodes if rules are enabled
    if rules_enabled:
        workflow.add_node("rules_loader", logged_rules_loader)
        workflow.add_node("rule_compliance_evaluator", logged_rule_compliance_evaluator)

    # Define the execution flow
    workflow.set_entry_point("preflight_check")
    workflow.add_conditional_edges(
        "preflight_check",
        decide_to_convert,
        {
            "pdf_converter": "pdf_converter",
            "loader": "loader"
        }
    )
    # PDF conversion with critic
    workflow.add_edge("pdf_converter", "pdf_critic")
    workflow.add_conditional_edges(
        "pdf_critic",
        should_rerun_pdf_conversion,
        {
            "retry_conversion": "pdf_converter",
            "continue": "loader"
        }
    )
    
    workflow.add_edge("loader", "entity_extractor")
    workflow.add_edge("entity_extractor", "target_classifier")
    
    # Classification critic after target classifier
    workflow.add_edge("target_classifier", "classification_critic")
    workflow.add_conditional_edges(
        "classification_critic",
        should_rerun_classification,
        {
            "retry_classification": "target_classifier",
            "continue": "rules_loader" if rules_enabled else "reference_classifier"
        }
    )
    
    # Conditional routing for rules processing
    if rules_enabled:
        # Classification critic continues to rules_loader when rules enabled
        workflow.add_edge("rules_loader", "rule_compliance_evaluator")
        workflow.add_edge("rule_compliance_evaluator", "reference_classifier")
    
    workflow.add_edge("reference_classifier", "questionnaire_processor")
    
    # Questionnaire critic after questionnaire processor
    workflow.add_edge("questionnaire_processor", "questionnaire_critic")
    workflow.add_conditional_edges(
        "questionnaire_critic",
        should_rerun_questionnaire,
        {
            "retry_questionnaire": "questionnaire_processor",
            "continue": "citation_critic"
        }
    )
    
    # Citation critic is last before YAML output
    
    # Conditional edge from citation critic
    workflow.add_conditional_edges(
        "citation_critic",
        should_rerun_citations,
        {
            "rerun_classification": "target_classifier",  # Go back to classification if issues found
            "continue": "yaml_populator"  # Continue to YAML output if validation passed
        }
    )
    
    workflow.add_edge("yaml_populator", END)

    # Compile the graph
    app = workflow.compile()
    return app