#!/usr/bin/env python3
"""
Production Flags Configuration and Validation
Manages critical production flags for Kumon Assistant V2 go-live
"""
import os
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class FlagStatus(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    KILLSWITCH = "killswitch"

@dataclass
class ProductionFlag:
    name: str
    status: FlagStatus
    default_value: str
    description: str
    validation_func: Optional[callable] = None

class ProductionFlagsManager:
    """Manages production flags for safe deployment"""
    
    def __init__(self):
        self.flags = self._define_flags()
    
    def _define_flags(self) -> Dict[str, ProductionFlag]:
        """Define all production flags with validation"""
        return {
            # Critical enforcement flags
            "OUTBOX_V2_ENFORCED": ProductionFlag(
                name="OUTBOX_V2_ENFORCED",
                status=FlagStatus.REQUIRED,
                default_value="true",
                description="Enforce V2 outbox handoff integrity",
                validation_func=self._validate_boolean
            ),
            "TEMPLATE_VARIABLE_POLICY_V2": ProductionFlag(
                name="TEMPLATE_VARIABLE_POLICY_V2", 
                status=FlagStatus.REQUIRED,
                default_value="true",
                description="Enforce V2 template variable stripping",
                validation_func=self._validate_boolean
            ),
            "STRICT_ENUM_STAGESTEP": ProductionFlag(
                name="STRICT_ENUM_STAGESTEP",
                status=FlagStatus.REQUIRED, 
                default_value="true",
                description="Enforce strict stage/step enum validation",
                validation_func=self._validate_boolean
            ),
            
            # Kill-switch flags
            "DELIVERY_DISABLE": ProductionFlag(
                name="DELIVERY_DISABLE",
                status=FlagStatus.KILLSWITCH,
                default_value="false",
                description="Kill-switch to disable message delivery",
                validation_func=self._validate_boolean
            ),
            
            # Optional flags
            "ROUTER_V2_SHADOW": ProductionFlag(
                name="ROUTER_V2_SHADOW",
                status=FlagStatus.OPTIONAL,
                default_value="false", 
                description="Enable shadow mode for V2 router comparison",
                validation_func=self._validate_boolean
            ),
            "CHECKPOINTER": ProductionFlag(
                name="CHECKPOINTER",
                status=FlagStatus.REQUIRED,
                default_value="postgres",
                description="Checkpointer backend (postgres|memory)",
                validation_func=self._validate_checkpointer
            ),
            "DATABASE_URL": ProductionFlag(
                name="DATABASE_URL",
                status=FlagStatus.REQUIRED,
                default_value="",
                description="PostgreSQL connection URL",
                validation_func=self._validate_database_url
            )
        }
    
    def _validate_boolean(self, value: str) -> Tuple[bool, str]:
        """Validate boolean flag values"""
        if value.lower() in ("true", "false"):
            return True, f"Valid boolean: {value}"
        return False, f"Invalid boolean: {value}. Must be 'true' or 'false'"
    
    def _validate_checkpointer(self, value: str) -> Tuple[bool, str]:
        """Validate checkpointer flag"""
        valid_values = ("postgres", "memory")
        if value.lower() in valid_values:
            return True, f"Valid checkpointer: {value}"
        return False, f"Invalid checkpointer: {value}. Must be one of {valid_values}"
    
    def _validate_database_url(self, value: str) -> Tuple[bool, str]:
        """Validate database URL"""
        if not value:
            return False, "DATABASE_URL is required but not set"
        
        if value.startswith("postgresql://") or value.startswith("postgres://"):
            return True, "Valid PostgreSQL URL format"
        
        return False, f"Invalid DATABASE_URL format: {value}. Must start with postgresql:// or postgres://"
    
    def get_current_values(self) -> Dict[str, str]:
        """Get current environment values for all flags"""
        return {
            name: os.getenv(name, flag.default_value)
            for name, flag in self.flags.items()
        }
    
    def validate_all_flags(self) -> Tuple[bool, List[str]]:
        """Validate all production flags"""
        errors = []
        current_values = self.get_current_values()
        
        for name, flag in self.flags.items():
            current_value = current_values[name]
            
            # Check required flags
            if flag.status == FlagStatus.REQUIRED and not current_value:
                errors.append(f"❌ REQUIRED flag {name} is not set")
                continue
            
            # Validate with custom function
            if flag.validation_func and current_value:
                is_valid, message = flag.validation_func(current_value)
                if not is_valid:
                    errors.append(f"❌ {name}: {message}")
                else:
                    print(f"✅ {name}: {message}")
        
        return len(errors) == 0, errors
    
    def generate_export_script(self) -> str:
        """Generate shell script to export production flags"""
        script_lines = [
            "#!/bin/bash",
            "# Production Flags for Kumon Assistant V2",
            "# Generated by production_flags.py",
            "",
            "echo '🚀 Setting production flags...'",
            ""
        ]
        
        for name, flag in self.flags.items():
            if flag.status == FlagStatus.REQUIRED:
                script_lines.append(f"# {flag.description}")
                script_lines.append(f"export {name}={flag.default_value}")
                script_lines.append(f"echo '✅ {name}=${name}'")
                script_lines.append("")
        
        # Kill-switch flags separate section
        script_lines.extend([
            "# Kill-switch flags (modify as needed)",
            "export DELIVERY_DISABLE=false  # Set to 'true' for emergency rollback",
            "echo '⚠️  DELIVERY_DISABLE=$DELIVERY_DISABLE'",
            "",
            "# Optional flags",
            "export ROUTER_V2_SHADOW=false  # Set to 'true' for comparison mode", 
            "echo 'ℹ️  ROUTER_V2_SHADOW=$ROUTER_V2_SHADOW'",
            "",
            "echo '🎯 All production flags set successfully!'"
        ])
        
        return "\n".join(script_lines)
    
    def check_production_readiness(self) -> Tuple[bool, List[str]]:
        """Check if system is ready for production deployment"""
        issues = []
        
        # Flag validation
        flags_valid, flag_errors = self.validate_all_flags()
        if not flags_valid:
            issues.extend(flag_errors)
        
        # Critical production checks
        current_values = self.get_current_values()
        
        # Check kill-switch is disabled
        if current_values.get("DELIVERY_DISABLE", "").lower() == "true":
            issues.append("❌ DELIVERY_DISABLE is set to 'true' - disable kill-switch for normal operation")
        
        # Check PostgreSQL checkpointer in production
        if current_values.get("CHECKPOINTER", "").lower() != "postgres":
            issues.append("⚠️  CHECKPOINTER should be 'postgres' in production (not memory)")
        
        # Check DATABASE_URL for Railway
        database_url = current_values.get("DATABASE_URL", "")
        if database_url and "yamabiko.proxy.rlwy.net" not in database_url:
            issues.append("⚠️  DATABASE_URL does not point to Railway PostgreSQL")
        
        return len(issues) == 0, issues

def main():
    """Main CLI interface"""
    manager = ProductionFlagsManager()
    
    if len(sys.argv) < 2:
        print("Usage: python production_flags.py <command>")
        print("Commands:")
        print("  validate     - Validate current flag configuration")
        print("  generate     - Generate shell script for flag export")
        print("  readiness    - Check production readiness")
        print("  status       - Show current flag status")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "validate":
        print("🔍 Validating production flags...")
        is_valid, errors = manager.validate_all_flags()
        
        if is_valid:
            print("\n🎉 All flags are valid!")
        else:
            print(f"\n❌ Found {len(errors)} validation errors:")
            for error in errors:
                print(f"  {error}")
            sys.exit(1)
    
    elif command == "generate":
        script = manager.generate_export_script()
        script_path = "set_production_flags.sh"
        
        with open(script_path, "w") as f:
            f.write(script)
        
        os.chmod(script_path, 0o755)
        print(f"✅ Generated executable script: {script_path}")
        print("Run with: ./set_production_flags.sh")
    
    elif command == "readiness":
        print("🚀 Checking production readiness...")
        is_ready, issues = manager.check_production_readiness()
        
        if is_ready:
            print("\n🎯 System is READY for production deployment!")
        else:
            print(f"\n⚠️  Found {len(issues)} readiness issues:")
            for issue in issues:
                print(f"  {issue}")
            print("\n🔧 Resolve these issues before deployment.")
            sys.exit(1)
    
    elif command == "status":
        print("📊 Current production flag status:")
        current_values = manager.get_current_values()
        
        for name, flag in manager.flags.items():
            current_value = current_values[name]
            status_icon = "✅" if current_value == flag.default_value else "⚠️"
            
            print(f"  {status_icon} {name}={current_value} ({flag.status.value})")
            print(f"     {flag.description}")
            print()
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()