# CIRO — Antigravity Development Plan
### Hackathon Edition · Free Stack · 24-Hour Sprint · Solo Build

---

## STRATEGIC READ BEFORE ANYTHING ELSE

Your two highest-weighted judging criteria together cover **45% of your score**:

| Criterion | Weight | What Judges Want |
|---|---|------|
| Crisis Detection & Severity Analysis | 25% | Reasoned classification with uncertainty — NOT keyword matching |
| Resource Optimization & Multi-Crisis Coordination | 20% | The "why" behind every allocation decision — visible in the trace |

**CIRO's current fatal flaw:** Both of these are faked. The classifier uses keyword lists. The trace logs are scripted strings. The allocation "reasoning" is a hardcoded sentence. You can win this competition by making those two things genuinely intelligent using Gemini (free tier) — and making that intelligence *visible* to the judges on screen.

**Your edge from the judging doc:** Source credibility weighting, coherence scoring, uncertainty estimates. These are already partially built in `credibility.py` and `classifier.py`. You don't need to rebuild from scratch — you need to wire Gemini *on top* of those algorithms and surface the reasoning in the trace.

---

## Free Production Stack (Zero Cost)

| Layer | Tool | Why Free |
|---|---|---|
| LLM / AI | Google Gemini 2.5 Flash | Free tier: 15 RPM, 1M tokens/month |
| Frontend hosting | Vercel | Free forever for hobby/hackathon |
| Backend hosting | Render | Free tier: 750 hrs/month (enough for demo) |
| Weather data | wttr.in | Completely free, no API key required |
| Maps | Leaflet + CartoDB tiles | Free, already in project |
| Database | None — in-memory | Already the architecture |

**Gemini free tier math:** At ~500 tokens per agent reasoning call × 7 agents × 50 demo runs = 175,000 tokens. You are nowhere near the 1M/month limit.

**Render free tier caveat:** The backend sleeps after 15 minutes of inactivity and takes ~30 seconds to cold-start. For your hackathon demo, just ping the backend URL once before the judges arrive. It will be awake.

---

## 24-Hour Sprint Plan

```
Hour  0–1   Phase 1: Environment setup + Gemini wiring
Hour  1–5   Phase 2: AI-powered classification engine   ← 25% criterion
Hour  5–8   Phase 3: Explainable allocation traces      ← 20% criterion
Hour  8–11  Phase 4: New crisis scenarios (3 new)
Hour 11–18  Phase 5: UI overhaul (ops-center aesthetic)
Hour 18–20  Phase 6: Free deployment
Hour 20–24  Buffer: polish, rehearse demo, fix bugs
```

---

## Phase 1 — Environment Setup (Hour 0–1)

### Goal
Replace `OpenWeatherMap` (paid) with `wttr.in` (free). Confirm Gemini free tier key works. Set up Vercel + Render accounts.

---

### ANTIGRAVITY PROMPT 1 — Free Weather Integration

```
You are a Python backend developer working on a FastAPI project called CIRO.

TASK: Replace the OpenWeatherMap API integration with wttr.in, which is completely
free and requires no API key.

FILE TO MODIFY: backend/data/generators.py

CURRENT BEHAVIOR:
- WeatherMockAPI class calls OpenWeatherMap using WEATHER_API_KEY from .env
- Falls back to hardcoded mock data when the key fails

NEW BEHAVIOR:
- Use wttr.in JSON API: https://wttr.in/{city}?format=j1
- This endpoint returns current weather with no authentication
- Extract: temp_C, weatherDesc, humidity, precipMM from the response
- Keep the same WeatherMockAPI interface so nothing else breaks
- Add a try/except so if wttr.in is unreachable, fall back to the existing mock data

CITIES TO SUPPORT (map these to wttr.in city names):
- Islamabad → "Islamabad"
- Lahore (Gulberg) → "Lahore"
- Karachi → "Karachi"
- Quetta (for new Balochistan earthquake scenario) → "Quetta"

Also update backend/.env.example — remove WEATHER_API_KEY and add a comment
explaining wttr.in requires no key.

Write the complete updated WeatherMockAPI class only. Keep all other classes
in generators.py unchanged.
```

