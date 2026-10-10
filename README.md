# Chaos Pit Wall

A Docker chaos-testing prototype for the OpenTelemetry Demo with a Streamlit dashboard and optional Gemini planning and interpretation.

## Run

Use Python 3.11+ and install `requirements.txt`. Run the OpenTelemetry Demo separately. Set `CHAOS_COMPOSE_PROJECT` to its Compose project label (default `opentelemetry-demo`) and `FRONTEND_URL` if not `http://localhost:8080`.

```sh
python main.py
streamlit run dashboard.py
```

Set `GEMINI_API_KEY` for optional AI generation. Cached plans take precedence. Numeric scores and observations always come from deterministic evaluation.

Network delay requires a locally available `local-netshoot:latest` image containing `tc` (override with `CHAOS_NETSHOOT_IMAGE`). Existing network rules cause the experiment to be refused. There is no application-level fallback disguised as a network fault.

## Behavior and safeguards

- Concurrent, bounded HTTP probing targets 10 requests/second; timestamps record completion. Errors include unsuccessful HTTP responses and transport failures.
- Experiments require a healthy baseline with at least five samples. Missing telemetry triggers rollback.
- A synchronous supervisor polls every 500ms after injection; telemetry runs in background workers.
- Only allowlisted services in the configured Compose project may be targeted. Ambiguous matches are refused.
- Rollback restores the original CPU quota and period, unpauses owned faults, and removes only the owned netem rule. Failed cleanup retains ownership for retry.
- A file lock prevents overlapping campaigns across CLI and dashboard processes. CLI signal handlers attempt cleanup on SIGINT/SIGTERM. Forced termination, host loss, and Docker failures cannot guarantee rollback; inspect resources after such failures.
- Recovery requires two healthy checks containing fresh samples. Timeout is reported as unconfirmed recovery.
- The dashboard executes real experiments when Docker is available. Otherwise it offers a labeled illustrative simulation. Measured summaries are written to `results.json`; raw probes are in `telemetry_history.json`. New runs do not fabricate replay curves.

## Evidence and scoring

Historical artifacts record cart pause, Valkey pause, and recommendation network delay. The saved Jaeger snapshot contains 13 nodes and 30 edges. Historical recovery estimates remain unverified under the corrected implementation. Illustrative timelines are not raw telemetry.

Score = max(15, 100 - 18*K - 10*E - 6*M), with additive penalties:

- K: experiments triggering rollback.
- E: experiments with peak probe error rate above 15%.
- M: experiments taking over four seconds to recover or timing out without confirmed recovery.

Failed injections and skipped experiments are excluded; no evaluable experiments means no score. Reapplying the formula to historical summaries gives 46, replacing the inconsistent 38. This is a heuristic campaign score, not a calibrated reliability guarantee.

Reports distinguish observed degradation from hypotheses. Probe results alone cannot establish session loss, revenue impact, or absence of circuit breakers.

## Verification

```sh
python -m unittest discover -s tests -v
```

Tests use mocked Docker operations and do not disrupt running services.
