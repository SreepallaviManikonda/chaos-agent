"""Stage 5: Gemini Flash Post-Mortem Resilience Scoring & Actionable Audit Report Generation."""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    REPORT_JSON_FILE,
    REPORT_MD_FILE,
)
from safety_guard import ExperimentResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AIReporter")


class Vulnerability(BaseModel):
    service: str = Field(description="Affected microservice name")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(description="Severity rank")
    title: str = Field(description="Short vulnerability summary")
    description: str = Field(description="Detailed explanation of failure mode")
    impact: str = Field(description="Business and system availability blast radius")


class PrescribedFix(BaseModel):
    service: str = Field(description="Target microservice for remediation")
    fix_type: str = Field(description="Architecture pattern: Circuit Breaker, Fallback Cache, Retry Backoff, etc.")
    recommendation: str = Field(description="Concrete actionable remediation steps")
    priority: int = Field(description="Priority ranking (1 = urgent)")
    effort: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="Implementation effort")


class ExperimentSummary(BaseModel):
    experiment_id: str
    target_service: str
    experiment_type: str
    kill_switch_triggered: bool
    mttr_sec: float
    peak_error_rate: float
    peak_p95_ms: float
    evaluation: str


class ResilienceAuditReport(BaseModel):
    overall_resilience_score: Optional[int] = Field(default=None, ge=0, le=100)
    summary: str = Field(description="Executive post-mortem summary")
    experiments_evaluated: List[ExperimentSummary]
    vulnerabilities: List[Vulnerability]
    prescribed_fixes: List[PrescribedFix]


def calculate_deterministic_report(results, baseline_stats):
    valid = [r for r in results if r.status in ('completed', 'aborted', 'recovery_timeout')]
    score = max(15, 100 - sum(18 * int(r.kill_switch_triggered)
                + 10 * int(r.failure_metrics.get('error_rate', 0) > .15)
                + 6 * int(r.mttr_sec > 4 or r.status == 'recovery_timeout') for r in valid)) if valid else None
    summaries, vulnerabilities, fixes = [], [], []
    for r in results:
        err = r.failure_metrics.get('error_rate', 0)
        p95 = r.failure_metrics.get('p95_latency_ms', 0)
        summaries.append(ExperimentSummary(
            experiment_id=r.experiment_id, target_service=r.target_service,
            experiment_type=r.experiment_type, kill_switch_triggered=r.kill_switch_triggered,
            mttr_sec=r.mttr_sec, peak_error_rate=err, peak_p95_ms=p95,
            evaluation=f'{r.status}: {r.trigger_reason or "No threshold breach observed"}; recovery confirmed={r.recovery_confirmed}'))
        if r in valid and (r.kill_switch_triggered or err > .15):
            vulnerabilities.append(Vulnerability(
                service=r.target_service, severity='HIGH', title='Observed degradation during fault',
                description=f'Aggregate probes reached p95 {p95:.1f}ms and error rate {err:.1%}. Root cause and affected user journeys require further investigation.',
                impact='Probe degradation observed; session loss, revenue impact, and missing circuit breakers are not established.'))
            fixes.append(PrescribedFix(service=r.target_service, priority=1, effort='MEDIUM',
                fix_type='Investigate dependency resilience',
                recommendation='Inspect affected traces and request paths. Evaluate bounded timeouts, circuit breakers, fallback behavior, and datastore redundancy where applicable; repeat the same experiment after changes.'))
    return ResilienceAuditReport(overall_resilience_score=score,
        summary=f'{len(valid)} of {len(results)} experiments produced evaluable results. Score: {score if score is not None else "unavailable"}. Findings describe aggregate probe observations; architectural causes remain hypotheses.',
        experiments_evaluated=summaries, vulnerabilities=vulnerabilities, prescribed_fixes=fixes)

class AIReporter:
    def __init__(self, api_key=None):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv('GEMINI_API_KEY', '')
        self.model = GEMINI_MODEL

    def generate_report(self, results, baseline_stats, topology=None):
        # Metrics, score, and findings always come from the deterministic evaluator.
        report = calculate_deterministic_report(results, baseline_stats)
        if self.api_key:
            try:
                from google import genai
                response = genai.Client(api_key=self.api_key).models.generate_content(
                    model=self.model, contents='Summarize these measured observations in two sentences. Do not infer root causes, session loss, or rollback guarantees. Preserve the score and distinguish unsuccessful experiments. Data: ' + report.model_dump_json())
                if response.text:
                    report.summary += '\nAI interpretation (not additional evidence): ' + response.text
            except Exception as exc:
                logger.warning('AI summary unavailable: %s', exc)
        self.export_artifacts(report, results, baseline_stats)
        return report

    def export_artifacts(self, report, results, baseline_stats):
        REPORT_JSON_FILE.write_text(report.model_dump_json(indent=2))
        REPORT_MD_FILE.write_text(self._render_markdown_report(report, results, baseline_stats))

    def _render_markdown_report(self, report, results, baseline_stats):
        lines = ['# Chaos resilience audit', '', report.summary, '',
                 'Score = max(15, 100 − 18×K − 10×E − 6×M). Penalties are additive.',
                 'K: rollback triggered; E: peak probe errors >15%; M: recovery >4s or unconfirmed at timeout.',
                 'Not-run and failed injections are excluded. No evaluable experiments means no score.', '',
                 '## Baseline', '', json.dumps(baseline_stats), '',
                 '## Experiments', '',
                 '| Target | Status | Peak p95 ms | Peak errors | Rollback seconds | Recovery seconds | Recovery confirmed |',
                 '|---|---|---:|---:|---:|---:|---|']
        for r in results:
            lines.append(f'| {r.target_service} | {r.status} | {r.failure_metrics.get("p95_latency_ms", 0):.1f} | {r.failure_metrics.get("error_rate", 0):.1%} | {r.rollback_sec} | {r.mttr_sec} | {r.recovery_confirmed} |')
        lines += ['', '## Evidence limits', '',
                  'Probe errors include unsuccessful HTTP responses and transport failures. Peak metrics are maxima across monitoring windows, not necessarily simultaneous.',
                  'Recovery requires two healthy checks with fresh samples. A timeout is not confirmed recovery.',
                  'The synchronous supervisor polls every 500ms after injection; telemetry workers run concurrently. Rollback timing is measured per experiment.',
                  'CLI SIGINT/SIGTERM handlers attempt scoped cleanup. Forced termination, host loss, and Docker failures cannot guarantee cleanup.',
                  'Network faults require the configured netshoot image and an unmodified qdisc. Existing network rules are never replaced.', '', '## Findings', '']
        for v in report.vulnerabilities:
            lines += [f'### {v.service}: {v.title}', v.description, v.impact, '']
        return '\n'.join(lines)
