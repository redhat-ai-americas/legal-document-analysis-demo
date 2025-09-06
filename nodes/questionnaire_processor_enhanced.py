"""
Enhanced Questionnaire Processor with Decision Attribution Tracking

This module processes questionnaires with comprehensive decision tracking,
providing clear attribution for how each answer was determined.
"""

import yaml
import json
import os
import time
from typing import Dict, List, Any, Tuple, Optional, cast
from workflows.state import ContractAnalysisState, ClassifiedSentence
from utils.granite_client import granite_client, GraniteAPIError
from utils.citation_tracker import citation_tracker
from utils.enhanced_confidence_scorer import enhanced_confidence_scorer
from utils.risk_assessor import risk_assessor
from utils.red_flag_detector import red_flag_detector
from utils.term_aliases import get_term_aliases
from utils.decision_tracker import (
    DecisionAttribution, 
    initialize_decision_tracker,
    track_decision
)

# Import original functions we'll reuse
from nodes.questionnaire_processor import (
    load_questionnaire,
    count_tokens,
    split_sentences_by_tokens,
    load_prompt_template,
    create_question_prompt
)


def get_relevant_sentences_with_attribution(
    question_id: str, 
    target_classified: List[ClassifiedSentence], 
    reference_classified: List[ClassifiedSentence], 
    terminology_data: List[Dict[str, Any]] | Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Enhanced version that also returns the terms that were searched for.
    Returns (target_sentences, reference_sentences, searched_terms)
    """
    # Determine relevant terms based on available terminology structure
    relevant_terms: List[str] = []

    # Case 1: terminology_data provided as a dict with 'terms' list (current schema)
    if isinstance(terminology_data, dict) and 'terms' in terminology_data:
        available_terms = {t.get('name', '') for t in terminology_data.get('terms', [])}
        # Static mapping from questionnaire IDs to terminology term names
        mapping: Dict[str, List[str]] = {
            'agreement_type': ['document_type'],  # Map agreement_type to document_type term
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
    
    # Alias expansion: include known aliases for the canonical terms
    aliases = get_term_aliases()
    expanded_terms = set(relevant_terms)
    for t in relevant_terms:
        expanded_terms |= aliases.get(t, set())
    relevant_terms = list(expanded_terms)

    # If no relevant terms specified, this question doesn't need classification-based search
    if not relevant_terms:
        return [], [], []
    
    target_sentences: List[Dict[str, Any]] = []
    reference_sentences: List[Dict[str, Any]] = []
    
    # Find sentences classified with relevant terms in target document
    for sentence_data in target_classified:
        sentence_classes = sentence_data.get('classes', [])
        for term in relevant_terms:
            if term in sentence_classes:
                target_sentences.append(cast(Dict[str, Any], sentence_data))
                break
    
    # Find sentences classified with relevant terms in reference document
    for sentence_data in reference_classified:
        sentence_classes = sentence_data.get('classes', [])
        for term in relevant_terms:
            if term in sentence_classes:
                reference_sentences.append(cast(Dict[str, Any], sentence_data))
                break
    
    return target_sentences, reference_sentences, relevant_terms


def answer_single_question_with_attribution(
    question: Dict[str, Any],
    target_sentences: List[Dict[str, Any]],
    reference_sentences: List[Dict[str, Any]],
    terminology_data: List[Dict[str, Any]],
    searched_terms: List[str],
    state: Optional[ContractAnalysisState] = None,
    use_dual_model: bool = True
) -> Dict[str, Any]:
    """Enhanced version that tracks decision attribution."""
    
    question_id = question.get('id', '')
    question_text = question.get('prompt', '')
    
    # Create attribution tracker for this question
    attribution = DecisionAttribution(question_id, question_text)
    start_time = time.time()
    
    # Load template
    template_data = load_prompt_template()
    
    # Special handling for agreement_type - no retrieval needed
    if question_id == 'agreement_type' and state:
        # Get document metadata directly from state
        document_metadata = state.get('document_metadata', {})
        target_path = state.get('target_document_path', '')
        document_text = state.get('document_text', '')
        
        # Prepare context for LLM
        context_parts = []
        
        # Add filename
        if target_path:
            filename = os.path.basename(target_path)
            context_parts.append(f"Filename: {filename}")
        
        # Add extracted title if available
        if document_metadata and document_metadata.get('document_title'):
            context_parts.append(f"Document Title: {document_metadata['document_title']}")
        
        # Add detected type if high confidence
        if document_metadata and document_metadata.get('document_type'):
            doc_type = document_metadata['document_type']
            confidence = document_metadata.get('document_type_confidence', 0)
            if confidence > 0.7:
                context_parts.append(f"Detected Type: {doc_type}")
        
        # Add first 250 characters of document
        if document_text:
            first_chars = document_text[:250].replace('\n', ' ').strip()
            context_parts.append(f"Document Beginning: {first_chars}...")
        
        # Build prompt from external template (prompts/agreement_type.yaml)
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tmpl_path = os.path.join(base_dir, "prompts", "agreement_type.yaml")
            with open(tmpl_path, 'r', encoding='utf-8') as f:
                tmpl_data = yaml.safe_load(f) or {}
        except Exception:
            tmpl_data = {}

        context_text = "\n".join(context_parts)
        instructions = (tmpl_data.get("instructions") or "Based on the following information, identify the type of agreement:\n${context}")
        schema_block = (tmpl_data.get("schema") or "Return your response as JSON:\n{\n  \"answer\": \"Type of agreement\",\n  \"reasoning\": \"Brief explanation of how you determined this\"\n}")
        from string import Template as _Template
        prompt = _Template(instructions).safe_substitute(
            context=context_text,
            question=question_text,
            guideline=question.get('guideline', '')
        ) + "\n\n" + schema_block

        # Call LLM with this focused context
        llm_name = "granite-3.3-8b-instruct"
        print("    🎯 Special handling for agreement_type (no retrieval)")
        
        try:
            api_response = granite_client.call_api(
                prompt=prompt,
                temperature=0.1,
                max_tokens=256,
                return_metadata=True
            )
            
            if isinstance(api_response, dict):
                raw_text = api_response["content"].strip()
                response_metadata = api_response["metadata"]
            else:
                raw_text = api_response.strip()
                response_metadata = {}
            
            # Parse response
            parsed_answer = None
            try:
                parsed_answer = json.loads(raw_text)
            except:
                # Try to extract JSON from response
                if "{" in raw_text and "}" in raw_text:
                    start_idx = raw_text.find("{")
                    end_idx = raw_text.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        try:
                            parsed_answer = json.loads(raw_text[start_idx:end_idx+1])
                        except:
                            pass
            
            if parsed_answer and "answer" in parsed_answer:
                answer = parsed_answer["answer"]
                reasoning = parsed_answer.get("reasoning", "")
            else:
                # Fallback
                answer = "Unable to determine agreement type"
                reasoning = "Could not parse document type from available information"
            
            # Extract logprobs if available
            logprobs = None
            if response_metadata and 'logprobs' in response_metadata:
                logprobs_data = response_metadata['logprobs']
                if isinstance(logprobs_data, dict) and 'content' in logprobs_data:
                    logprobs = [token.get('logprob', 0) for token in logprobs_data.get('content', [])]
                elif isinstance(logprobs_data, list):
                    logprobs = logprobs_data
            
            # Calculate confidence
            confidence_result = enhanced_confidence_scorer.score_extraction_confidence(
                question_text, answer, prompt[:200],
                logprobs=logprobs
            )
            
            # Set attribution
            attribution.set_llm_decision(
                llm_name=llm_name,
                answer=answer,
                confidence=confidence_result.get("overall_confidence", 50) / 100.0,
                prompt=prompt,
                raw_response=raw_text,
                reasoning=reasoning,
                token_count=len(prompt.split())
            )
            
            attribution.processing_time_ms = (time.time() - start_time) * 1000
            track_decision(attribution)
            
            print(f"    ✅ Identified as: {answer}")
            
            return {
                "answer": answer,
                "confidence": confidence_result.get("overall_confidence", 50) / 100.0,
                "extraction_confidence": confidence_result,
                "citations": [],
                "source_sentences": [],
                "processing_metadata": {
                    "type": "agreement_type_special",
                    "llm_used": llm_name,
                    "used_retrieval": False
                },
                "decision_attribution": attribution.to_dict()
            }
            
        except Exception as e:
            print(f"    ❌ Error identifying agreement type: {e}")
            attribution.set_error(str(e))
            attribution.processing_time_ms = (time.time() - start_time) * 1000
            track_decision(attribution)
            
            confidence_result = enhanced_confidence_scorer.score_error(str(e))
            
            return {
                "answer": "Error determining agreement type",
                "confidence": 0,
                "extraction_confidence": confidence_result,
                "citations": [],
                "source_sentences": [],
                "processing_metadata": {"error": str(e)},
                "decision_attribution": attribution.to_dict()
            }
    
    # Handle deterministic fields
    deterministic_fields = {
        'document_name', 'datasite_location', 'reviewer_name', 
        'target_company_name', 'counterparty_name', 'contract_start_date'
    }
    
    if question_id in deterministic_fields:
        attribution.set_deterministic("DETERMINISTIC_FIELD", "user_input")
        attribution.processing_time_ms = (time.time() - start_time) * 1000
        track_decision(attribution)
        
        # Use enhanced confidence scoring for deterministic fields
        confidence_result = enhanced_confidence_scorer.score_deterministic()
        
        return {
            "answer": "DETERMINISTIC_FIELD",
            "confidence": 1.0,
            "extraction_confidence": confidence_result,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {"type": "deterministic"},
            "decision_attribution": attribution.to_dict()
        }
    
    # Check if no relevant sentences were found
    if not target_sentences and searched_terms:
        # No clauses found for this topic
        attribution.set_no_clauses_found(searched_terms)
        attribution.processing_time_ms = (time.time() - start_time) * 1000
        track_decision(attribution)
        
        # Use enhanced confidence scoring for no clauses found
        confidence_result = enhanced_confidence_scorer.score_no_clauses_found(searched_terms)
        
        return {
            "answer": "Not specified in the contract",
            "confidence": 1.0,
            "extraction_confidence": confidence_result,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {
                "type": "no_clauses_found",
                "searched_terms": searched_terms
            },
            "decision_attribution": attribution.to_dict()
        }
    
    # Prepare for LLM processing
    target_sentence_texts = [s.get("sentence", s) if isinstance(s, dict) else s for s in target_sentences]
    reference_sentence_texts = [s.get("sentence", s) if isinstance(s, dict) else s for s in reference_sentences]
    
    # If we have sentences but they're empty, handle specially
    if target_sentences and not any(target_sentence_texts):
        attribution.set_error("Found classified sentences but no text content")
        attribution.processing_time_ms = (time.time() - start_time) * 1000
        track_decision(attribution)
        
        return {
            "answer": "Error: Empty sentence content",
            "confidence": 0,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {"error": "empty_sentences"},
            "decision_attribution": attribution.to_dict()
        }
    
    # Create prompt for LLM
    prompt = create_question_prompt(question, target_sentence_texts, reference_sentence_texts, template_data=template_data)
    prompt_tokens = count_tokens(prompt)
    
    try:
        # Call LLM (Granite by default)
        llm_name = "granite-3.3-8b-instruct"
        print(f"    🤖 Calling {llm_name} with {len(target_sentences)} clauses")
        
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

        # Parse response
        parsed_answer = None
        reasoning = None
        try:
            parsed_answer = json.loads(raw_text)
            reasoning = parsed_answer.get("reasoning", "")
        except Exception:
            # Try to extract JSON from code blocks
            if "```" in raw_text:
                try:
                    start = raw_text.find("{")
                    end = raw_text.rfind("}")
                    if start != -1 and end != -1:
                        parsed_answer = json.loads(raw_text[start:end+1])
                        reasoning = parsed_answer.get("reasoning", "")
                except Exception:
                    parsed_answer = None

        if isinstance(parsed_answer, dict) and "answer" in parsed_answer:
            answer = str(parsed_answer.get("answer", "")).strip()
            # NEVER use model-reported confidence - it's unreliable
        else:
            answer = raw_text
        
        # Extract logprobs from response metadata if available
        logprobs = None
        if response_metadata and 'logprobs' in response_metadata:
            logprobs_data = response_metadata['logprobs']
            # Extract token logprobs (format depends on API response structure)
            if isinstance(logprobs_data, dict) and 'content' in logprobs_data:
                # New format: logprobs.content[].logprob
                logprobs = [token.get('logprob', 0) for token in logprobs_data.get('content', [])]
            elif isinstance(logprobs_data, list):
                # Old format: direct list of logprobs
                logprobs = logprobs_data
        
        # Calculate confidence with enhanced method tracking
        # Use logprobs if available, otherwise fall back to heuristics
        confidence_result = enhanced_confidence_scorer.score_extraction_confidence(
            question_text, answer, ' '.join(target_sentence_texts[:3]),
            logprobs=logprobs  # Use actual logprobs, not model-reported confidence
        )
        final_confidence = confidence_result.get("overall_confidence", 50) / 100.0
        
        # Store confidence method for tracking
        confidence_result.get("confidence_method", "unknown")
        confidence_result.get("reasoning", "")
        
        # Set LLM attribution
        attribution.set_llm_decision(
            llm_name=llm_name,
            answer=answer,
            confidence=final_confidence,
            prompt=prompt,
            raw_response=raw_text,
            reasoning=reasoning,
            token_count=prompt_tokens
        )
        
        # Add source evidence
        attribution.source_sentences = target_sentences
        attribution.classified_terms = searched_terms
        
        # Check if reference shows deviation
        if reference_sentences and len(target_sentences) != len(reference_sentences):
            attribution.reference_deviation = "Different clause coverage vs reference"
        
        attribution.processing_time_ms = (time.time() - start_time) * 1000
        track_decision(attribution)
        
        print(f"    ✅ Answer: {answer[:100]}... (conf: {final_confidence:.1%})")
        
        # Create citations
        source_sentences_for_citation = []
        for sentence_data in target_sentences:
            if isinstance(sentence_data, dict):
                source_sentences_for_citation.append({
                    "sentence": sentence_data.get("sentence", ""),
                    "sentence_id": sentence_data.get("sentence_id"),
                    "page_number": sentence_data.get("page_number"),
                    "section_name": sentence_data.get("section_name")
                })
        
        citations = citation_tracker.create_citation_from_match(
            question_text, answer, source_sentences_for_citation
        )
        citation_ids = [c.citation_id for c in citations]
        
        # Risk assessment for relevant questions
        risk_assessment = None
        risk_relevant_questions = [
            'limitation_of_liability', 'indemnity', 'ip_rights', 'assignment_coc',
            'exclusivity_non_competes', 'forced_pricing_adjustments'
        ]
        
        if question_id in risk_relevant_questions:
            source_context = ' '.join(target_sentence_texts[:5])
            risk_context = f"Question: {question_text}\nAnswer: {answer}\nSource context: {source_context}"
            red_flags = red_flag_detector.detect_red_flags(risk_context)
            risk_assessment = risk_assessor.assess_clause_risk(risk_context, question_id)
            risk_assessment["red_flags"] = [red_flag_detector._serialize_red_flag(flag) for flag in red_flags]
            risk_assessment["red_flag_count"] = len(red_flags)
        
        return {
            "answer": answer,
            "confidence": final_confidence,
            "extraction_confidence": confidence_result,
            "citations": citation_ids,
            "source_sentences": source_sentences_for_citation,
            "risk_assessment": risk_assessment,
            "processing_metadata": {
                "type": "llm",
                "llm_used": llm_name,
                "prompt_tokens": prompt_tokens,
                "response_metadata": response_metadata,
                "citation_count": len(citations),
                "risk_assessed": risk_assessment is not None
            },
            "decision_attribution": attribution.to_dict()
        }
        
    except GraniteAPIError as e:
        print(f"    ❌ LLM Error: {e}")
        attribution.set_error(str(e))
        attribution.processing_time_ms = (time.time() - start_time) * 1000
        track_decision(attribution)
        
        # Use enhanced confidence scoring for error case
        confidence_result = enhanced_confidence_scorer.score_error(str(e))
        
        return {
            "answer": "Error: Could not process question",
            "confidence": 0,
            "extraction_confidence": confidence_result,
            "citations": [],
            "source_sentences": [],
            "processing_metadata": {"error": str(e)},
            "decision_attribution": attribution.to_dict()
        }


def process_questionnaire_enhanced(state: ContractAnalysisState) -> dict:
    """
    Enhanced questionnaire processor with comprehensive decision tracking.
    """
    print("--- PROCESSING QUESTIONNAIRE (ENHANCED WITH ATTRIBUTION) ---")
    
    # Initialize decision tracker
    tracker = initialize_decision_tracker()
    
    # Load questionnaire
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    questionnaire_path = os.path.join(base_dir, "questionnaires", "contract_evaluation.yaml")
    questionnaire_data = load_questionnaire(questionnaire_path)
    
    # Get classified sentences from both documents
    target_classified = state.get('classified_sentences', [])
    reference_classified = state.get('reference_classified_sentences', [])
    terminology_data = state.get('terminology_data', [])
    
    print(f"  Target classified sentences: {len(target_classified)}")
    print(f"  Reference classified sentences: {len(reference_classified)}")
    
    # If classification did not produce any target sentences, mark as unavailable
    classification_unavailable = (len(target_classified) == 0)

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
            
            print(f"\n  Question {total_questions}: {question_id}")
            
            # Get relevant sentences with attribution tracking
            target_sentences, reference_sentences, searched_terms = \
                get_relevant_sentences_with_attribution(
                    question_id, target_classified, reference_classified, terminology_data
                )
            
            print(f"    Searched terms: {searched_terms}")
            print(f"    Found: {len(target_sentences)} target, {len(reference_sentences)} reference sentences")
            
            # Handle sentence chunking if needed
            if target_sentences and len(target_sentences) > 10:
                target_chunks = split_sentences_by_tokens(target_sentences, max_tokens=2000)
                if len(target_chunks) > 1:
                    print(f"    Split into {len(target_chunks)} chunks")
                target_sentences = target_chunks[0]  # Use first chunk

            # If classification is unavailable, avoid misleading "Not specified" answers
            if classification_unavailable and question_id not in {"document_name", "datasite_location", "reviewer_name", "target_company_name", "counterparty_name", "contract_start_date", "agreement_type"}:
                print("    ⚠️  Classification unavailable – setting answer to Unknown and flagging for review")
                confidence_result = enhanced_confidence_scorer.score_error("classification_unavailable")
                answer_result = {
                    "answer": "Unknown – classification unavailable",
                    "confidence": 0,
                    "extraction_confidence": confidence_result,
                    "citations": [],
                    "source_sentences": [],
                    "processing_metadata": {"type": "classification_unavailable"},
                    "decision_attribution": {
                        "question_id": question_id,
                        "question_text": question.get("prompt", ""),
                        "method": "error",
                        "attribution": {"error": "classification_unavailable"}
                    }
                }
            else:
                # Answer with attribution tracking
                answer_result = answer_single_question_with_attribution(
                    question, target_sentences, reference_sentences,
                    terminology_data, searched_terms, state
                )
            
            # Extract results
            if isinstance(answer_result, dict):
                answer_text = answer_result.get("answer", "Error: No answer")
                confidence = answer_result.get("confidence", 0)
                citations = answer_result.get("citations", [])
                extraction_confidence = answer_result.get("extraction_confidence", {})
                risk_assessment = answer_result.get("risk_assessment")
                processing_metadata = answer_result.get("processing_metadata", {})
                decision_attribution = answer_result.get("decision_attribution", {})
            else:
                # Backward compatibility
                answer_text = answer_result
                confidence = 0.5
                citations = []
                extraction_confidence = {}
                risk_assessment = None
                processing_metadata = {}
                decision_attribution = {}
            
            # Build enhanced response
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
                'processing_metadata': processing_metadata,
                'decision_attribution': decision_attribution  # NEW: Full attribution
            }
            
            # Add answer source indicator
            ptype = (processing_metadata or {}).get('type')
            if ptype == 'deterministic':
                question_response['answer_source'] = 'Deterministic'
            elif ptype == 'no_clauses_found':
                question_response['answer_source'] = 'No Clauses Found'
            else:
                llm_used = (processing_metadata or {}).get('llm_used', 'LLM')
                question_response['answer_source'] = llm_used
            
            # Display summary
            method = decision_attribution.get('method', 'unknown')
            if method == 'no_relevant_clauses':
                print("    ⚠️  No relevant clauses found")
            elif method == 'deterministic':
                print("    ✅ Deterministic field")
            elif method in ['llm_granite', 'llm_mixtral', 'llm_ollama']:
                llm = decision_attribution.get('attribution', {}).get('llm_used', 'LLM')
                print(f"    🤖 {llm}: {answer_text[:80]}...")
            
            questionnaire_responses[section_key]['questions'].append(question_response)
    
    # Get decision tracking summary
    if tracker:
        decision_summary = tracker.get_summary_report()
        print("\n📊 Decision Attribution Summary:")
        print(f"  Total questions: {decision_summary['statistics']['total_questions']}")
        print(f"  Deterministic: {decision_summary['statistics']['deterministic_answers']}")
        print(f"  LLM answers: {decision_summary['statistics']['llm_answers']}")
        print(f"  No clauses found: {decision_summary['statistics']['no_clauses_found']}")
        print(f"  Errors: {decision_summary['statistics']['errors']}")
        print(f"  Requires review: {decision_summary['statistics']['requires_review']}")
        
        # Add tracker metadata to state
        questionnaire_responses['_decision_tracking'] = tracker.export_to_yaml_metadata()
    
    print(f"\nCompleted enhanced questionnaire processing: {total_questions} questions")
    
    return {
        'questionnaire_responses': questionnaire_responses,
        'decision_tracking_summary': decision_summary if tracker else {}
    }