# Chaos resilience audit

3 of 3 experiments produced evaluable results. Score: 36. Findings describe aggregate probe observations; architectural causes remain hypotheses.

Score = max(15, 100 − 18×K − 10×E − 6×M). Penalties are additive.
K: rollback triggered; E: peak probe errors >15%; M: recovery >4s or unconfirmed at timeout.
Not-run and failed injections are excluded. No evaluable experiments means no score.

## Baseline

{"total_requests": 48, "error_rate": 0.0, "p50_latency_ms": 10.24, "p95_latency_ms": 123.85, "avg_latency_ms": 41.89}

## Experiments

| Target | Status | Peak p95 ms | Peak errors | Rollback seconds | Recovery seconds | Recovery confirmed |
|---|---|---:|---:|---:|---:|---|
| cart | aborted | 2501.9 | 22.2% | 0.0418 | 2.52 | True |
| valkey-cart | aborted | 2501.8 | 12.5% | 0.0282 | 2.52 | True |
| recommendation | aborted | 1556.0 | 0.0% | 0.6418 | 3.51 | True |

## Evidence limits

Probe errors include unsuccessful HTTP responses and transport failures. Peak metrics are maxima across monitoring windows, not necessarily simultaneous.
Recovery requires two healthy checks with fresh samples. A timeout is not confirmed recovery.
The synchronous supervisor polls every 500ms after injection; telemetry workers run concurrently. Rollback timing is measured per experiment.
CLI SIGINT/SIGTERM handlers attempt scoped cleanup. Forced termination, host loss, and Docker failures cannot guarantee cleanup.
Network faults require the configured netshoot image and an unmodified qdisc. Existing network rules are never replaced.

## Findings

### cart: Observed degradation during fault
Aggregate probes reached p95 2501.9ms and error rate 22.2%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.

### valkey-cart: Observed degradation during fault
Aggregate probes reached p95 2501.8ms and error rate 12.5%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.

### recommendation: Observed degradation during fault
Aggregate probes reached p95 1556.0ms and error rate 0.0%. Root cause and affected user journeys require further investigation.
Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.