---

## Phase 2 — AI-Powered Classification Engine (Hours 1–5)

### Goal
Replace the keyword-based classifier with Gemini reasoning that:
1. Produces a confidence score with explanation
2. Flags contradictions with a coherence score
3. Generates uncertainty language judges can see

This directly addresses the **25% Crisis Detection criterion**.

---

### ANTIGRAVITY PROMPT 2 — Gemini Signal Fusion

```
You are a Python AI engineer working on CIRO, a crisis intelligence system.

TASK: Add a Gemini-powered signal fusion step to the existing classification
pipeline. This runs AFTER the existing credibility scoring in credibility.py
and BEFORE the final crisis object is returned.

FILE TO CREATE: backend/intelligence/gemini_fusion.py

The function signature must be:

async def fuse_signals_with_gemini(
    scored_signals: list[dict],
    classifier_result: dict,
    gemini_client  # google.generativeai client
) -> dict

INPUT: scored_signals is a list of dicts with keys:
  source_type, content, credibility_score, geo_precision, mention_frequency

INPUT: classifier_result is the existing output from classifier.py with keys:
  crisis_type, severity, confidence, radius_km

OUTPUT: Return a dict with these fields:
  gemini_reasoning: str          # 3–4 sentences explaining the classification
  uncertainty_level: str         # "LOW" | "MEDIUM" | "HIGH"
  coherence_score: float         # 0.0–1.0, how consistent are the signals?
  contradiction_flags: list[str] # list of strings describing any conflicts
  adjusted_confidence: float     # Gemini's final confidence (0.0–1.0)
  source_weight_summary: str     # one sentence on which sources drove the verdict

GEMINI SYSTEM PROMPT TO USE (inject as system instruction):
  "You are a crisis intelligence analyst. You receive scored sensor signals
   and a preliminary classification. Your job is to reason about signal
   coherence, contradiction, and confidence. Be concise and technical.
   Always output valid JSON matching the exact schema provided."

USER PROMPT TEMPLATE:
  Build it to inject the scored_signals and classifier_result as JSON,
  then ask Gemini to return JSON matching the output schema above.
  Use model: gemini-2.5-flash-preview-05-20
  Set temperature to 0.2 for consistency.
  Parse the response as JSON and return it.

ERROR HANDLING:
  If Gemini fails or times out, return a fallback dict with:
  - gemini_reasoning: "Signal fusion unavailable — using baseline classifier"
  - uncertainty_level: "MEDIUM"
  - coherence_score: classifier_result["confidence"]
  - contradiction_flags: []
  - adjusted_confidence: classifier_result["confidence"]
  - source_weight_summary: "Baseline keyword classifier used"

Do not modify any existing files. Only create gemini_fusion.py.
```

---

### ANTIGRAVITY PROMPT 3 — Wire Gemini Fusion Into the Pipeline

```
You are a Python backend developer. CIRO's classification pipeline needs to
call the new gemini_fusion.py module and include its output in the API response.

FILES TO MODIFY:
1. backend/api/crisis.py — the POST /detect endpoint
2. backend/agents/agent_configs.py — the OrchestrationPipeline class

CHANGE 1 — crisis.py POST /detect:
After calling the classifier, import and call fuse_signals_with_gemini()
with the scored signals and classifier result.
Merge the fusion output into the crisis dict before returning it.
Add these new fields to the response: gemini_reasoning, uncertainty_level,
coherence_score, contradiction_flags, adjusted_confidence, source_weight_summary.
Use the adjusted_confidence as the final confidence value shown in the UI.

CHANGE 2 — agent_configs.py OrchestrationPipeline:
In the ClassificationAgent step (step 2), after running the classifier,
call fuse_signals_with_gemini and store the result in the pipeline state.
Add a new compat_log entry for the ClassificationAgent step that includes:
  - The gemini_reasoning text
  - The coherence_score formatted as a percentage
  - Any contradiction_flags, formatted as bullet points
This replaces the current scripted trace text for step 2.

Keep all existing behavior if Gemini returns the fallback dict.
Show exact code diffs, not full file rewrites.
```

