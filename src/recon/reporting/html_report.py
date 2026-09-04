"""HTML Report generator for reconciliation results."""

import logging
from pathlib import Path
from jinja2 import Environment, BaseLoader

from recon.audit.db import AuditDB
from recon.config import settings

logger = logging.getLogger(__name__)


TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Finance Controller - Reconciliation Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 2rem; }
        h1, h2 { color: #1a56db; }
        .summary-card { background: #f3f4f6; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; display: flex; gap: 2rem; }
        .metric { display: flex; flex-direction: column; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #1a56db; }
        .metric-label { font-size: 0.875rem; color: #6b7280; text-transform: uppercase; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background-color: #f9fafb; font-weight: 600; color: #374151; }
        tr:hover { background-color: #f9fafb; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        .badge-error { background-color: #fee2e2; color: #991b1b; }
        .badge-warning { background-color: #fef3c7; color: #92400e; }
        .badge-success { background-color: #d1fae5; color: #065f46; }
    </style>
</head>
<body>
    <h1>AI Finance Controller - Reconciliation Report</h1>
    
    {% if not llm_configured %}
    <div style="background-color: #fee2e2; border: 1px solid #dc2626; color: #991b1b; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-weight: bold;">
        WARNING: Tier 3 AI Investigation was SKIPPED because no LLM API key was configured. All exceptions defaulted to manual review.
    </div>
    {% endif %}
    
    <div class="summary-card">
        <div class="metric">
            <span class="metric-value">{{ summary.total_records }}</span>
            <span class="metric-label">Total Records</span>
        </div>
        <div class="metric">
            <span class="metric-value" style="color: #059669;">{{ summary.tier1_matched + summary.tier2_matched + summary.tier3_matched }}</span>
            <span class="metric-label">Matched</span>
        </div>
        <div class="metric">
            <span class="metric-value" style="color: #dc2626;">{{ summary.human_review }}</span>
            <span class="metric-label">Exceptions (Review)</span>
        </div>
        <div class="metric">
            <span class="metric-value" style="color: #4f46e5;">{{ summary.processing_time_ms }} ms</span>
            <span class="metric-label">Processing Time</span>
        </div>
    </div>

    <h2>Exception Report & AI Diagnosis</h2>
    <p>These records could not be automatically reconciled and require human review. Where applicable, the AI has provided a diagnosis.</p>

    <table>
        <thead>
            <tr>
                <th>Source</th>
                <th>Record ID</th>
                <th>Diagnosis Category</th>
                <th>Explanation & AI Reasoning</th>
                <th>Confidence</th>
            </tr>
        </thead>
        <tbody>
            {% for exc in exceptions %}
            <tr>
                <td><span class="badge" style="background: #e5e7eb; color: #374151;">{{ exc.record_source }}</span></td>
                <td style="font-family: monospace; font-size: 0.875rem;">{{ exc.record_id }}</td>
                <td><span class="badge badge-warning">{{ exc.category }}</span></td>
                <td>
                    {{ exc.explanation }}
                    {% if exc.ai_response %}
                    <details style="margin-top: 0.5rem; font-size: 0.875rem; background: #f9fafb; padding: 0.5rem; border: 1px solid #e5e7eb; border-radius: 4px;">
                        <summary style="cursor: pointer; font-weight: 600; color: #4b5563;">View Raw AI Response</summary>
                        <pre style="white-space: pre-wrap; font-family: monospace; margin-top: 0.5rem; color: #374151;">{{ exc.ai_response }}</pre>
                    </details>
                    {% endif %}
                </td>
                <td>
                    {% if exc.confidence > 0 %}
                    {{ "%.2f"|format(exc.confidence) }}
                    {% else %}
                    -
                    {% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="5" style="text-align: center; color: #6b7280; font-style: italic;">No exceptions flagged. Perfect match!</td></tr>
            {% endfor %}
        </tbody>
    </table>

    <h2 style="margin-top: 3rem;">Tier Breakdown</h2>
    <table>
        <thead>
            <tr>
                <th>Tier</th>
                <th>Matches</th>
                <th>Coverage</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Tier 1 (Deterministic)</td>
                <td>{{ summary.tier1_matched }}</td>
                <td>{{ "%.1f"|format(summary.tier1_matched / summary.total_records * 100) }}%</td>
            </tr>
            <tr>
                <td>Tier 2 (Fuzzy Rules)</td>
                <td>{{ summary.tier2_matched }}</td>
                <td>{{ "%.1f"|format(summary.tier2_matched / summary.total_records * 100) }}%</td>
            </tr>
            <tr>
                <td>Tier 3 (AI Investigation)</td>
                <td>{{ summary.tier3_matched }}</td>
                <td>{{ "%.1f"|format(summary.tier3_matched / summary.total_records * 100) }}%</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""


def generate_html_report(batch_id: str, db: AuditDB, output_path: str = "results/report.html"):
    """Generate a static HTML report for a reconciliation batch."""
    summary = db.get_batch_summary(batch_id)
    if not summary:
        logger.error(f"No summary found for batch {batch_id}")
        return

    decisions = db.get_decisions_for_batch(batch_id)
    human_review = [d for d in decisions if d["decision"] != "matched"]
    
    exceptions = []
    for hr in human_review:
        ai_data = db.get_ai_investigation(hr["id"])
        ai_resp = None
        if ai_data:
            cat = ai_data['diagnosis_category']
            expl = ai_data['explanation']
            conf = hr["confidence"] or 0.0
            ai_resp = ai_data.get('response_text')
        else:
            cat = "Unreconcilable"
            expl = hr["explanation"] or "Failed matching rules."
            conf = 0.0
            
        exceptions.append({
            "record_source": hr["record_source"],
            "record_id": hr["record_id"],
            "category": cat,
            "explanation": expl,
            "confidence": conf,
            "ai_response": ai_resp
        })

    env = Environment(loader=BaseLoader())
    template = env.from_string(TEMPLATE)
    
    html_content = template.render(
        summary=summary,
        exceptions=exceptions,
        llm_configured=settings.llm_configured
    )
    
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    logger.info(f"HTML report generated at {out_path}")
