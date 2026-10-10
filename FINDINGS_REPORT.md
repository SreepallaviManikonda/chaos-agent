# Chaos resilience audit

Historical audit; score recalculated from saved summary metrics. Rollback timing and recovery estimates are unverified. No new experiment was run. 3 of 3 experiments produced evaluable results. Score: 46. Findings describe aggregate probe observations; architectural causes remain hypotheses.

Score = max(15, 100 − 18×K − 10×E − 6×M). Penalties are additive.
K: rollback triggered; E: peak probe errors >15%; M: recovery >4s or unconfirmed at timeout.
Not-run and failed injections are excluded. No evaluable experiments means no score.

## Baseline

{"provenance": "historical baseline", "p50_latency_ms": 31.3, "p95_latency_ms": 464.9, "error_rate": 0, "total_requests": 30}

## Experiments

| Target | Status | Peak p95 ms | Peak errors | Rollback seconds | Recovery seconds | Recovery confirmed |
|---|---|---:|---:|---:|---:|---|
| cart | aborted | 2500.0 | 10.0% | None | 0.51 | False |
| valkey-cart | aborted | 2500.0 | 10.0% | None | 0.1 | False |
| recommendation | aborted | 1996.2 | 0.0% | None | 0.51 | False |

## Evidence limits

Probe errors include unsuccessful HTTP responses and transport failures. Peak metrics are maxima across monitoring windows, not necessarily simultaneous.
Recovery requires two healthy checks with fresh samples. A timeout is not confirmed recovery.
The synchronous supervisor polls every 500ms after injection; telemetry workers run concurrently. Rollback timing is measured per experiment.
CLI SIGINT/SIGTERM handlers attempt scoped cleanup. Forced termination, host loss, and Docker failures cannot guarantee cleanup.
Network faults require the configured netshoot image and an unmodified qdisc. Existing network rules are never replaced.

## Findings

### cart: Observed degradation during fault
Aggregate probes reached p95 2500.0ms and error rate 10.0%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.

### valkey-cart: Observed degradation during fault
Aggregate probes reached p95 2500.0ms and error rate 10.0%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.

### recommendation: Observed degradation during fault
Aggregate probes reached p95 1996.2ms and error rate 0.0%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.
