"""Tier 3: AI Exception Investigation.

Uses LLM (Google Gemini) to investigate records that failed Tiers 1 and 2.
Returns structured JSON with diagnosis and suggested actions.
"""

import json
import time
import logging
from typing import Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from recon.models import NormalizedRecord, ExceptionRecord, RecordSource
from recon.config import settings
from recon.audit.db import AuditDB

logger = logging.getLogger(__name__)


class AIDiagnosis(BaseModel):
    """Structured output expected from the LLM."""
    diagnosis_category: str = Field(..., description="One of: timing_lag, fee_variance, duplicate, missing_record, data_entry_error, dispute_adjustment, genuinely_unreconcilable")
    confidence: float = Field(..., description="0.0 to 1.0 confidence in the diagnosis")
    suggested_match_id: Optional[str] = Field(None, description="The ID of the suggested matching record, if one exists")
    explanation: str = Field(..., description="Human-readable explanation of why this conclusion was reached")
    suggested_action: str = Field(..., description="One of: auto_match, manual_review, write_off, investigate")


def _build_llm_prompt(unmatched_record: NormalizedRecord, context_records: list[NormalizedRecord]) -> str:
    """Build the prompt for the LLM."""
    prompt = f"""You are a financial reconciliation expert.
Please diagnose why the following record could not be matched automatically.

UNMATCHED RECORD:
Source: {unmatched_record.source.value}
ID: {unmatched_record.record_id}
Type: {unmatched_record.transaction_type.value}
Gross Amount: {unmatched_record.gross_amount}
Net Amount: {unmatched_record.net_amount}
Date: {unmatched_record.timestamp}
Description: {unmatched_record.description}
Ref IDs: {unmatched_record.reference_ids}

CONTEXT (Near-misses from other sources):
"""
    if not context_records:
        prompt += "None available.\n"
    else:
        for r in context_records:
            prompt += f"- [{r.source.value}] ID: {r.record_id}, Amount: {r.gross_amount}, Date: {r.timestamp}, Desc: {r.description}, Refs: {r.reference_ids}\n"

    prompt += """
If the unmatched record clearly corresponds to one of the context records (e.g. a typo in the amount, or a date lag), provide its ID in suggested_match_id and set confidence accordingly.
"""
    return prompt


def investigate_exceptions(
    unmatched_by_source: dict[str, list[NormalizedRecord]],
    db: AuditDB,
    batch_decision_ids: dict[str, int] = None, # mapping of record_id to match_decision_id
) -> list[ExceptionRecord]:
    """Run Tier 3 AI investigation on unmatched records.
    
    To avoid excessive API calls, limits to settings.tier3_max_llm_calls.
    """
    if not settings.llm_configured:
        logger.warning("Gemini API key not configured. Skipping Tier 3 AI Investigation.")
        return _fallback_flag_exceptions(unmatched_by_source)

    client = genai.Client(api_key=settings.gemini_api_key)
    exceptions: list[ExceptionRecord] = []
    
    # Flatten unmatched records
    all_unmatched = []
    for source, records in unmatched_by_source.items():
        all_unmatched.extend(records)

    # Sort by amount descending to prioritize large exceptions
    all_unmatched.sort(key=lambda r: r.gross_amount, reverse=True)
    
    processed = 0
    max_calls = settings.tier3_max_llm_calls

    for record in all_unmatched:
        if processed >= max_calls:
            logger.warning("Reached max Tier 3 LLM calls (%d). Flagging remaining without AI.", max_calls)
            # Add remaining as manual review
            exceptions.append(ExceptionRecord(
                source=record.source,
                record_id=record.record_id,
                diagnosis_category="uninvestigated",
                confidence=0.0,
                explanation="Reached Tier 3 LLM API limit.",
                suggested_action="manual_review",
                investigated_by="tier2_rules"
            ))
            continue

        context = [
            r for r in all_unmatched 
            if r.source != record.source 
            and abs(((r.timestamp.replace(tzinfo=None) if hasattr(r.timestamp, "replace") else r.timestamp) - 
                    (record.timestamp.replace(tzinfo=None) if hasattr(record.timestamp, "replace") else record.timestamp)).days) <= 7
        ][:5]

        prompt = _build_llm_prompt(record, context)
        
        try:
            max_retries = 1
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model=settings.llm_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=AIDiagnosis,
                            system_instruction="You are a financial reconciliation expert AI.",
                            temperature=0.0
                        )
                    )
                    
                    # The response text will be a valid JSON matching the schema
                    diagnosis_data = json.loads(response.text)
                    diagnosis = AIDiagnosis(**diagnosis_data)
                    
                    usage_in = 0
                    usage_out = 0
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        usage_in = response.usage_metadata.prompt_token_count
                        usage_out = response.usage_metadata.candidates_token_count
                    break # Success, break out of retry loop
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str and attempt < max_retries - 1:
                        logger.warning(f"Rate limited. Sleeping 25s before retry (attempt {attempt+1}/{max_retries})...")
                        time.sleep(35)
                    else:
                        raise e
            
            if batch_decision_ids and record.record_id in batch_decision_ids:
                decision_id = batch_decision_ids[record.record_id]
                db.log_ai_investigation(
                    match_decision_id=decision_id,
                    llm_model=settings.llm_model,
                    prompt_text=prompt,
                    response_text=response.text,
                    diagnosis_category=diagnosis.diagnosis_category,
                    suggested_action=diagnosis.suggested_action,
                    explanation=diagnosis.explanation,
                    token_count_input=usage_in,
                    token_count_output=usage_out,
                )

            action = diagnosis.suggested_action
            if action == "auto_match" and diagnosis.confidence < settings.tier3_confidence_threshold:
                action = "manual_review"
                
            exceptions.append(ExceptionRecord(
                source=record.source,
                record_id=record.record_id,
                diagnosis_category=diagnosis.diagnosis_category,
                confidence=diagnosis.confidence,
                explanation=diagnosis.explanation,
                suggested_action=action,
                suggested_match_id=diagnosis.suggested_match_id,
                investigated_by="tier3_ai"
            ))
            processed += 1
            logger.debug(f"AI diagnosed {record.record_id} as {diagnosis.diagnosis_category}")
            
        except Exception as e:
            logger.error(f"LLM API failed for record {record.record_id}: {e}")
            exceptions.append(ExceptionRecord(
                source=record.source,
                record_id=record.record_id,
                diagnosis_category="api_error",
                confidence=0.0,
                explanation=str(e),
                suggested_action="manual_review",
                investigated_by="tier3_ai"
            ))
            
        time.sleep(4.5)  # Enforce 15 RPM free tier limit

    return exceptions

def _fallback_flag_exceptions(unmatched_by_source: dict[str, list[NormalizedRecord]]) -> list[ExceptionRecord]:
    """Fallback if LLM is not configured."""
    exceptions = []
    for source, records in unmatched_by_source.items():
        for r in records:
            exceptions.append(ExceptionRecord(
                source=r.source,
                record_id=r.record_id,
                diagnosis_category="unreconcilable",
                confidence=0.0,
                explanation="No AI investigation performed (LLM not configured).",
                suggested_action="manual_review",
                investigated_by="tier2_rules"
            ))
    return exceptions