---

## Phase 3 — Explainable Allocation Traces (Hours 5–8)

### Goal
Make the resource allocation agent explain its decisions in plain language through Gemini. The judges want to see *"we sent 2 rescue teams to G-10 because..."* on screen.

This directly addresses the **20% Resource Optimization criterion**.

---

### ANTIGRAVITY PROMPT 4 — Allocation Reasoning Engine

```
You are a Python AI engineer. CIRO allocates emergency resources using a
rule-based algorithm in backend/reasoning/allocation.py.

TASK: Create a new module that uses Gemini to generate a human-readable,
judge-quality explanation of WHY a specific allocation was made.

FILE TO CREATE: backend/reasoning/allocation_explainer.py

Function signature:
async def explain_allocation(
    crisis: dict,           # crisis object with type, severity, location, confidence
    allocation_plan: dict,  # output from allocation.py with units, ETAs
    population: int,        # population of affected zone
    competing_crises: list, # list of other active crises (may be empty)
    gemini_client
) -> dict

OUTPUT fields:
  headline: str        # one punchy sentence like an ops bulletin
  rationale: str       # 2–3 sentences: why this many units, why these types
  tradeoffs: str       # what was deprioritized and why (especially if competing crises)
  eta_context: str     # what the ETA means in human terms
  confidence_note: str # note on how classification confidence affected the allocation

GEMINI SYSTEM PROMPT:
  "You are an emergency operations commander writing a briefing for senior officials.
   Be direct, specific, and quantitative. Explain resource allocation decisions
   as if lives depend on the clarity of your reasoning. Never use filler phrases.
   Output valid JSON."

Use model: gemini-2.5-flash-preview-05-20, temperature 0.3.

ERROR HANDLING: If Gemini fails, return:
  headline: f"Deploying {total_units} units to {crisis['location']}"
  rationale: "Standard protocol allocation based on {crisis['severity']} severity."
  tradeoffs: "No competing crises recorded."
  eta_context: "Units dispatched per travel-time matrix."
  confidence_note: f"Classification confidence: {crisis['confidence']:.0%}"
```

---

### ANTIGRAVITY PROMPT 5 — Wire Allocation Explainer into Trace

```
TASK: Wire the allocation_explainer into the compat_logs trace so the
frontend's Trace tab shows real Gemini reasoning for every allocation.

FILES TO MODIFY:
1. backend/api/resources.py — POST /allocate endpoint
2. backend/main.py — /api/trigger handler for g10_flood and false_positive scenarios

CHANGE 1 — resources.py POST /allocate:
After running the existing allocation algorithm, call explain_allocation().
Add the explanation fields to the returned allocation response.
Add a new key "explanation" containing the full dict from explain_allocation().

CHANGE 2 — main.py compat layer for g10_flood:
Replace the hardcoded compat_logs entry for ResourceAllocationAgent (step 3)
with a dynamic entry that uses the explanation from explain_allocation():
  - Use explanation["headline"] as the log title
  - Use explanation["rationale"] + explanation["tradeoffs"] as the log body
  - Use explanation["confidence_note"] as a sub-note
This makes the Trace tab show real AI reasoning instead of the scripted text.

Do the same for the false_positive scenario's allocation log entry.

Keep existing fallback behavior if explain_allocation returns the error dict.
Show exact code diffs only.
```

---

## Phase 4 — New Crisis Scenarios (Hours 8–11)

### Goal
Add 3 new scenarios to demonstrate breadth. Judges need to see the system generalize beyond its demo script.

---

### ANTIGRAVITY PROMPT 6 — Three New Scenarios

