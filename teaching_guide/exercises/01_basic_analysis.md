# Exercise 1: Basic Document Analysis

## Objective
Learn to run a basic document analysis workflow and interpret the results.

## Prerequisites
- Completed Module 2: Getting Started
- Environment configured with API keys
- Sample documents available

## Tasks

### Task 1: Run Analysis Without Rules

Run a basic analysis on the AI addendum sample:

```bash
python scripts/main.py \
  sample_documents/target_docs/ai_addendum/AI-Services-Addendum.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md
```

**Questions to Answer:**
1. How many sentences were classified?
2. What are the top 3 classification categories?
3. How long did the analysis take?

### Task 2: Examine Classification Output

Open the JSONL file with classifications:

```bash
# Find the latest run
ls -lt data/output/runs/

# View first 5 classifications
head -5 data/output/runs/run_*/classified_sentences.jsonl
```

**Questions to Answer:**
1. What fields are included in each classification?
2. What is the confidence range for classifications?
3. Can you identify any misclassifications?

### Task 3: Review Questionnaire Results

Open the questionnaire results:

```bash
# View YAML results
cat data/output/runs/run_*/questionnaire_results.yaml
```

**Questions to Answer:**
1. How many questions were answered?
2. Do all answers have citations?
3. What page numbers are most frequently cited?

### Task 4: Analyze State File

Examine the workflow state:

```python
import json

# Load state file
with open('data/output/runs/run_[YOUR_RUN_ID]/workflow_state.json') as f:
    state = json.load(f)

# Explore metadata
print(f"Status: {state['metadata']['status']}")
print(f"Last Node: {state['metadata']['last_node']}")

# Explore summary
summary = state['state_summary']
for key, value in summary.items():
    print(f"{key}: {value}")
```

**Questions to Answer:**
1. What is the final status?
2. Which node completed last?
3. How many sentences were processed?

## Deliverables

Create a file `exercise1_results.md` with:
1. Answers to all questions
2. One interesting observation about the analysis
3. One suggestion for improvement

## Hints

- Use `grep` to search for specific patterns in JSONL
- The state file contains a complete snapshot
- Excel files have multiple sheets - check them all

## Solution
See [solutions/01_basic_analysis_solution.md](../solutions/01_basic_analysis_solution.md)