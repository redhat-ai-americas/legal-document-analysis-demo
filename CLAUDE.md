# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a legal document analysis system built with LangGraph that performs contract review by:
1. Classifying document sentences into business/legal categories
2. Answering questionnaires about contract terms with citations
3. Evaluating compliance with business rules (when enabled)
4. Generating structured outputs (YAML, Excel, CSV) with page-level citations

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
make venv

# Activate virtual environment  
source .venv/bin/activate
```

### Running Tests
```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_citation_critic.py

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run tests matching pattern
pytest -k "citation"
```

### Running the Application
```bash
# Run main workflow programmatically
make run
# or
python scripts/main.py target.pdf reference.pdf

# Run with rules enabled
python scripts/main.py target.pdf reference.pdf --rules-file rules.yaml

# Batch processing
make batch
# or
python scripts/batch_process.py

# Launch Streamlit UI
make ui
# or
./start_ui.sh
```

### Code Quality
```bash
# Lint code with ruff
make lint

# Auto-fix linting issues
. .venv/bin/activate && ruff check . --fix

# Check for unsafe fixes available
. .venv/bin/activate && ruff check . --unsafe-fixes
```

### Utilities
```bash
# Analyze previous run logs
make analyze
# or
python scripts/analyze_run.py

# Verify reference fixes
make verify
# or
python scripts/verify_reference_fix.py
```

## Critical Environment Variables

Copy `.env.example` to `.env` and configure:

### Required
- `GRANITE_INSTRUCT_API_KEY` - Granite model API key
- `GRANITE_INSTRUCT_URL` - Granite API endpoint
- `GRANITE_INSTRUCT_MODEL_NAME` - Model identifier (e.g., granite-3.3-8b-instruct)

### Feature Flags
- `RULES_MODE_ENABLED` - Enable/disable rules processing
- `DUAL_MODEL_ENABLED` - Enable dual-model comparison mode  
- `USE_ENHANCED_ATTRIBUTION` - Use enhanced questionnaire processor
- `USE_SELECTIVE_LOGGING` - Reduce log file generation
- `USE_TEMPLATE_EXCEL` - Generate Excel output format
- `FORCE_GRANITE` - Force use of Granite model
- `VALIDATE_HIGH_SEVERITY_ONLY` - Only validate high-severity issues

## High-Level Architecture

### Workflow State Management
The system uses a LangGraph state machine (`workflows/state.py`) with critic agents that can trigger conditional reruns. The main workflow flows through three phases:

**Phase 1: Preflight & Conversion**
- Preflight checks (model connectivity)
- PDF to Markdown conversion if needed
- PDF conversion critic validates quality

**Phase 2: Classification & Rules**
- Document loading and sentence extraction
- Entity extraction (metadata)
- Target document classification
- Classification coverage critic ensures completeness
- Optional rules loading and evaluation (ALL rules, not just top_k)
- Reference document classification

**Phase 3: Q&A & Output**
- Questionnaire processing with citations
- Questionnaire completeness critic
- Citation critic validates quality (can trigger reclassification)
- YAML/Excel output generation

### Critic Agent Pattern
All critic nodes inherit from `base_critic.py` and implement a validation/rerun pattern:
- Validate current state quality
- Determine if rerun is needed based on severity
- Update state with `needs_*_rerun` flags
- Graph edges conditionally route based on these flags
- Maximum retry attempts prevent infinite loops

### Progress Reporting System
- All nodes inherit from `BaseNode` for consistent progress reporting
- Singleton `ProgressReporter` manages updates across workflow
- Real-time updates displayed in Streamlit UI
- LLM responses shown as they complete

### Model Configuration
The system supports multiple LLM backends configured in `utils/model_config.py`:
- **Granite 3.3**: Primary model with system message support for JSON output
- **Mixtral**: Optional validation model
- **Ollama**: Local model support
- Dual-model mode runs both for comparison

### Prompts Management
All prompts are externalized as YAML templates in `prompts/` directory. Nodes load prompts via `load_prompt_template()` helper rather than hardcoding. Each prompt template supports variable substitution with `{variable_name}` format.

### Citation System
Multi-layered citation tracking:
- `CitationManager` singleton tracks all citations globally
- Page anchors extracted from document markers (`[[page=N]]`)
- Fallback citation creation when primary extraction fails
- Citations validated by critic for quality and page references

### Classification System
Efficient batch classification with caching:
- Categories defined in `config/canonical_labels.yaml`
- Term aliases mapped to canonical forms
- Classification cache prevents redundant API calls
- Efficient mode batches multiple sentences per API call

### Rule Compliance System
When enabled, evaluates ALL rules systematically:
- Rules loaded from YAML with metadata and exceptions
- Each rule evaluated with structured JSON output
- Clear compliance statuses (compliant, non_compliant, partially_compliant, not_applicable, requires_review)
- Results exported to rule-centric Excel sheets

### Logging Architecture
Multi-level logging system:
- State changes logged to `logs/runs/{timestamp}/`
- Selective logging reduces volume when enabled
- Enhanced state logger provides detailed analysis
- Workflow visualization exported as JSON

## Testing Approach

Tests use pytest with comprehensive fixtures:
- Unit tests for individual nodes
- Integration tests for complete workflows
- Critic agent tests verify retry logic
- Mock external API calls for offline testing
- Test both success and failure paths

## Project Structure Notes

- `nodes/` - Workflow nodes grouped by concern (loading, classification, rules, questionnaire, critics)
- `nodes/proposed/` - Experimental nodes not yet integrated
- `workflows/` - LangGraph builders and state definitions
- `utils/` - Shared utilities (models, prompts, logging, scoring, retrieval)
- `prompts/` - YAML prompt templates
- `questionnaires/` - Questionnaire definitions
- `config/` - Configuration files (feature flags, canonical labels)
- `logs/runs/` - Runtime logs (gitignored by default)
- `data/output/` - Generated analysis outputs