```
You are a Python backend developer on CIRO. The system currently has three
demo scenarios: idle, g10_flood, false_positive. You need to add three more.

NEW SCENARIOS TO ADD:

1. balochistan_earthquake
   - Location: Quetta, Balochistan
   - Coordinates: 30.1798° N, 66.9750° E
   - Crisis type: EARTHQUAKE (add this to CrisisType enum if not present)
   - Severity: CRITICAL
   - Signals: 12 social posts (Urdu + English) reporting tremors, collapsed buildings
   - Mock calls: 35 calls/min (highest of all scenarios)
   - Resources needed: Search & rescue teams, NDMA units, medical helicopters
   - Weather: Dry, extreme heat (use wttr.in Quetta)

2. karachi_industrial_fire
   - Location: SITE Industrial Area, Karachi
   - Coordinates: 24.8607° N, 67.0011° E
   - Crisis type: FIRE (already exists)
   - Severity: HIGH
   - Signals: 8 social posts, smoke visible from multiple areas, chemical hazard
   - Mock calls: 22 calls/min
   - Resources needed: Fire brigades, hazmat units, evacuation teams
   - Weather: Humid coastal conditions (use wttr.in Karachi)

3. lahore_smog_health_crisis
   - Location: Lahore City, Punjab
   - Coordinates: 31.5204° N, 74.3587° E
   - Crisis type: HEATWAVE (repurpose for air quality / health emergency)
   - Severity: HIGH
   - Signals: 15 social posts about AQI >400, hospital admissions, school closures
   - Mock calls: 18 calls/min
   - Resources needed: Medical outreach, ambulances, air quality monitors

FILES TO MODIFY:
1. backend/data/generators.py — add SignalStreamScheduler scenarios for all 3
   Add social posts in both Urdu and English for each scenario.
   Use realistic Urdu text (not transliterated — actual Urdu script).

2. backend/main.py — add these 3 scenarios to the /api/trigger handler
   Each should populate compat_crises and compat_allocation like g10_flood does.
   Run OrchestrationPipeline for each new scenario.

3. backend/models/crisis_models.py — add EARTHQUAKE to CrisisType enum if missing

4. frontend/src/App.jsx — add the 3 new scenarios to the scenario selector UI
   Add them as buttons/options alongside the existing idle/g10_flood/false_positive.
   Add appropriate map coordinates for each new scenario's marker.

Write complete implementations for all 4 files. Show the full new sections,
not diffs, since these are additive changes.
```

---

## Phase 5 — UI Overhaul (Hours 11–18)

### Goal
Transform the dashboard from a functional demo into a visually impressive ops-center that judges remember. The aesthetic target: **military ops room meets modern SaaS** — dark, data-dense, authoritative.

---

### ANTIGRAVITY PROMPT 7 — Dashboard Redesign

