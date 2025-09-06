# Module 2: Getting Started

## Prerequisites

### System Requirements
- **Operating System**: Linux, macOS, or Windows with WSL2
- **Python**: Version 3.11 or higher
- **Memory**: Minimum 8GB RAM (16GB recommended)
- **Disk Space**: At least 2GB free space
- **Network**: Internet connection for API calls

### Required Software
```bash
# Check Python version
python --version  # Should show 3.11.x or higher

# Check pip
pip --version

# Check git
git --version
```

## Installation

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd legal-document-analysis
```

### Step 2: Create Virtual Environment
```bash
# Using the Makefile (recommended)
make venv

# Or manually
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

#### Essential Environment Variables
```bash
# Primary Model Configuration (Required)
GRANITE_INSTRUCT_API_KEY=your-api-key-here
GRANITE_INSTRUCT_URL=https://your-api-endpoint
GRANITE_INSTRUCT_MODEL_NAME=granite-3-8b-instruct

# Feature Flags (Optional - defaults shown)
RULES_MODE_ENABLED=true
USE_ENHANCED_ATTRIBUTION=true
USE_TEMPLATE_EXCEL=true
USE_SELECTIVE_LOGGING=false
DUAL_MODEL_ENABLED=false
```

### Step 4: Verify Installation
```bash
# Run tests to verify setup
make test

# Or run specific test
pytest tests/test_preflight.py -v
```

## First Run

### Basic Document Analysis

#### 1. Prepare Your Documents
```bash
# Check sample documents
ls sample_documents/
```

Sample structure:
```
sample_documents/
├── target_docs/      # Documents to analyze
├── standard_docs/    # Reference templates
└── rules/           # Rule definitions
```

#### 2. Run Simple Analysis (No Rules)
```bash
# Analyze AI addendum without rules
python scripts/main.py \
  sample_documents/target_docs/ai_addendum/AI-Services-Addendum.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md
```

#### 3. Run Full Analysis (With Rules)
```bash
# Analyze with rule compliance checking
python scripts/main.py \
  sample_documents/target_docs/ai_addendum/AI-Services-Addendum.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md \
  --rules-file sample_documents/rules/ai_addendum_rules.yaml
```

### Understanding the Output

#### Console Output
You'll see progress messages like:
```
============================================================
🚀 STARTING NODE: preflight_check
============================================================
✅ Model connectivity verified
✅ NODE preflight_check COMPLETED SUCCESSFULLY

============================================================
🚀 STARTING NODE: loader
============================================================
📄 Loading document: AI-Services-Addendum.pdf
✅ NODE loader COMPLETED SUCCESSFULLY

[... more nodes ...]
```

#### Output Files Location
```bash
# Check generated outputs
ls -la data/output/runs/run_*/

# You should see:
# - workflow_state.json         # Complete state snapshot
# - classified_sentences.jsonl  # All classifications
# - rule_evaluation_results.json # Rule findings (if rules enabled)
# - questionnaire_results.yaml  # Q&A responses
# - analysis_report.xlsx        # Excel report
# - analysis_summary.md         # Markdown summary
```

### Using the Streamlit UI

#### Launch the Interface
```bash
# Start the UI
make ui

# Or directly
streamlit run ui/streamlit_app.py
```

#### UI Features
1. **File Upload**: Drag and drop documents
2. **Configuration**: Set analysis parameters
3. **Progress Tracking**: Real-time node updates
4. **Results Download**: Get all outputs in one place

## Common Setup Issues

### Issue 1: API Key Not Working
```bash
# Test API connectivity
python -c "
import os
from utils.model_config import get_primary_model
model = get_primary_model()
print('API connection successful')
"
```

**Solution**: Verify your API key and endpoint URL in `.env`

### Issue 2: Missing Dependencies
```bash
# Reinstall requirements
pip install -r requirements.txt --upgrade
```

