from typing import TypedDict, List, Dict, Any, Optional

class ErrorInfo(TypedDict):
    """Information about errors encountered during processing."""
    error_id: str
    timestamp: str
    node_name: str
    error_type: str
    error_message: str
    severity: str
    recoverable: bool
    fallback_used: Optional[str]
    resolution_attempted: bool

class QualityMetrics(TypedDict):
    """Quality metrics for processing steps."""
    confidence_score: float
    validation_score: float
    needs_manual_review: bool
    review_reason: Optional[str]
    processing_method: str

class ClassifiedSentence(TypedDict):
    """Represents a single sentence and its validated classifications with quality metrics."""
    sentence: str
    classes: List[str]  # List of validated term names
    confidence: Optional[float]  # Overall confidence score
    classification_confidence: Optional[float]  # Classification step confidence
    validation_confidence: Optional[float]  # Validation step confidence
    needs_manual_review: Optional[bool]  # Flag for manual review
    review_reason: Optional[str]  # Reason for manual review
    error: Optional[str]  # Error message if processing failed
    processing_metadata: Optional[Dict[str, Any]]  # Additional processing info
    # Citation and reference information
    sentence_id: Optional[str]  # Unique identifier for the sentence
    page_number: Optional[int]  # Page number in source document
    section_name: Optional[str]  # Section/heading name
    location_info: Optional[Dict[str, Any]]  # Additional location metadata
    citations: Optional[List[str]]  # List of citation IDs

class ProcessingCheckpoint(TypedDict):
    """Checkpoint information for workflow resumption."""
    checkpoint_id: str
    timestamp: str
    node_name: str
    completed_nodes: List[str]
    current_state: Dict[str, Any]
    can_resume: bool

class ContractAnalysisState(TypedDict):
    """The central state object for the graph with enhanced error tracking and checkpointing."""
    
    # Inputs
    questionnaire_path: str  # Path to the questionnaire YAML file
    target_document_path: str
    reference_document_path: str
    terminology_path: str
    baseline_summary: Dict[str, str]
    spreadsheet_template_path: str
    output_path: str
    # Rules mode inputs
    rules_path: Optional[str]

    # Processed Paths & Data
    processed_document_path: str  # Path to the markdown file after conversion (optional)
    document_text: str
    document_sentences: List[str]
    document_metadata: Optional[Dict[str, Any]]  # Extracted document metadata
    reference_document_text: str
    reference_document_sentences: List[str]
    terminology_data: List[Dict[str, Any]]
    classified_sentences: List[ClassifiedSentence]
    reference_classified_sentences: List[ClassifiedSentence]
    extracted_data: Dict[str, Any]
    extracted_entities: Dict[str, Any]  # Deterministic entity extraction results
    red_flag_analysis: str
    questionnaire_responses: Dict[str, Any]
    # Rules results
    rule_compliance_results: Optional[List[Dict[str, Any]]]
    rule_violations: Optional[List[Dict[str, Any]]]
    compliance_metrics: Optional[Dict[str, Any]]
    
    # Model-specific questionnaire responses (future support for multiple models)
    questionnaire_responses_granite: Optional[Dict[str, Any]]
    
    # Model metadata (future support for model-specific tracking)
    model_metadata: Optional[Dict[str, Any]]
    
    # Final Output
    final_spreadsheet_row: Dict[str, Any]
    
    # Enhanced Error Tracking and Quality Metrics
    processing_errors: List[ErrorInfo]  # All errors encountered
    quality_metrics: Dict[str, QualityMetrics]  # Quality metrics by processing step
    overall_quality_score: Optional[float]  # Overall processing quality
    manual_review_required: bool  # Flag if manual review is needed
    processing_warnings: List[str]  # Non-critical warnings
    
    # Workflow Resilience and Checkpointing
    workflow_status: str  # Current workflow status (running, completed, failed, paused)
    last_successful_node: Optional[str]  # Last successfully completed node
    current_processing_node: Optional[str]  # Currently processing node
    checkpoints: List[ProcessingCheckpoint]  # Available checkpoints for resumption
    processing_start_time: str  # When processing started
    processing_metadata: Dict[str, Any]  # Additional processing metadata
    
    # Conversion and Fallback Information
    conversion_metadata: Optional[Dict[str, Any]]  # PDF conversion metadata if applicable
    fallback_strategies_used: List[str]  # List of fallback strategies used
    api_call_metrics: Optional[Dict[str, Any]]  # API usage statistics
    
    # Classification Enhancement
    classification_metrics: Optional[Dict[str, Any]]  # Detailed classification metrics
    
    # Preflight Check Results
    preflight_results: Optional[Dict[str, Any]]  # Model endpoint connectivity test results