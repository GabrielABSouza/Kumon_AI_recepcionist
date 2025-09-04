#!/usr/bin/env python3
"""
Production Monitoring Commands
Grep/jq commands for real-time monitoring of Kumon Assistant V2
"""
import os
import sys
import subprocess
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class MonitoringResult:
    success: bool
    message: str
    data: Optional[Dict] = None
    count: Optional[int] = None

class ProductionMonitor:
    """Real-time production monitoring with grep/jq commands"""
    
    def __init__(self, log_file: str = "app.log"):
        self.log_file = log_file
        
    def _run_command(self, command: str) -> Tuple[str, int]:
        """Execute shell command and return output"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            return result.stdout.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "Command timed out", 1
        except Exception as e:
            return f"Command failed: {str(e)}", 1
    
    def check_outbox_handoff_integrity(self) -> MonitoringResult:
        """Check for outbox handoff violations (critical)"""
        command = f"""
        grep -E 'OUTBOX_TRACE\\|' {self.log_file} | awk -F'[=| ]' '
          /phase=planner/ {{ k=$6"|" $8; p[k]=$12 }}
          /phase=delivery/ {{ k=$6"|" $8; d=$12; if (k in p && p[k] > 0 && d == 0) print "MISMATCH conv=" $6 " idem=" $8 " planner=" p[k] " delivery=" d }}
        '
        """
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="✅ No outbox handoff violations detected",
                count=0
            )
        
        violations = output.strip().split('\n')
        return MonitoringResult(
            success=False,
            message=f"❌ Found {len(violations)} outbox handoff violations",
            data={"violations": violations},
            count=len(violations)
        )
    
    def check_state_id_consistency(self) -> MonitoringResult:
        """Check if state_id/outbox_id are consistent between Planner and Delivery"""
        command = f"""
        grep -E 'OUTBOX_TRACE\\|' {self.log_file} | awk -F'[=| ]' '
          /phase=planner/ {{ k=$6"|" $8; ps[k]=$10; po[k]=$12 }}
          /phase=delivery/ {{ k=$6"|" $8; if (ps[k]!="" && (ps[k]!=$10 || po[k]!=$12)) {{
              print "ID-DIFF conv=" $6 " idem=" $8 " state_id(planner)=" ps[k] " state_id(delivery)=" $10 " outbox_id(planner)=" po[k] " outbox_id(delivery)=" $12
          }} }}
        '
        """
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="✅ State ID consistency maintained",
                count=0
            )
        
        inconsistencies = output.strip().split('\n')
        return MonitoringResult(
            success=False,
            message=f"❌ Found {len(inconsistencies)} state ID inconsistencies",
            data={"inconsistencies": inconsistencies},
            count=len(inconsistencies)
        )
    
    def check_invalid_instance_patterns(self) -> MonitoringResult:
        """Check for invalid instance patterns (critical)"""
        command = f"grep -E 'INSTANCE_GUARD\\|level=CRITICAL\\|type=invalid_pattern' {self.log_file}"
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="✅ No invalid instance patterns detected",
                count=0
            )
        
        violations = output.strip().split('\n')
        return MonitoringResult(
            success=False,
            message=f"❌ Found {len(violations)} invalid instance patterns",
            data={"violations": violations},
            count=len(violations)
        )
    
    def check_delivery_success_rate(self, minimum_rate: float = 0.95) -> MonitoringResult:
        """Check delivery success rate"""
        success_command = f"grep -E 'DELIVERY_TRACE\\|action=result\\|status=success' {self.log_file} | wc -l"
        failed_command = f"grep -E 'DELIVERY_TRACE\\|action=result\\|status=failed' {self.log_file} | wc -l"
        
        success_output, _ = self._run_command(success_command)
        failed_output, _ = self._run_command(failed_command)
        
        try:
            success_count = int(success_output) if success_output else 0
            failed_count = int(failed_output) if failed_output else 0
            total_count = success_count + failed_count
            
            if total_count == 0:
                return MonitoringResult(
                    success=True,
                    message="ℹ️  No delivery attempts recorded yet",
                    count=0
                )
            
            success_rate = success_count / total_count
            
            if success_rate >= minimum_rate:
                return MonitoringResult(
                    success=True,
                    message=f"✅ Delivery success rate: {success_rate:.1%} ({success_count}/{total_count})",
                    data={"success_rate": success_rate, "success_count": success_count, "total_count": total_count},
                    count=total_count
                )
            else:
                return MonitoringResult(
                    success=False,
                    message=f"❌ Delivery success rate below threshold: {success_rate:.1%} ({success_count}/{total_count})",
                    data={"success_rate": success_rate, "success_count": success_count, "total_count": total_count},
                    count=total_count
                )
        except ValueError:
            return MonitoringResult(
                success=False,
                message="❌ Failed to parse delivery statistics",
                count=0
            )
    
    def get_recent_outbox_traces(self, limit: int = 20) -> MonitoringResult:
        """Get recent outbox traces for debugging"""
        command = f"grep -E 'OUTBOX_TRACE\\|' {self.log_file} | tail -{limit}"
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="ℹ️  No outbox traces found",
                count=0
            )
        
        traces = output.strip().split('\n')
        return MonitoringResult(
            success=True,
            message=f"📊 Retrieved {len(traces)} recent outbox traces",
            data={"traces": traces},
            count=len(traces)
        )
    
    def get_instance_resolution_traces(self, limit: int = 10) -> MonitoringResult:
        """Get recent instance resolution traces"""
        command = f"grep -E 'INSTANCE_TRACE\\|' {self.log_file} | tail -{limit}"
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="ℹ️  No instance resolution traces found",
                count=0
            )
        
        traces = output.strip().split('\n')
        return MonitoringResult(
            success=True,
            message=f"📊 Retrieved {len(traces)} recent instance traces",
            data={"traces": traces},
            count=len(traces)
        )
    
    def get_delivery_failures(self, limit: int = 10) -> MonitoringResult:
        """Get recent delivery failures for analysis"""
        command = f"grep -E 'DELIVERY_TRACE\\|action=result\\|status=failed' {self.log_file} | tail -{limit}"
        
        output, returncode = self._run_command(command)
        
        if not output:
            return MonitoringResult(
                success=True,
                message="✅ No recent delivery failures",
                count=0
            )
        
        failures = output.strip().split('\n')
        return MonitoringResult(
            success=False,
            message=f"⚠️  Found {len(failures)} recent delivery failures",
            data={"failures": failures},
            count=len(failures)
        )
    
    def run_comprehensive_health_check(self) -> Dict[str, MonitoringResult]:
        """Run all critical health checks"""
        checks = {
            "outbox_handoff": self.check_outbox_handoff_integrity(),
            "state_consistency": self.check_state_id_consistency(),
            "invalid_instances": self.check_invalid_instance_patterns(),
            "delivery_rate": self.check_delivery_success_rate(),
            "recent_failures": self.get_delivery_failures()
        }
        
        return checks
    
    def generate_monitoring_report(self) -> str:
        """Generate comprehensive monitoring report"""
        print("🔍 Running comprehensive health check...")
        
        checks = self.run_comprehensive_health_check()
        report_lines = [
            f"# Kumon Assistant V2 - Health Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Log file: {self.log_file}",
            "",
            "## Critical Checks",
            ""
        ]
        
        critical_issues = 0
        
        for check_name, result in checks.items():
            status_icon = "✅" if result.success else "❌"
            report_lines.append(f"**{check_name.replace('_', ' ').title()}**: {status_icon} {result.message}")
            
            if not result.success:
                critical_issues += 1
                if result.data:
                    report_lines.append("```")
                    if "violations" in result.data:
                        for violation in result.data["violations"][:5]:  # Limit to first 5
                            report_lines.append(violation)
                    elif "inconsistencies" in result.data:
                        for inconsistency in result.data["inconsistencies"][:5]:
                            report_lines.append(inconsistency)
                    elif "failures" in result.data:
                        for failure in result.data["failures"][:5]:
                            report_lines.append(failure)
                    report_lines.append("```")
            
            report_lines.append("")
        
        # Summary
        report_lines.extend([
            "## Summary",
            "",
            f"**Overall Status**: {'🚨 CRITICAL ISSUES' if critical_issues > 0 else '🎯 HEALTHY'}",
            f"**Critical Issues**: {critical_issues}",
            "",
            "## Quick Commands",
            "",
            "```bash",
            "# Monitor outbox handoff in real-time",
            f"tail -f {self.log_file} | grep -E 'OUTBOX_TRACE|OUTBOX_GUARD'",
            "",
            "# Monitor instance resolution", 
            f"tail -f {self.log_file} | grep -E 'INSTANCE_TRACE|INSTANCE_GUARD'",
            "",
            "# Monitor delivery results",
            f"tail -f {self.log_file} | grep -E 'DELIVERY_TRACE.*action=result'",
            "```"
        ])
        
        return "\n".join(report_lines)

def main():
    """Main CLI interface for production monitoring"""
    if len(sys.argv) < 2:
        print("Usage: python monitoring_commands.py <command> [log_file]")
        print("Commands:")
        print("  handoff      - Check outbox handoff integrity")
        print("  consistency  - Check state ID consistency") 
        print("  instances    - Check for invalid instance patterns")
        print("  delivery     - Check delivery success rate")
        print("  failures     - Show recent delivery failures")
        print("  traces       - Show recent outbox traces")
        print("  health       - Run comprehensive health check")
        print("  report       - Generate monitoring report")
        sys.exit(1)
    
    command = sys.argv[1]
    log_file = sys.argv[2] if len(sys.argv) > 2 else "app.log"
    
    monitor = ProductionMonitor(log_file)
    
    if command == "handoff":
        result = monitor.check_outbox_handoff_integrity()
        print(result.message)
        if result.data and "violations" in result.data:
            for violation in result.data["violations"]:
                print(f"  {violation}")
    
    elif command == "consistency":
        result = monitor.check_state_id_consistency()
        print(result.message)
        if result.data and "inconsistencies" in result.data:
            for inconsistency in result.data["inconsistencies"]:
                print(f"  {inconsistency}")
    
    elif command == "instances":
        result = monitor.check_invalid_instance_patterns()
        print(result.message)
        if result.data and "violations" in result.data:
            for violation in result.data["violations"]:
                print(f"  {violation}")
    
    elif command == "delivery":
        result = monitor.check_delivery_success_rate()
        print(result.message)
    
    elif command == "failures":
        result = monitor.get_delivery_failures()
        print(result.message)
        if result.data and "failures" in result.data:
            for failure in result.data["failures"]:
                print(f"  {failure}")
    
    elif command == "traces":
        result = monitor.get_recent_outbox_traces()
        print(result.message)
        if result.data and "traces" in result.data:
            for trace in result.data["traces"]:
                print(f"  {trace}")
    
    elif command == "health":
        checks = monitor.run_comprehensive_health_check()
        print("\n🔍 Comprehensive Health Check Results:\n")
        
        critical_issues = 0
        for check_name, result in checks.items():
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {check_name.replace('_', ' ').title()}: {result.message}")
            
            if not result.success:
                critical_issues += 1
        
        print(f"\n{'🚨 CRITICAL ISSUES DETECTED' if critical_issues > 0 else '🎯 SYSTEM HEALTHY'}")
        
        if critical_issues > 0:
            sys.exit(1)
    
    elif command == "report":
        report = monitor.generate_monitoring_report()
        
        # Save report
        report_file = f"monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"📊 Monitoring report generated: {report_file}")
        print("\nReport summary:")
        print(report.split("## Summary")[1].split("## Quick Commands")[0])
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()