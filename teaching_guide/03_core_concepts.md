# Module 3: Core Concepts

## LangGraph Fundamentals

### What is LangGraph?

LangGraph is a framework for building stateful, multi-agent applications with Large Language Models (LLMs). It provides:
- **State Management**: Centralized state that flows through nodes
- **Graph Structure**: Nodes connected by edges with conditional routing
- **Checkpointing**: Save and resume workflow execution
- **Observability**: Built-in logging and tracing

### Our Implementation

```python
from langgraph.graph import StateGraph, END
from workflows.state import ContractAnalysisState

# Create graph with our state type
workflow = StateGraph(ContractAnalysisState)

# Add nodes
workflow.add_node("classifier", document_classifier)
workflow.add_node("evaluator", rule_evaluator)

# Add edges
workflow.add_edge("classifier", "evaluator")
workflow.add_conditional_edges(
    "evaluator",
    should_continue,  # Decision function
    {
        "continue": "next_node",
        "retry": "classifier",
        "end": END
    }
)
```

## State Management

### The State Object

The state is the central data structure that flows through the workflow:

```python
class ContractAnalysisState(TypedDict):
    # Input paths
    target_document_path: str
    reference_document_path: str
    rules_path: Optional[str]
    
    # Document content
    target_sentences: List[Dict[str, Any]]
    target_document_text: str
    
    # Processing results
    classified_sentences: List[Dict[str, Any]]
    rule_compliance_results: List[Dict[str, Any]]
    questionnaire_results: Dict[str, Any]
    
    # Critic feedback
    citation_quality_score: float
    should_reclassify: bool
    
    # Metadata
    run_id: str
    processing_start_time: str
    errors: List[str]
```

### State Updates

Each node returns updates to merge into the state:

```python
def classifier_node(state: Dict) -> Dict:
    sentences = state['target_sentences']
    
    # Process sentences
    classified = classify_sentences(sentences)
    
    # Return state updates
    return {
        'classified_sentences': classified,
        'classification_completed': True
    }
```

### State Persistence

The state is saved at key points:

```python
from utils.classification_output_writer import save_workflow_state

# After each node
save_workflow_state(
    state=state,
    status="running",
    node_name="classifier",
    run_id=state['run_id']
)

# On error
save_workflow_state(
    state=state,
    status="error",
    node_name="classifier",
    run_id=state['run_id'],
    error=str(exception)
)
```

## Node Architecture

### BaseNode Pattern

All class-based nodes inherit from BaseNode:

```python
from nodes.base_node import BaseNode

class DocumentClassifier(BaseNode):
    def __init__(self):
        super().__init__("Document Classifier")
    
    def process(self, state: Dict) -> Dict:
        # Report progress
        self.report_progress("Starting classification...")
        
        # Node logic
        results = self.classify_documents(state)
        
        # Report completion
        self.report_progress("Classification complete")
        
        return {"classified_sentences": results}
```

### Enhanced Node Wrapper

Function-based nodes use the wrapper for automatic logging:

```python
from utils.enhanced_node_wrapper import enhanced_logged_node

@enhanced_logged_node("rule_evaluator")
def evaluate_rules(state: Dict) -> Dict:
    # Automatic:
    # - Progress reporting
    # - Error handling
    # - State saving
    # - Logging
    
    results = process_rules(state)
    return {"rule_compliance_results": results}
```

### Node Responsibilities

Each node has specific responsibilities:

| Node | Input | Processing | Output |
|------|-------|------------|--------|
| loader | File paths | Load and parse documents | Sentences, text |
| classifier | Sentences | Categorize each sentence | Classifications |
| rule_evaluator | Rules, document | Check compliance | Compliance results |
| questionnaire | Questions, document | Answer questions | Q&A with citations |

## Critic Validation Pattern

### What are Critics?

Critics are specialized nodes that validate outputs and can trigger reruns:

```python
def citation_critic(state: Dict) -> Dict:
    # Evaluate quality
    quality_score = evaluate_citations(state)
    
    # Make decision
    if quality_score < 0.7:
        return {
            "citation_quality_score": quality_score,
            "next": "reclassify"  # Trigger rerun
        }
    
    return {"citation_quality_score": quality_score}
```

### Critic Types

#### 1. Citation Critic
- **Purpose**: Ensure citation quality
- **Metrics**: Coverage, accuracy, specificity
- **Actions**: Can trigger reclassification

#### 2. Coverage Critic
- **Purpose**: Verify complete classification
- **Metrics**: Percentage of sentences classified
- **Actions**: Can request additional processing

#### 3. Compliance Critic
- **Purpose**: Validate rule evaluations
- **Metrics**: Evidence quality, consistency
- **Actions**: Can trigger re-evaluation

#### 4. Completeness Critic
- **Purpose**: Check questionnaire answers
- **Metrics**: Answer completeness, citation presence
- **Actions**: Can request reprocessing

### Conditional Routing

Critics enable dynamic workflow paths:

```python
def route_after_critic(state: Dict) -> str:
    if state.get('should_reclassify'):
        return "reclassify"
    elif state.get('needs_more_evidence'):
        return "gather_evidence"
    else:
        return "continue"

workflow.add_conditional_edges(
    "citation_critic",
    route_after_critic,
    {
        "reclassify": "classifier",
        "gather_evidence": "evidence_collector",
        "continue": "output_generator"
    }
)
```