```
You are a senior frontend engineer and UI designer. You are redesigning the
CIRO crisis intelligence dashboard (frontend/src/App.jsx, currently ~930 lines).

AESTHETIC DIRECTION: "Tactical Operations Center"
- Dark theme: background #0a0e1a, surface #111827, accent #00d4ff (electric cyan)
- Alert colors: RED #ff3b3b for CRITICAL, AMBER #f59e0b for HIGH, CYAN for active
- Font: 'JetBrains Mono' for data/metrics, 'Inter' for body text (both Google Fonts)
- Grid layout: CSS Grid with a left sidebar (scenario controls), main content area,
  and right panel (live signal stream)
- Animated elements: pulsing crisis markers, live signal ticker, typing effect
  for AI reasoning text, scanline animation on the header

SPECIFIC COMPONENTS TO BUILD:

1. Header bar
   - "CIRO" wordmark in cyan on left, glowing text-shadow
   - Real-time clock (Pakistan Standard Time, PKT = UTC+5)
   - System status indicator: green "ONLINE" or red "DEGRADED"
   - Current scenario label

2. Left sidebar — Scenario Control Panel
   - Title: "SCENARIO INJECTION"
   - Six scenario buttons (idle, g10_flood, false_positive, plus the 3 new ones)
   - Each button shows: icon, scenario name, short description
   - Active scenario highlighted with cyan border + glow
   - "RUN DEMO" button — large, prominent, with loading spinner during demo

3. Main content — Crisis Intelligence Feed
   - Replace existing crisis cards with a "ACTIVE THREATS" panel
   - Each crisis card shows:
     * Threat type icon (flood, fire, earthquake, etc.)
     * Location in CAPS
     * Severity badge (CRITICAL/HIGH/MEDIUM/LOW) with color coding
     * Confidence percentage with a thin progress bar
     * Coherence score (new — from Gemini fusion) as a small circular gauge
     * Gemini reasoning snippet (first sentence, expandable)
   - Below: "RESOURCE DEPLOYMENT" section showing allocation with
     the Gemini-generated headline and rationale

4. Right panel — Live Signal Stream
   - Title: "SIGNAL STREAM"
   - Scrolling live feed of incoming signals (from WebSocket /ws/signals)
   - Each signal shows: source icon, timestamp, truncated content, credibility score
   - Color-code by source: social=blue, weather=teal, traffic=amber, calls=red
   - Auto-scrolls, shows last 20 entries

5. Bottom panel — Agent Trace (replaces the Trace tab)
   - Full-width, collapsible
   - Shows all agent steps with timestamps
   - Each step expands to show the full Gemini reasoning text
   - Steps animate in one-by-one during demo run (existing timing logic)
   - Step icons: 🔍 SignalFusion, 🧠 Classification, 🚁 Allocation,
     📋 ResponsePlan, 📢 Stakeholder, 🎯 Orchestrator, ✅ Verification

6. Map tab (keep existing Leaflet map, improve styling)
   - Dark basemap (already CartoDB dark — keep this)
   - Make crisis markers pulse with CSS animation
   - Add a legend panel overlay
   - Show resource deployment lines from depot to crisis location

TECHNICAL REQUIREMENTS:
- Keep all existing API call logic and state management unchanged
- Keep VITE_BACKEND_URL environment variable
- Add Google Fonts import at top of index.html or via @import in CSS
- All new components inline in App.jsx (single file, as before)
- Must work with the existing backend API responses

Write the complete new App.jsx. This is a full rewrite of the frontend.
```

---

### ANTIGRAVITY PROMPT 8 — Before/After Comparison Panel

```
The CIRO dashboard has a "Before/After" tab that currently shows hardcoded
marketing numbers. Replace it with a dynamic, visually impressive comparison
that pulls real data.

FILE TO MODIFY: frontend/src/App.jsx (the before_after tab section only)

CURRENT STATE: Static HTML showing "47 min → 2.3 min", "95% Faster" etc.

NEW STATE:
1. Call GET /api/alerts/comparison when the tab is opened
2. Display a split-panel comparison: left = "Traditional Response", right = "CIRO"
3. For each metric, show an animated counter that counts up to the value
4. Metrics to show:
   - Detection time (ms)
   - Classification confidence
   - Resources deployed
   - Estimated lives impacted (from population data)
   - False positive rate
5. Add a "CIRO ADVANTAGE" highlight box showing the % improvement for each metric
6. Show the Gemini-generated allocation reasoning in a "Reasoning Transparency" box
   on the CIRO side — this is your showcase of AI explainability

STYLING: Match the tactical ops-center aesthetic from Prompt 7.
Animated number counters should use requestAnimationFrame for smooth counting.
Make the CIRO side significantly more detailed than the Traditional side to
visually reinforce the advantage.
```

---

## Phase 6 — Free Deployment (Hours 18–20)

### ANTIGRAVITY PROMPT 9 — Render Backend Deploy Config

