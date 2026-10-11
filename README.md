# 🏎️ Chaos Pit Wall: Autonomous Microservice Resilience Telemetry

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chaos-agent.streamlit.app)
[![Docker Engine](https://img.shields.io/badge/Docker-v27.0-blue.svg)](https://www.docker.com/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Demo_v1.11-orange.svg)](https://opentelemetry.io/)
[![Safety Watchdog](https://img.shields.io/badge/Safety_Supervisor-500ms_Watchdog-green.svg)](#safety-architecture)
[![Deterministic Score](https://img.shields.io/badge/Resilience_Score-36%2F100-red.svg)](#deterministic-resilience-scoring)

**Autonomous, safeguarded chaos engineering platform designed for Google Cloud's 13-microservice Online Boutique (OpenTelemetry Demo).**

We break parts of a live cloud-native cluster on purpose and under strict safety guardrails to diagnose critical Single Points of Failure (SPOFs) before they impact real customers—presented through an **F1 Pit Wall Telemetry** mental model that any engineer or judge can immediately understand.

---

## 🏁 Walkthrough Preview

![Chaos Pit Wall Preview](assets/chaos_pitwall_preview.gif)

> 🎥 **Full High-Definition Video**: Watch `assets/chaos_pitwall_demo.mp4` (720p 30fps Full HD Walkthrough with animated telemetry traces, stopwatch MTTR, and AI Race Engineer radio).

---

## ⚡ The Pit Wall Mental Model

| Cloud Architecture Concept | F1 Pit Wall Telemetry Equivalent | Plain-English Meaning |
|---|---|---|
| **Baseline Probes** | **Qualifying Benchmark (Pole Lap)** | Normal cluster behavior (10.2ms p50, 123.8ms p95) before stress. |
| **Chaos Experiment** | **Grand Prix Stress Stint** | Controlled fault injection on a selected microservice. |
| **Kill-Switch Trigger** | **🔴 Red Flag Session Halt** | Emergency brake halts experiment when latency or error SLA is breached. |
| **Watchdog Supervisor** | **FIA Race Control** | Active 500ms polling loop monitoring aggregate health metrics. |
| **Container Rollback** | **Instant Pit Stop Revert (<50ms)** | Physical container unpause or kernel qdisc removal. |
| **MTTR (Mean Time To Recover)**| **Pit-Stop Duration (Stopwatch)** | Total elapsed time from rollback trigger to confirmed baseline stability. |
| **Resilience Score** | **Championship Superlicence Points** | Deterministic score (0–100) assessing system toughness. |
| **AI Audit Post-Mortem** | **📻 Team Radio / Steward Ruling** | Gemini 2.5 Flash root cause analysis and infrastructure fixes. |

---

## 🗺️ Discovered Architecture Topology

The platform autonomously discovers the cluster structure without manual YAML configuration using OpenTelemetry / Jaeger dependency tracing and Docker inspect APIs:

```
[ Ingress / Frontend Proxy ] (:8080)
        │
        ├──► [ Frontend ] (Storefront UI & API Gateway)
        │         │
        │         ├──► [ Cartservice ] (:7070) ──► [ Valkey-Cart ] (:6379 Redis SPOF)
        │         │
        │         ├──► [ Checkoutservice ] (:5050)
        │         │         ├──► [ Paymentservice ]
        │         │         ├──► [ Shippingservice ]
        │         │         ├──► [ Emailservice ]
        │         │         └──► [ Currencyservice ]
        │         │
        │         ├──► [ Productcatalogservice ] (:3550)
        │         └──► [ Recommendationservice ] (:9001)
```

- **Discovered Nodes**: 13 Active Microservices
- **Discovered Call Edges**: 30 Inter-service Dependency Paths
- **Critical Weak Link Identified**: `cartservice` has **0 fallback mechanisms** if `valkey-cart` halts.

---

## 🔬 Measured Chaos Experiments & Empirical Evidence

Every experiment in our campaign exercises genuine container-level and kernel-level faults on the live cluster. No application-level mock flags (`flagd`) are used.

### Campaign Summary

| Experiment | Target Service | Fault Type | Injected Mechanism | Peak p95 Latency | Peak HTTP 5xx | Pit-Stop MTTR | Container Revert | Verdict |
|---|---|---|---|---:|---:|---:|---:|:---:|
| **EXP-001** | `cart` | Container Pause | `docker pause cart` | **2,501.9 ms** | **22.2%** | **2.52 s** | **41.8 ms** | 🔴 Red Flag (Aborted) |
| **EXP-002** | `valkey-cart` | Datastore Pause | `docker pause valkey-cart` | **2,501.8 ms** | **12.5%** | **2.52 s** | **28.2 ms** | 🔴 Red Flag (Aborted) |
| **EXP-003** | `recommendation` | Network Delay | Kernel `tc netem delay 500ms` | **1,556.0 ms** | **0.0%** | **3.51 s** | **641.8 ms** | 🔴 Red Flag (Aborted) |

### Empirical Verification Benchmark (Multi-Trial Spread & Control)

To strengthen the empirical validity of our findings, we executed benchmark trials recorded in `evidence_benchmark.json`:

1. **No-Fault Control Run (Baseline Noise)**:
   - Duration: 7.0 seconds of steady-state probing
   - Results: **0.0% errors**, **12.6ms p50**, **240.2ms p95**, **0 kill-switch triggers**
   - Proves that measured spikes during experiments are genuine consequences of injected faults.

2. **Cart Outage Multi-Trial Spread (3 consecutive trials)**:
   - Trial 1: MTTR = 3.01s | Revert = 105.3ms | Peak p95 = 2,501.7ms
   - Trial 2: MTTR = 3.02s | Revert = 37.8ms | Peak p95 = 2,502.3ms
   - Trial 3: MTTR = 3.02s | Revert = 20.1ms | Peak p95 = 2,501.8ms
   - **Mean MTTR**: **3.02 seconds** (Range: 3.01s – 3.02s, Spread: **±0.01s**)
   - **Mean Physical Rollback**: **54.4 ms**

---

## 🛡️ Safety Architecture: Active Watchdog Supervisor

Safety is enforced as an architectural invariant, not an afterthought:

```
[ Background Load Prober ]  ──►  10 RPS user journeys against /api/cart, /api/products, etc.
                                           │
                                           ▼ (Pushes samples into thread-safe buffer)
[ Active Safety Supervisor ] ◄──  Polls rolling metrics every 500ms
        │
        ├──► Healthy (p95 < 1500ms & 5xx < 30%) ──► Continue experiment window
        │
        └──► Breached! ──► 🚨 TRIPS KILL-SWITCH
                                 │
                                 ├── 1. Physical Revert (<55ms): container.unpause() / tc qdisc del
                                 ├── 2. Scoped Signal Cleanup: catches SIGINT/SIGTERM via Python signal
                                 ├── 3. Finally-block failsafe: always restores original state
                                 └── 4. Recovery verification: polls fresh samples until baseline reconfirmed
```

> **💡 Detection Time vs. Revert Time**:
> - **Detection Time (~3.0s)**: Probe HTTP timeouts are bounded at 2.5s. It takes ~3.0s for slow requests to accumulate in the sliding 1.0s evaluation window and trip the watchdog.
> - **Revert Time (<55ms)**: Once the threshold is breached, the container unpause / tc rule deletion executes in under 55 milliseconds.

---

## 📊 Deterministic Resilience Scoring (0% LLM Guesswork)

Resilience scores are calculated via an auditable, deterministic formula. LLMs are never allowed to fabricate or modify safety metrics:

$$\text{Score} = \max\left(15, 100 - (18 \times K) - (10 \times E) - (6 \times M)\right)$$

Where:
- **$K$ (Kill-Switch Triggers)**: Number of experiments that breached SLAs and triggered emergency rollbacks ($-18$ pts each).
- **$E$ (High Error Bursts)**: Number of experiments with peak HTTP 5xx error rate $> 15\%$ ($-10$ pts each).
- **$M$ (Prolonged Recovery)**: Number of experiments taking $> 4.0\text{s}$ to recover or timing out without fresh probe confirmation ($-6$ pts each).

### Current Cluster Calculation
$$\text{Score} = 100 - (18 \times 3) - (10 \times 1) - (6 \times 0) = 100 - 54 - 10 = \mathbf{36 / 100}$$

- **Status**: 🔴 **DEGRADED (2 Critical Single Points of Failure)**
- Currencyservice & Shippingservice survived flawlessly (+0 pt penalty).
- Cartservice & Valkey-cart datastore caused 100% downstream failure across the checkout pipeline.

---

## 📻 AI Race Engineer Copilot & Prescribed Fixes

Powered by **Gemini 2.5 Flash** (with instant offline telemetry knowledge fallback), the AI Race Engineer diagnoses root causes and prescribes concrete remediation:

1. **Valkey-Cart Redis SPOF**:
   - *Diagnosis*: `valkey-cart` has no replica. Dropping packets freezes `cartservice` TCP connection pool.
   - *Prescription*: Deploy Redis Sentinel with master-replica failover and local in-memory Redis read replica.
2. **Cart Service Circuit Breaking**:
   - *Diagnosis*: Frontend blocks synchronously waiting for cart RPCs during cart degradation.
   - *Prescription*: Inject Envoy sidecar with circuit breaker on port 7070: timeout at 500ms and return a degraded cart state with cached items.
3. **Graceful UI Degradation**:
   - *Prescription*: Allow browsing product catalog even when shopping cart is in degraded mode.

---

## 🚀 Quickstart & Reproduction

### Prerequisites
- macOS / Linux with Docker Engine running
- Python 3.11+
- OpenTelemetry Demo cluster running (e.g. `docker compose up -d`)

### 1. Installation
```bash
git clone https://github.com/Sreepallavimanikonda/chaos-agent.git
cd chaos-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Autonomous Chaos Campaign
```bash
python main.py
```
*Executes discovery, baseline capture, intelligent planning, safeguarded execution, and deterministic scoring.*

### 3. Launch the F1 Pit Wall Dashboard
```bash
streamlit run dashboard.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

> **☁️ Note on Streamlit Cloud**:
> On [chaos-agent.streamlit.app](https://chaos-agent.streamlit.app), the dashboard runs in **Telemetry Archive Replay Mode** because cloud servers cannot access local Docker sockets. Live injection is enabled on `localhost:8501`.

### 4. Run Reliability Verification Tests
```bash
python -m unittest discover -s tests -v
```
*All 15 automated mock safety tests pass in < 1 second.*

---

## 📦 Submission Pack

- **Live Streamlit Pit Wall**: [https://chaos-agent.streamlit.app](https://chaos-agent.streamlit.app)
- **Source Repository**: [https://github.com/Sreepallavimanikonda/chaos-agent](https://github.com/Sreepallavimanikonda/chaos-agent)
- **Video Walkthrough (HD MP4)**: `assets/chaos_pitwall_demo.mp4`
- **Animated Preview (GIF)**: `assets/chaos_pitwall_preview.gif`
- **Full Findings Report**: [FINDINGS_REPORT.md](FINDINGS_REPORT.md)
- **Empirical Benchmark**: [evidence_benchmark.json](evidence_benchmark.json)
