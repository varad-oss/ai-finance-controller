"""Tier 1: Deterministic exact matching.

Matches records across sources using exact ID and amount equality.
No AI, no fuzzy logic — just provably correct matches.

Expected coverage: ~60-70% of records.
Confidence: always 1.0.
"""

import logging
from dataclasses import dataclass, field

from recon.models import NormalizedRecord, MatchResult, RecordSource

logger = logging.getLogger(__name__)


@dataclass
class Tier1Result:
    """Output of Tier 1 matching."""
    matches: list[MatchResult] = field(default_factory=list)
    unmatched_by_source: dict[str, list[NormalizedRecord]] = field(default_factory=dict)


def _build_index(records: list[NormalizedRecord], key_fn) -> dict[str, list[NormalizedRecord]]:
    """Build a lookup index from records using a key function.

    Returns a dict mapping key values to lists of records with that key.
    Records where key_fn returns None are excluded.
    """
    index: dict[str, list[NormalizedRecord]] = {}
    for record in records:
        key = key_fn(record)
        if key is not None:
            index.setdefault(key, []).append(record)
    return index


def match_oms_to_gateway(
    oms_records: list[NormalizedRecord],
    gateway_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Match OMS orders to Gateway payments via receipt/order_ref.

    Matching rule: oms.reference_ids["receipt"] == gateway.reference_ids["receipt"]
                   AND oms.gross_amount == gateway.gross_amount

    Returns:
        (matches, unmatched_oms, unmatched_gateway)
    """
    # Index gateway records by receipt
    gateway_by_receipt = _build_index(
        gateway_records,
        lambda r: r.reference_ids.get("receipt"),
    )

    matches: list[MatchResult] = []
    matched_gateway_ids: set[str] = set()
    unmatched_oms: list[NormalizedRecord] = []

    for oms_record in oms_records:
        receipt = oms_record.reference_ids.get("receipt")
        if receipt is None:
            unmatched_oms.append(oms_record)
            continue

        candidates = gateway_by_receipt.get(receipt, [])
        matched = False
        for gw_record in candidates:
            if gw_record.record_id in matched_gateway_ids:
                continue
            if oms_record.gross_amount == gw_record.gross_amount:
                matches.append(MatchResult(
                    left_source=RecordSource.OMS,
                    left_record_id=oms_record.record_id,
                    right_source=RecordSource.GATEWAY,
                    right_record_id=gw_record.record_id,
                    match_tier=1,
                    confidence=1.0,
                    rules_applied=["exact_receipt_match", "exact_amount_match"],
                    decision="matched",
                    explanation=f"Exact match: receipt={receipt}, amount={oms_record.gross_amount}",
                ))
                matched_gateway_ids.add(gw_record.record_id)
                matched = True
                break

        if not matched:
            unmatched_oms.append(oms_record)

    unmatched_gateway = [
        r for r in gateway_records if r.record_id not in matched_gateway_ids
    ]

    logger.info(
        "OMS↔Gateway Tier 1: %d matched, %d OMS unmatched, %d Gateway unmatched",
        len(matches), len(unmatched_oms), len(unmatched_gateway),
    )
    return matches, unmatched_oms, unmatched_gateway


def match_gateway_to_recon(
    gateway_records: list[NormalizedRecord],
    recon_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Match Gateway payments/refunds to Settlement Recon via entity_id.

    Matching rule: gateway.record_id == recon.record_id (entity_id)
                   AND types are compatible (payment↔payment, refund↔refund)

    Returns:
        (matches, unmatched_gateway, unmatched_recon)
    """
    # Index recon records by entity_id (which IS the record_id)
    recon_by_id = _build_index(recon_records, lambda r: r.record_id)

    matches: list[MatchResult] = []
    matched_recon_ids: set[str] = set()
    unmatched_gateway: list[NormalizedRecord] = []

    for gw_record in gateway_records:
        candidates = recon_by_id.get(gw_record.record_id, [])
        matched = False
        for recon_record in candidates:
            if recon_record.record_id in matched_recon_ids:
                continue
            # Types must be compatible
            if gw_record.transaction_type == recon_record.transaction_type:
                matches.append(MatchResult(
                    left_source=RecordSource.GATEWAY,
                    left_record_id=gw_record.record_id,
                    right_source=RecordSource.RECON,
                    right_record_id=recon_record.record_id,
                    match_tier=1,
                    confidence=1.0,
                    rules_applied=["exact_entity_id_match", "type_match"],
                    decision="matched",
                    explanation=(
                        f"Exact match: entity_id={gw_record.record_id}, "
                        f"type={gw_record.transaction_type.value}"
                    ),
                ))
                matched_recon_ids.add(recon_record.record_id)
                matched = True
                break

        if not matched:
            unmatched_gateway.append(gw_record)

    unmatched_recon = [
        r for r in recon_records if r.record_id not in matched_recon_ids
    ]

    logger.info(
        "Gateway↔Recon Tier 1: %d matched, %d Gateway unmatched, %d Recon unmatched",
        len(matches), len(unmatched_gateway), len(unmatched_recon),
    )
    return matches, unmatched_gateway, unmatched_recon


def match_recon_to_bank(
    recon_records: list[NormalizedRecord],
    bank_records: list[NormalizedRecord],
) -> tuple[list[MatchResult], list[NormalizedRecord], list[NormalizedRecord]]:
    """Match Settlement Recon to Bank Statement via UTR.

    This matches at the SETTLEMENT level, not individual payment level.
    Multiple recon records share a settlement_id+UTR; the bank has one credit per UTR.

    Matching rule: recon.reference_ids["utr"] == bank.reference_ids["utr"]
                   AND settlement net amount == bank credit amount

    Returns:
        (matches, unmatched_recon, unmatched_bank)
    """
    matches: list[MatchResult] = []
    matched_bank_ids: set[str] = set()
    unmatched_recon: list[NormalizedRecord] = []

    # Index bank records by UTR
    bank_by_utr = {}
    for r in bank_records:
        utr = r.reference_ids.get("utr")
        if utr:
            bank_by_utr[utr] = r

    # Group recon records by UTR
    recon_by_utr = {}
    for r in recon_records:
        utr = r.reference_ids.get("utr")
        if utr:
            recon_by_utr.setdefault(utr, []).append(r)
        else:
            unmatched_recon.append(r)

    for utr, recon_group in recon_by_utr.items():
        bank_record = bank_by_utr.get(utr)
        if not bank_record or bank_record.record_id in matched_bank_ids:
            unmatched_recon.extend(recon_group)
            continue
            
        # Sum net amounts
        total_recon_net = sum(r.net_amount for r in recon_group)
        
        if total_recon_net == bank_record.gross_amount:
            # Match them all
            for recon_record in recon_group:
                matches.append(MatchResult(
                    left_source=RecordSource.RECON,
                    left_record_id=recon_record.record_id,
                    right_source=RecordSource.BANK,
                    right_record_id=bank_record.record_id,
                    match_tier=1,
                    confidence=1.0,
                    rules_applied=["exact_utr_match", "exact_aggregated_amount_match"],
                    decision="matched",
                    explanation=f"Exact match (batch): UTR={utr}, aggregated_amount={total_recon_net}",
                ))
            matched_bank_ids.add(bank_record.record_id)
        else:
            unmatched_recon.extend(recon_group)

    unmatched_bank = [
        r for r in bank_records if r.record_id not in matched_bank_ids
    ]

    logger.info(
        "Recon↔Bank Tier 1: %d matched, %d Recon unmatched, %d Bank unmatched",
        len(matches), len(unmatched_recon), len(unmatched_bank),
    )
    return matches, unmatched_recon, unmatched_bank


def run_tier1(
    oms_records: list[NormalizedRecord],
    gateway_records: list[NormalizedRecord],
    recon_records: list[NormalizedRecord],
    bank_records: list[NormalizedRecord],
) -> Tier1Result:
    """Run all Tier 1 deterministic matching across all source pairs.

    Returns a Tier1Result with all matches and remaining unmatched records.
    """
    all_matches: list[MatchResult] = []

    # OMS ↔ Gateway
    oms_gw_matches, unmatched_oms, unmatched_gw = match_oms_to_gateway(
        oms_records, gateway_records
    )
    all_matches.extend(oms_gw_matches)

    # Gateway ↔ Recon (use ALL gateway records, not just unmatched from OMS step)
    gw_recon_matches, unmatched_gw_from_recon, unmatched_recon = match_gateway_to_recon(
        gateway_records, recon_records
    )
    all_matches.extend(gw_recon_matches)

    # Recon ↔ Bank
    recon_bank_matches, unmatched_recon_from_bank, unmatched_bank = match_recon_to_bank(
        recon_records, bank_records
    )
    all_matches.extend(recon_bank_matches)

    result = Tier1Result(
        matches=all_matches,
        unmatched_by_source={
            RecordSource.OMS.value: unmatched_oms,
            RecordSource.GATEWAY.value: unmatched_gw,
            RecordSource.RECON.value: unmatched_recon_from_bank,
            RecordSource.BANK.value: unmatched_bank,
        },
    )

    logger.info(
        "Tier 1 complete: %d total matches across all source pairs",
        len(all_matches),
    )
    return result