```
TASK: Prepare the CIRO FastAPI backend for free deployment on Render.

Create the following files:

1. render.yaml (in project root):
   services:
     - type: web
       name: ciro-backend
       env: python
       buildCommand: pip install -r backend/requirements.txt
       startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
       envVars:
         - key: GEMINI_API_KEY
           sync: false
         - key: DEMO_MODE
           value: "true"
         - key: PORT
           value: "8000"

2. Update backend/main.py CORS settings:
   Change allow_origins=["*"] to read from an env variable ALLOWED_ORIGINS.
   Default to ["*"] if not set (keeps local dev working).
   Add: allow_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

3. Update backend/main.py startup:
   The background g10_flood generator currently runs always.
   Gate it behind: if os.getenv("DEMO_MODE", "false").lower() == "true"
   This prevents it burning free tier resources when idle.

4. Create a /health endpoint upgrade:
   Return JSON with: status, uptime_seconds, active_crises_count,
   signal_buffer_size, gemini_available (bool), weather_source ("wttr.in")
   This gives judges a confidence-inspiring status page.

Show all complete file contents.
```

---

### ANTIGRAVITY PROMPT 10 — Vercel Frontend Deploy Config

```
TASK: Prepare the CIRO React frontend for free deployment on Vercel.

Create or update the following:

1. frontend/vercel.json:
   {
     "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
     "env": {
       "VITE_BACKEND_URL": "@ciro_backend_url"
     }
   }

2. Update frontend/.env.example:
   VITE_BACKEND_URL=https://your-ciro-backend.onrender.com
   (Replace with actual Render URL after deployment)

3. In frontend/src/App.jsx, add a visual indicator when the backend is offline:
   On startup, call GET /health with a 5-second timeout.
   If it fails, show a banner: "Backend warming up — this may take 30 seconds"
   with a spinner. Retry every 5 seconds until health check passes.
   Remove the banner automatically when the backend is up.
   This handles Render's cold-start gracefully during the demo.

4. Create frontend/public/og.png placeholder note:
   Add a comment in index.html for Open Graph meta tags:
   title: "CIRO — Crisis Intelligence & Response Orchestrator"
   description: "AI-powered multi-source crisis detection and resource allocation"

Show all complete file contents.
```

---

## Demo Script for Judges (Rehearse This)

**Opening line (30 seconds):**
> "CIRO doesn't just detect crises — it reasons about them. Watch the agent trace. Every confidence score, every allocation decision, every false-positive retraction has a Gemini-generated explanation behind it. Let me show you."

**Demo sequence (3 minutes):**
1. Start on idle → point to the live signal stream on the right
2. Click "G-10 FLOOD" scenario → hit RUN DEMO
3. As the trace animates in: *"This coherence score is Gemini comparing all six signal sources against each other in real time — social, weather, traffic, emergency calls"*
4. Point to the allocation panel: *"The system chose 3 rescue teams not because that's hardcoded — it reasoned that G-10's population of 85,000 at CRITICAL severity demands a 60% resource commit with a 12-minute ETA"*
5. Switch to FALSE POSITIVE: *"Now watch — a CDA water department report contradicts the flood classification. EASE-Net-style contradiction scoring crosses 0.60 threshold, VerificationAgent retracts. This is real-time uncertainty handling."*
6. Show Before/After tab: *"95% faster detection. But more importantly — every decision is auditable. You can see the exact reasoning chain."*

**Closing line:**
> "Traditional emergency systems generate alerts. CIRO generates reasoning."

---

## Checklist Before Submission

- [ ] Gemini free tier key added to Render env vars
- [ ] `VITE_BACKEND_URL` pointing to live Render URL in Vercel settings
- [ ] Cold-start banner tested (ping backend 30 min before demo)
- [ ] All 6 scenarios tested end-to-end
- [ ] wttr.in working for all 4 cities
- [ ] Agent trace shows Gemini text (not scripted text) for flood scenario
- [ ] Before/After tab loads from API (not hardcoded)
- [ ] No API keys committed to git (check `.gitignore`)
- [ ] Demo rehearsed at least 3 times

---

*CIRO Antigravity Dev Plan · Solo Sprint Edition · Generated 2026-05-21*
