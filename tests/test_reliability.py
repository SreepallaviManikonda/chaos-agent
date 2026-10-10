import time
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock, patch
from telemetry import TelemetryCollector, ProbeSample, RollingStats
from chaos_injector import ChaosInjector
from safety_guard import ExperimentResult, SafetyGuard
from ai_reporter import calculate_deterministic_report
from execution import campaign_scope, save_dashboard_results
import tempfile
import json
from pathlib import Path

def result(**kw):
    args = dict(experiment_id='x', target_service='cart', experiment_type='container_pause', planned_duration_sec=8,
                actual_duration_sec=1, kill_switch_triggered=True, trigger_reason='latency', breached_metric='p95_latency_ms',
                breached_value=2500, baseline_metrics={}, failure_metrics={'error_rate': .1, 'p95_latency_ms':2500},
                recovery_metrics={}, mttr_sec=.51, status='aborted', recovery_confirmed=True)
    args.update(kw)
    return ExperimentResult(**args)

class ReliabilityTests(unittest.TestCase):
    def test_stale_and_empty_samples_are_not_healthy(self):
        t=TelemetryCollector()
        t._samples.append(ProbeSample(time.time()-10, '', 200, 20, False))
        stats=t.get_stats()
        self.assertEqual(stats.total_requests,0)
        self.assertFalse(stats.healthy)
        t.measure_mttr(timeout_sec=.02, poll_interval_sec=.005)
        self.assertFalse(t.last_recovery_confirmed)

    def test_probe_completion_timestamp_and_http_error(self):
        t=TelemetryCollector(); client=MagicMock()
        client.get.return_value.status_code=404
        before=time.time(); t._probe(client,'/','x')
        self.assertGreaterEqual(t._samples[0].timestamp,before)
        self.assertTrue(t._samples[0].is_error)

    def test_concurrent_probing(self):
        t=TelemetryCollector(rate_rps=30)
        def slow(*a,**k):
            time.sleep(.15)
            return MagicMock(status_code=200)
        with patch('telemetry.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.side_effect=slow
            t.start(); time.sleep(.3); t.stop()
        self.assertGreaterEqual(len(t.get_history()),5)

    def injector(self):
        i=ChaosInjector.__new__(ChaosInjector)
        i.client=MagicMock(); i.project='opentelemetry-demo'; i.active_injections={}
        c=MagicMock(); c.id='owned'; c.status='running'; c.attrs={'HostConfig':{'CpuQuota':40000,'CpuPeriod':50000}}
        i.client.containers.list.return_value=[c]; i.client.containers.get.return_value=c
        return i,c

    def test_restore_exact_cpu_and_no_global_cleanup(self):
        i,c=self.injector()
        self.assertTrue(i.inject('cart','cpu_throttle'))
        self.assertTrue(i.emergency_rollback_all())
        c.update.assert_called_with(cpu_quota=40000,cpu_period=50000)
        self.assertEqual(i.client.containers.list.call_count,1)
        self.assertFalse(i.active_injections)

    def test_failed_rollback_retains_ownership(self):
        i,c=self.injector(); i.inject('cart','cpu_throttle')
        c.update.side_effect=RuntimeError('offline')
        self.assertFalse(i.emergency_rollback_all())
        self.assertIn('cart',i.active_injections)

    def test_protected_or_unknown_target_rejected(self):
        i,c=self.injector()
        for name in ['frontend-proxy','CART','unknown','']:
            self.assertFalse(i.inject(name,'container_pause'))
        i.client.containers.list.assert_not_called()

    def test_existing_network_rules_preserved(self):
        i,c=self.injector(); i._tc=MagicMock(return_value=b'[{"kind":"fq_codel"}]')
        self.assertFalse(i.inject('cart','network_latency'))
        self.assertEqual(i._tc.call_count,1)
        self.assertFalse(i.active_injections)

    def test_score_additive_and_failed_injection_excluded(self):
        self.assertEqual(calculate_deterministic_report([result()]*3,{}).overall_resilience_score,46)
        r=result(failure_metrics={'error_rate':.2},mttr_sec=5)
        self.assertEqual(calculate_deterministic_report([r],{}).overall_resilience_score,66)
        report=calculate_deterministic_report([result(status='injection_failed')],{})
        self.assertIsNone(report.overall_resilience_score)
        self.assertEqual(report.vulnerabilities,[])

    def test_exception_always_rolls_back(self):
        i=MagicMock(); t=MagicMock()
        t.get_stats.side_effect=[RollingStats(time.time(),2,10,0,0,10,20,15,True),RuntimeError('metric failure')]
        with patch('safety_guard.time.sleep'), self.assertRaises(RuntimeError):
            SafetyGuard(i,t).execute_safeguarded_experiment('x','cart','container_pause')
        i.revert.assert_called_once_with('cart')

    def test_unhealthy_baseline_prevents_injection(self):
        i=MagicMock(); t=TelemetryCollector()
        r=SafetyGuard(i,t).execute_safeguarded_experiment('x','cart','container_pause')
        self.assertEqual(r.status,'not_run'); i.inject.assert_not_called()

    def test_campaign_lock_and_cleanup(self):
        i=MagicMock()
        with tempfile.TemporaryDirectory() as tmp, patch('execution.BASE_DIR',Path(tmp)):
            with campaign_scope(i):
                with self.assertRaises(RuntimeError):
                    with campaign_scope(MagicMock()): pass
            i.emergency_rollback_all.assert_called_once()

    def test_measured_export_has_no_fabricated_timeline(self):
        r=result(); report=calculate_deterministic_report([r],{})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'results.json'; save_dashboard_results([r],{},report,path)
            d=json.loads(path.read_text())
            self.assertEqual(d['provenance'],'measured')
            self.assertEqual(d['experiments'][0]['timeline'],[])

    def test_peak_metrics_are_maxima_not_final_window(self):
        i=MagicMock(); t=MagicMock()
        baseline=RollingStats(time.time(),2,10,0,0,10,20,15,True)
        early=RollingStats(time.time(),1,10,2,.2,500,1000,600,False)
        late=RollingStats(time.time(),1,10,0,0,900,2000,1000,False)
        t.get_stats.side_effect=[baseline,early,late,baseline]
        t.measure_mttr.return_value=1; t.last_recovery_confirmed=True
        with patch('safety_guard.time.sleep'):
            r=SafetyGuard(i,t).execute_safeguarded_experiment('x','cart','container_pause')
        self.assertEqual(r.failure_metrics['error_rate'],.2)
        self.assertEqual(r.failure_metrics['p95_latency_ms'],2000)
        self.assertIsNotNone(r.rollback_sec)

    def test_recovery_requires_new_samples(self):
        t=TelemetryCollector()
        for _ in range(10):
            t._samples.append(ProbeSample(time.time(),'',200,10,False))
        t.measure_mttr(timeout_sec=.02,poll_interval_sec=.005)
        self.assertFalse(t.last_recovery_confirmed)

    def test_failed_injection_is_not_a_pass(self):
        i=MagicMock(); i.inject.return_value=False
        t=MagicMock(); t.get_stats.return_value=RollingStats(time.time(),2,10,0,0,10,20,15,True)
        r=SafetyGuard(i,t).execute_safeguarded_experiment('x','cart','container_pause')
        self.assertEqual(r.status,'injection_failed')
        t.measure_mttr.assert_not_called()
        i.revert.assert_called_once_with('cart')

if __name__=='__main__': unittest.main()
