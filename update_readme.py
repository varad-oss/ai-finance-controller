import json
import sqlite3

with open("results/metrics.json") as f:
    m = json.load(f)

conn = sqlite3.connect("audit_trail.db")
conn.row_factory = sqlite3.Row
exc_count = conn.execute("SELECT COUNT(*) as c FROM match_decisions WHERE batch_id=? AND decision != 'matched'", (m["batch_id"],)).fetchone()["c"]

with open("README_new.md") as f:
    readme = f.read()

replacements = {
    "{TOTAL_RECORDS}": str(m["total_records"]),
    "{PROCESSING_TIME}": str(m["processing_time_ms"]),
    "{TOTAL_MATCHES}": str(m["matches_made"]),
    "{CORRECT_MATCHES}": str(m["correct_matches"]),
    "{UNVERIFIED_MATCHES}": str(m["unverified_matches"]),
    "{EXCEPTIONS_FLAGGED}": str(exc_count),
    "{FALSE_MATCHES}": str(m["false_matches"]),
    "{EXCEPTION_LEAKAGE}": str(m["exception_leakage"]),
    "{TIER1}": str(m["tier1_matched"]),
    "{TIER2}": str(m["tier2_matched"]),
    "{TIER3}": str(m["tier3_matched"]),
    "{TIER3_ATTEMPTS}": "15"
}

for k, v in replacements.items():
    readme = readme.replace(k, v)
    
with open("README.md", "w") as f:
    f.write(readme)
