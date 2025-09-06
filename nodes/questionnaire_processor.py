import yaml
import json
import tiktoken
import os
from typing import Dict, List, Any, Tuple, cast
from workflows.state import ContractAnalysisState, ClassifiedSentence
from utils.granite_client import granite_client, GraniteAPIError
from utils.citation_tracker import citation_tracker
from utils.confidence_scorer import confidence_scorer
from utils.risk_assessor import risk_assessor
from utils.red_flag_detector import red_flag_detector
from utils.fallback_citation_creator import fallback_citation_creator

def load_questionnaire(path: str) -> Dict[str, Any]:
    """Load questionnaire from YAML file."""
    with open(path, 'r') as f:
        questionnaire_data = yaml.safe_load(f)
    return questionnaire_data

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except KeyError:
        # Fallback to cl100k_base if model not found
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

def get_relevant_sentences_for_question(question_id: str, 
                                       target_classified: List[ClassifiedSentence], 
                                       reference_classified: List[ClassifiedSentence], 
                                       terminology_data: List[Dict[str, Any]] | Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get sentences relevant to a specific question based on relevant_terms field.
    Returns (target_sentences, reference_sentences) as full sentence dictionaries.
    """
    # Determine relevant terms based on available terminology structure
    relevant_terms: List[str] = []

    # Case 1: terminology_data provided as a dict with 'terms' list (current schema)
    if isinstance(terminology_data, dict) and 'terms' in terminology_data:
        available_terms = {t.get('name', '') for t in terminology_data.get('terms', [])}
        # Static mapping from questionnaire IDs to terminology term names
        mapping: Dict[str, List[str]] = {
            'contract_start_date': ['term'],
            'source_code_access': ['source_code_escrow', 'intellectual_property_rights'],
            'exclusivity_non_competes': ['non_compete_exclusivity'],
            'forced_pricing_adjustments': ['most_favored_nation'],
            'ip_rights': ['intellectual_property_rights'],
            'limitation_of_liability': ['limitation_of_liability'],
            'assignment_coc': ['assignment_change_of_control'],
            'indemnity': ['indemnification'],
        }
        # Use only those terms that actually exist in the terminology set
        for candidate in mapping.get(question_id, []):
            if candidate in available_terms:
                relevant_terms.append(candidate)
    else:
        # Case 2: legacy list of dicts with explicit question_id -> term mapping
        try:
            for item in terminology_data:  # type: ignore[iteration-over-possible-non-sequence]
                if isinstance(item, dict) and item.get('question_id') == question_id:
                    if term := item.get('term'):
                        relevant_terms.append(term)
        except Exception:
            relevant_terms = []
    
    # If no relevant terms specified, this question doesn't need LLM processing
    if not relevant_terms:
        return [], []
    
    target_sentences: List[Dict[str, Any]] = []
    reference_sentences: List[Dict[str, Any]] = []
    
    # Find sentences classified with relevant terms in target document
    for sentence_data in target_classified:
        sentence_classes = sentence_data.get('classes', [])
        for term in relevant_terms:
            if term in sentence_classes:
                # Include full sentence data with page info
                sentence_dict = cast(Dict[str, Any], sentence_data)
                # Debug: Check if page info is present
                if not sentence_dict.get('page') and not sentence_dict.get('page_number'):
                    print(f"    ⚠️ WARNING: Sentence missing page info for term '{term}'")
                target_sentences.append(sentence_dict)
                break
    
    # Find sentences classified with relevant terms in reference document
    for sentence_data in reference_classified:
        sentence_classes = sentence_data.get('classes', [])
        for term in relevant_terms:
            if term in sentence_classes:
                reference_sentences.append(cast(Dict[str, Any], sentence_data))
                break
    
    return target_sentences, reference_sentences

def split_sentences_by_tokens(sentences: List[Dict[str, Any]], max_tokens: int = 2000) -> List[List[Dict[str, Any]]]:
    """Split sentences into chunks that fit within token limit."""
    chunks = []
    current_chunk = []
    current_tokens = 0
    encoding = tiktoken.get_encoding("cl100k_base")
    
    for sentence_data in sentences:
        sentence = sentence_data.get('sentence', '')
        tokens = len(encoding.encode(sentence))
        
        if current_tokens + tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0
        
        current_chunk.append(sentence_data)
        current_tokens += tokens
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def load_prompt_template() -> Dict[str, Any]:
    """Load the questionnaire answering prompt template."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "questionnaire_answer.yaml")
    try:
        with open(prompt_path, 'r') as f:
            template_data = yaml.safe_load(f)
            if not template_data:
                raise ValueError("Empty template file")
            return template_data
    except (IOError, yaml.YAMLError, ValueError) as e:
        raise ValueError(f"Failed to load prompt template: {e}")

def create_question_prompt(question: Dict[str, Any], target_sentences: List[str], 
                         reference_sentences: List[str], template_data: Dict[str, Any]) -> str:
    """
    Create a focused prompt for answering a single question using YAML template.
    """
    # Calculate available tokens for content
    base_tokens = count_tokens(template_data['template'])
    available_tokens = 4096 - base_tokens - 200  # Buffer for response and variables
    
    # Format target clauses with token limiting
    target_clauses = []
    current_tokens = 0
    target_token_limit = available_tokens // 2  # Use half for target, half for reference
    
    for i, sentence in enumerate(target_sentences, 1):
        sentence_line = f"{i}. {sentence}"
        sentence_tokens = count_tokens(sentence_line)
        
        if current_tokens + sentence_tokens > target_token_limit:
            break
            
        target_clauses.append(sentence_line)
        current_tokens += sentence_tokens
    
    target_clauses_text = "\n".join(target_clauses) if target_clauses else "No relevant clauses found."
    
    # Format reference section if available
    reference_section = ""
    if reference_sentences:
        reference_clauses = []
        current_tokens = 0
        reference_token_limit = available_tokens - count_tokens(target_clauses_text)
        
        for i, sentence in enumerate(reference_sentences, 1):
            sentence_line = f"{i}. {sentence}"
            sentence_tokens = count_tokens(sentence_line)
            
            if current_tokens + sentence_tokens > reference_token_limit:
                break
                
            reference_clauses.append(sentence_line)
            current_tokens += sentence_tokens
        
        if reference_clauses:
            reference_clauses_text = "\n".join(reference_clauses)
            reference_section = template_data['reference_template'].format(
                reference_clauses=reference_clauses_text
            )
    
    # Create the final prompt using template
    # Use safe formatting that avoids interpreting braces in the template as format fields
    from string import Template
    tmpl = Template(template_data['template']
                    .replace('{', '{{')
                    .replace('}', '}}')
                    .replace('{{question_prompt}}', '$question_prompt')
                    .replace('{{guideline}}', '$guideline')
                    .replace('{{target_clauses}}', '$target_clauses')
                    .replace('{{reference_section}}', '$reference_section'))
    prompt = tmpl.substitute(
        question_prompt=question['prompt'],
        guideline=question['guideline'],
        target_clauses=target_clauses_text,
        reference_section=reference_section
    )
    
    return prompt

def answer_single_question(
    question: Dict[str, Any],
    target_sentences: List[Dict[str, Any]],
    reference_sentences: List[Dict[str, Any]],
    terminology_data: List[Dict[str, Any]],
    use_dual_model: bool = True,
    all_target_classified: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process a single question using relevant sentences."""
    question_id = question.get('id', '')
    
    # Load template
    template_data = load_prompt_template()
    
    # Skip LLM processing for deterministic fields
    deterministic_fields = {'document_name', 'datasite_location', 'reviewer_name', 'target_company_name', 'counterparty_name', 'contract_start_date'}
    if question_id in deterministic_fields:
        return {
            "answer": "DETERMINISTIC_FIELD",
            "confidence": 1.0,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {"type": "deterministic"}
        }
    
    # Extract sentence text for prompt creation (backwards compatibility)
    target_sentence_texts = [s.get("sentence", s) if isinstance(s, dict) else s for s in target_sentences]
    reference_sentence_texts = [s.get("sentence", s) if isinstance(s, dict) else s for s in reference_sentences]
    
    prompt = create_question_prompt(question, target_sentence_texts, reference_sentence_texts, template_data=template_data)
    
    # Count total tokens in prompt (Granite 3.3 supports large context; allow more)
    prompt_tokens = count_tokens(prompt)
    
    try:
        # Get enhanced response with metadata
        api_response = granite_client.call_api(
            prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
            return_metadata=True
        )
        
        if isinstance(api_response, dict):
            raw_text = api_response["content"].strip()
            response_metadata = api_response["metadata"]
        else:
            raw_text = api_response.strip()
            response_metadata = {}

        # Parse expected JSON; fall back to raw text
        parsed_answer = None
        try:
            parsed_answer = json.loads(raw_text)
        except Exception:
            # Try to extract JSON from code blocks if present
            if "```" in raw_text:
                try:
                    start = raw_text.find("{")
                    end = raw_text.rfind("}")
                    if start != -1 and end != -1:
                        parsed_answer = json.loads(raw_text[start:end+1])
                except Exception:
                    parsed_answer = None

        if isinstance(parsed_answer, dict) and "answer" in parsed_answer:
            answer = str(parsed_answer.get("answer", "")).strip()
            # Incorporate model-provided confidence if available
            parsed_answer.get("confidence")
        else:
            answer = raw_text
        
        print(f"    Prompt tokens: {prompt_tokens}")
        
        # Score extraction confidence
        question_prompt = question.get('prompt', '')
        source_context = ' '.join(target_sentence_texts[:3])  # First few sentences for context
        
        # Prefer model logprobs if available for confidence
        logprobs = response_metadata.get('logprobs', {}) if isinstance(response_metadata, dict) else {}
        token_logprobs = []
        try:
            # Granite logprobs shape may include 'tokens' with per-token logprob
            # Example: {'content': [{'token': '...', 'logprob': -0.12}, ...]}
            content_lp = logprobs.get('content') or []
            for t in content_lp:
                lp = t.get('logprob')
                if isinstance(lp, (int, float)):
                    token_logprobs.append(float(lp))
        except Exception:
            token_logprobs = []

        if token_logprobs:
            # Convert average logprob to a 0-100 confidence (sigmoid-like mapping)
            avg_lp = sum(token_logprobs) / max(1, len(token_logprobs))
            # Fix confidence calculation: logprobs are very negative (e.g., -5)
            # Map -5 to 50%, -2 to 75%, -0.5 to 90%, 0 to 95%
            if avg_lp >= 0:
                prob = 0.95  # Very confident
            elif avg_lp <= -5:
                prob = 0.5  # Low confidence  
            else:
                # Linear interpolation between -5 and 0
                prob = 0.5 + (avg_lp + 5) * 0.09  # Maps -5->0.5, 0->0.95
            model_confidence = round(min(100.0, max(0.0, prob * 100.0)), 1)
            confidence_result = {
                "overall_confidence": model_confidence,
                "answer_completeness": None,
                "source_support": None,
                "answer_specificity": None,
                "factual_accuracy": None,
                "reasoning": "Derived from model logprobs",
                "concerns": [],
                "needs_review": model_confidence < 60.0
            }
        else:
            # Fallback heuristic
            confidence_result = confidence_scorer.score_extraction_confidence(
                question_prompt, answer, source_context
            )
        
        # Create citations linking answer to source sentences
        source_sentences_for_citation = []
        for sentence_data in target_sentences:
            if isinstance(sentence_data, dict):
                # Extract page info from multiple possible field names
                page_number = (sentence_data.get("page") or 
                              sentence_data.get("page_number") or 
                              sentence_data.get("page_num"))
                section_name = sentence_data.get("section") or sentence_data.get("section_name")
                
                source_sentences_for_citation.append({
                    "sentence": sentence_data.get("sentence", ""),
                    "sentence_id": sentence_data.get("sentence_id"),
                    "page_number": page_number,
                    "section_name": section_name
                })
            else:
                # Handle backward compatibility
                source_sentences_for_citation.append({
                    "sentence": sentence_data,
                    "sentence_id": None,
                    "page_number": None,
                    "section_name": None
                })
        
        citations = citation_tracker.create_citation_from_match(
            question_prompt, answer, source_sentences_for_citation
        )
        
        # Enhance citations with better page info if available
        if citations and all_target_classified:
            citations = fallback_citation_creator.enhance_citations_with_context(
                citations, all_target_classified, window_size=2
            )
        
        citation_ids = [c.citation_id for c in citations]
        
        # Debug: Check citation creation
        if not citations and source_sentences_for_citation:
            print(f"    ⚠️ No citations created despite {len(source_sentences_for_citation)} source sentences")
        elif citations:
            pages_found = 0
            for c in citations:
                if c.page_number:
                    pages_found += 1
            if pages_found > 0:
                print(f"    ✓ Created {len(citations)} citations, {pages_found} with page anchors")
            else:
                print(f"    ⚠️ Created {len(citations)} citations but none have page anchors")
        
        # Assess risk level for relevant questions
        risk_assessment = None
        risk_relevant_questions = [
            'limitation_of_liability', 'indemnity', 'ip_rights', 'assignment_coc',
            'exclusivity_non_competes', 'forced_pricing_adjustments'
        ]
        
        if question_id in risk_relevant_questions and answer != "DETERMINISTIC_FIELD":
            # Combine answer with source context for risk assessment
            risk_context = f"Question: {question_prompt}\nAnswer: {answer}\nSource context: {source_context}"
            
            # Detect red flags in the context
            red_flags = red_flag_detector.detect_red_flags(risk_context)
            
            # Assess overall risk using risk assessor
            risk_assessment = risk_assessor.assess_clause_risk(risk_context, question_id)
            
            # Add red flag information to risk assessment
            risk_assessment["red_flags"] = [red_flag_detector._serialize_red_flag(flag) for flag in red_flags]
            risk_assessment["red_flag_count"] = len(red_flags)
        
        return {
            "answer": answer,
            "confidence": confidence_result.get("overall_confidence", 50),
            "extraction_confidence": confidence_result,
            "citations": citation_ids,
            "source_sentences": source_sentences_for_citation,
            "risk_assessment": risk_assessment,
            "processing_metadata": {
                "type": "llm",
                "prompt_tokens": prompt_tokens,
                "response_metadata": response_metadata,
                "citation_count": len(citations),
                "risk_assessed": risk_assessment is not None
            }
        }
        
    except GraniteAPIError as e:
        print(f"Error answering question {question.get('id', 'unknown')}: {e}")
        return {
            "answer": "Error: Could not process question",
            "confidence": 0,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {"error": str(e)}
        }

def process_questionnaire(state: ContractAnalysisState) -> dict:
    """
    Process the questionnaire by answering each question one at a time using classified sentences.
    """
    print("--- PROCESSING QUESTIONNAIRE ---")
    
    # Load questionnaire - use relative path from current directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    questionnaire_path = os.path.join(base_dir, "questionnaires", "contract_evaluation.yaml")
    questionnaire_data = load_questionnaire(questionnaire_path)
    
    # Load prompt template
    load_prompt_template()
    
    # Get classified sentences from both documents
    target_classified = state.get('classified_sentences', [])
    reference_classified = state.get('reference_classified_sentences', [])
    terminology_data = state.get('terminology_data', [])
    
    print(f"  Target classified sentences: {len(target_classified)}")
    print(f"  Reference classified sentences: {len(reference_classified)}")
    
    # Process each section and question
    questionnaire_responses = {}
    total_questions = 0
    
    for section_key, section_data in questionnaire_data['contract_evaluation'].items():
        print(f"\nProcessing section: {section_data['title']}")
        questionnaire_responses[section_key] = {
            'title': section_data['title'],
            'questions': []
        }
        
        for question in section_data['questions']:
            total_questions += 1
            question_id = question['id']
            
            print(f"  Question {total_questions}: {question_id}")
            
            # Get relevant sentences for this question from both documents
            target_sentences, reference_sentences = get_relevant_sentences_for_question(
                question_id, target_classified, reference_classified, terminology_data
            )
            
            print(f"    Target sentences: {len(target_sentences)}, Reference sentences: {len(reference_sentences)}")
            
            # If no sentences found, try fallback search
            if not target_sentences and question_id not in ['document_name', 'datasite_location', 'reviewer_name', 'target_company_name', 'counterparty_name']:
                print(f"    Using fallback search for {question_id}")
                target_sentences = fallback_citation_creator.find_relevant_sentences(
                    question_id, target_classified, max_sentences=5
                )
                if target_sentences:
                    print(f"    Fallback found {len(target_sentences)} sentences")
            
            # If we have too many target sentences, split them
            if target_sentences:
                target_chunks = split_sentences_by_tokens(target_sentences, max_tokens=2000)
                if len(target_chunks) > 1:
                    print(f"    Split target sentences into {len(target_chunks)} chunks")
                    # Use first chunk for now (could iterate through all)
                    target_sentences = target_chunks[0]
            
            # Answer the question with enhanced response
            answer_result = answer_single_question(
                question, target_sentences, reference_sentences, terminology_data,
                use_dual_model=True, all_target_classified=target_classified
            )
            
            # Extract answer text for display
            if isinstance(answer_result, dict):
                answer_text = answer_result.get("answer", "Error: No answer")
                confidence = answer_result.get("confidence", 0)
                citations = answer_result.get("citations", [])
                extraction_confidence = answer_result.get("extraction_confidence", {})
                risk_assessment = answer_result.get("risk_assessment")
                processing_metadata = answer_result.get("processing_metadata", {})
            else:
                # Backward compatibility
                answer_text = answer_result
                confidence = 0.5
                citations = []
                extraction_confidence = {}
                risk_assessment = None
                processing_metadata = {}
            
            # Store the enhanced response
            question_response = {
                'id': question_id,
                'prompt': question['prompt'],
                'guideline': question['guideline'],
                'answer': answer_text,
                'confidence': confidence,
                'extraction_confidence': extraction_confidence,
                'citations': citations,
                'risk_assessment': risk_assessment,
                'target_sentences_count': len(target_sentences),
                'reference_sentences_count': len(reference_sentences),
                'processing_metadata': processing_metadata
            }
            # Add answer source indicator
            ptype = (processing_metadata or {}).get('type')
            question_response['answer_source'] = 'Deterministic' if ptype == 'deterministic' else 'LLM'
            
            # Add risk display for console output
            risk_display = ""
            if risk_assessment:
                risk_level = risk_assessment.get("risk_level", "Unknown")
                risk_score = risk_assessment.get("risk_score", 0)
                red_flag_count = risk_assessment.get("red_flag_count", 0)
                risk_display = f" [Risk: {risk_level} ({risk_score:.0f})"
                if red_flag_count > 0:
                    risk_display += f", {red_flag_count} red flags"
                risk_display += "]"
            
            questionnaire_responses[section_key]['questions'].append(question_response)
            confidence_display = f" (conf: {confidence:.1f})" if confidence > 0 else ""
            full_display = confidence_display + risk_display
            print(f"    Answer: {answer_text[:100]}...{full_display}" if len(answer_text) > 100 else f"    Answer: {answer_text}{full_display}")
    
    print(f"\nCompleted questionnaire processing: {total_questions} questions answered")
    
    return {
        'questionnaire_responses': questionnaire_responses
    }