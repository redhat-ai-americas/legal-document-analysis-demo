# ARCHITECTURE.md

## System Overview

The Legal Document Analysis system is a sophisticated LangGraph-based pipeline that performs multi-stage contract analysis with critic validation. It systematically classifies document content, evaluates rule compliance, answers questionnaires, and generates comprehensive outputs with page-level citations.

## Core Architecture Principles

### 1. State-Driven Workflow
The system uses a centralized state object that flows through all nodes, accumulating results and enabling conditional routing based on validation outcomes.

### 2. Critic Validation Pattern
Multiple critic agents validate outputs at key stages and can trigger targeted reruns to ensure quality.

### 3. Separation of Concerns
Rules evaluation is separated from questionnaire processing to avoid redundancy and enable independent scaling.

### 4. Single State File Approach
One workflow state file is maintained and overwritten throughout execution, providing a complete snapshot at any point.

## Workflow Architecture

### Main Workflow Pipeline

```
START 
  ↓
[Preflight & Validation]
  ├─→ preflight_check
  ├─→ convert_pdfs_if_needed (conditional)
  └─→ loader
  ↓
[Entity & Classification]  
  ├─→ entity_extraction
  └─→ document_classifier
  ↓
[Rule Evaluation] (conditional based on RULES_MODE_ENABLED)
  └─→ rule_compliance_evaluator
  ↓
[Questionnaire Processing]
  └─→ questionnaire_processor
  ↓
[Critic Validation Loop]
  ├─→ citation_critic ──────────┐
  ├─→ coverage_critic          │ (can trigger reruns)
  ├─→ compliance_critic        │
  └─→ completeness_critic ─────┘
  ↓
[Output Generation]
  ├─→ yaml_output_generator
  ├─→ excel_output_generator
  └─→ markdown_summary_generator
  ↓
END
```

### Conditional Routing

Critics can trigger specific reruns based on validation results:

```python
# Example: Citation critic triggers reclassification
if citation_quality_score < 0.7:
    return {"next": "reclassify_documents"}
    
# Example: Coverage critic triggers additional classification
if uncovered_sections > threshold:
    return {"next": "classify_remaining"}
```

## State Management

### ContractAnalysisState Structure

```python
class ContractAnalysisState(TypedDict):
    # Core Paths
    target_document_path: str
    reference_document_path: str  
    rules_path: Optional[str]
    
    # Document Content
    target_sentences: List[Dict[str, Any]]
    reference_sentences: List[Dict[str, Any]]
    
    # Classification Results
    classified_sentences: List[Dict[str, Any]]
    classification_completed: bool
    
    # Rule Evaluation Results
    rule_compliance_results: List[Dict[str, Any]]
    rules_evaluated: bool
    
    # Questionnaire Results
    questionnaire_results: Dict[str, Any]
    questionnaire_completed: bool
    
    # Critic Feedback
    citation_quality_score: float
    coverage_score: float
    compliance_score: float
    should_reclassify: bool
    should_rerun_rules: bool
    
    # Workflow Metadata
    run_id: str
    processing_start_time: str
    current_node: str
    workflow_status: str
    errors: List[str]
```

### State Persistence

The state is saved to `workflow_state.json` at three key points:
1. **After each node completion** - Captures progress
2. **On error** - Preserves context for debugging
3. **On workflow completion** - Final results

```python
save_workflow_state(
    state=state,
    status="running|completed|error",
    node_name="current_node",
    run_id="20250106_120000",
    error="error_message"  # Only on errors
)
```

## Node Architecture

### BaseNode Pattern

All class-based nodes inherit from BaseNode:

```python
class DocumentClassifier(BaseNode):
    def __init__(self):
        super().__init__("Document Classifier")
        
    def process(self, state: Dict) -> Dict:
        self.report_progress("Classifying sentences...")
        
        # Load prompt from YAML
        prompt = load_prompt("classifier")
        
        # Process with model
        results = self.classify_sentences(state)
        
        # Save outputs
        save_classification_results(results, state['run_id'])
        
        return {
            "classified_sentences": results,
            "classification_completed": True
        }
```

### Enhanced Node Wrapper

Function-based nodes use the enhanced wrapper:

```python
@enhanced_logged_node("rule_evaluator")
def evaluate_rules(state: Dict) -> Dict:
    # Automatic logging and error handling
    # State saved on error
    results = process_rules(state)
    save_rule_evaluation_results(results, state['run_id'])
    return {"rule_compliance_results": results}
```

