"""AI-assisted before/after resolution verification.

Three outcomes only - and never a silent auto-close:
    verified        both photos look like the same place and the issue is gone
    requires_review ambiguous / low confidence / different-looking location
    failed          the reported issue is still visible in the after photo

The verdict is advisory: an admin can always override it, and the citizen's
confirmation is what finally closes the complaint.
"""
import logging
from typing import Optional

from . import ai

logger = logging.getLogger(__name__)

VERDICT_VERIFIED = "verified"
VERDICT_REVIEW = "requires_review"
VERDICT_FAILED = "failed"

PROMPT = """You are auditing a municipal grievance resolution.
You receive two photos: IMAGE 1 = the original complaint, IMAGE 2 = the officer's
after-resolution photo.

Judge:
1. SAME_LOCATION: do both photos plausibly show the same spot (same street,
   building, wall, pole, vegetation, perspective)? Answer yes/no/unsure.
2. ISSUE_ADDRESSED: is the reported issue (e.g. garbage pile, pothole, broken
   light, water leak) no longer visible in IMAGE 2?
3. EVIDENCE: one short sentence describing what changed.

Return JSON ONLY:
{
  "same_location": "yes|no|unsure",
  "issue_addressed": true|false,
  "confidence": 0.0-1.0,
  "verdict": "verified|requires_review|failed",
  "evidence": "one sentence"
}

Rules:
- verdict "verified" only if same_location is yes AND issue_addressed is true
  AND confidence >= 0.7.
- verdict "failed" if the issue is clearly still visible in IMAGE 2.
- otherwise verdict "requires_review".
"""


def verify_resolution(original_bytes: bytes, after_bytes: bytes,
                      description: str = "", category: str = "") -> dict:
    """Return {'verdict','confidence','same_location','evidence','error'}."""
    result = {"verdict": VERDICT_REVIEW, "confidence": 0.0, "same_location": "unsure",
              "evidence": "", "error": ""}
    try:
        context = f"\nComplaint: {description[:300]}\nCategory: {category or 'unknown'}\n"
        reply = ai.chat(ai.vision_prompt(PROMPT + context, [original_bytes, after_bytes]),
                        max_tokens=350, temperature=0.0)
        data = ai.extract_json(reply)

        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in (VERDICT_VERIFIED, VERDICT_REVIEW, VERDICT_FAILED):
            verdict = VERDICT_REVIEW

        confidence = float(data.get("confidence") or 0.0)
        same_location = str(data.get("same_location", "unsure")).strip().lower()

        # Deterministic guard rails on top of the model's own verdict.
        if verdict == VERDICT_VERIFIED and (same_location != "yes" or confidence < 0.7):
            verdict = VERDICT_REVIEW

        result.update({
            "verdict": verdict,
            "confidence": confidence,
            "same_location": same_location,
            "evidence": str(data.get("evidence", ""))[:300],
        })
    except Exception as exc:
        # Missing key / network / bad JSON -> manual review, never auto-approve.
        logger.error("Resolution verification failed: %s", exc)
        result["error"] = str(exc)[:300]
    return result
