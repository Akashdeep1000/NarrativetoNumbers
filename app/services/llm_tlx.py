from __future__ import annotations
import os, json, logging, re
from typing import Optional, Tuple, Dict

log = logging.getLogger("llm_tlx")

# --- Config ---
MIN_WORDS = 8  # >= 8 words (updated per your requirement)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
_USE_LLM = bool(os.getenv("OPENAI_API_KEY"))

# Try to init client (safe if missing)
client = None
if _USE_LLM:
    try:
        from openai import OpenAI
        client = OpenAI()
    except Exception as e:
        log.warning("OpenAI init failed: %s", e)
        _USE_LLM = False
        client = None

# --- Validator (system + user) ---
VALIDATOR_RUBRIC = (
    "You are a validator for NASA-TLX free-text responses.\n"
    "Return STRICT JSON only: {\"pass\": true/false, \"reason\": \"<short>\", \"quality\": \"high|medium|low\"}.\n"
    "Pass when the text is coherent natural English and clearly refers to the participant’s experience in THIS sliding-puzzle round.\n"
    "Do NOT require numbers, tile IDs, or detailed procedures.\n"
    f"Minimum length: {MIN_WORDS} words.\n"
    "Fail only for obvious gibberish/word-salad, random/offensive content, or clearly unrelated topics.\n"
    "Quality tiers (for accepted answers only):\n"
    "  - high   = clear, multi-sentence reflection, ~15+ words\n"
    "  - medium = specific enough but brief, ~10–15 words\n"
    f"  - low    = minimal but acceptable, {MIN_WORDS}–10 words\n"
)
VALIDATOR_USER_TEMPLATE = 'Text: "{text}"\nReturn ONLY the JSON object.'

# --- Rater (system returns score+explanation JSON) ---
RATER_RUBRIC = (
    "You are scoring NASA-TLX dimension responses.\n"
    "Return STRICT JSON only: {\"score\": 1..7, \"explanation\": \"<short>\"}.\n"
    "Use the anchors:\n"
    " 1 = very low, 7 = very high for ALL dimensions.\n"
    " SPECIAL CASE — FOR PERFORMANCE QUESTION: 1 = very high success, 7 = very low success (do NOT invert).\n"
    "Base your score ONLY on the participant's answer. Pay attention to negations.\n"
    "If the answer is off-topic, pick the best score and explain briefly."
)

RATER_USER_TEMPLATE = (
    "[Dimension] {dimension}\n"
    "[Question] {question}\n"
    "[Answer] {text}\n"
    "Score strictly from the answer using the anchors."
)

TLX_QUESTIONS = {
    "Mental Demand":      "How mentally demanding was the task?",
    "Physical Demand":    "How physically demanding was the task?",
    "Temporal Demand":    "How hurried or rushed was the pace of the task?",
    "Performance":        "How successful were you in accomplishing what you were asked to do?",
    "Effort":             "How hard did you have to work to accomplish your level of performance?",
    "Frustration":        "How insecure, discouraged, irritated, stressed, or annoyed were you?"
}



def _offline_valid(text: str) -> Tuple[bool, str, str, str]:
    words = [w for w in (text or "").split() if w.strip()]
    wc = len(words)
    txt = (text or "").lower()

    # simple topic signal
    on_topic = any(t in txt for t in [
        "puzzle","tile","grid","move","time","effort","frustrat",
        "strategy","mistake","rush","easy","hard","solve","solved"
    ])

    passed = wc >= MIN_WORDS and on_topic
    if not passed:
        return False, "Too short or off-topic.", "offline", "fail"

    quality = "high" if wc >= 15 else ("medium" if wc >= 10 else "low")
    return True, "OK", "offline", quality

