# Exercise 3: Create a Custom Node

## Objective
Learn to create a custom node that extends the workflow with new functionality.

## Prerequisites
- Completed Modules 1-3
- Understanding of BaseNode pattern
- Basic Python knowledge

## Scenario
Your legal team wants to identify and extract all monetary values mentioned in contracts for quick reference.

## Tasks

### Task 1: Create the Node Class

Create a new file `nodes/monetary_extractor.py`:

```python
from typing import Dict, List, Any
import re
from nodes.base_node import BaseNode

class MonetaryExtractor(BaseNode):
    def __init__(self):
        super().__init__("Monetary Value Extractor")
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all monetary values from the document."""
        
        self.report_progress("Extracting monetary values...")
        
        # Get document text
        doc_text = state.get('target_document_text', '')
        
        # TODO: Implement extraction logic
        monetary_values = self.extract_money(doc_text)
        
        self.report_progress(f"Found {len(monetary_values)} monetary values")
        
        return {
            'monetary_values': monetary_values,
            'monetary_extraction_complete': True
        }
    
    def extract_money(self, text: str) -> List[Dict[str, Any]]:
        """Extract monetary values with context."""
        
        # Pattern for currency values
        # TODO: Implement regex pattern
        pattern = r'\$[\d,]+\.?\d*'  # Simple starting pattern
        
        values = []
        # TODO: Find matches and extract context
        
        return values
```

**Your Tasks:**
1. Complete the `extract_money` method
2. Extract both the value and surrounding context (20 words before/after)
3. Handle multiple currency formats ($, USD, EUR, etc.)
4. Return structured data with value, currency, and context

### Task 2: Integrate the Node

Add your node to the workflow in `workflows/graph_builder.py`:

```python
from nodes.monetary_extractor import MonetaryExtractor

def build_graph():
    # ... existing code ...
    
    # Add your node
    monetary_extractor = MonetaryExtractor()
    workflow.add_node("monetary_extractor", monetary_extractor.process)
    
    # Add edge after entity extraction
    workflow.add_edge("entity_extraction", "monetary_extractor")
    workflow.add_edge("monetary_extractor", "classify_target_document")
    
    # ... rest of workflow ...
```

### Task 3: Update State Definition

Add fields to `workflows/state.py`:

```python
class ContractAnalysisState(TypedDict):
    # ... existing fields ...
    
    # Add your fields
    monetary_values: List[Dict[str, Any]]
    monetary_extraction_complete: bool
```

### Task 4: Test Your Node

Create a test file `tests/test_monetary_extractor.py`:

```python
import pytest
from nodes.monetary_extractor import MonetaryExtractor

def test_extract_usd():
    extractor = MonetaryExtractor()
    
    text = "The contract value is $50,000 per year."
    result = extractor.extract_money(text)
    
    assert len(result) == 1
    assert result[0]['value'] == 50000
    assert result[0]['currency'] == 'USD'
    assert 'contract value' in result[0]['context'].lower()

def test_extract_multiple_currencies():
    # TODO: Add test for multiple currencies
    pass

def test_extract_with_context():
    # TODO: Add test for context extraction
    pass
```

### Task 5: Create Output Writer

Add a function to save monetary values to JSON:

```python
# utils/monetary_output_writer.py
import json
from typing import List, Dict, Any

def save_monetary_values(values: List[Dict], run_id: str):
    """Save extracted monetary values to JSON."""
    
    output_path = f"data/output/runs/run_{run_id}/monetary_values.json"
    
    with open(output_path, 'w') as f:
        json.dump({
            'total_values_found': len(values),
            'values': values,
            'summary': create_summary(values)
        }, f, indent=2)

def create_summary(values: List[Dict]) -> Dict:
    """Create summary statistics."""
    # TODO: Implement summary
    # - Total contract value
    # - Largest amount
    # - Most frequent currency
    pass
```

## Challenge Tasks

### Challenge 1: Smart Context
Instead of fixed word count, extract the complete sentence containing the monetary value.

### Challenge 2: Value Normalization
Convert all values to a common currency (USD) for comparison.

### Challenge 3: Temporal Association
Associate monetary values with dates/time periods mentioned nearby.

### Challenge 4: Integration with Excel
Add monetary values as a new sheet in the Excel output.

## Testing Your Implementation

Run the full workflow with your node:

```bash
python scripts/main.py \
  sample_documents/target_docs/ai_addendum/AI-Services-Addendum.pdf \
  sample_documents/standard_docs/ai_addendum/AI-Addendum.md
```

Check for:
1. Your node appearing in console output
2. `monetary_values.json` in output directory
3. Correct extraction of values
4. No workflow errors

## Deliverables

1. Complete `monetary_extractor.py` implementation
2. Working tests (at least 3 test cases)
3. JSON output file with extracted values
4. Brief analysis of what values were found

## Hints

### Regex Patterns
```python
# More comprehensive pattern
currency_pattern = r'(?:[\$€£¥]|USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?'

# With word boundaries
pattern = r'\b' + currency_pattern + r'\b'
```

### Context Extraction
```python
def get_context(text: str, match_start: int, match_end: int, words: int = 20):
    # Get surrounding words
    before = text[:match_start].split()[-words:]
    after = text[match_end:].split()[:words]
    return ' '.join(before + [text[match_start:match_end]] + after)
```

### Currency Mapping
```python
CURRENCY_MAP = {
    '$': 'USD',
    '€': 'EUR',
    '£': 'GBP',
    '¥': 'JPY'
}
```

## Common Issues

### Issue: Node not executing
- Check workflow edges are correct
- Verify node is added to graph
- Look for errors in logs

### Issue: Regex not matching
- Test pattern separately
- Account for formatting variations
- Handle edge cases (decimals, thousands)

### Issue: State not updating
- Ensure return dictionary has correct keys
- Check state type definition
- Verify no exceptions in node

## Solution
See [solutions/03_create_custom_node_solution.md](../solutions/03_create_custom_node_solution.md)