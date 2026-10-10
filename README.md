# 🛡️ Autonomous AI-Driven Chaos Engineering System for Cloud-Native Resilience

An autonomous, safe, and closed-loop Chaos Engineering agent built to stress-test microservices within the **OpenTelemetry Demo** on Apple Silicon (M4). Powered by **Gemini 2.5 Flash**, **Docker SDK**, and real-time **Observability Telemetry**.

---

## 🚀 Key Features

- **Automated Topology Discovery:** Discovers runtime microservice call graphs directly from Jaeger Tracing REST API (`/jaeger/ui/api/dependencies`) with Docker Compose fallback.
- **Continuous Observability & Probing:** Asynchronous load generator probing storefront and microservice APIs (`/`, `/api/products`, `/api/cart`, `/api/recommendations`) at 10 req/s, tracking 1-second rolling p50/p95 latency and HTTP 5xx error rates.
- **500ms Safety Watchdog & Emergency Kill-Switch:** Real-time supervisor running concurrently with all injections. If error rate exceeds 30% or p95 exceeds 1500ms, the automated kill-switch executes instant rollback in `<50ms`.
- **Intelligent Experiment Planner:** Uses Gemini 2.5 Flash structured output to prioritize experiments based on graph centrality and blast radius.
- **Post-Mortem Resilience Scorer:** Automatically scores resilience (0–100), detects architectural vulnerabilities (CRITICAL, HIGH, MEDIUM), and outputs actionable cloud-native remediations.
- **Interactive Streamlit Console:** Real-time rolling latency/error charts, interactive DAG visualization, MTTR comparison, and operator controls.

---

## 📁 Repository Structure

```text
chaos-agent/
├── config.py                 # Global constants, target URLs, safety thresholds
├── topology.py               # Stage 1: Maps services, dependencies, and call counts via Jaeger API
├── telemetry.py              # Stage 2 & 4: Load generator (10 RPS), rolling p95 latency & MTTR tracker
├── chaos_injector.py         # Stage 3: Docker-py executor (container pause/unpause, CPU throttle, Flagd delay)
├── safety_guard.py           # Stage 3: Watchdog polling every 500ms; auto-reverts on threshold breach
├── ai_planner.py             # Stage 2: Gemini Flash structured JSON planner with local cache & offline fallback
├── ai_reporter.py            # Stage 5: Gemini Flash post-mortem report, resilience score (0-100) & fixes
├── dashboard.py              # Live Streamlit UI showing topology graph, real-time metrics, & AI reports
├── main.py                   # Master CLI pipeline orchestrating Stages 1 through 5 end-to-end
├── findings_report.json      # Structured post-mortem audit results
├── FINDINGS_REPORT.md        # Formatted Markdown resilience report
├── discovered_topology.json  # Discovered Jaeger dependency graph
├── telemetry_history.json    # Recorded real-time telemetry stream
└── requirements.txt          # Python dependencies
```

---

## 🛠️ Quickstart

### 1. Prerequisites
- Docker & Docker Compose running [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) (`http://localhost:8080`)
- Python 3.11+

### 2. Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Chaos Pipeline
```bash
# Optional: Set Gemini API Key for live AI generation
export GEMINI_API_KEY="your-gemini-api-key"

# Run master pipeline
python main.py
```

### 4. Launch Live Dashboard
```bash
streamlit run dashboard.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📊 Latest Resilience Scorecard

| Target Service | Failure Injection | Duration | Safety Kill-Switch? | MTTR | Peak p95 Latency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cart` | Container Pause | 4.02s / 8.0s | 🚨 **TRIGGERED** | 0.51s | 2500.0 ms | **Rollback by Watchdog** |
| `product-catalog` | CPU Throttle (10%) | 8.05s / 8.0s | 🛡️ Safe Complete | 1.52s | 7.1 ms | **Passed Safely** |
| `recommendation` | Network Latency | 8.04s / 8.0s | 🛡️ Safe Complete | 0.10s | 93.3 ms | **Passed Safely** |

- **Overall System Resilience:** **74 / 100**
- **Safety Guarantee:** Zero permanent crashes or left-over paused containers.