## Output File Structure

### Inspection Files (data/output/runs/run_[timestamp]/)

1. **workflow_state.json** - Complete workflow state
   ```json
   {
     "metadata": {
       "status": "completed",
       "last_node": "output_generator",
       "timestamp": "2025-01-06T12:00:00"
     },
     "state_summary": {
       "classified_sentences": 150,
       "rules_evaluated": 12,
       "questionnaire_sections": 3
     },
     "state": { /* full state object */ }
   }
   ```

2. **classified_sentences.jsonl** - Line-delimited classification results
   ```json
   {"sentence_id": 1, "text": "...", "classes": ["term"], "confidence": 0.95}
   {"sentence_id": 2, "text": "...", "classes": ["obligation"], "confidence": 0.88}
   ```

3. **rule_evaluation_results.json** - Detailed rule findings
   ```json
   {
     "rules": [
       {
         "rule_id": "data_protection",
         "status": "compliant",
         "evidence": [/* citations */],
         "confidence": 0.92
       }
     ]
   }
   ```

### Report Files

1. **questionnaire_results.yaml** - Q&A with citations
2. **rule_compliance_results.yaml** - Rule summary
3. **analysis_report.xlsx** - Excel with dynamic columns
4. **analysis_summary.md** - Human-readable summary

## Prompt Management System

### YAML Template Structure

All prompts stored in `prompts/` directory:

```yaml
name: "Document Classifier"
description: "Classifies sentences into business/legal categories"
version: "1.0"

template: |
  You are analyzing a legal document. Classify each sentence.
  
  Sentence: {sentence}
  Document Context: {context}
  
  Categories:
  {categories}
  
  Return JSON: {"classes": [...], "confidence": 0.0-1.0}

variables:
  - name: sentence
    type: string
    required: true
  - name: context
    type: string
    required: false
  - name: categories
    type: list
    required: true

parameters:
  temperature: 0.3
  max_tokens: 200
```

### Prompt Loading

```python
from utils.prompt_manager import load_prompt

prompt = load_prompt("classifier")
formatted = prompt.format(
    sentence="The agreement shall commence...",
    categories=["term", "obligation", "warranty"]
)
```

## Model Configuration

### Multi-Model Support

The system supports multiple LLM backends configured via environment:

```python
# Primary Model (Required)
GRANITE_INSTRUCT_API_KEY=xxx
GRANITE_INSTRUCT_URL=https://api.endpoint
GRANITE_INSTRUCT_MODEL_NAME=granite-3b-instruct

# Validation Model (Optional)
MIXTRAL_API_KEY=xxx
MIXTRAL_URL=https://api.endpoint

# Local Model (Optional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Feature Flags
DUAL_MODEL_ENABLED=true  # Compare models
```

### Model Selection Logic

```python
def get_model(purpose="primary"):
    if purpose == "primary":
        return GraniteModel()
    elif purpose == "validation" and DUAL_MODEL_ENABLED:
        return MixtralModel()
    elif purpose == "local":
        return OllamaModel()
    return GraniteModel()  # Fallback
```

## Critic Agent Architecture

### Critic Validation Flow

1. **Input Validation** - Check state has required data
2. **Quality Assessment** - Evaluate output quality
3. **Decision Making** - Determine if rerun needed
4. **Routing** - Return next node or continue

### Example: Citation Critic

```python
def citation_critic(state: Dict) -> Dict:
    # Validate citations exist
    citations = extract_citations(state)
    
    # Calculate quality metrics
    coverage = calculate_coverage(citations, state['target_sentences'])
    accuracy = verify_citations(citations, state['page_anchors'])
    
    quality_score = (coverage * 0.6 + accuracy * 0.4)
    
    # Conditional routing
    if quality_score < 0.7:
        return {
            "citation_quality_score": quality_score,
            "should_reclassify": True,
            "next": "reclassify_with_focus"
        }
    
    return {"citation_quality_score": quality_score}
```

## Rule Compliance System

### Rule Definition Format

```yaml
rules:
  - id: data_protection
    description: "Verify data protection clauses"
    keywords: ["data", "privacy", "GDPR"]
    evaluation_criteria: |
      Check for:
      1. Data processing terms
      2. Privacy policy references
      3. Compliance statements
    severity: high
    
  - id: liability_limits
    description: "Check liability limitations"
    keywords: ["liability", "damages", "limitation"]
    evaluation_criteria: |
      Verify liability caps and exclusions
    severity: medium
```