## Prompt Management

### YAML Template Structure

Prompts are externalized for maintainability:

```yaml
# prompts/classifier.yaml
name: "Document Classifier"
description: "Classifies sentences into categories"
version: "1.0"

template: |
  You are a legal document analyst. Classify each sentence.
  
  Sentence: {sentence}
  Context: {context}
  
  Categories:
  - obligation: Legal obligations and requirements
  - term: Contract terms and conditions
  - warranty: Warranties and representations
  - liability: Liability and indemnification
  
  Respond with JSON:
  {
    "classes": ["primary_class", "secondary_class"],
    "confidence": 0.95
  }

variables:
  - name: sentence
    type: string
    required: true
  - name: context
    type: string
    required: false

parameters:
  temperature: 0.3
  max_tokens: 200
```

### Loading and Using Prompts

```python
from utils.prompt_manager import load_prompt

# Load prompt
prompt_config = load_prompt("classifier")

# Format with variables
formatted_prompt = prompt_config['template'].format(
    sentence="The vendor shall provide support.",
    context="Section on service obligations"
)

# Use with model
response = model.generate(
    formatted_prompt,
    temperature=prompt_config['parameters']['temperature']
)
```

## Model Configuration

### Multi-Model Architecture

The system supports multiple models for different purposes:

```python
# utils/model_config.py
def get_model_for_task(task: str):
    if task == "classification":
        return get_primary_model()  # Granite
    elif task == "validation":
        return get_validation_model()  # Mixtral
    elif task == "development":
        return get_local_model()  # Ollama
```

### Model Abstraction

All models implement a common interface:

```python
class BaseModel:
    def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError
    
    def generate_json(self, prompt: str, **kwargs) -> Dict:
        response = self.generate(prompt, **kwargs)
        return json.loads(response)

class GraniteModel(BaseModel):
    def generate(self, prompt: str, **kwargs) -> str:
        # Granite-specific implementation
        return self.client.complete(prompt, **kwargs)
```

## Output Management

### File Organization

Outputs are organized by run:

```
data/output/runs/run_20250106_120000/
├── workflow_state.json         # Complete state
├── classified_sentences.jsonl  # Classifications
├── rule_evaluation_results.json # Rule findings
├── questionnaire_results.yaml  # Q&A responses
├── analysis_report.xlsx        # Excel report
└── analysis_summary.md         # Summary
```

### Output Writers

Specialized writers for each format:

```python
# JSONL for streaming data
def save_classification_results(results, run_id):
    path = f"data/output/runs/run_{run_id}/classified_sentences.jsonl"
    with open(path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')

# State file (overwritten)
def save_workflow_state(state, status, node_name, run_id):
    path = f"data/output/runs/run_{run_id}/workflow_state.json"
    with open(path, 'w') as f:
        json.dump({
            'metadata': {
                'status': status,
                'last_node': node_name,
                'timestamp': datetime.now().isoformat()
            },
            'state': state
        }, f, indent=2)
```

## Error Handling

### Three-Layer Strategy

#### 1. Node Level
```python
try:
    result = process_node(state)
except Exception as e:
    log_error(f"Node failed: {e}")
    save_error_state(state, e)
    raise  # Propagate to workflow
```

#### 2. Workflow Level
```python
try:
    final_state = workflow.invoke(initial_state)
except NodeError as e:
    # Graceful degradation
    return handle_partial_results(e.partial_state)
```

#### 3. System Level
```python
def main():
    try:
        run_workflow()
    except Exception as e:
        # Last resort error handling
        log_critical_error(e)
        notify_administrators(e)
        sys.exit(1)
```

## Performance Considerations

### Caching Strategy

```python
# Classification cache
cache = {}

def classify_with_cache(sentence: str) -> Dict:
    cache_key = hash(sentence)
    
    if cache_key in cache:
        return cache[cache_key]
    
    result = classify_sentence(sentence)
    cache[cache_key] = result
    return result
```

### Batch Processing

```python
def classify_batch(sentences: List[str]) -> List[Dict]:
    # Process multiple sentences in one API call
    batch_size = 10
    results = []
    
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i+batch_size]
        batch_results = model.classify_batch(batch)
        results.extend(batch_results)
    
    return results
```

## Key Patterns Summary

### 1. State-Driven Workflow
- Central state object
- Nodes update state
- State persisted throughout

### 2. Critic Validation
- Quality gates
- Conditional reruns
- Progressive improvement

### 3. Separation of Concerns
- Independent nodes
- Single responsibility
- Loose coupling

### 4. Error Resilience
- Multi-layer handling
- State preservation
- Graceful degradation

## Exercises

### Exercise 1: Create a Custom Node
Create a node that counts legal terms in the document.

### Exercise 2: Implement a Critic
Build a critic that validates minimum citation requirements.

### Exercise 3: Add State Field
Extend the state to track processing time per node.

## Next Steps

With core concepts understood:
1. Proceed to [04_workflow_walkthrough.md](04_workflow_walkthrough.md) for detailed node analysis
2. Try modifying a simple node
3. Experiment with critic thresholds

## Key Takeaways

1. **LangGraph** provides the workflow orchestration framework
2. **State management** ensures data flows correctly through nodes
3. **Critics** enable quality control and dynamic routing
4. **Prompts** are externalized for easy modification
5. **Error handling** occurs at multiple levels for resilience