### Issue 3: Permission Errors
```bash
# Ensure proper permissions
chmod +x scripts/*.py
chmod +x start_ui.sh
```

### Issue 4: Out of Memory
```bash
# Set environment variable to limit batch size
export CLASSIFICATION_BATCH_SIZE=5
```

## Quick Experiments

### Experiment 1: Analyze Your Own Document
1. Place your PDF in `sample_documents/target_docs/`
2. Run:
```bash
python scripts/main.py \
  sample_documents/target_docs/your-document.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md
```

### Experiment 2: Modify Questionnaire
1. Edit `questionnaires/contract_evaluation.yaml`
2. Add a new question:
```yaml
- id: new_question
  question: "What is the contract duration?"
  importance: medium
```
3. Run analysis again and check the output

### Experiment 3: Adjust Feature Flags
1. Edit `.env`:
```bash
USE_SELECTIVE_LOGGING=true  # Reduce log verbosity
```
2. Run analysis and notice cleaner output

## Project Structure Overview

```
legal-document-analysis/
├── scripts/
│   ├── main.py              # Main entry point
│   ├── batch_process.py     # Batch processing
│   └── analyze_run.py       # Analyze previous runs
├── nodes/                   # Workflow nodes
│   ├── document_classifier.py
│   ├── rule_compliance_evaluator.py
│   └── questionnaire_processor.py
├── workflows/
│   ├── graph_builder.py     # LangGraph workflow
│   └── state.py            # State definition
├── utils/                  # Utilities
│   ├── model_config.py     # LLM configuration
│   └── citation_manager.py # Citation handling
├── prompts/               # YAML prompt templates
├── questionnaires/        # Question definitions
├── config/               # Configuration files
└── data/output/         # Generated outputs
```

## Monitoring a Run

### Check Logs
```bash
# View latest run log
tail -f logs/runs/run_*/workflow.log

# Check specific node log
grep "document_classifier" logs/runs/run_*/workflow.log
```

### Inspect State File
```bash
# View current state
python -c "
import json
with open('data/output/runs/run_20250106_120000/workflow_state.json') as f:
    state = json.load(f)
    print(f\"Status: {state['metadata']['status']}\")
    print(f\"Last Node: {state['metadata']['last_node']}\")
    print(f\"Sentences Classified: {state['state_summary']['classified_sentences']}\")
"
```

## Next Steps

### Recommended Learning Path

1. **Run Basic Analysis**
   - Try different document combinations
   - Observe output differences

2. **Explore Outputs**
   - Open Excel files to see dynamic columns
   - Review JSONL classification details
   - Check YAML for structured Q&A

3. **Modify Configuration**
   - Toggle feature flags
   - Adjust model parameters
   - Change batch sizes

4. **Deep Dive**
   - Proceed to [03_core_concepts.md](03_core_concepts.md)
   - Understand LangGraph patterns
   - Learn about critics

## Troubleshooting Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] Dependencies installed (`requirements.txt`)
- [ ] `.env` file configured with API keys
- [ ] Test suite passes (`make test`)
- [ ] Sample documents accessible
- [ ] Write permissions for output directories

## Key Commands Reference

```bash
# Environment setup
make venv                    # Create virtual environment
source .venv/bin/activate   # Activate environment

# Running analysis
make run                    # Run with defaults
python scripts/main.py ...  # Run with custom args

# Testing
make test                   # Run all tests
pytest tests/ -v           # Verbose test output

# UI
make ui                    # Launch Streamlit interface

# Utilities
make analyze              # Analyze previous run
make lint                # Check code quality
```

## Summary

You should now have:
1. ✅ Working environment with all dependencies
2. ✅ Configured API access
3. ✅ Successfully run your first analysis
4. ✅ Located and understood output files
5. ✅ Basic familiarity with project structure

Proceed to [03_core_concepts.md](03_core_concepts.md) to understand the underlying architecture and patterns.