# Exercise 2: Add a Custom Business Rule

## Objective
Learn to create and evaluate custom business rules for contract compliance.

## Prerequisites
- Completed Exercise 1
- Understanding of rule structure from Module 3

## Background
Your legal team has identified a new compliance requirement: all AI contracts must explicitly address model training rights. You need to add this as a rule.

## Tasks

### Task 1: Create Rule Definition

Create a new rule file `my_custom_rules.yaml`:

```yaml
rules:
  - id: model_training_rights
    name: "Model Training Rights"
    description: "Verify contract addresses AI model training rights"
    keywords:
      - training
      - train
      - model improvement
      - learning
    evaluation_criteria: |
      Check if the contract explicitly addresses:
      1. Whether customer data can be used for model training
      2. Opt-out mechanisms for training
      3. Data retention for training purposes
    severity: high
    category: data_usage
```

**Your Task**: Add two more rules:
1. A rule about data deletion rights
2. A rule about audit provisions

### Task 2: Run Analysis with Custom Rules

```bash
python scripts/main.py \
  sample_documents/target_docs/ai_addendum/AI-Services-Addendum.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md \
  --rules-file my_custom_rules.yaml
```

### Task 3: Examine Rule Evaluation Results

```python
import json

# Load rule results
with open('data/output/runs/run_*/rule_evaluation_results.json') as f:
    results = json.load(f)

# Analyze each rule
for rule in results['rules']:
    print(f"Rule: {rule['rule_id']}")
    print(f"Status: {rule['status']}")
    print(f"Evidence count: {len(rule.get('evidence', []))}")
    print("---")
```

**Questions to Answer:**
1. What is the compliance status for each rule?
2. Which rule has the most evidence citations?
3. Are there any rules marked as "not_applicable"?

### Task 4: Review Excel Output

Open the generated Excel file and examine:
1. Are there columns for your custom rules?
2. What values appear in these columns?
3. Is the evidence/rationale included?

## Challenge Tasks

### Challenge 1: Complex Rule
Create a rule that checks for MULTIPLE conditions:
- Payment terms AND
- Late payment penalties AND  
- Payment dispute resolution

### Challenge 2: Rule Dependencies
Create two rules where the second rule only makes sense if the first is compliant.

### Challenge 3: Rule Scoring
Modify a rule to include a scoring mechanism (0-100) instead of just compliant/non-compliant.

## Deliverables

1. Your custom `my_custom_rules.yaml` file with at least 3 rules
2. Analysis of rule evaluation results
3. Screenshot or description of Excel output with custom rule columns
4. (Optional) Solution to one challenge task

## Hints

- Keywords help the system find relevant sections
- Clear evaluation_criteria improve accuracy
- Severity affects how rules are prioritized
- Check existing rules in `sample_documents/rules/` for examples

## Common Issues

### Issue: Rules not being evaluated
- Check RULES_MODE_ENABLED=true in .env
- Verify rule YAML syntax is correct
- Ensure rules file path is correct

### Issue: Poor evidence quality
- Add more specific keywords
- Make evaluation_criteria more explicit
- Check if document actually contains relevant content

## Solution
See [solutions/02_add_custom_rule_solution.md](../solutions/02_add_custom_rule_solution.md)