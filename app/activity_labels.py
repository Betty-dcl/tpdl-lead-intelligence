"""Map activity_log action codes to human-readable labels for the UI."""

ACTIVITY_LABELS: dict[str, str] = {
    "scanned_market": "ran a market scan",
    "scored_company": "scored a company",
    "drafted_post": "drafted a LinkedIn post",
    "wrote_email": "wrote an outbound email",
    "structured_case_study": "wrote a case study",
    "scanned_trends": "scanned trends",
    "monitored_news": "monitored news",
    "scanned_linkedin": "scanned LinkedIn activity",
    "generated_brief": "generated a TPDL brief",
    "scanned_signal": "scanned signal pipeline",
    "responded_to_user": "answered a message",
}


def label_for(action: str) -> str:
    return ACTIVITY_LABELS.get(action, action.replace("_", " "))
