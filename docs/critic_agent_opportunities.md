# Critic Agent Opportunities in Contract Analysis Workflow

## Current Workflow Flow
1. **preflight_check** → Validates inputs exist
2. **pdf_converter** → Converts PDF to markdown (conditional)
3. **loader** → Loads and preps document, extracts sentences
4. **entity_extractor** → Extracts entities (dates, parties, etc.)
5. **target_classifier** → Classifies sentences against terminology
6. **rules_loader** → Loads compliance rules (conditional)
7. **rule_compliance_checker** → Checks rule compliance
8. **reference_classifier** → Classifies reference document
9. **questionnaire_processor** → Answers questions using classifications
10. **citation_critic** → Validates citations ✅ (ALREADY IMPLEMENTED)
11. **yaml_populator** → Creates final YAML output

## High-Impact Critic Agent Opportunities

### 1. 🎯 **PDF Conversion Quality Critic**
**Location**: After `pdf_converter`, before `loader`
**Purpose**: Validate PDF conversion quality
**What to Check**:
- Verify page anchors were extracted
- Check for excessive image placeholders (indicates OCR failure)
- Validate text extraction completeness (minimum character count)
- Detect garbled text or encoding issues
- Check for table extraction quality

**Retry Strategy**:
- If page anchors missing → retry with enhanced page detection
- If too many images → retry with OCR enabled
- If text too short → retry with different extraction method

**Implementation Priority**: HIGH
**Impact**: Foundation for all downstream processing

---

### 2. 🎯 **Classification Coverage Critic**
**Location**: After `target_classifier`, before rules/reference processing
**Purpose**: Ensure adequate classification coverage
**What to Check**:
- Percentage of sentences classified (vs "no-class")
- Coverage of critical terminology terms
- Confidence distribution (too many low-confidence)
- Detection of amendment documents needing special handling
- Validate all expected sections are found

**Retry Strategy**:
- If coverage < 30% → retry with relaxed thresholds
- If critical terms missing → retry with enhanced prompts
- If all low confidence → retry with different model

**Implementation Priority**: HIGH
**Impact**: Directly affects questionnaire and rule compliance quality

---

### 3. 🎯 **Entity Extraction Completeness Critic**
**Location**: After `entity_extractor`
**Purpose**: Validate critical entities were extracted
**What to Check**:
- Contract start/end dates found
- Both parties identified
- Governing law detected
- Contract value/fees extracted (if applicable)
- Signature blocks validated

**Retry Strategy**:
- If dates missing → retry with date-focused patterns
- If parties missing → retry with header/signature analysis
- If all missing → retry with fallback extraction methods

**Implementation Priority**: MEDIUM
**Impact**: Affects document information section accuracy

---

### 4. 🎯 **Rule Compliance Logic Critic**
**Location**: After `rule_compliance_checker`
**Purpose**: Validate rule evaluation quality
**What to Check**:
- Ratio of "not_evaluated" vs evaluated rules
- Rules with empty evidence
- Conflicting compliance determinations
- Rules that should always have matches (e.g., governing law)

**Retry Strategy**:
- If >50% not evaluated → retry with retrieval fallback
- If no evidence → retry with expanded search
- If conflicts → retry with enhanced reasoning

**Implementation Priority**: MEDIUM
**Impact**: Critical for compliance assessment accuracy

---

### 5. 🎯 **Questionnaire Completeness Critic**
**Location**: After `questionnaire_processor`, before citation_critic
**Purpose**: Validate questionnaire answers
**What to Check**:
- Percentage of "Not specified" answers
- Answers that contradict each other
- Required fields that are empty
- Suspicious patterns (all same answer)
- Risk questions without risk assessments

**Retry Strategy**:
- If >40% not specified → retry with retrieval fallback
- If contradictions → retry specific questions
- If patterns detected → retry with different prompts

**Implementation Priority**: HIGH
**Impact**: Directly affects output quality

---

