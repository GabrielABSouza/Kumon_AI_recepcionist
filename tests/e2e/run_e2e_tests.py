#!/usr/bin/env python3
"""
Script de Execução dos Testes E2E WhatsApp

Script principal para executar todos os cenários E2E com observabilidade completa.

Usage:
    python tests/e2e/run_e2e_tests.py staging
    python tests/e2e/run_e2e_tests.py production --detailed-logs
    python tests/e2e/run_e2e_tests.py staging --scenario 1 --verbose
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tests.e2e.test_scenarios import run_all_e2e_scenarios
from tests.e2e.whatsapp_e2e_framework import print_test_report, E2ETestResult


class E2EObservabilityDashboard:
    """Dashboard de observabilidade para testes E2E"""
    
    def __init__(self, results: List[E2ETestResult]):
        self.results = results
        self.timestamp = datetime.now()
    
    def generate_detailed_report(self, output_file: str = None):
        """Gera relatório detalhado dos testes"""
        report = {
            "timestamp": self.timestamp.isoformat(),
            "summary": self._generate_summary(),
            "scenarios": self._generate_scenario_details(),
            "observability_metrics": self._generate_observability_metrics(),
            "critical_validations": self._generate_critical_validations(),
            "recommendations": self._generate_recommendations()
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"📄 Relatório detalhado salvo em: {output_file}")
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Gera resumo executivo"""
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        total_duration = sum(r.duration_ms for r in self.results)
        
        return {
            "total_scenarios": len(self.results),
            "passed": passed,
            "failed": failed, 
            "success_rate": f"{(passed/len(self.results)*100):.1f}%",
            "total_duration_ms": total_duration,
            "average_duration_ms": int(total_duration / len(self.results)) if self.results else 0
        }
    
    def _generate_scenario_details(self) -> List[Dict[str, Any]]:
        """Gera detalhes de cada cenário"""
        scenarios = []
        
        for result in self.results:
            scenario = {
                "name": result.test_name,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "assertions_passed": result.assertions_passed,
                "assertions_failed": result.assertions_failed,
                "key_metrics": {
                    "outbox_after_planning": result.metrics.get('outbox_after_planning', 0),
                    "messages_delivered": result.metrics.get('messages_delivered', 0),
                    "safety_blocks": result.metrics.get('safety_blocks', 0),
                    "emergency_fallbacks": result.metrics.get('emergency_fallbacks', 0),
                    "idempotency_hits": result.metrics.get('idempotency_hits', 0)
                },
                "critical_logs": self._extract_critical_logs(result.logs_captured)
            }
            
            if result.error_message:
                scenario["error"] = result.error_message
            
            scenarios.append(scenario)
        
        return scenarios
    
    def _extract_critical_logs(self, logs: List[Dict]) -> List[str]:
        """Extrai logs críticos para análise"""
        critical_patterns = [
            "StageResolver.*stage=",
            "planner_outbox_count_after:",
            "delivery_outbox_count_before:",
            "Message delivered successfully",
            "should_end.*True",
            "BLOCKED configuration template",
            "delivery_emergency_fallback_added",
            "idempotency_dedup_hits"
        ]
        
        critical_logs = []
        for log in logs:
            message = log.get("message", "")
            for pattern in critical_patterns:
                if any(p in message for p in pattern.split(".*")):
                    critical_logs.append(f"[{log.get('level', 'INFO')}] {message}")
                    break
        
        return critical_logs[:10]  # Top 10 most relevant
    
    def _generate_observability_metrics(self) -> Dict[str, Any]:
        """Gera métricas de observabilidade consolidadas"""
        total_outbox_planning = sum(r.metrics.get('outbox_after_planning', 0) for r in self.results)
        total_messages_delivered = sum(r.metrics.get('messages_delivered', 0) for r in self.results)
        total_safety_blocks = sum(r.metrics.get('safety_blocks', 0) for r in self.results)
        total_emergency_fallbacks = sum(r.metrics.get('emergency_fallbacks', 0) for r in self.results)
        total_idempotency_hits = sum(r.metrics.get('idempotency_hits', 0) for r in self.results)
        
        return {
            "pipeline_health": {
                "total_outbox_after_planning": total_outbox_planning,
                "total_messages_delivered": total_messages_delivered,
                "delivery_success_rate": f"{(total_messages_delivered/max(total_outbox_planning,1)*100):.1f}%"
            },
            "safety_system": {
                "total_safety_blocks": total_safety_blocks,
                "safety_effectiveness": "Active" if total_safety_blocks > 0 else "Not Triggered"
            },
            "reliability": {
                "total_emergency_fallbacks": total_emergency_fallbacks,
                "emergency_fallback_rate": f"{(total_emergency_fallbacks/len(self.results)*100):.1f}%"
            },
            "performance": {
                "total_idempotency_hits": total_idempotency_hits,
                "deduplication_active": total_idempotency_hits > 0
            }
        }
    
    def _generate_critical_validations(self) -> Dict[str, bool]:
        """Valida aspectos críticos do sistema"""
        validations = {}
        
        # 1. Outbox nunca vazio após planning (exceto em testes específicos)
        outbox_healthy = all(
            r.metrics.get('outbox_after_planning', 0) > 0 
            for r in self.results 
            if 'outbox vazio' not in r.test_name.lower()
        )
        validations["outbox_always_populated"] = outbox_healthy
        
        # 2. Safety system funcionando
        has_safety_scenarios = any(
            'segurança' in r.test_name.lower() or 'template' in r.test_name.lower()
            for r in self.results
        )
        safety_working = any(r.metrics.get('safety_blocks', 0) > 0 for r in self.results) if has_safety_scenarios else True
        validations["safety_system_active"] = safety_working
        
        # 3. Delivery funcionando
        delivery_working = any(r.metrics.get('messages_delivered', 0) > 0 for r in self.results)
        validations["delivery_system_working"] = delivery_working
        
        # 4. Sem async warnings críticos
        no_async_warnings = all(
            not any("coroutine" in log.get("message", "") and "never awaited" in log.get("message", "") 
                   for log in r.logs_captured)
            for r in self.results
        )
        validations["no_async_warnings"] = no_async_warnings
        
        # 5. Emergency fallbacks controlados
        emergency_controlled = sum(r.metrics.get('emergency_fallbacks', 0) for r in self.results) <= len(self.results)
        validations["emergency_fallbacks_controlled"] = emergency_controlled
        
        return validations
    
    def _generate_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos resultados"""
        recommendations = []
        
        failed_tests = [r for r in self.results if not r.success]
        if failed_tests:
            recommendations.append(f"🚨 {len(failed_tests)} cenários falharam - investigar logs detalhados")
        
        # Verificar se safety está funcionando
        safety_blocks = sum(r.metrics.get('safety_blocks', 0) for r in self.results)
        if safety_blocks == 0:
            recommendations.append("⚠️ Sistema de safety não foi testado - considerar adicionar mais cenários perigosos")
        
        # Verificar emergency fallbacks
        emergency_fallbacks = sum(r.metrics.get('emergency_fallbacks', 0) for r in self.results)
        if emergency_fallbacks > len(self.results) * 0.5:
            recommendations.append("⚠️ Muitos emergency fallbacks - verificar qualidade dos templates")
        
        # Verificar performance
        slow_tests = [r for r in self.results if r.duration_ms > 10000]  # > 10s
        if slow_tests:
            recommendations.append(f"⚠️ {len(slow_tests)} testes lentos (>10s) - otimizar performance")
        
        if not recommendations:
            recommendations.append("✅ Todos os indicadores estão saudáveis")
        
        return recommendations
    
    def print_observability_dashboard(self):
        """Imprime dashboard de observabilidade completo"""
        print("\n" + "="*90)
        print("📊 E2E WHATSAPP OBSERVABILITY DASHBOARD")
        print("="*90)
        
        # Summary
        summary = self._generate_summary()
        print(f"📈 RESUMO EXECUTIVO:")
        print(f"   Cenários: {summary['total_scenarios']} total, {summary['passed']} ✅, {summary['failed']} ❌")
        print(f"   Taxa Sucesso: {summary['success_rate']}")
        print(f"   Tempo Total: {summary['total_duration_ms']}ms ({summary['total_duration_ms']/1000:.1f}s)")
        print(f"   Tempo Médio: {summary['average_duration_ms']}ms")
        
        # Pipeline Health
        obs_metrics = self._generate_observability_metrics()
        pipeline = obs_metrics['pipeline_health']
        print(f"\n🔄 SAÚDE DO PIPELINE:")
        print(f"   Mensagens Planejadas: {pipeline['total_outbox_after_planning']}")
        print(f"   Mensagens Entregues: {pipeline['total_messages_delivered']}")
        print(f"   Taxa Entrega: {pipeline['delivery_success_rate']}")
        
        # Safety System
        safety = obs_metrics['safety_system']
        print(f"\n🛡️ SISTEMA DE SEGURANÇA:")
        print(f"   Bloqueios Safety: {safety['total_safety_blocks']}")
        print(f"   Status: {safety['safety_effectiveness']}")
        
        # Reliability
        reliability = obs_metrics['reliability']
        print(f"\n🚨 CONFIABILIDADE:")
        print(f"   Emergency Fallbacks: {reliability['total_emergency_fallbacks']}")
        print(f"   Taxa Emergência: {reliability['emergency_fallback_rate']}")
        
        # Critical Validations
        validations = self._generate_critical_validations()
        print(f"\n✅ VALIDAÇÕES CRÍTICAS:")
        for validation, status in validations.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {validation.replace('_', ' ').title()}")
        
        # Recommendations
        recommendations = self._generate_recommendations()
        print(f"\n💡 RECOMENDAÇÕES:")
        for rec in recommendations:
            print(f"   {rec}")
        
        print("\n" + "="*90)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="E2E WhatsApp Tests Runner")
    parser.add_argument("environment", choices=["staging", "production"], 
                       help="Target environment")
    parser.add_argument("--scenario", type=int, choices=[1,2,3,4,5], 
                       help="Run specific scenario only")
    parser.add_argument("--detailed-logs", action="store_true",
                       help="Generate detailed log report")
    parser.add_argument("--output", type=str,
                       help="Output file for detailed report")
    parser.add_argument("--verbose", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting E2E WhatsApp Tests - Environment: {args.environment}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    if args.scenario:
        print(f"🎯 Running specific scenario: {args.scenario}")
        # TODO: Implement single scenario execution
        print("❌ Single scenario execution not implemented yet")
        return
    
    # Run all scenarios
    try:
        results = await run_all_e2e_scenarios(args.environment)
        
        # Print basic report
        print_test_report(results)
        
        # Generate observability dashboard
        dashboard = E2EObservabilityDashboard(results)
        dashboard.print_observability_dashboard()
        
        # Generate detailed report if requested
        if args.detailed_logs or args.output:
            output_file = args.output or f"e2e_report_{args.environment}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            dashboard.generate_detailed_report(output_file)
        
        # Exit with proper code
        failed_count = sum(1 for r in results if not r.success)
        exit_code = 0 if failed_count == 0 else 1
        
        print(f"\n🏁 Tests completed with exit code: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"❌ E2E Tests failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())