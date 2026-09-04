"""Tier 2: Fuzzy Rule-Based Matching.

Applies heuristic rules (amount tolerance, date windows, description similarity)
to records that failed Tier 1 deterministic matching.
No AI is used here, just code rules. Match accepted if confidence >= threshold (0.75).
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from Levenshtein import ratio

from recon.models import NormalizedRecord, MatchResult, RecordSource
from recon.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Tier2Result:
    """Output of Tier 2 matching."""
    matches: list[MatchResult] = field(default_factory=list)
    unmatched_by_source: dict[str, list[NormalizedRecord]] = field(default_factory=dict)


def _check_amount_tolerance(amt1: int, amt2: int, tolerance_percent: float) -> bool:
    """Check if two amounts are within tolerance."""
    if amt1 == 0 and amt2 == 0:
        return True
    diff = abs(amt1 - amt2)
    max_amt = max(amt1, amt2)
    return (diff / max_amt * 100) <= tolerance_percent


def _check_date_window(date1, date2, window_days: int) -> bool:
    """Check if two dates are within the window."""
    if not date1 or not date2:
        return False
    d1 = date1.replace(tzinfo=None) if hasattr(date1, "replace") else date1
    d2 = date2.replace(tzinfo=None) if hasattr(date2, "replace") else date2
    diff = abs((d1 - d2).days)
    return diff <= window_days


def match_oms_to_gateway_fuzzy(
    oms_records: list[NormalizedRecord],
    gateway_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Fuzzy match OMS to Gateway."""
    matches = []
    matched_gw_ids = set()
    matched_oms_ids = set()

    tolerance = settings.tier2_amount_tolerance_percent
    window = settings.tier2_date_window_days

    for oms_rec in oms_records:
        if oms_rec.record_id in matched_oms_ids:
            continue
            
        best_match = None
        best_score = 0.0
        best_rules = []
        best_explanation = ""
        scored_candidates = []

        # Find the best fuzzy match
        for gw_rec in gateway_records:
            if gw_rec.record_id in matched_gw_ids:
                continue

            score = 0.0
            rules = []
            
            # Rule 1: Amount within tolerance
            if _check_amount_tolerance(oms_rec.gross_amount, gw_rec.gross_amount, tolerance):
                score += 0.4
                rules.append("amount_within_tolerance")
            
            # Rule 2: Dates within window
            if _check_date_window(oms_rec.timestamp, gw_rec.timestamp, window):
                score += 0.3
                rules.append("date_within_window")

            # Rule 3: Receipt partial match or email match
            oms_receipt = str(oms_rec.reference_ids.get("receipt", ""))
            gw_receipt = str(gw_rec.reference_ids.get("receipt", ""))
            if oms_receipt and gw_receipt and (oms_receipt in gw_receipt or gw_receipt in oms_receipt):
                score += 0.25
                rules.append("receipt_substring_match")

            if score > 0:
                scored_candidates.append((score, rules, gw_rec))

            if score > best_score:
                best_score = score
                best_match = gw_rec
                best_rules = rules
                best_explanation = f"Fuzzy matched with score {score:.2f} using rules: {rules}"

        # Filter out cases where there are multiple top-scoring candidates (ambiguous)
        top_score_candidates = [
            (score, rules, rec) for score, rules, rec in scored_candidates
            if score == best_score
        ]
        
        if best_match and best_score >= settings.tier2_confidence_threshold and len(top_score_candidates) == 1:
            matches.append(MatchResult(
                left_source=RecordSource.OMS,
                left_record_id=oms_rec.record_id,
                right_source=RecordSource.GATEWAY,
                right_record_id=best_match.record_id,
                match_tier=2,
                confidence=best_score,
                rules_applied=best_rules,
                decision="matched",
                explanation=best_explanation,
            ))
            matched_gw_ids.add(best_match.record_id)
            matched_oms_ids.add(oms_rec.record_id)
        elif best_match:
            logger.debug(f"Tier 2 OMS↔Gateway Near Miss: oms {oms_rec.record_id} -> gw {best_match.record_id} (Score: {best_score:.2f})")

    unmatched_oms = [r for r in oms_records if r.record_id not in matched_oms_ids]
    unmatched_gw = [r for r in gateway_records if r.record_id not in matched_gw_ids]
    
    logger.info("OMS↔Gateway Tier 2: %d matched", len(matches))
    return matches, unmatched_oms, unmatched_gw


