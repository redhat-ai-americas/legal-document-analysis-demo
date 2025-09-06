# Legal Document Analysis

A sophisticated contract and legal document review system built on LangGraph that performs multi-stage analysis with critic validation. The system classifies document sentences, evaluates rule compliance, answers questionnaires, and generates comprehensive outputs with page-level citations.

## Key Features

- **Document Classification**: Categorizes every sentence into business/legal categories
- **Rule Compliance Evaluation**: Systematically evaluates documents against configurable business rules
- **Questionnaire Processing**: Answers contract-specific questions with evidence citations
- **Critic Validation System**: Multiple validation agents ensure output quality and can trigger reruns
- **Multi-Format Output**: YAML, Excel, CSV, Markdown, and JSONL with full traceability
- **Page-Level Citations**: Precise references with page anchors for all findings

## Quick Start

1) Create virtual environment and install dependencies:
```bash
make venv
source .venv/bin/activate
```

2) Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

3) Run the test suite:
```bash
make test
```

4) Process a document:
```bash
# Basic analysis (questionnaire only)
python scripts/main.py target.pdf reference.pdf

# With rule compliance evaluation
python scripts/main.py target.pdf reference.pdf --rules-file rules.yaml

# Batch processing
python scripts/batch_process.py
```

5) Launch the Streamlit UI:
```bash
make ui
# or
./start_ui.sh
```

## Project Structure

```
legal-document-analysis/
├── nodes/                      # Workflow nodes
│   ├── critics/                # Validation agents (citation, coverage, compliance)
│   ├── document_classifier.py  # Sentence classification
│   ├── rule_compliance_evaluator.py  # Rule evaluation
│   └── questionnaire_processor.py    # Q&A processing
├── workflows/                  # LangGraph workflow definitions
│   ├── graph_builder.py       # Main workflow orchestration
│   └── state.py               # State management
├── utils/                     # Shared utilities
│   ├── model_config.py        # LLM configuration
│   ├── citation_manager.py    # Citation tracking
│   └── classification_output_writer.py  # Output file management
├── prompts/                   # YAML prompt templates
├── questionnaires/           # Contract questionnaire definitions
├── config/                   # Configuration files
├── tests/                    # Test suite
├── logs/                     # Runtime logs (gitignored)
└── data/output/             # Analysis outputs
```

## Workflow Architecture

The system uses a LangGraph state machine with conditional routing and critic validation:

1. **Preflight & Loading**: Validates inputs, converts PDFs if needed, loads documents
2. **Entity Extraction**: Identifies parties and contract metadata
3. **Classification**: Categorizes every sentence into business/legal categories
4. **Rule Evaluation** (optional): Evaluates document against business rules
5. **Questionnaire Processing**: Answers contract-specific questions
6. **Critic Validation**: Multiple critics validate outputs and can trigger reruns:
   - Citation Critic: Ensures citation quality
   - Coverage Critic: Validates classification completeness  
   - Compliance Critic: Verifies rule evaluation accuracy
   - Completeness Critic: Checks questionnaire answers
7. **Output Generation**: Creates YAML, Excel, CSV, and inspection files

## Configuration

### Environment Variables (.env)
```bash
# Required - Granite Model
GRANITE_INSTRUCT_API_KEY=your_key
GRANITE_INSTRUCT_URL=https://api.endpoint
GRANITE_INSTRUCT_MODEL_NAME=model-name

# Feature Flags
RULES_MODE_ENABLED=true          # Enable rule compliance evaluation
USE_ENHANCED_ATTRIBUTION=true    # Enhanced questionnaire processing
USE_TEMPLATE_EXCEL=true         # Generate Excel output
USE_SELECTIVE_LOGGING=false     # Reduce log verbosity
DUAL_MODEL_ENABLED=false        # Compare two models
```

### Prompt Management
All prompts are externalized as YAML templates in `prompts/`:
- `classifier.yaml` - Document classification
- `questionnaire_answer.yaml` - Q&A processing
- `rule_compliance.yaml` - Rule evaluation
- `preflight.yaml` - System checks
- `agreement_type.yaml` - Contract type detection

## Output Files

The system generates comprehensive outputs in `data/output/runs/run_[timestamp]/`:

### Inspection Files
- `workflow_state.json` - Complete workflow state (overwritten on updates)
- `classified_sentences.jsonl` - All classified sentences with categories
- `rule_evaluation_results.json` - Detailed rule compliance findings

### Report Files  
- `questionnaire_results.yaml` - Q&A answers with citations
- `rule_compliance_results.yaml` - Rule evaluation summary
- `analysis_report.xlsx` - Excel report with dynamic rule columns
- `analysis_summary.md` - Markdown summary report

## Advanced Features

### Rule Compliance System
When rules are enabled, the system:
- Evaluates each rule systematically against the document
- Generates evidence citations for compliance/non-compliance
- Dynamically adds rule columns to Excel output
- Separates rule evaluation from questionnaire to avoid redundancy

### Critic Agent Pattern
Critics provide quality assurance through conditional reruns:
```python
# Critics can trigger specific node reruns
if citation_quality < threshold:
    return {"next": "reclassify_documents"}
```

### State Management
Single state file approach with error handling:
- State saved to `workflow_state.json` 
- Overwritten on each node completion
- Error states captured with full context
- Enables workflow inspection and debugging

## Development

### Running Tests
```bash
# All tests
make test

# Specific test file
pytest tests/test_citation_critic.py

# With coverage
pytest --cov=. --cov-report=html
```

### Linting
```bash
make lint
# or
ruff check . --fix
```

### Analyzing Runs
```bash
# Analyze previous run
python scripts/analyze_run.py

# Verify reference fixes
python scripts/verify_reference_fix.py
```

## API Usage

```python
from workflows.graph_builder import build_graph

# Build workflow
app = build_graph()

# Create initial state
state = {
    'target_document_path': 'contract.pdf',
    'reference_document_path': 'template.pdf', 
    'rules_path': 'rules.yaml',  # Optional
    'processing_start_time': '20250106_120000'
}

# Run workflow
result = app.invoke(state)

# Access outputs
questionnaire_results = result['questionnaire_results']
rule_results = result.get('rule_compliance_results', [])
```

## Contributing

See `CONTRIBUTING.md` for development setup, coding standards, and contribution guidelines.
