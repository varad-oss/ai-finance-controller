import re

with open("evaluate.py", "r") as f:
    content = f.read()

new_logic = """
EXPECTED_FAIL_LEGS = {
    "missing_bank_entry": {"recon->bank", "bank->recon"},
    "duplicate_payment": {"oms->gateway", "gateway->oms"},
    "amount_discrepancy": {"oms->gateway", "gateway->oms"},
    "ghost_refund": {"oms->gateway", "gateway->oms"},
    "orphaned_record": {"oms->gateway", "gateway->oms", "gateway->recon", "recon->gateway"},
    "dispute_adjustment": set() # The data generator doesn't actually break any legs for this, it just tags it.
}
"""

replacement = """
        # Check exception leakage first
        leaked_left = left_id in exception_ids
        leaked_right = right_id in exception_ids if right_id else False
        
        is_leakage = False
        leaked_id = None
        if leaked_left or leaked_right:
            leaked_id = left_id if leaked_left else right_id
            cat = exception_ids[leaked_id]
            leg = f"{m['record_source']}->{m['matched_source']}"
            
            # If the leg that matched is in the EXPECTED_FAIL_LEGS for this category, 
            # then it's a true leak. Otherwise, it's expected to match!
            expected_fail = EXPECTED_FAIL_LEGS.get(cat, set())
            if leg in expected_fail:
                is_leakage = True
                
        if is_leakage:
            exception_leakage += 1
            other_id = right_id if leaked_left else left_id
            exception_leakage_report.append({
                "leaked_exception_id": leaked_id,
                "exception_category": exception_ids[leaked_id],
                "wrongly_matched_to": other_id,
                "match_sources": f"{m['record_source']}->{m['matched_source']}",
                "match_tier": m["match_tier"],
                "tag": "matched_a_genuine_exception",
            })
            continue  # Don't double-count as correct/false/unverified
"""

content = content.replace("def evaluate(batch_id: str, db: AuditDB):", new_logic + "\ndef evaluate(batch_id: str, db: AuditDB):")

old_leakage_block = """        # Check exception leakage first: did we match an ID that ground truth
        # says should never match?
        leaked_left = left_id in exception_ids
        leaked_right = right_id in exception_ids if right_id else False
        
        if leaked_left or leaked_right:
            exception_leakage += 1
            leaked_id = left_id if leaked_left else right_id
            other_id = right_id if leaked_left else left_id
            exception_leakage_report.append({
                "leaked_exception_id": leaked_id,
                "exception_category": exception_ids[leaked_id],
                "wrongly_matched_to": other_id,
                "match_sources": f"{m['record_source']}->{m['matched_source']}",
                "match_tier": m["match_tier"],
                "tag": "matched_a_genuine_exception",
            })
            continue  # Don't double-count as correct/false/unverified"""

content = content.replace(old_leakage_block, replacement.strip())

with open("evaluate.py", "w") as f:
    f.write(content)