def match_gateway_to_recon_fuzzy(
    gateway_records: list[NormalizedRecord],
    recon_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Fuzzy match Gateway to Settlement Recon."""
    matches = []
    matched_recon_ids = set()
    matched_gw_ids = set()

    tolerance = settings.tier2_amount_tolerance_percent
    window = settings.tier2_date_window_days

    for gw_rec in gateway_records:
        best_match = None
        best_score = 0.0
        best_rules = []

        for recon_rec in recon_records:
            if recon_rec.record_id in matched_recon_ids:
                continue

            score = 0.0
            rules = []
            
            # Rule 1: Amount exact or net amount exact
            if gw_rec.gross_amount == recon_rec.gross_amount:
                score += 0.5
                rules.append("amount_exact")
            elif _check_amount_tolerance(gw_rec.gross_amount, recon_rec.gross_amount, tolerance):
                score += 0.3
                rules.append("amount_within_tolerance")
                
            # Rule 2: Dates within window
            if _check_date_window(gw_rec.timestamp, recon_rec.timestamp, window):
                score += 0.4
                rules.append("date_within_window")

            # Rule 3: Type matches
            if gw_rec.transaction_type == recon_rec.transaction_type:
                score += 0.1
                rules.append("type_match")

            if score > best_score:
                best_score = score
                best_match = recon_rec
                best_rules = rules

        if best_match and best_score >= settings.tier2_confidence_threshold:
            matches.append(MatchResult(
                left_source=RecordSource.GATEWAY,
                left_record_id=gw_rec.record_id,
                right_source=RecordSource.RECON,
                right_record_id=best_match.record_id,
                match_tier=2,
                confidence=best_score,
                rules_applied=best_rules,
                decision="matched",
                explanation=f"Fuzzy matched with score {best_score:.2f}",
            ))
            matched_recon_ids.add(best_match.record_id)
            matched_gw_ids.add(gw_rec.record_id)
        elif best_match:
            logger.debug(f"Tier 2 Gateway↔Recon Near Miss: gw {gw_rec.record_id} -> recon {best_match.record_id} (Score: {best_score:.2f})")

    unmatched_gw = [r for r in gateway_records if r.record_id not in matched_gw_ids]
    unmatched_recon = [r for r in recon_records if r.record_id not in matched_recon_ids]
    
    logger.info("Gateway↔Recon Tier 2: %d matched", len(matches))
    return matches, unmatched_gw, unmatched_recon


def match_recon_to_bank_fuzzy(
    recon_records: list[NormalizedRecord],
    bank_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Fuzzy match Settlement Recon to Bank Statement.
    Particularly useful for garbled descriptions and missing UTRs.
    """
    matches = []
    matched_bank_ids = set()
    matched_recon_ids = set()

    tolerance = settings.tier2_amount_tolerance_percent
    window = settings.tier2_date_window_days

    for recon_rec in recon_records:
        utr = recon_rec.reference_ids.get("utr", "")
        
        best_match = None
        best_score = 0.0
        best_rules = []

        for bank_rec in bank_records:
            if bank_rec.record_id in matched_bank_ids:
                continue

            score = 0.0
            rules = []

            # Rule 1: Amount exact match
            if recon_rec.net_amount == bank_rec.gross_amount:
                score += 0.4
                rules.append("amount_exact_match")
            elif _check_amount_tolerance(recon_rec.net_amount, bank_rec.gross_amount, tolerance):
                score += 0.2
                rules.append("amount_within_tolerance")

            # Rule 2: Date window
            # Bank settlement date vs recon settlement date
            recon_date = recon_rec.settlement_date or recon_rec.timestamp
            bank_date = bank_rec.timestamp
            if _check_date_window(recon_date, bank_date, window):
                score += 0.2
                rules.append("date_within_window")

            # Rule 3: Description similarity (Levenshtein)
            # Find if UTR is hidden inside the bank description
            if utr and utr in bank_rec.description:
                score += 0.4
                rules.append("utr_in_description")
            else:
                sim = ratio(str(utr).lower(), bank_rec.description.lower())
                if sim > 0.6:
                    score += 0.2
                    rules.append(f"description_similarity_{sim:.2f}")

            if score > best_score:
                best_score = score
                best_match = bank_rec
                best_rules = rules

        if best_match and best_score >= settings.tier2_confidence_threshold:
            matches.append(MatchResult(
                left_source=RecordSource.RECON,
                left_record_id=recon_rec.record_id,
                right_source=RecordSource.BANK,
                right_record_id=best_match.record_id,
                match_tier=2,
                confidence=best_score,
                rules_applied=best_rules,
                decision="matched",
                explanation=f"Fuzzy match (score {best_score:.2f}): {', '.join(best_rules)}",
            ))
            matched_bank_ids.add(best_match.record_id)
            matched_recon_ids.add(recon_rec.record_id)
        elif best_match:
            logger.debug(f"Tier 2 Recon↔Bank Near Miss: recon {recon_rec.record_id} -> bank {best_match.record_id} (Score: {best_score:.2f})")

    unmatched_recon = [
        r for r in recon_records if r.record_id not in matched_recon_ids
    ]
    unmatched_bank = [
        r for r in bank_records if r.record_id not in matched_bank_ids
    ]

    logger.info(
        "Recon↔Bank Tier 2: %d matched",
        len(matches),
    )
    return matches, unmatched_recon, unmatched_bank


def run_tier2(
    oms_records: list[NormalizedRecord],
    gateway_records: list[NormalizedRecord],
    recon_records: list[NormalizedRecord],
    bank_records: list[NormalizedRecord],
) -> Tier2Result:
    """Run Tier 2 fuzzy matching on records that failed Tier 1."""
    all_matches = []

    # OMS ↔ Gateway
    oms_gw_matches, unmatched_oms, unmatched_gw = match_oms_to_gateway_fuzzy(
        oms_records, gateway_records
    )
    all_matches.extend(oms_gw_matches)

    # Gateway ↔ Recon
    gw_recon_matches, unmatched_gw, unmatched_recon = match_gateway_to_recon_fuzzy(
        unmatched_gw, recon_records
    )
    all_matches.extend(gw_recon_matches)

    # Recon ↔ Bank
    recon_bank_matches, unmatched_recon, unmatched_bank = match_recon_to_bank_fuzzy(
        unmatched_recon, bank_records
    )
    all_matches.extend(recon_bank_matches)

    result = Tier2Result(
        matches=all_matches,
        unmatched_by_source={
            RecordSource.OMS.value: unmatched_oms,
            RecordSource.GATEWAY.value: unmatched_gw,
            RecordSource.RECON.value: unmatched_recon,
            RecordSource.BANK.value: unmatched_bank,
        },
    )

    logger.info("Tier 2 complete: %d total matches", len(all_matches))
    return result
