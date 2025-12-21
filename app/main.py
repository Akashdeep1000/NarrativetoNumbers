from __future__ import annotations
import os, secrets, json
from pathlib import Path
from fastapi import FastAPI, Depends, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from sqlalchemy import func, inspect

from pathlib import Path

from .db import Base, engine, get_db
from .models import Participant, Session as DBSession, Demographics, Level
from .schemas import DemographicsIn
from .services import llm_tlx, exporter

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(16))
SESSION_COOKIE_NAME = "sid"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 7 

TLX_DIMS = ["Mental Demand","Physical Demand","Temporal Demand","Performance","Effort","Frustration"]


SEQS_2R = {
    "A": [
        {"difficulty": "easy", "tlx_order": ["slider", "descriptive"]},
        {"difficulty": "hard", "tlx_order": ["descriptive", "slider"]},
    ],
    "B": [
        {"difficulty": "easy", "tlx_order": ["descriptive", "slider"]},
        {"difficulty": "hard", "tlx_order": ["slider", "descriptive"]},
    ],
}



PNO_FILE = Path("data/meta/pno_counter.txt")

def _read_pno_counter() -> int:
    try:
        return int(PNO_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 0

def _write_pno_counter(n: int) -> None:
    PNO_FILE.parent.mkdir(parents=True, exist_ok=True)
    PNO_FILE.write_text(str(int(n)), encoding="utf-8")



SEQ_COUNT_FILE = Path("data/meta/sequence_counts.json")
def _load_seq_counts():
    try:
        return json.loads(SEQ_COUNT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"research": {"A": 0, "B": 0}, "pilot": {"A": 0, "B": 0}}

def _save_seq_counts(d):
    SEQ_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEQ_COUNT_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

def _choose_sequence_key(mode: str) -> str:
    mode = (mode or "research").lower()
    counts = _load_seq_counts()
    counts.setdefault(mode, {"A": 0, "B": 0})
    return "A" if counts[mode]["A"] <= counts[mode]["B"] else "B"

app = FastAPI(title="Web Study — Sliding Puzzle")
app.mount("/static", StaticFiles(directory=str(os.path.join(os.path.dirname(__file__), "..", "static"))), name="static")
templates = Jinja2Templates(directory=str(os.path.join(os.path.dirname(__file__), "..", "templates")))


Base.metadata.create_all(bind=engine)


insp = inspect(engine)
cols = [c['name'] for c in insp.get_columns('participants')]
if 'participant_no' not in cols:
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE participants ADD COLUMN participant_no INTEGER")

def get_current_session(request: Request, db: Session) -> DBSession | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return db.query(DBSession).filter(DBSession.cookie_token == token).first()

DATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/demographics", response_class=HTMLResponse)
def demographics_page(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    mode = (request.cookies.get("mode") or "research").lower()
    pno = sess.participant.participant_no if mode == "research" else None

    return templates.TemplateResponse(
        "demographics.html",
        {"request": request, "participant_no": pno, "mode": mode}
    )



@app.get("/study", response_class=HTMLResponse)
def study_page(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("study.html", {"request": request})


@app.post("/api/consent")
async def api_consent(request: Request, response: Response, db: Session = Depends(get_db)):
    data = await request.json()
    name   = (data.get("name") or "").strip()
    email  = (data.get("email") or "").strip()
    consent_flag = bool(data.get("consent") or data.get("agree") or data.get("agreed"))
    mode   = (data.get("mode") or "research").lower()
    seq    = (data.get("seq") or "").upper()

    if not consent_flag:
        raise HTTPException(status_code=400, detail="Consent is required to participate.")

  
    p = db.query(Participant).filter(Participant.email == email).first()
    if p is None:
        p = Participant(name=name, email=email, consent=True)
        db.add(p); db.flush()
    else:
        p.name = name
        p.consent = True

    if mode == "research" and p.participant_no is None:
        db_max = db.query(func.max(Participant.participant_no)).scalar() or 0
        file_max = _read_pno_counter()
        next_no = max(db_max, file_max) + 1
        p.participant_no = next_no
        _write_pno_counter(next_no)

    token = secrets.token_urlsafe(24)
    sess = DBSession(participant=p, cookie_token=token)
    db.add(sess); db.commit()

    exporter.record_participant(p, mode=mode)

    
    response.set_cookie(SESSION_COOKIE_NAME, token, httponly=True, samesite="lax",
                        max_age=SESSION_COOKIE_MAX_AGE, secure=False)
    response.set_cookie("mode", mode, httponly=False, samesite="Lax",
                        max_age=SESSION_COOKIE_MAX_AGE, secure=False)
    if seq in ("A","B"):
        response.set_cookie("seq", seq, httponly=False, samesite="Lax",
                            max_age=SESSION_COOKIE_MAX_AGE, secure=False)

    if mode == "research" and p.participant_no is not None:
        response.set_cookie("pno", str(p.participant_no), httponly=False, samesite="Lax",
                            max_age=SESSION_COOKIE_MAX_AGE, secure=False)
    else:
        response.delete_cookie("pno", samesite="Lax")

    return {
        "ok": True,
        "redirect": "/demographics",
        "participant_no": (p.participant_no if mode == "research" else None)
    }

@app.post("/api/demographics")
def api_demographics(payload: DemographicsIn, request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        raise HTTPException(status_code=401, detail="No active session.")

    p = sess.participant

    if p.demographics is None:
        d = Demographics(
            participant=p,
            age_band=payload.age_band,
            gender=payload.gender,
            puzzle_experience=payload.puzzle_experience
        )
        db.add(d)
    else:
        p.demographics.age_band = payload.age_band
        p.demographics.gender = payload.gender
        p.demographics.puzzle_experience = payload.puzzle_experience

    db.commit()

    mode = (request.cookies.get("mode") or "research").lower()
    exporter.record_demographics(p, mode=mode)

    return {"ok": True, "redirect": "/study", "participant_no": p.participant_no}


MIN_TIME_EASY = 20  
MIN_TIME_HARD = 30  
EASY_MD_MIN, EASY_MD_MAX = 8, 16     
HARD_MD_MIN, HARD_MD_MAX = 56, 76    


@app.post("/api/session/start")
def api_session_start(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    set_sid_cookie = False
    if not sess:
        p = Participant(name="Unknown", email="", consent=False)
        db.add(p); db.flush()
        token = secrets.token_urlsafe(24)
        sess = DBSession(participant=p, cookie_token=token)
        db.add(sess); db.commit()
        set_sid_cookie = True

    mode = (request.cookies.get("mode") or "research").lower()
    seq_cookie = (request.cookies.get("seq") or "").upper()
    if seq_cookie in ("A","B"):
        seq_key = seq_cookie
    else:
        counts = _load_seq_counts()
        counts.setdefault(mode, {"A": 0, "B": 0})
        seq_key = "A" if counts[mode]["A"] <= counts[mode]["B"] else "B"
        counts[mode][seq_key] += 1
        _save_seq_counts(counts)

    seq_def = SEQS_2R[seq_key]
    plan = []
    for i, item in enumerate(seq_def, start=1):
        difficulty = item["difficulty"]
        tlx_order  = item["tlx_order"]
        shuffle_steps = 25 if difficulty == "easy" else 45

        lvl = db.query(Level).filter(Level.session_id == sess.id, Level.index == i).first()
        if not lvl:
            cond_label = f"{'E' if difficulty=='easy' else 'H'}{i}"
            lvl = Level(session_id=sess.id, index=i, condition=cond_label,
                        difficulty=difficulty, shuffle_steps=shuffle_steps)
            db.add(lvl)

        plan.append({
            "index": i,
            "difficulty": difficulty,
            "shuffle_steps": shuffle_steps,
            "completed": bool(lvl.completed),
            "tlx_order": tlx_order,   
        })
    db.commit()

    resp = JSONResponse({"ok": True, "mode": mode, "sequence": seq_key, "plan": plan})
    if set_sid_cookie:
        resp.set_cookie(SESSION_COOKIE_NAME, sess.cookie_token, httponly=True, samesite="lax")
    return resp

@app.post("/api/level/start")
async def api_level_start(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        raise HTTPException(status_code=401, detail="No active session.")
    body = await request.json()
    idx = int(body.get("index", 1))

    lvl = db.query(Level).filter(Level.session_id == sess.id, Level.index == idx).first()
    if not lvl:
        raise HTTPException(status_code=404, detail="Level not found.")

    if not lvl.started_at:
        from datetime import datetime
        lvl.started_at = datetime.utcnow()
        db.commit()

    min_time = MIN_TIME_EASY if lvl.difficulty == "easy" else MIN_TIME_HARD

    if lvl.difficulty == "easy":
        md_min, md_max = EASY_MD_MIN, EASY_MD_MAX
    else:
        md_min, md_max = HARD_MD_MIN, HARD_MD_MAX

    return {
        "ok": True,
        "difficulty": lvl.difficulty,
        "min_time": min_time,
        "shuffle_steps": lvl.shuffle_steps,  
        "md_min": md_min,
        "md_max": md_max,
    }


@app.post("/api/level/complete")
async def api_level_complete(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        raise HTTPException(status_code=401, detail="No active session.")
    body = await request.json()
    idx = int(body.get("index", 1))
    moves = int(body.get("moves", 0))
    time_ms_client = int(body.get("time_ms", 0))
    completed = bool(body.get("completed", False))

    lvl = db.query(Level).filter(Level.session_id==sess.id, Level.index==idx).first()
    if not lvl or not lvl.started_at:
        raise HTTPException(status_code=400, detail="Level not started.")
    from datetime import datetime
    elapsed_s = int((datetime.utcnow() - lvl.started_at).total_seconds())
    min_time = MIN_TIME_EASY if lvl.difficulty == "easy" else MIN_TIME_HARD
    if elapsed_s < min_time:
        return JSONResponse(
            {"ok": False, "error": "min_time_not_reached", "min_remaining": max(0, min_time - elapsed_s)},
            status_code=202
        )

    lvl.completed = bool(completed)
    lvl.moves = moves
    lvl.time_ms = time_ms_client
    lvl.completed_at = datetime.utcnow()
    db.commit()

    mode = (request.cookies.get("mode") or "research").lower()
    exporter.record_level(sess.participant, sess, lvl, mode=mode)

    all_levels = sorted(sess.levels, key=lambda x: x.index)
    remaining = [L for L in all_levels if not L.completed]
    return {"ok": True, "remaining": len(remaining)}

@app.post("/api/tlx/submit")
async def api_tlx_submit(request: Request, db: Session = Depends(get_db)):
    """
    Body:
      { "index": 1..2, "type": "slider"|"descriptive",
        "ratings": {dim:int,..}  
        "notes":   {dim:str,..}  
      }
    """
    sess = get_current_session(request, db)
    if not sess:
        raise HTTPException(status_code=401, detail="No active session.")

    b = await request.json()
    idx = int(b.get("index", 1))
    tlx_type = (b.get("type") or "").strip()
    lvl = db.query(Level).filter(Level.session_id == sess.id, Level.index == idx).first()
    if not lvl:
        raise HTTPException(status_code=400, detail="Level not found.")
    if tlx_type not in {"slider","descriptive"}:
        raise HTTPException(status_code=400, detail="Invalid tlx type.")

    mode = (request.cookies.get("mode") or "research").lower()

    if tlx_type == "slider":
        ratings = b.get("ratings") or {}
        clean = {}
        for d in TLX_DIMS:
            try:
                v = int(ratings.get(d, 0))
            except:
                v = 0
            if v < 1 or v > 7:
                return JSONResponse({"ok": False, "failed": [{"dimension": d, "reason": "missing or out of range (1–7)"}]}, status_code=400)
            clean[d] = v
        exporter.record_tlx_slider(sess.participant, sess, lvl, clean, mode=mode)
        return {"ok": True}

    notes = b.get("notes") or {}
    failed, validated = [], {}
    for d in TLX_DIMS:
        raw = notes.get(d, "")
        txt = (raw if isinstance(raw, str) else str(raw)).strip()
        passed, reason, source, quality = llm_tlx.validate_descriptive(d, "", txt,
                                   context={"participant": sess.participant.id, "level_index": idx})
        validated[d] = {"text": txt, "llm_valid": passed, "llm_reason": reason,
                        "llm_source": source, "llm_quality": quality}
        if not passed:
            failed.append({"dimension": d, "reason": reason})
    if failed:
        return JSONResponse({"ok": False, "failed": failed, "min_words": llm_tlx.MIN_WORDS}, status_code=400)

    for d in TLX_DIMS:
        txt = validated[d]["text"]
        score, expl = llm_tlx.rate_descriptive(d, txt)
        validated[d]["llm_likert"] = score
        validated[d]["llm_explanation"] = expl

    exporter.record_tlx_descriptive(sess.participant, sess, lvl, validated, mode=mode)
    return {"ok": True}

@app.get("/post")
def post_get(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("post.html", {"request": request})

@app.post("/post")
async def post_submit(request: Request, db: Session = Depends(get_db)):
    sess = get_current_session(request, db)
    if not sess:
        return RedirectResponse("/", status_code=302)

    form = await request.form()
    answers = {
        "method_natural": (form.get("method_natural") or "").strip(),
        "method_nuance": (form.get("method_nuance") or "").strip(),
        "summarization_fairness_text": (form.get("summarization_fairness_text") or "").strip(),
        "method_why": (form.get("method_why") or "").strip(),
    }
    mode = (request.cookies.get("mode") or "research").lower()
    exporter.record_post_survey(sess.participant, sess, answers, mode=mode)
    return RedirectResponse("/thank-you", status_code=303)

@app.get("/thank-you")
def thank_you(request: Request):
    return templates.TemplateResponse("thankyou.html", {"request": request})
