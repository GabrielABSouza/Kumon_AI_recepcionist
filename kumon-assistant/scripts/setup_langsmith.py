#!/usr/bin/env python3
"""
LangSmith Setup and Validation Script for Kumon Assistant

This script helps configure LangSmith Hub integration:
1. Validates API key and connectivity
2. Creates/validates project setup
3. Uploads local templates to LangSmith Hub
4. Tests prompt fetching
5. Provides configuration guidance

Usage:
    python scripts/setup_langsmith.py --validate
    python scripts/setup_langsmith.py --upload-templates
    python scripts/setup_langsmith.py --test-prompt kumon:greeting:initial
"""

import asyncio
import os
import sys
from pathlib import Path
import argparse
from typing import Dict, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logger import app_logger


class LangSmithSetup:
    """LangSmith configuration and validation helper"""
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize LangSmith client"""
        try:
            from langsmith import Client as LangSmithClient
            
            api_key = os.getenv("LANGSMITH_API_KEY") or settings.LANGSMITH_API_KEY
            if not api_key:
                print("❌ LANGSMITH_API_KEY not configured")
                print("📋 Setup steps:")
                print("   1. Get API key from https://smith.langchain.com/")
                print("   2. Set environment variable: export LANGSMITH_API_KEY='your-key'")
                print("   3. Or add to .env file: LANGSMITH_API_KEY=your-key")
                return
            
            self.client = LangSmithClient(
                api_url=settings.LANGSMITH_ENDPOINT,
                api_key=api_key
            )
            print("✅ LangSmith client initialized")
            
        except ImportError:
            print("❌ langsmith package not installed")
            print("📋 Install with: pip install langsmith")
        except Exception as e:
            print(f"❌ Failed to initialize LangSmith client: {e}")
    
    async def validate_connection(self) -> bool:
        """Validate LangSmith API connectivity"""
        if not self.client:
            return False
        
        try:
            # Try to list projects to validate connection
            projects = list(self.client.list_projects())
            print(f"✅ LangSmith connection validated")
            print(f"📊 Found {len(projects)} projects")
            
            # Check if our project exists
            project_name = settings.LANGSMITH_PROJECT
            project_exists = any(p.name == project_name for p in projects)
            
            if project_exists:
                print(f"✅ Project '{project_name}' exists")
            else:
                print(f"⚠️ Project '{project_name}' not found")
                print(f"📋 Create project at: https://smith.langchain.com/")
            
            return True
            
        except Exception as e:
            print(f"❌ LangSmith connection failed: {e}")
            print("📋 Check:")
            print("   1. API key is correct")
            print("   2. Network connectivity")
            print("   3. LangSmith service status")
            return False
    
    async def list_prompts(self) -> Dict[str, str]:
        """List existing prompts in LangSmith Hub"""
        if not self.client:
            return {}
        
        try:
            # Note: LangSmith doesn't have a direct list_prompts method
            # We'll try to pull known prompt names
            known_prompts = [
                "kumon:greeting:initial",
                "kumon:information:method_explanation", 
                "kumon:pricing:details",
                "kumon:scheduling:appointment_booking",
            ]
            
            found_prompts = {}
            for prompt_name in known_prompts:
                try:
                    prompt = self.client.pull_prompt(prompt_name)
                    found_prompts[prompt_name] = "✅ Available"
                except:
                    found_prompts[prompt_name] = "❌ Not found"
            
            print("📋 LangSmith Hub prompts:")
            for name, status in found_prompts.items():
                print(f"   {name}: {status}")
            
            return found_prompts
            
        except Exception as e:
            print(f"❌ Failed to list prompts: {e}")
            return {}
    
    async def upload_local_templates(self):
        """Upload local templates to LangSmith Hub"""
        if not self.client:
            return
        
        templates_dir = Path(__file__).parent.parent / "app" / "prompts" / "templates"
        
        if not templates_dir.exists():
            print(f"❌ Templates directory not found: {templates_dir}")
            return
        
        print(f"📁 Scanning templates in: {templates_dir}")
        
        # Map local templates to LangSmith prompt names
        template_mapping = {
            "cecilia_greeting.txt": "kumon:greeting:initial",
            "cecilia_pricing.txt": "kumon:pricing:details",
            "cecilia_conversation.txt": "kumon:conversation:general",
        }
        
        uploaded = 0
        for local_file, langsmith_name in template_mapping.items():
            local_path = templates_dir / local_file
            if local_path.exists():
                try:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    # Create PromptTemplate for LangSmith
                    from langchain.prompts import PromptTemplate
                    prompt_template = PromptTemplate(
                        template=content,
                        input_variables=self._extract_variables(content)
                    )
                    
                    # Push to LangSmith (this creates/updates the prompt)
                    self.client.push_prompt(langsmith_name, object=prompt_template)
                    print(f"✅ Uploaded: {local_file} → {langsmith_name}")
                    uploaded += 1
                    
                except Exception as e:
                    print(f"❌ Failed to upload {local_file}: {e}")
            else:
                print(f"⚠️ Template not found: {local_path}")
        
        print(f"📤 Upload completed: {uploaded} templates")
    
    def _extract_variables(self, template: str) -> list:
        """Extract variable names from template"""
        import re
        variables = re.findall(r'\{([^}]+)\}', template)
        return list(set(variables))
    
    async def test_prompt_fetch(self, prompt_name: str):
        """Test fetching a specific prompt"""
        if not self.client:
            return
        
        try:
            print(f"🧪 Testing prompt fetch: {prompt_name}")
            prompt = self.client.pull_prompt(prompt_name)
            
            if hasattr(prompt, 'template'):
                print(f"✅ Prompt fetched successfully")
                print(f"📝 Template preview: {prompt.template[:200]}...")
                print(f"🔧 Variables: {getattr(prompt, 'input_variables', [])}")
            else:
                print(f"⚠️ Unexpected prompt format: {type(prompt)}")
            
        except Exception as e:
            print(f"❌ Failed to fetch prompt: {e}")
    
    def print_configuration_status(self):
        """Print current LangSmith configuration status"""
        print("📊 LangSmith Configuration Status:")
        print(f"   API Key: {'✅ Set' if os.getenv('LANGSMITH_API_KEY') else '❌ Missing'}")
        print(f"   Project: {settings.LANGSMITH_PROJECT}")
        print(f"   Endpoint: {settings.LANGSMITH_ENDPOINT}")
        print(f"   Tracing: {'✅ Enabled' if settings.LANGCHAIN_TRACING_V2 else '❌ Disabled'}")
        print(f"   Client: {'✅ Initialized' if self.client else '❌ Failed'}")


async def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="LangSmith Setup for Kumon Assistant")
    parser.add_argument("--validate", action="store_true", help="Validate LangSmith connection")
    parser.add_argument("--upload-templates", action="store_true", help="Upload local templates to LangSmith Hub")
    parser.add_argument("--test-prompt", type=str, help="Test fetching a specific prompt")
    parser.add_argument("--list-prompts", action="store_true", help="List available prompts")
    parser.add_argument("--status", action="store_true", help="Show configuration status")
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        args.status = True  # Default to showing status
    
    setup = LangSmithSetup()
    
    if args.status:
        setup.print_configuration_status()
    
    if args.validate:
        await setup.validate_connection()
    
    if args.list_prompts:
        await setup.list_prompts()
    
    if args.upload_templates:
        await setup.upload_local_templates()
    
    if args.test_prompt:
        await setup.test_prompt_fetch(args.test_prompt)


if __name__ == "__main__":
    asyncio.run(main())