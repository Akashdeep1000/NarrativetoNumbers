# NarrativetoNumbers

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-green)](https://fastapi.tiangolo.com/)
[![Code style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Source code and experimental materials for:**
> 
> *From Narrative to Numbers: Evaluating Survey Questionnaires with Large Language Models*
> 
> This research investigates how Large Language Models can convert free-text workload narratives into quantitative NASA-TLX dimension scores, bridging qualitative and quantitative assessment methodologies in human-computer interaction research.

---

## 📖 Overview

**Narrative to Numbers** is a web-based research platform that implements a dual-interface NASA-TLX assessment system:

1. **Sliding Puzzle Task** – A controlled cognitive load induction tool (HTML5 Canvas) with two difficulty levels:
   - **Easy**: Manhattan Distance 8–16, minimum 20s completion
   - **Hard**: Manhattan Distance 56–76, minimum 30s completion

2. **Multimodal NASA-TLX Assessment** – Participants rate workload using:
   - **Slider ratings** (1–7 Likert scale)
   - **Free-text descriptions** (qualitative narratives)
   - Counterbalanced order across conditions

3. **LLM-Powered Analysis Pipeline** – Automated processing of descriptive responses:
   - **Validator**: Checks coherence, topic relevance, and quality using LLM (with offline fallback)
   - **Rater**: Converts validated text to NASA-TLX scores (1–7) per dimension
   - **Exports**: Structured CSV outputs for statistical analysis (ICC, TOST, Pearson correlations)

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| **Counterbalanced Design** | Tracks Sequence A vs. B assignments to minimize order effects |
| **Session Management** | HTTPOnly cookies for secure, privacy-respecting participant tracking |
| **Real-time Data Export** | Automatic CSV generation to multiple formats |
| **Pilot vs. Research Modes** | Separate data directories for pilot testing and formal study |
| **Transparent Provenance** | Every response logged with LLM source (online/offline), validation quality, and timestamp |

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.9+** (3.10+ recommended)
- **OpenAI API Key** (optional, for LLM validation and scoring)
- **SQLite 3** (built-in with Python)

### Step 1: Clone the Repository
```bash
git clone https://github.com/Akashdeep1000/NarrativetoNumbers.git
cd NarrativetoNumbers
```

### Step 2: Create and Activate Virtual Environment
```bash
# Using Python venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# OR using Conda (recommended for research projects)
conda create -n narrative2numbers python=3.9
conda activate narrative2numbers
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Create a `.env` file in the root directory:

```env
# LLM Configuration
OPENAI_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o-mini

```

---

## 🚀 Running the Application

### Start the Development Server
```bash
uvicorn app.main:app --reload --port 8088
```

Then open your browser to: **http://127.0.0.1:8088**

---

## 📂 Project Structure

```
NarrativetoNumbers/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI routes & core logic (15 KB)
│   │                                 # - Session management, puzzle task, data collection
│   ├── db.py                        # SQLAlchemy ORM setup
│   ├── models.py                    # Database models
│   │                                 # - Participant, Session, Demographics, Level
│   ├── schemas.py                   # Pydantic request/response schemas
│   │
│   └── services/
│       ├── __init__.py
│       ├── llm_tlx.py               # LLM validation & scoring pipeline
│       │                             # - validate_descriptive(): Check quality & coherence
│       │                             # - rate_descriptive(): Generate 1–7 scores per dimension
│       │                             # - Includes offline heuristic fallback
│       ├── exporter.py              # Multi-format CSV export logic
│       │                             # - Per-participant folders
│       │                             # - Aggregated exports for analysis
│       └── latin_square.py          # Counterbalancing utility (optional, for 4-level designs)
│
├── templates/                        # Jinja2 HTML templates
│   ├── base.html                    # Base layout & CSS injection point
│   ├── index.html                   # Consent & home page
│   ├── demographics.html            # Age, gender, puzzle experience form
│   ├── study.html                   # Puzzle task + NASA-TLX survey interface
│   ├── post.html                    # Post-study questionnaire (optional)
│   └── thankyou.html                # Completion & gratitude screen
│
├── static/
│   │
│   └── js/                          # Frontend logic (puzzle game, AJAX)
│       ├── game.js                  # 17.7 KB - Puzzle implementation
│       │                             # - Puzzle class (4x4 sliding puzzle with canvas rendering)
│       │                             # - Timer class (min:sec display with performance.now())
│       │                             # - shuffleToRange() (difficulty control via Manhattan distance)
│       │                             # - initStudy() (orchestrates game + NASA-TLX flow)
│       │
│       └── main.js                  # 2.3 KB - Form handling & API utilities
│                                     # - Demographics form submission via POST /api/demographics
│                                     # - postJson() (fetch wrapper with error parsing)
│                                     # - Error message display
│
├── data/                            # Data storage (auto-generated)
│   ├── by_participant/              # Folder per participant (P001_name/, P002_name/, etc.)
│   │   ├── {participant_id}/
│   │   │   ├── info.csv
│   │   │   ├── demographics.csv
│   │   │   ├── levels.csv
│   │   │   ├── tlx_slider.csv
│   │   │   ├── tlx_descriptive_wide.csv
│   │   │   └── tlx_descriptive_long.csv
│   │   └── ...
│   │
│   ├── exports/                     # Full snapshots (by timestamp)
│   │   ├── 20250101_120000/
│   │   │   ├── participants.csv
│   │   │   ├── demographics.csv
│   │   │   └── levels.csv
│   │   └── ...
│   │
│   ├── meta/
│   │   ├── pno_counter.txt          # Participant number counter
│   │   └── sequence_counts.json     # Seq A/B balance tracking
│   │
│   └── responses.db                 # SQLite database
│
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (NOT in git)
├── .gitignore                       # Ignore __pycache__, .env, data/
├── LICENSE                          # MIT License
└── README.md                        # This file
```

---

## 🔑 Core Endpoints

### Authentication & Consent
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /` | GET | Home page (consent form) |
| `POST /api/consent` | POST | Process consent & create session |

### Study Interface
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /demographics` | GET | Demographic form page |
| `POST /api/demographics` | POST | Submit demographics |
| `GET /study` | GET | Puzzle task + NASA-TLX page |
| `POST /api/session/start` | POST | Initialize puzzle session |
| `POST /api/level/start` | POST | Start a specific level |
| `POST /api/level/complete` | POST | Submit puzzle completion + moves/time |
| `POST /api/tlx/slider` | POST | Record slider-based NASA-TLX ratings |
| `POST /api/tlx/descriptive` | POST | Submit free-text + get LLM validation & scores |


---

## 🧩 Puzzle Implementation Details

### Difficulty Calibration
Puzzles are generated to match specific Manhattan distance (MD) ranges:
- **Easy (MD 8–16)**: 20 minimum seconds required by server
- **Hard (MD 56–76)**: 30 minimum seconds required by server


---

### Configuration

In `app/services/llm_tlx.py`:
```python
MIN_WORDS = 8              # Minimum text length
LLM_MODEL = "gpt-4o-mini"  # Set via env: LLM_MODEL=gpt-4o-mini
```

---

## 🔐 Privacy & Security

### Data Protection
- **HTTPOnly Cookies**: Session tokens cannot be accessed via JavaScript
- **No plaintext passwords**: Not applicable (consent-based study)
- **Participant anonymization**: Use participant_no instead of email in exports

### Data Retention
- Raw data stored locally in `./data/` directory
- Export snapshots archived with timestamp

### IRB Compliance
- Consent recorded in database (`participants.consent` flag)
- Demographic data minimal (age band, gender, puzzle experience)
- Free-text responses logged separately from PII


---


## 📜 License

This project is distributed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---
