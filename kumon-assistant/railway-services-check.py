#!/usr/bin/env python3
"""
Railway Services Connectivity Check
Verifies that all services are properly connected and accessible
"""

import os
import sys
import asyncio
import asyncpg
import aioredis
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_postgresql_connection():
    """Test PostgreSQL connection"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ DATABASE_URL not found in environment")
        return False
    
    try:
        logger.info(f"🔍 Testing PostgreSQL connection...")
        logger.info(f"   URL: {database_url[:50]}...")
        
        # Test connection with timeout
        conn = await asyncio.wait_for(
            asyncpg.connect(database_url), 
            timeout=10.0
        )
        
        # Test simple query
        result = await conn.fetchval('SELECT 1')
        await conn.close()
        
        if result == 1:
            logger.info("✅ PostgreSQL connection successful")
            return True
        else:
            logger.error("❌ PostgreSQL connection failed - unexpected result")
            return False
            
    except asyncio.TimeoutError:
        logger.error("❌ PostgreSQL connection timeout (>10s)")
        return False
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False

async def test_redis_connection():
    """Test Redis connection"""
    redis_url = os.getenv('REDIS_URL') or os.getenv('MEMORY_REDIS_URL')
    
    if not redis_url:
        logger.error("❌ REDIS_URL not found in environment")
        return False
    
    try:
        logger.info(f"🔍 Testing Redis connection...")
        logger.info(f"   URL: {redis_url[:50]}...")
        
        # Test connection with timeout
        redis = await asyncio.wait_for(
            aioredis.from_url(redis_url),
            timeout=10.0
        )
        
        # Test simple operation
        await redis.set('railway_test', 'ok', ex=60)
        result = await redis.get('railway_test')
        await redis.delete('railway_test')
        await redis.close()
        
        if result == b'ok':
            logger.info("✅ Redis connection successful")
            return True
        else:
            logger.error("❌ Redis connection failed - unexpected result")
            return False
            
    except asyncio.TimeoutError:
        logger.error("❌ Redis connection timeout (>10s)")
        return False
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False

def test_environment_variables():
    """Test critical environment variables"""
    logger.info("🔍 Testing environment variables...")
    
    critical_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'OPENAI_API_KEY',
        'EVOLUTION_API_KEY'
    ]
    
    optional_vars = [
        'RAILWAY_ENVIRONMENT',
        'FORCE_RAILWAY_DETECTION',
        'MEMORY_REDIS_URL',
        'QDRANT_URL',
        'QDRANT_API_KEY'
    ]
    
    missing_critical = []
    missing_optional = []
    
    for var in critical_vars:
        if not os.getenv(var):
            missing_critical.append(var)
        else:
            logger.info(f"   ✅ {var}: PRESENT")
    
    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)
        else:
            logger.info(f"   ✅ {var}: PRESENT")
    
    if missing_critical:
        logger.error(f"❌ Missing critical environment variables: {missing_critical}")
        return False
    
    if missing_optional:
        logger.warning(f"⚠️ Missing optional environment variables: {missing_optional}")
    
    logger.info("✅ All critical environment variables present")
    return True

def test_railway_detection():
    """Test Railway environment detection"""
    logger.info("🔍 Testing Railway environment detection...")
    
    # Test our detection logic
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from app.core.railway_environment_fix import detect_railway_environment, get_railway_database_url
        
        is_railway = detect_railway_environment()
        logger.info(f"   Railway detected: {is_railway}")
        
        if is_railway:
            db_url = get_railway_database_url()
            logger.info(f"   Database URL detected: {'YES' if db_url else 'NO'}")
            
            if db_url:
                logger.info("✅ Railway detection working properly")
                return True
            else:
                logger.error("❌ Railway detected but DATABASE_URL not found")
                return False
        else:
            logger.error("❌ Railway environment not detected")
            logger.info("💡 Try setting FORCE_RAILWAY_DETECTION=1")
            return False
            
    except Exception as e:
        logger.error(f"❌ Railway detection test failed: {e}")
        return False

def test_network_connectivity():
    """Test network connectivity between services"""
    logger.info("🔍 Testing network connectivity...")
    
    # Test if we can resolve Railway internal hostnames
    database_url = os.getenv('DATABASE_URL', '')
    redis_url = os.getenv('REDIS_URL', '')
    
    network_issues = []
    
    # Check if using Railway internal networking
    if 'railway.internal' in database_url:
        logger.info("   ✅ PostgreSQL using Railway internal network")
    elif 'localhost' in database_url or '127.0.0.1' in database_url:
        network_issues.append("PostgreSQL using localhost (should use Railway internal)")
    else:
        logger.info("   ✅ PostgreSQL using external network")
    
    if 'railway.internal' in redis_url:
        logger.info("   ✅ Redis using Railway internal network")  
    elif 'localhost' in redis_url or '127.0.0.1' in redis_url:
        network_issues.append("Redis using localhost (should use Railway internal)")
    else:
        logger.info("   ✅ Redis using external network")
    
    if network_issues:
        logger.warning(f"⚠️ Network issues detected: {network_issues}")
        return False
    
    logger.info("✅ Network configuration looks good")
    return True

async def main():
    """Main connectivity test"""
    logger.info("🚀 Railway Services Connectivity Check")
    logger.info("=" * 50)
    
    results = {
        'environment_vars': False,
        'railway_detection': False,
        'network_config': False,
        'postgresql': False,
        'redis': False
    }
    
    # Test 1: Environment Variables
    logger.info("\n1. ENVIRONMENT VARIABLES TEST:")
    results['environment_vars'] = test_environment_variables()
    
    # Test 2: Railway Detection  
    logger.info("\n2. RAILWAY DETECTION TEST:")
    results['railway_detection'] = test_railway_detection()
    
    # Test 3: Network Configuration
    logger.info("\n3. NETWORK CONFIGURATION TEST:")
    results['network_config'] = test_network_connectivity()
    
    # Test 4: PostgreSQL Connectivity
    logger.info("\n4. POSTGRESQL CONNECTIVITY TEST:")
    results['postgresql'] = await test_postgresql_connection()
    
    # Test 5: Redis Connectivity  
    logger.info("\n5. REDIS CONNECTIVITY TEST:")
    results['redis'] = await test_redis_connection()
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 CONNECTIVITY CHECK SUMMARY:")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"   {test_name.replace('_', ' ').title()}: {status}")
    
    logger.info(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 All services are properly connected!")
        return True
    else:
        logger.error("🚨 Some services have connectivity issues")
        logger.info("\n💡 TROUBLESHOOTING TIPS:")
        
        if not results['environment_vars']:
            logger.info("   - Configure missing environment variables in Railway dashboard")
        if not results['railway_detection']:  
            logger.info("   - Set FORCE_RAILWAY_DETECTION=1 in Railway dashboard")
        if not results['postgresql']:
            logger.info("   - Create PostgreSQL service in Railway dashboard")
        if not results['redis']:
            logger.info("   - Create Redis service in Railway dashboard")
        if not results['network_config']:
            logger.info("   - Check service names and networking in Railway")
            
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"🚨 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)