### Rule Evaluation Process

1. **Rule Loading** - Parse rule definitions
2. **Document Scanning** - Find relevant sections
3. **Compliance Check** - Evaluate against criteria
4. **Evidence Collection** - Gather supporting citations
5. **Result Aggregation** - Compile findings

### Dynamic Excel Columns

Excel output automatically includes columns for each evaluated rule:

```python
def add_rule_columns(df, rule_results):
    for rule in rule_results:
        rule_id = rule['rule_id']
        status = 'Y' if rule['status'] == 'non_compliant' else 'N'
        df[f'Rule_{rule_id}'] = status
        df[f'Rule_{rule_id}_Evidence'] = rule.get('rationale', '')
```

## Performance Optimizations

### 1. Classification Caching
```python
# Cache classified sentences to avoid re-processing
cache_key = hash(sentence_text + model_name)
if cache_key in classification_cache:
    return classification_cache[cache_key]
```

### 2. Batch Processing
```python
# Process multiple sentences in one API call
batch_size = 10
for i in range(0, len(sentences), batch_size):
    batch = sentences[i:i+batch_size]
    results = classify_batch(batch)
```

### 3. Selective Logging
```python
# Only log major milestones in production
if USE_SELECTIVE_LOGGING:
    log_only_milestones()
else:
    log_all_state_changes()
```

### 4. Parallel Processing
```python
# Run independent critics concurrently
with ThreadPoolExecutor() as executor:
    futures = [
        executor.submit(citation_critic, state),
        executor.submit(coverage_critic, state),
        executor.submit(compliance_critic, state)
    ]
    results = [f.result() for f in futures]
```

## Error Handling Strategy

### Three-Level Error Handling

1. **Node Level** - Try/catch with state preservation
2. **Workflow Level** - Graceful degradation
3. **System Level** - Error aggregation and reporting

```python
# Node level
try:
    result = process_node(state)
except Exception as e:
    log_error(e)
    save_error_state(state, e)
    return {"error": str(e), "status": "failed"}

# Workflow level  
if state.get("status") == "failed":
    return handle_graceful_degradation(state)

# System level
aggregate_errors(state.get("errors", []))
```

## Testing Architecture

### Test Categories

1. **Unit Tests** - Individual node validation
2. **Integration Tests** - Workflow execution
3. **Critic Tests** - Validation logic
4. **Output Tests** - File generation
5. **Error Tests** - Failure handling

### Test Structure

```
tests/
├── unit/
│   ├── test_classifier.py
│   ├── test_rule_evaluator.py
│   └── test_questionnaire.py
├── integration/
│   ├── test_full_workflow.py
│   └── test_critic_reruns.py
├── critics/
│   ├── test_citation_critic.py
│   └── test_coverage_critic.py
└── fixtures/
    ├── sample_documents.py
    └── mock_responses.py
```

## Security Considerations

### Input Validation
- Path traversal prevention
- File type validation
- Size limits enforcement

### Data Protection
- No credentials in code
- Environment variable configuration
- Sanitized logging (no PII)

### Access Control
- API key validation
- Rate limiting support
- Audit logging

## Deployment Architecture

### Container Strategy
```dockerfile
FROM registry.redhat.io/ubi9/python-311
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "scripts/main.py"]
```

### Environment Configuration
```yaml
# OpenShift ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: legal-analysis-config
data:
  RULES_MODE_ENABLED: "true"
  USE_ENHANCED_ATTRIBUTION: "true"
  USE_TEMPLATE_EXCEL: "true"
```

### Scaling Considerations
- Stateless node design
- Redis for shared state
- Queue-based job processing
- Horizontal pod autoscaling

## Monitoring & Observability

### Metrics Collection
- Node execution times
- Model response latencies  
- Error rates by node
- Citation quality scores
- Rule compliance rates

### Logging Strategy
- Structured JSON logs
- Correlation IDs for tracing
- Log aggregation with ELK
- Alert on error patterns

### Health Checks
```python
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model_available": check_model_connection(),
        "disk_space": check_disk_space(),
        "memory_usage": get_memory_usage()
    }
```

## Future Architecture Enhancements

### Near-term
1. Streaming responses for real-time feedback
2. Incremental processing for large documents
3. Caching layer with Redis
4. Webhook notifications on completion

### Long-term
1. Multi-language support
2. Custom rule builder UI
3. ML-based rule suggestions
4. Document version tracking
5. Collaborative review features
6. Integration with contract management systems