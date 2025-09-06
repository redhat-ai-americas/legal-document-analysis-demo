# API Reference

This document provides detailed API reference for the Contract Analysis system components.

## Core Workflow Functions

### `workflows.graph_builder`

#### `build_graph()`
Builds and compiles the LangGraph workflow with state logging.

**Returns:**
- `CompiledGraph`: The compiled workflow graph ready for execution

**Example:**
```python
from workflows.graph_builder import build_graph

workflow = build_graph()
result = workflow.invoke({
    'target_document_path': 'contract.pdf',
    'reference_document_path': 'reference.pdf'
})
```

#### `decide_to_convert(state: ContractAnalysisState) -> str`
Determines the starting point of the graph based on file extension.

**Parameters:**
- `state`: Current workflow state

**Returns:**
- `str`: Next node name ("pdf_converter" or "loader")

## Document Processing Nodes

### `nodes.pdf_to_markdown`

#### `convert_pdf_to_markdown(state: ContractAnalysisState) -> dict`
Converts PDF documents to markdown format for processing.

**Parameters:**
- `state`: Workflow state containing `target_document_path`

**Returns:**
- `dict`: Updated state with `processed_document_path` and `conversion_metadata`

**State Updates:**
- `processed_document_path`: Path to converted markdown file
- `conversion_metadata`: Conversion statistics and metadata

### `nodes.document_loader`

#### `load_and_prep_document(state: ContractAnalysisState) -> dict`
Loads and preprocesses documents into analyzable sentences.

**Parameters:**
- `state`: Workflow state with document paths

**Returns:**
- `dict`: Updated state with processed document content

**State Updates:**
- `document_text`: Full document text
- `document_sentences`: List of processed sentences
- `reference_document_text`: Reference document text
- `reference_document_sentences`: Reference document sentences

### `nodes.entity_extractor`

#### `extract_entities_from_document(state: ContractAnalysisState) -> dict`
Extracts structured entities from document content.

**Parameters:**
- `state`: Workflow state with document content

**Returns:**
- `dict`: Updated state with extracted entities

**State Updates:**
- `extracted_entities`: Dictionary of extracted entities
  - `parties`: Contract parties
  - `dates`: Important dates
  - `terms`: Key terms and conditions

### `nodes.document_classifier`

#### `classify_and_validate_sentences(state: ContractAnalysisState) -> dict`
Classifies sentences from the target contract document.

**Parameters:**
- `state`: Workflow state with document sentences

**Returns:**
- `dict`: Updated state with classified sentences

**State Updates:**
- `classified_sentences`: List of classified sentences with terminology mappings
- `classification_metrics`: Classification performance metrics

#### `classify_reference_document(state: ContractAnalysisState) -> dict`
Classifies sentences from the reference contract document.

**Parameters:**
- `state`: Workflow state with reference document content

**Returns:**
- `dict`: Updated state with classified reference sentences

**State Updates:**
- `reference_classified_sentences`: Classified reference document sentences

## Questionnaire Processing

### `nodes.questionnaire_processor`

#### `process_questionnaire(state: ContractAnalysisState) -> dict`
Processes questionnaire with single model validation.

**Parameters:**
- `state`: Workflow state with classified sentences

**Returns:**
- `dict`: Updated state with questionnaire responses

**State Updates:**
- `questionnaire_responses`: Dictionary of question-answer pairs

### `nodes.questionnaire_processor_dual`

#### `process_questionnaire_dual(state: ContractAnalysisState) -> dict`
Processes questionnaire with dual model validation (Granite + Mixtral).

**Parameters:**
- `state`: Workflow state with classified sentences

**Returns:**
- `dict`: Updated state with dual model responses

**State Updates:**
- `questionnaire_responses_granite`: Granite model responses
- `questionnaire_responses_ollama`: Mixtral model responses
- `model_comparison`: Model agreement analysis
- `questionnaire_responses`: Final consolidated responses

### `nodes.questionnaire_yaml_populator`

#### `questionnaire_yaml_populator_node(state: ContractAnalysisState) -> dict`
Generates structured outputs including template Excel files.

**Parameters:**
- `state`: Workflow state with questionnaire responses

**Returns:**
- `dict`: Updated state with output file paths

**State Updates:**
- `final_spreadsheet_row`: Structured data for spreadsheet
- `output_path`: Path to generated outputs

## Template Integration

### `utils.template_excel_writer`

#### `TemplateWriter` Class

##### `extract_y_n_and_details(response_text: str) -> dict`
Extracts Y/N determination and details from LLM response.

**Parameters:**
- `response_text`: Natural language response from LLM

**Returns:**
- `dict`: Contains "y_n" and "details" keys

**Example:**
```python
from utils.template_excel_writer import TemplateWriter

writer = TemplateWriter()
result = writer.extract_y_n_and_details("The contract does not specify any source code access provisions.")
# Returns: {"y_n": "N", "details": "The contract does not specify any source code access provisions."}
```

##### `map_questionnaire_to_template_row(questionnaire_responses: dict) -> dict`
Maps questionnaire responses to template structure.

**Parameters:**
- `questionnaire_responses`: Dictionary of question responses

**Returns:**
- `dict`: template row data