### 6. 🎯 **Cross-Document Consistency Critic**
**Location**: After `reference_classifier`
**Purpose**: Validate target vs reference alignment
**What to Check**:
- Major discrepancies in key clauses
- Missing standard clauses from reference
- Unusual deviations flagged
- Ensure reference document was actually used

**Retry Strategy**:
- If no reference matches → retry with relaxed matching
- If reference not used → retry with enforcement flag

**Implementation Priority**: LOW
**Impact**: Important for gap analysis but not critical path

---

### 7. 🎯 **Final Output Sanitization Critic**
**Location**: After `yaml_populator`, before END
**Purpose**: Final quality gate
**What to Check**:
- No PII/sensitive data in output
- All required sections present
- No error messages in output
- Formatting and structure valid
- File size reasonable

**Retry Strategy**:
- If PII detected → sanitize and retry
- If sections missing → go back to questionnaire
- If errors → identify source and retry that component

**Implementation Priority**: MEDIUM
**Impact**: Ensures production-ready output

---

## Implementation Recommendations

### Quick Wins (Implement First):
1. **Classification Coverage Critic** - Biggest impact on quality
2. **PDF Conversion Quality Critic** - Foundation for everything
3. **Questionnaire Completeness Critic** - Direct user impact

### Architecture Patterns:

```python
class BaseCritic:
    """Base class for all critic agents"""
    
    def validate(self, state: ContractAnalysisState) -> ValidationResult:
        """Perform validation checks"""
        pass
    
    def should_retry(self, validation_result: ValidationResult) -> bool:
        """Determine if retry is warranted"""
        pass
    
    def prepare_retry_state(self, state: ContractAnalysisState) -> ContractAnalysisState:
        """Modify state for retry with improvements"""
        pass
```

### Configuration Strategy:

```bash
# .env configuration for each critic
CLASSIFICATION_CRITIC_ENABLED=true
CLASSIFICATION_MIN_COVERAGE=0.3
CLASSIFICATION_MAX_RETRIES=2

PDF_CRITIC_ENABLED=true
PDF_MIN_TEXT_LENGTH=1000
PDF_MAX_IMAGE_RATIO=0.5
PDF_MAX_RETRIES=2

QUESTIONNAIRE_CRITIC_ENABLED=true
QUESTIONNAIRE_MAX_NOT_SPECIFIED=0.4
QUESTIONNAIRE_MAX_RETRIES=2
```

### Retry Orchestration:

```python
# Track retries per critic to avoid loops
state['critic_attempts'] = {
    'pdf_conversion': 0,
    'classification': 0,
    'entity_extraction': 0,
    'questionnaire': 0,
    'citations': 0
}

# Global circuit breaker
MAX_TOTAL_RETRIES = 10  # Across all critics
```

## Benefits of Multi-Critic Architecture

1. **Self-Healing Pipeline**: Automatically fixes common issues
2. **Quality Assurance**: Multiple validation gates ensure quality
3. **Observability**: Each critic provides detailed diagnostics
4. **Configurability**: Tune validation thresholds per deployment
5. **Graceful Degradation**: Continue with warnings if can't fix
6. **Learning Opportunity**: Critic logs reveal systemic issues

## Potential Risks to Manage

1. **Infinite Loops**: Need careful retry limits and circuit breakers
2. **Performance**: More critics = longer processing time
3. **Over-Correction**: Too many retries might degrade quality
4. **Complexity**: More nodes make debugging harder
5. **Cost**: Retries mean more API calls

## Suggested Rollout Plan

### Phase 1: Foundation Critics
- PDF Conversion Quality Critic
- Classification Coverage Critic

### Phase 2: Quality Critics  
- Questionnaire Completeness Critic
- Entity Extraction Completeness Critic

### Phase 3: Advanced Critics
- Rule Compliance Logic Critic
- Cross-Document Consistency Critic
- Final Output Sanitization Critic

## Monitoring and Metrics

Track for each critic:
- Validation pass rate
- Retry success rate
- Average retries needed
- Time impact
- Quality improvement metrics

This data helps tune thresholds and identify systemic issues needing fixes in the base agents rather than critics.