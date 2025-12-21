from __future__ import annotations
import os, csv
from pathlib import Path
from datetime import datetime
import re


BASE_DIR = Path(os.getenv("DATA_DIR", "./data"))

def _slug_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or "participant"

def _label_for_participant(p) -> str:
    n = getattr(p, "participant_no", None)
    slug = _slug_name(getattr(p, "name", ""))
    if n is None:
        return f"NA_{getattr(p,'id','X')}_{slug}"
    return f"{int(n):03d}_{slug}"


def _dir_for_mode(mode: str) -> Path:
    mode = (mode or "research").lower()
    return Path("./data_pilot") if mode == "pilot" else BASE_DIR

def _ensure_base(base: Path):
    (base / "by_participant").mkdir(parents=True, exist_ok=True)
    (base / "exports").mkdir(parents=True, exist_ok=True)

def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt else ""

def _write_row(path: Path, fieldnames: list[str], row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new:
            w.writeheader()
        w.writerow(row)

def _p_folder(base: Path, p) -> Path:
    label = _label_for_participant(p)
    return base / "by_participant" / label


def record_participant(p, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    row = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "created_at": _iso(p.created_at),
        "name": p.name,
        "email": p.email,
        "consent": bool(p.consent),
    }
    _write_row(base / "participants.csv",
               ["participant_no","participant_id","created_at","name","email","consent"],
               row)
    pf = _p_folder(base, p)
    _write_row(pf / "info.csv",
               ["participant_no","participant_id","created_at","name","email","consent"],
               row)

def record_demographics(p, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    d = p.demographics
    if not d: return
    row = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "age_band": d.age_band,
        "gender": d.gender,
        "puzzle_experience": d.puzzle_experience,
        "updated_at": _iso(datetime.utcnow()),
    }
    _write_row(base / "demographics.csv",
               ["participant_no","participant_id","age_band","gender","puzzle_experience","updated_at"],
               row)
    pf = _p_folder(base, p)
    _write_row(pf / "demographics.csv",
               ["participant_no","participant_id","age_band","gender","puzzle_experience","updated_at"],
               row)

def record_level(p, sess, lvl, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    row = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "session_id": sess.id,
        "level_index": lvl.index,
        "condition": lvl.condition,
        "difficulty": lvl.difficulty,
        "shuffle_steps": lvl.shuffle_steps,
        "started_at": _iso(lvl.started_at),
        "completed_at": _iso(lvl.completed_at),
        "completed": bool(lvl.completed),
        "moves": lvl.moves,
        "time_ms": lvl.time_ms,
    }
    _write_row(base / "levels.csv",
               ["participant_no","participant_id","session_id","level_index","condition","difficulty","shuffle_steps",
                "started_at","completed_at","completed","moves","time_ms"],
               row)
    pf = _p_folder(base, p)
    _write_row(pf / "levels.csv",
               ["participant_no","participant_id","session_id","level_index","condition","difficulty","shuffle_steps",
                "started_at","completed_at","completed","moves","time_ms"],
               row)

def export_snapshot(db, participants, levels_dir: Path | None = None) -> str:
    """
    Unchanged: writes a full snapshot under ./data/exports/...
    """
    base = BASE_DIR
    (base / "exports").mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    root = base / "exports" / ts
    root.mkdir(parents=True, exist_ok=True)

    with (root / "participants.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["participant_no","participant_id","created_at","name","email","consent"])
        for p in participants:
            w.writerow([getattr(p,"participant_no",None), p.id, _iso(p.created_at), p.name, p.email, int(bool(p.consent))])

    with (root / "demographics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["participant_no","participant_id","age_band","gender","puzzle_experience"])
        for p in participants:
            if p.demographics:
                d = p.demographics
                w.writerow([getattr(p,"participant_no",None), p.id, d.age_band, d.gender, d.puzzle_experience])

    L = []
    for p in participants:
        for s in p.sessions:
            for lvl in s.levels:
                L.append((p, s, lvl))
    with (root / "levels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["participant_no","participant_id","session_id","level_index","condition","difficulty","shuffle_steps",
                    "started_at","completed_at","completed","moves","time_ms"])
        for p,s,lvl in L:
            w.writerow([getattr(p,"participant_no",None), p.id, s.id, lvl.index, lvl.condition, lvl.difficulty,
                        lvl.shuffle_steps, _iso(lvl.started_at), _iso(lvl.completed_at),
                        int(bool(lvl.completed)), lvl.moves, lvl.time_ms])

    return str(root)

def record_tlx_slider(p, sess, lvl, ratings: dict, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    ts = datetime.utcnow().isoformat(timespec="seconds")
    row = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "session_id": sess.id,
        "level_index": lvl.index,
        "condition": lvl.condition,
        "difficulty": lvl.difficulty,
        "tlx_type": "slider",
        "ts": ts,
    }
    row.update(ratings)
    headers = ["participant_no","participant_id","session_id","level_index",
               "condition","difficulty","tlx_type","ts",
               "Mental Demand","Physical Demand","Temporal Demand","Performance","Effort","Frustration"]
    _write_row(base / "tlx_slider.csv", headers, row)
    pf = _p_folder(base, p); _write_row(pf / "tlx_slider.csv", headers, row)

def record_tlx_descriptive(p, sess, lvl, validated: dict, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    ts = datetime.utcnow().isoformat(timespec="seconds")

    wide = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "session_id": sess.id,
        "level_index": lvl.index,
        "condition": lvl.condition,
        "difficulty": lvl.difficulty,
        "tlx_type": "descriptive",
        "ts": ts,
    }
    for d in ["Mental Demand","Physical Demand","Temporal Demand","Performance","Effort","Frustration"]:
        wide[f"{d}__text"] = (validated.get(d, {}) or {}).get("text", "")
    wide_headers = ["participant_no","participant_id","session_id","level_index",
                    "condition","difficulty","tlx_type","ts"] + \
                   [f"{d}__text" for d in ["Mental Demand","Physical Demand","Temporal Demand","Performance","Effort","Frustration"]]
    _write_row(base / "tlx_descriptive_wide.csv", wide_headers, wide)
    pf = _p_folder(base, p); _write_row(pf / "tlx_descriptive_wide.csv", wide_headers, wide)

    long_headers = ["participant_no","participant_id","session_id","level_index","condition",
                    "difficulty","tlx_type","dimension","text",
                    "llm_valid","llm_reason","llm_source","llm_quality",
                    "llm_likert","llm_explanation","ts"]
    for dim, v in validated.items():
        long_row = {
            "participant_no": getattr(p, "participant_no", None),
            "participant_id": p.id,
            "session_id": sess.id,
            "level_index": lvl.index,
            "condition": lvl.condition,
            "difficulty": lvl.difficulty,
            "tlx_type": "descriptive",
            "dimension": dim,
            "text": v.get("text",""),
            "llm_valid": v.get("llm_valid"),
            "llm_reason": v.get("llm_reason"),
            "llm_source": v.get("llm_source"),
            "llm_quality": v.get("llm_quality"),
            "llm_likert": v.get("llm_likert"),
            "llm_explanation": v.get("llm_explanation"),
            "ts": ts
        }
        _write_row(base / "tlx_descriptive_long.csv", long_headers, long_row)
        _write_row(pf / "tlx_descriptive_long.csv", long_headers, long_row)

def record_post_survey(p, sess, answers: dict, mode: str = "research"):
    base = _dir_for_mode(mode)
    _ensure_base(base)
    ts = datetime.utcnow().isoformat(timespec="seconds")

    # Map form keys -> human-readable question text
    q_text = {
        "method_natural": "Which method felt more natural to describe your workload?",
        "method_nuance": "Which captured nuances or context better?",
        "summarization_fairness_text": "If descriptive answers are summarized into 1–7 later, how fair/accurate would that feel?",
        "method_why": "Briefly, which method did you prefer over the other and why?",

    }

    # ---- Wide row (one row per participant/session) ----
    wide_row = {
        "participant_no": getattr(p, "participant_no", None),
        "participant_id": p.id,
        "session_id": sess.id,
        "ts": ts,
    }
    for k in q_text.keys():
        v = answers.get(k, "")
        if isinstance(v, str):
            v = v.strip()
        wide_row[k] = v

    wide_headers = ["participant_no","participant_id","session_id","ts"] + list(q_text.keys())
    _write_row(base / "post_survey.csv", wide_headers, wide_row)
    pf = _p_folder(base, p)
    _write_row(pf / "post_survey.csv", wide_headers, wide_row)

    # ---- Long rows (one row per question) ----
    long_headers = ["participant_no","participant_id","session_id","ts","question_key","question","response"]
    for k, q in q_text.items():
        v = answers.get(k, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            v = str(v)
        long_row = {
            "participant_no": getattr(p, "participant_no", None),
            "participant_id": p.id,
            "session_id": sess.id,
            "ts": ts,
            "question_key": k,
            "question": q,
            "response": v.strip(),
        }
        _write_row(base / "post_survey_long.csv", long_headers, long_row)
        _write_row(pf / "post_survey_long.csv", long_headers, long_row)

