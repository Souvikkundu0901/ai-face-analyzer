"""
LLM prompt construction and medical-language safety net.

The system prompt is the primary defense against the LLM inventing
recommendations or using medical language. The banned-terms filter
is a secondary safety net, not a substitute for prompt discipline.
"""

from typing import List, Dict, Any
import json


# ==============================================================================
# Banned Medical Terms — post-generation keyword safety net
# ==============================================================================
# If any of these terms appear in LLM output, that explanation item
# falls back to canned text from recommendations.py.
BANNED_MEDICAL_TERMS = [
    # Condition names
    "rosacea", "eczema", "psoriasis", "dermatitis", "acne vulgaris",
    "melasma", "vitiligo", "lupus", "seborrheic", "keratosis",
    "carcinoma", "melanoma", "basal cell", "squamous cell",
    "folliculitis", "impetigo", "cellulitis", "herpes", "shingles",
    "hives", "urticaria", "angioedema", "contact dermatitis",
    # Diagnostic language
    "diagnosis", "diagnose", "diagnosed", "prognosis", "pathology",
    "clinical", "symptom", "symptoms", "condition", "disease",
    "disorder", "syndrome", "infection", "inflammation",
    "chronic", "acute", "malignant", "benign",
    # Treatment language
    "treatment", "treat", "prescribe", "prescription", "medication",
    "medicine", "drug", "therapy", "procedure", "surgery",
    "antibiotic", "steroid", "retinoid", "corticosteroid",
    "topical cream", "ointment",
    # Medical professional directives
    "you should see a doctor", "seek medical",
    "medical attention", "medical advice",
]


def check_banned_terms(text: str) -> bool:
    """
    Return True if the text contains any banned medical terms.
    Case-insensitive check.
    """
    text_lower = text.lower()
    return any(term in text_lower for term in BANNED_MEDICAL_TERMS)


# ==============================================================================
# System Prompt
# ==============================================================================
SYSTEM_PROMPT = """You are a skin analysis report writer for a computer vision application called "AI Face Analyzer."

Your ONLY job is to explain the recommendation IDs you are given. You must NEVER:
- Introduce new observations, conditions, or suggestions not in the provided list
- Use medical or diagnostic language (no condition names, diagnoses, or treatments)
- Suggest seeing a doctor, seeking medical advice, or any medical professional
- Sound alarming, urgent, or anxiety-inducing
- Add disclaimers or caveats (the app handles disclaimers separately)

Your output MUST:
- Frame everything as visible/observational: "localized redness was detected" NOT "this indicates rosacea"
- Be calm, factual, and encouraging in tone
- Contain exactly one short paragraph (2-3 sentences) per recommendation ID provided
- End with exactly one closing summary sentence
- Use the supporting scores to add specificity (e.g. "a redness level of 0.52 was measured")
- Mention the detected face shape naturally if relevant

Respond ONLY with valid JSON matching this exact schema:
{
  "explanations": [
    {"id": "RECOMMENDATION_ID", "text": "Your 2-3 sentence explanation here."}
  ],
  "summary": "One closing summary sentence."
}"""


def build_user_prompt(
    triggered_ids: List[str],
    supporting_scores: Dict[str, Any],
    face_shape: str = "unknown"
) -> str:
    """
    Build the user-facing prompt that provides the LLM with
    the already-decided recommendation IDs and supporting data.
    """
    payload = {
        "triggered_recommendations": triggered_ids,
        "supporting_scores": supporting_scores,
        "face_shape": face_shape,
    }

    return (
        f"Generate explanations for these triggered recommendations.\n\n"
        f"Input data:\n```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        f"Remember: explain ONLY the recommendation IDs listed above. "
        f"Do not add any new observations. Use observational, non-medical language. "
        f"Return valid JSON only."
    )