def validate_descriptive(dimension: str, level_label: str, text: str,
                         context: Optional[Dict[str,str]] = None) -> Tuple[bool, str, str, str]:
    """
    Returns (passed: bool, reason: str, source: 'llm'|'offline', quality: 'high'|'medium'|'low'|'fail')
    """
    if not _USE_LLM or client is None:
        return _offline_valid(text)

    ctx_lines = ""
    if context:
        for k, v in context.items():
            ctx_lines += f"{k}: {v}\n"

    question = TLX_QUESTIONS.get(dimension, "")
    if question and "Question:" not in ctx_lines:
        ctx_lines = f"Question: {question}\n" + ctx_lines

    user_prompt = (
        f"Dimension: {dimension}\n"
        f"{ctx_lines}"
        f"Answer: {text}\n"
        f"Apply the rubric strictly and respond in JSON only."
    )

    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": VALIDATOR_RUBRIC},
                {"role": "user", "content": user_prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        passed  = bool(data.get("pass", False))
        reason  = str(data.get("reason", "") or ("OK" if passed else "Failed rubric."))
        quality = str(data.get("quality", "")).lower().strip()
        if not passed:
            return False, reason, "llm", "fail"
        if quality not in {"high","medium","low"}:
            wc = len((text or "").split())
            quality = "high" if wc >= 40 else ("medium" if wc >= 25 else "low")
        return True, reason, "llm", quality
    except Exception as e:
        log.warning("validate_descriptive LLM error: %s", e)
        ok, reason, src, q = _offline_valid(text)
        return ok, (reason if ok else f"Temporary validator issue: {e}"), src, q

# --- Helpers for scoring ---
_POS_SUCCESS = [
    "very successful","extremely successful","highly successful","did great",
    "went very well","flawless","perfect","nailed it","excellent"
]
_NEG_SUCCESS = [
    "not successful","unsuccessful","failed","went poorly","did badly","struggled a lot"
]

def _offline_score(dimension: str, text: str) -> Tuple[int, str]:
    """
    Offline heuristic fallback for 1..7 scoring with dimension-aware tweaks.
    """
    txt = (text or "").lower()
    score = 4  # neutral start

    if dimension == "Performance":
        if any(ph in txt for ph in _POS_SUCCESS): score = max(score, 6)
        if any(ph in txt for ph in _NEG_SUCCESS): score = min(score, 2)
        # generic cues
        if "many mistakes" in txt or "lot of mistakes" in txt: score = min(score, 3)
        if "few mistakes" in txt or "minimal mistakes" in txt: score = max(score, 5)
        return score, "offline heuristic"


    inc = ["overwhelm","intense","very high","extreme","frustrat","stress","rushed","panic","pressure","hard"]
    dec = ["easy","simple","smooth","relax","low","little","calm","manageable"]
    for w in inc:
        if w in txt: score = min(7, score + 2)
    for w in dec:
        if w in txt: score = max(1, score - 2)
    return score, "offline heuristic"

def rate_descriptive(dimension: str, text: str) -> Tuple[int, str]:
    """
    Likert 1..7 + brief explanation. Uses the exact TLX question per dimension to stabilize polarity.
    IMPORTANT: Performance remains *non-inverted*: 1 = very high success, 7 = very low success.
    If you need TLX inversion for analytics, do it later: inv = 8 - score.
    """
    # Offline heuristic
    if not _USE_LLM or client is None:
        return _offline_score(dimension, text)

    question = TLX_QUESTIONS.get(dimension, "")

    RATER_RUBRIC = (
        "You are scoring NASA-TLX dimension responses.\n"
        "Return STRICT JSON only: {\"score\": 1..7, \"explanation\": \"<short>\"}.\n"
        "Use the anchors:\n"
        " 1 = very low, 7 = very high for ALL dimensions.\n"
        " SPECIAL CASE — FOR PERFORMANCE QUESTION: 1 = very high success, 7 = very low success (do NOT invert).\n"
        "Base your score ONLY on the participant's answer. Pay attention to negations.\n"
        "If the answer is off-topic, pick the best score and explain briefly."
    )
    prompt = (
        f"[Dimension] {dimension}\n"
        f"[Question] {question}\n"
        f"[Answer] {text}\n"
        "Score strictly from the answer using the anchors."
    )

    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RATER_RUBRIC},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        score = int(data.get("score", 4))
        score = max(1, min(7, score))
        explanation = str(data.get("explanation", "")).strip()

        # Tiny safety net for Performance polarity
        if dimension == "Performance":
            low = any(ph in (text or "").lower() for ph in _NEG_SUCCESS)
            high = any(ph in (text or "").lower() for ph in _POS_SUCCESS)
            if high and score <= 3:
                score = max(score, 6)
            if low and score >= 5:
                score = min(score, 2)

        return score, (explanation or "OK")
    except Exception as e:
        log.warning("rate_descriptive LLM error: %s", e)
        return _offline_score(dimension, text)



validator_system = VALIDATOR_RUBRIC         # <- adjust to your existing name
validator_user_template = VALIDATOR_USER_TEMPLATE
rater_system = RATER_RUBRIC
rater_user_template = RATER_USER_TEMPLATE
tlx_questions = TLX_QUESTIONS               # must be a dict with 6 TLX keys