##### `create_template_excel(data: dict, output_path: str) -> str`
Creates individual template Excel file.

**Parameters:**
- `data`: Template row data
- `output_path`: Output file path

**Returns:**
- `str`: Path to created Excel file

##### `update_master_template_excel(data: dict, master_path: str) -> str`
Updates master comparison Excel file.

**Parameters:**
- `data`: Template row data
- `master_path`: Master file path

**Returns:**
- `str`: Path to updated master file

### `utils.output_organizer`

#### `OutputOrganizer` Class

##### `create_organized_outputs(state: ContractAnalysisState, use_template: bool = True) -> dict`
Creates organized, structured outputs in multiple formats.

**Parameters:**
- `state`: Complete workflow state
- `use_template`: Whether to generate template Excel

**Returns:**
- `dict`: Output file paths and metadata

## Utility Functions

### `utils.model_config`

#### `get_questionnaire_processor() -> callable`
Returns the appropriate questionnaire processor based on configuration.

**Returns:**
- `callable`: Questionnaire processor function

#### `is_dual_model_enabled() -> bool`
Checks if dual model processing is enabled.

**Returns:**
- `bool`: True if dual model is enabled

### `utils.log_viewer`

#### `LogViewer` Class

##### `view_latest_run(errors_only: bool = False) -> dict`
Views the latest run logs.

**Parameters:**
- `errors_only`: Show only error entries

**Returns:**
- `dict`: Log data

##### `view_run(run_id: str, node: str = None) -> dict`
Views specific run logs.

**Parameters:**
- `run_id`: Run identifier
- `node`: Specific node to view (optional)

**Returns:**
- `dict`: Log data for specified run/node

### `utils.granite_client`

#### `GraniteClient` Class

##### `call_granite(prompt: str, max_tokens: int = 512) -> str`
Makes API call to Granite model.

**Parameters:**
- `prompt`: Input prompt
- `max_tokens`: Maximum response tokens

**Returns:**
- `str`: Model response

**Raises:**
- `GraniteServerError`: On API failures
- `GraniteRateLimitError`: On rate limit exceeded

### `utils.ollama_client`

#### `OllamaClient` Class

##### `call_ollama(prompt: str, model: str = "mixtral:8x7b-instruct-v0.1") -> str`
Makes API call to Ollama/Mixtral model.

**Parameters:**
- `prompt`: Input prompt
- `model`: Model identifier

**Returns:**
- `str`: Model response

## State Management

### `workflows.state`

#### `ContractAnalysisState` TypedDict
Central state object containing all workflow data.

**Key Fields:**
- `target_document_path`: Path to target contract
- `reference_document_path`: Path to reference contract
- `document_sentences`: Processed target sentences
- `classified_sentences`: Classified target sentences
- `questionnaire_responses`: Final Q&A responses
- `extracted_entities`: Extracted structured data
- `quality_metrics`: Processing quality metrics

## Error Handling

### Exception Classes

#### `GraniteServerError`
Raised when Granite API returns server errors.

#### `GraniteRateLimitError`
Raised when Granite API rate limits are exceeded.

#### `ClassificationError`
Raised when sentence classification fails.

#### `ProcessingError`
Generic processing error for workflow failures.

## Configuration Classes

### `utils.model_config.ModelConfig`

#### Attributes:
- `use_tuned_model`: Boolean for tuned model usage
- `enable_dual_model`: Boolean for dual model validation
- `granite_model`: Granite model identifier
- `mixtral_model`: Mixtral model identifier

## Batch Processing

### `batch_process`

#### `process_batch(input_dir: str, reference_file: str) -> dict`
Processes multiple documents in batch mode.

**Parameters:**
- `input_dir`: Directory containing contracts
- `reference_file`: Reference contract path

**Returns:**
- `dict`: Batch processing results and statistics

## Testing Utilities

### Test Functions

#### `test_questionnaire.test_questionnaire_processing()`
Tests questionnaire processing functionality.

#### `test_classifier_granite.test_classification()`
Tests Granite-based classification.

#### `demo_template.demonstrate_template()`
Demonstrates template functionality with sample data.

## Example Usage

### Basic Workflow
```python
from workflows.graph_builder import build_graph

# Build workflow
workflow = build_graph()

# Process single document
result = workflow.invoke({
    'target_document_path': 'contract.pdf',
    'reference_document_path': 'reference.pdf'
})

# Access results
print(result['questionnaire_responses'])
print(result['output_path'])
```

### Template Generation
```python
from utils.template_excel_writer import TemplateWriter

writer = TemplateWriter()
template_data = writer.map_questionnaire_to_template_row(responses)
excel_path = writer.create_template_excel(template_data, "output.xlsx")
```

### Batch Processing
```python
from batch_process import process_batch

results = process_batch("./contracts/", "reference.pdf")
print(f"Processed {results['total_documents']} documents")
```

## Error Handling Example

```python
from utils.granite_client import GraniteClient, GraniteServerError

try:
    client = GraniteClient()
    response = client.call_granite("Analyze this contract clause...")
except GraniteServerError as e:
    print(f"API Error: {e}")
    # Handle error or retry
```

This API reference provides comprehensive documentation for all major components and functions in the Contract Analysis system. 