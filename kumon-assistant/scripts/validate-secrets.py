#!/usr/bin/env python3
"""
Kumon Assistant - Secrets Validation Script
Validates all required secrets are configured before startup
"""

import os
import sys
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SecretCheck:
    name: str
    required: bool
    env_var: str
    description: str
    validation_func: callable = None

def validate_openai_key(value: str) -> Tuple[bool, str]:
    """Validate OpenAI API key format"""
    if not value.startswith('sk-'):
        return False, "OpenAI API key must start with 'sk-'"
    if len(value) < 20:
        return False, "OpenAI API key too short"
    return True, "Valid OpenAI API key format"

def validate_jwt_secret(value: str) -> Tuple[bool, str]:
    """Validate JWT secret strength"""
    if len(value) < 32:
        return False, "JWT secret must be at least 32 characters"
    if not re.match(r'^[a-fA-F0-9]+$', value):
        return False, "JWT secret should be hexadecimal"
    return True, "Strong JWT secret"

def validate_phone_number(value: str) -> Tuple[bool, str]:
    """Validate business phone number"""
    # Remove non-digits
    digits = ''.join(filter(str.isdigit, value))
    if len(digits) < 10:
        return False, "Phone number too short"
    if len(digits) > 15:
        return False, "Phone number too long"
    return True, f"Valid phone number ({len(digits)} digits)"

def validate_email(value: str) -> Tuple[bool, str]:
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, value):
        return False, "Invalid email format"
    return True, "Valid email format"

def validate_url(value: str) -> Tuple[bool, str]:
    """Validate URL format"""
    if not value.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    if 'localhost' in value or '127.0.0.1' in value:
        return False, "Production URL should not use localhost"
    return True, "Valid production URL"

def validate_environment(value: str) -> Tuple[bool, str]:
    """Validate environment setting"""
    valid_envs = ['development', 'production', 'testing']
    if value not in valid_envs:
        return False, f"Environment must be one of: {', '.join(valid_envs)}"
    return True, f"Valid environment: {value}"

def validate_boolean(value: str) -> Tuple[bool, str]:
    """Validate boolean setting"""
    valid_bools = ['true', 'false', 'True', 'False', '1', '0']
    if value not in valid_bools:
        return False, f"Boolean must be one of: {', '.join(valid_bools)}"
    return True, f"Valid boolean: {value}"

# Define all secret requirements
SECRET_REQUIREMENTS = [
    # Core Authentication
    SecretCheck("JWT Secret Key", True, "JWT_SECRET_KEY", "JWT token signing key", validate_jwt_secret),
    SecretCheck("App Secret Key", True, "SECRET_KEY", "Application secret key", validate_jwt_secret),
    
    # LLM Providers
    SecretCheck("OpenAI API Key", True, "OPENAI_API_KEY", "OpenAI API access key", validate_openai_key),
    SecretCheck("Anthropic API Key", False, "ANTHROPIC_API_KEY", "Anthropic API access key (fallback)"),
    
    # Evolution API
    SecretCheck("Evolution API Key", True, "EVOLUTION_API_KEY", "Evolution API access key"),
    SecretCheck("Evolution API URL", True, "EVOLUTION_API_URL", "Evolution API base URL", validate_url),
    
    # Business Configuration
    SecretCheck("Business Phone", True, "BUSINESS_PHONE", "Business contact number", validate_phone_number),
    SecretCheck("Business Email", True, "BUSINESS_EMAIL", "Business contact email", validate_email),
    SecretCheck("Business Name", True, "BUSINESS_NAME", "Business name"),
    
    # Environment Configuration
    SecretCheck("Environment", True, "ENVIRONMENT", "Deployment environment", validate_environment),
    SecretCheck("Debug Mode", True, "DEBUG", "Debug mode setting", validate_boolean),
    SecretCheck("HTTPS Required", True, "REQUIRE_HTTPS", "HTTPS enforcement", validate_boolean),
    SecretCheck("API Key Validation", True, "VALIDATE_API_KEYS", "API key validation", validate_boolean),
    
    # Optional Services
    SecretCheck("LangSmith API Key", False, "LANGSMITH_API_KEY", "LangSmith observability key"),
    SecretCheck("LangSmith Project", False, "LANGSMITH_PROJECT", "LangSmith project name"),
    SecretCheck("LangChain Tracing", False, "LANGCHAIN_TRACING_V2", "LangChain tracing enabled"),
]

