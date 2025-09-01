#!/usr/bin/env python3
"""
Railway Environment Detection Debug Script
Execute this script on Railway to debug DATABASE_URL detection issues
"""

import os
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("🔍 RAILWAY DATABASE_URL DETECTION DEBUG")
    print("=" * 60)
    
    # 1. Environment Analysis
    print("\n1. ENVIRONMENT ANALYSIS:")
    print("-" * 30)
    
    # Check basic environment indicators
    env_indicators = {
        "PORT": os.getenv("PORT"),
        "NODE_ENV": os.getenv("NODE_ENV"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT"),
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
        "HOSTNAME": os.getenv("HOSTNAME"),
    }
    
    for key, value in env_indicators.items():
        print(f"  {key}: {value if value else 'NOT SET'}")
    
    # 2. Railway Variable Detection
    print("\n2. RAILWAY VARIABLES:")
    print("-" * 25)
    
    railway_vars = [
        "RAILWAY_ENVIRONMENT_ID", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID",
        "RAILWAY_DEPLOYMENT_ID", "RAILWAY_REPLICA_ID", "RAILWAY_GIT_COMMIT_SHA"
    ]
    
    found_railway_vars = []
    for var in railway_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value[:20]}..." if len(value) > 20 else f"  ✅ {var}: {value}")
            found_railway_vars.append(var)
        else:
            print(f"  ❌ {var}: NOT SET")
    
    print(f"\nRailway variables found: {len(found_railway_vars)}")
    
    # 3. Database Variables Analysis
    print("\n3. DATABASE VARIABLES:")
    print("-" * 25)
    
    db_vars = [
        "DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL", "DB_URL",
        "DATABASE_PRIVATE_URL", "DATABASE_PUBLIC_URL",
        "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGPORT"
    ]
    
    found_db_vars = []
    for var in db_vars:
        value = os.getenv(var)
        if value:
            if "PASSWORD" in var or "PASS" in var:
                print(f"  ✅ {var}: [MASKED]")
            else:
                print(f"  ✅ {var}: {value[:50]}..." if len(value) > 50 else f"  ✅ {var}: {value}")
            found_db_vars.append(var)
        else:
            print(f"  ❌ {var}: NOT SET")
    
    print(f"\nDatabase variables found: {len(found_db_vars)}")
    
    # 4. Test Railway Detection Logic
    print("\n4. RAILWAY DETECTION TEST:")
    print("-" * 30)
    
    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.path.dirname(__file__))
        
        from app.core.railway_environment_fix import detect_railway_environment, get_railway_database_url, apply_railway_environment_fixes
        
        # Test detection
        is_railway = detect_railway_environment()
        print(f"Railway detected: {is_railway}")
        
        if is_railway:
            db_url = get_railway_database_url()
            print(f"Database URL found: {'YES' if db_url else 'NO'}")
            if db_url:
                print(f"Database URL: {db_url[:50]}...")
            
            # Apply fixes
            print("\nApplying Railway fixes...")
            apply_railway_environment_fixes()
            
            # Check if fixes worked
            final_db_url = os.getenv("DATABASE_URL")
            print(f"Final DATABASE_URL status: {'SET' if final_db_url else 'NOT SET'}")
            
        else:
            print("❌ Railway not detected - no database URL search performed")
            print("\n🔧 You can force Railway detection by setting:")
            print("   FORCE_RAILWAY_DETECTION=1")
    
    except Exception as e:
        print(f"❌ ERROR testing Railway detection: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. All Environment Variables (database-related)
    print("\n5. ALL DATABASE-RELATED ENV VARS:")
    print("-" * 40)
    
    all_vars = sorted(os.environ.keys())
    db_related = [var for var in all_vars if any(keyword in var.upper() for keyword in ['DATABASE', 'POSTGRES', 'PG', 'DB', 'SQL'])]
    
    if db_related:
        for var in db_related:
            value = os.getenv(var, "")
            if any(keyword in var.upper() for keyword in ['PASSWORD', 'PASS', 'SECRET', 'KEY']):
                display = '[PRESENT]' if value else '[MISSING]'
            else:
                display = f'{value[:30]}...' if len(value) > 30 else value
            print(f"  {var}: {display}")
    else:
        print("  No database-related environment variables found!")
    
    print("\n" + "=" * 60)
    print("🏁 DEBUG COMPLETE")
    
    # Summary
    print("\n📊 SUMMARY:")
    print(f"  - Railway vars: {len(found_railway_vars)}")
    print(f"  - DB vars: {len(found_db_vars)}")
    print(f"  - Detection working: {'YES' if 'detect_railway_environment' in locals() else 'NO'}")
    
    return len(found_db_vars) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)