def check_secret(secret: SecretCheck) -> Dict[str, Any]:
    """Check individual secret configuration"""
    value = os.getenv(secret.env_var, "").strip()
    
    result = {
        "name": secret.name,
        "env_var": secret.env_var,
        "required": secret.required,
        "configured": bool(value),
        "valid": True,
        "error": None,
        "message": None
    }
    
    # Check if required secret is missing
    if secret.required and not value:
        result["valid"] = False
        result["error"] = f"Required secret {secret.env_var} is not configured"
        return result
    
    # Validate secret if configured and validation function exists
    if value and secret.validation_func:
        try:
            is_valid, message = secret.validation_func(value)
            result["valid"] = is_valid
            result["message"] = message
            if not is_valid:
                result["error"] = f"Validation failed for {secret.env_var}: {message}"
        except Exception as e:
            result["valid"] = False
            result["error"] = f"Validation error for {secret.env_var}: {str(e)}"
    elif value:
        result["message"] = "Configured (no validation)"
    
    return result

def print_colored(text: str, color: str = ""):
    """Print colored text"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m", 
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "purple": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "reset": "\033[0m"
    }
    if color in colors:
        print(f"{colors[color]}{text}{colors['reset']}")
    else:
        print(text)

def main():
    """Main validation function"""
    print_colored("🔐 Kumon Assistant - Secrets Validation", "blue")
    print_colored("=" * 50, "blue")
    print()
    
    results = []
    errors = []
    warnings = []
    
    for secret in SECRET_REQUIREMENTS:
        result = check_secret(secret)
        results.append(result)
        
        # Determine status icon and color
        if result["valid"] and result["configured"]:
            status = "✅"
            color = "green"
        elif result["required"] and not result["configured"]:
            status = "❌"
            color = "red"
        elif not result["valid"]:
            status = "❌"
            color = "red"
        elif not result["configured"]:
            status = "⚪"
            color = "white"
        else:
            status = "⚠️"
            color = "yellow"
        
        # Format output
        optional = " (optional)" if not secret.required else ""
        message = f" - {result['message']}" if result.get('message') else ""
        
        if color == "red":
            print_colored(f"{status} {result['name']}{optional}{message}", "red")
        elif color == "green":
            print_colored(f"{status} {result['name']}{optional}{message}", "green")
        elif color == "yellow":
            print_colored(f"{status} {result['name']}{optional}{message}", "yellow")
        else:
            print(f"{status} {result['name']}{optional}{message}")
        
        # Collect errors and warnings
        if result["error"]:
            if result["required"]:
                errors.append(result["error"])
            else:
                warnings.append(result["error"])
    
    print()
    print_colored("=" * 50, "blue")
    
    # Summary statistics
    configured_count = sum(1 for r in results if r["configured"])
    required_count = sum(1 for r in results if r["required"])
    required_configured = sum(1 for r in results if r["required"] and r["configured"] and r["valid"])
    total_count = len(results)
    
    if errors:
        print_colored(f"❌ {len(errors)} CRITICAL ERRORS FOUND:", "red")
        for error in errors:
            print_colored(f"   • {error}", "red")
        print()
        print_colored("🚨 APPLICATION CANNOT START WITH THESE ERRORS!", "red")
        print_colored("📋 Run './scripts/setup-railway-secrets.sh' to configure secrets", "yellow")
        print()
        sys.exit(1)
    
    if warnings:
        print_colored(f"⚠️  {len(warnings)} WARNINGS:", "yellow")
        for warning in warnings:
            print_colored(f"   • {warning}", "yellow")
        print()
    
    # Success summary
    print_colored("✅ Secrets validation passed!", "green")
    print()
    print_colored("📊 Configuration Summary:", "blue")
    print(f"   • Total secrets: {total_count}")
    print(f"   • Required secrets: {required_count}")
    print(f"   • Required configured: {required_configured}/{required_count}")
    print(f"   • Optional configured: {configured_count - required_configured}")
    print(f"   • Configuration completeness: {(configured_count/total_count)*100:.1f}%")
    
    if required_configured == required_count:
        print()
        print_colored("🚀 Application ready to start!", "green")
        print_colored(f"⏰ Validated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "cyan")
    else:
        print()
        print_colored("⚠️  Some required secrets missing - check configuration", "yellow")
        sys.exit(1)

if __name__ == "__main__":
    main()