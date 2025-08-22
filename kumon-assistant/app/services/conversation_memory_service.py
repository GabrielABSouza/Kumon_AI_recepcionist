"""
Advanced Conversation Memory Service

High-performance hybrid Redis + PostgreSQL conversation memory system
optimized for ML pipelines and real-time analytics.

Architecture:
- Redis: Hot cache for active conversations (< 7 days)
- PostgreSQL: Cold storage for historical data and analytics
- Async operations with connection pooling
- Client-side caching with invalidation
- Event-driven updates for real-time insights

Performance Characteristics:
- < 5ms read latency for active conversations
- < 20ms write latency with batching
- Automatic scaling with connection pools
- Memory-efficient with TTL policies
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import asynccontextmanager
from dataclasses import asdict

import redis.asyncio as redis
import asyncpg
from asyncpg import Pool, Connection
from pydantic_settings import BaseSettings

from ..models.conversation_memory import (
    ConversationSession, ConversationMessage, UserProfile,
    ConversationStage, ConversationStep, ConversationStatus,
    UserIntent, SentimentLabel, LeadScore,
    create_conversation_session, create_user_profile
)
from ..core.config import settings
from ..core.logger import app_logger
from ..core.circuit_breaker import circuit_breaker, CircuitBreakerOpenError

# ============================================================================
# CONFIGURATION
# ============================================================================

class MemoryServiceConfig(BaseSettings):
    """Configuration for conversation memory service"""
    
    # Redis Configuration  
    redis_url: str = settings.MEMORY_REDIS_URL or "redis://localhost:6379/0"
    redis_max_connections: int = 10 if os.getenv("RAILWAY_ENVIRONMENT") else 20
    redis_retry_on_timeout: bool = True
    redis_socket_timeout: float = 5.0
    redis_socket_connect_timeout: float = 5.0
    
    # Redis Caching Policies
    active_session_ttl: int = 7 * 24 * 3600  # 7 days
    user_profile_ttl: int = 30 * 24 * 3600   # 30 days
    analytics_cache_ttl: int = 3600           # 1 hour
    
    # PostgreSQL Configuration  
    postgres_url: str = settings.DATABASE_URL
    postgres_min_pool_size: int = 2 if os.getenv("RAILWAY_ENVIRONMENT") else 5
    postgres_max_pool_size: int = 10 if os.getenv("RAILWAY_ENVIRONMENT") else 20
    postgres_command_timeout: float = 10.0 if os.getenv("RAILWAY_ENVIRONMENT") else 30.0
    postgres_server_settings: Dict[str, str] = {
        "application_name": "kumon_conversation_memory",
        "timezone": "UTC"
    }
    
    # Performance Settings
    batch_write_size: int = 100
    batch_write_interval: float = 2.0  # seconds
    enable_client_side_cache: bool = True
    cache_invalidation_channel: str = "memory_invalidation"
    
    # ML Feature Settings
    enable_ml_features: bool = True
    feature_extraction_batch_size: int = 50
    embedding_cache_ttl: int = 24 * 3600  # 24 hours
    
    class Config:
        env_prefix = "MEMORY_"

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class ConversationMemoryError(Exception):
    """Base exception for conversation memory operations"""
    pass

class SessionNotFoundError(ConversationMemoryError):
    """Raised when conversation session is not found"""
    pass

class UserNotFoundError(ConversationMemoryError):
    """Raised when user profile is not found"""
    pass

class StorageError(ConversationMemoryError):
    """Raised when storage operation fails"""
    pass

# ============================================================================
# REDIS KEY PATTERNS
# ============================================================================

class RedisKeys:
    """Redis key patterns for organized data access"""
    
    # Session keys
    SESSION = "session:{session_id}"
    USER_SESSIONS = "user_sessions:{user_id}"
    ACTIVE_SESSIONS = "active_sessions"
    SESSION_LOCK = "lock:session:{session_id}"
    
    # User profile keys
    USER_PROFILE = "user:{user_id}"
    PHONE_TO_USER = "phone_to_user:{phone_number}"
    
    # Analytics keys
    DAILY_METRICS = "metrics:daily:{date}"
    HOURLY_METRICS = "metrics:hourly:{date}:{hour}"
    USER_ANALYTICS = "analytics:user:{user_id}"
    
    # ML feature keys
    SESSION_FEATURES = "features:session:{session_id}"
    USER_EMBEDDINGS = "embeddings:user:{user_id}"
    MESSAGE_EMBEDDINGS = "embeddings:message:{message_id}"
    
    # Cache invalidation
    INVALIDATION_CHANNEL = "invalidation"
    
    @staticmethod
    def format_key(pattern: str, **kwargs) -> str:
        """Format key pattern with parameters"""
        return pattern.format(**kwargs)

# ============================================================================
# MAIN MEMORY SERVICE
# ============================================================================

class ConversationMemoryService:
    """
    Advanced conversation memory service with Redis + PostgreSQL
    
    Features:
    - Hybrid storage with intelligent caching
    - Async operations with connection pooling
    - ML-ready data structures
    - Real-time analytics support
    - Automatic cleanup and optimization
    """
    
    def __init__(self, config: Optional[MemoryServiceConfig] = None):
        self.config = config or MemoryServiceConfig()
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.postgres_pool: Optional[Pool] = None
        self._write_queue: List[Dict[str, Any]] = []
        self._write_task: Optional[asyncio.Task] = None
        self._client_cache: Dict[str, Any] = {}
        self._cache_invalidation_task: Optional[asyncio.Task] = None
        self._initialized = False
        
        app_logger.info("ConversationMemoryService initialized", extra={
            "config": {
                "redis_url": self.config.redis_url,
                "postgres_max_pool": self.config.postgres_max_pool_size,
                "batch_write_size": self.config.batch_write_size
            }
        })
    
    # ========================================================================
    # INITIALIZATION AND CLEANUP
    # ========================================================================
    
    async def initialize(self) -> None:
        """Initialize Redis and PostgreSQL connections"""
        if self._initialized:
            return
            
        try:
            # Initialize Redis connection pool
            self.redis_pool = redis.ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.redis_max_connections,
                retry_on_timeout=self.config.redis_retry_on_timeout,
                socket_timeout=self.config.redis_socket_timeout,
                socket_connect_timeout=self.config.redis_socket_connect_timeout
            )
            
            # Test Redis connection
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                await r.ping()
                app_logger.info("Redis connection established")
            
            # Initialize PostgreSQL connection pool with shorter timeout
            try:
                app_logger.info("Attempting PostgreSQL connection", extra={
                    "postgres_url": self.config.postgres_url[:50] + "...",
                    "timeout": 10
                })
                
                self.postgres_pool = await asyncio.wait_for(
                    asyncpg.create_pool(
                        self.config.postgres_url,
                        min_size=self.config.postgres_min_pool_size,
                        max_size=self.config.postgres_max_pool_size,
                        command_timeout=self.config.postgres_command_timeout,
                        server_settings=self.config.postgres_server_settings
                    ),
                    timeout=10.0  # Railway-optimized: 10 seconds timeout
                )
            except asyncio.TimeoutError:
                app_logger.error("PostgreSQL connection pool creation timed out after 10 seconds")
                app_logger.error("This usually indicates DATABASE_URL is incorrect or PostgreSQL is not accessible")
                raise
            except Exception as e:
                app_logger.error(f"PostgreSQL connection failed: {e}")
                app_logger.error("Check DATABASE_URL environment variable and PostgreSQL service status")
                raise
            
            app_logger.info("PostgreSQL connection pool established")
            
            # Initialize database schema with shorter timeout
            try:
                app_logger.info("Initializing database schema...")
                await asyncio.wait_for(self._initialize_database_schema(), timeout=15.0)
                app_logger.info("Database schema initialized successfully")
            except asyncio.TimeoutError:
                app_logger.error("Database schema initialization timed out after 15 seconds")
                app_logger.error("This may indicate permission issues or database connectivity problems")
                raise
            except Exception as e:
                app_logger.error(f"Database schema initialization failed: {e}")
                raise
            
            # Start background tasks
            if self.config.batch_write_size > 1:
                self._write_task = asyncio.create_task(self._batch_write_worker())
                
            if self.config.enable_client_side_cache:
                self._cache_invalidation_task = asyncio.create_task(self._cache_invalidation_worker())
            
            self._initialized = True
            app_logger.info("ConversationMemoryService fully initialized")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize ConversationMemoryService: {e}")
            await self.cleanup()
            raise StorageError(f"Initialization failed: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup connections and background tasks"""
        app_logger.info("Cleaning up ConversationMemoryService")
        
        # Cancel background tasks
        if hasattr(self, '_write_task') and self._write_task and not self._write_task.done():
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
                
        if hasattr(self, '_cache_invalidation_task') and self._cache_invalidation_task and not self._cache_invalidation_task.done():
            self._cache_invalidation_task.cancel()
            try:
                await self._cache_invalidation_task
            except asyncio.CancelledError:
                pass
        
        # Flush pending writes
        if hasattr(self, '_write_queue') and self._write_queue:
            await self._flush_write_queue()
        
        # Close connections
        if hasattr(self, 'redis_pool') and self.redis_pool:
            await self.redis_pool.disconnect()
            
        if hasattr(self, 'postgres_pool') and self.postgres_pool:
            await self.postgres_pool.close()
        
        # Clear cache
        if hasattr(self, '_client_cache') and self._client_cache:
            self._client_cache.clear()
        
        self._initialized = False
        app_logger.info("ConversationMemoryService cleanup completed")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the conversation memory service"""
        try:
            if not self._initialized:
                return {"status": "unhealthy", "reason": "service not initialized"}
            
            # Test Redis connection
            if hasattr(self, 'redis_pool') and self.redis_pool:
                async with redis.Redis(connection_pool=self.redis_pool) as r:
                    await r.ping()
                    redis_status = "healthy"
            else:
                redis_status = "unavailable"
            
            # Test PostgreSQL connection
            if hasattr(self, 'postgres_pool') and self.postgres_pool:
                async with self.postgres_pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    postgres_status = "healthy"
            else:
                postgres_status = "unavailable"
            
            return {
                "status": "healthy",
                "redis": redis_status,
                "postgres": postgres_status,
                "initialized": self._initialized
            }
            
        except Exception as e:
            return {
                "status": "unhealthy", 
                "reason": str(e),
                "initialized": self._initialized
            }
    
    async def _initialize_database_schema(self) -> None:
        """Initialize PostgreSQL database schema"""
        schema_sql = """
        -- Enable extensions
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS "pg_trgm";
        CREATE EXTENSION IF NOT EXISTS "btree_gin";
        
        -- User profiles table (dimension table for analytics)
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id VARCHAR(50) PRIMARY KEY,
            phone_number VARCHAR(20) UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_interaction TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Personal information
            parent_name TEXT,
            preferred_name TEXT,
            child_name TEXT,
            child_age INTEGER,
            
            -- Preferences (JSONB for flexibility)
            program_interests JSONB DEFAULT '[]'::jsonb,
            availability_preferences JSONB DEFAULT '{}'::jsonb,
            communication_preferences JSONB DEFAULT '{}'::jsonb,
            
            -- Aggregated metrics
            total_interactions INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            avg_session_duration DECIMAL(10,2) DEFAULT 0,
            conversion_events JSONB DEFAULT '[]'::jsonb,
            
            -- ML computed features
            engagement_score DECIMAL(5,4) DEFAULT 0,
            churn_probability DECIMAL(5,4) DEFAULT 0,
            lifetime_value_prediction DECIMAL(10,2) DEFAULT 0,
            persona_cluster TEXT,
            
            -- Metadata
            schema_version VARCHAR(10) DEFAULT '1.0'
        );
        
        -- Conversation sessions table (fact table for analytics)
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            session_id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL REFERENCES user_profiles(user_id),
            phone_number VARCHAR(20) NOT NULL,
            
            -- Timestamps (partitioned by created_at)
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMPTZ,
            
            -- Status and progression
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            current_stage VARCHAR(30) NOT NULL DEFAULT 'greeting',
            current_step VARCHAR(50) NOT NULL DEFAULT 'welcome',
            
            -- Metrics (denormalized for performance)
            message_count INTEGER DEFAULT 0,
            duration_seconds INTEGER DEFAULT 0,
            failed_attempts INTEGER DEFAULT 0,
            sentiment_score_avg DECIMAL(5,4) DEFAULT 0,
            satisfaction_score DECIMAL(5,4) DEFAULT 0,
            
            -- Business metrics
            lead_score INTEGER DEFAULT 0,
            lead_score_category VARCHAR(20) DEFAULT 'unqualified',
            conversion_probability DECIMAL(5,4) DEFAULT 0,
            estimated_value DECIMAL(10,2) DEFAULT 0,
            
            -- ML features and predictions (JSONB for flexibility)
            session_features JSONB DEFAULT '{}'::jsonb,
            predictions JSONB DEFAULT '{}'::jsonb,
            labels JSONB DEFAULT '{}'::jsonb,
            
            -- Historical data
            stage_history JSONB DEFAULT '[]'::jsonb,
            conversion_events JSONB DEFAULT '[]'::jsonb,
            scheduling_context JSONB DEFAULT '{}'::jsonb,
            
            -- Metadata
            schema_version VARCHAR(10) DEFAULT '1.0'
        );
        
        -- Messages table (optimized for time-series analysis)
        CREATE TABLE IF NOT EXISTS conversation_messages (
            message_id VARCHAR(50) PRIMARY KEY,
            conversation_id VARCHAR(50) NOT NULL REFERENCES conversation_sessions(session_id),
            user_id VARCHAR(50) NOT NULL REFERENCES user_profiles(user_id),
            
            -- Timestamp (primary partition key)
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Content
            content TEXT NOT NULL,
            is_from_user BOOLEAN NOT NULL,
            message_type VARCHAR(20) DEFAULT 'text',
            message_length INTEGER GENERATED ALWAYS AS (char_length(content)) STORED,
            
            -- AI-generated features
            intent VARCHAR(30),
            intent_confidence DECIMAL(5,4) DEFAULT 0,
            sentiment VARCHAR(20),
            sentiment_score DECIMAL(5,4) DEFAULT 0,
            entities JSONB DEFAULT '[]'::jsonb,
            
            -- Context
            conversation_stage VARCHAR(30) NOT NULL,
            conversation_step VARCHAR(50) NOT NULL,
            response_time_seconds DECIMAL(8,3),
            
            -- ML features
            features JSONB DEFAULT '{}'::jsonb,
            embeddings REAL[], -- For vector similarity
            
            -- Metadata
            schema_version VARCHAR(10) DEFAULT '1.0'
        );
        
        -- Analytics aggregation tables
        CREATE TABLE IF NOT EXISTS daily_conversation_metrics (
            date DATE PRIMARY KEY,
            total_sessions INTEGER DEFAULT 0,
            active_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            abandoned_sessions INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            avg_session_duration DECIMAL(10,2) DEFAULT 0,
            conversion_rate DECIMAL(5,4) DEFAULT 0,
            satisfaction_avg DECIMAL(5,4) DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_user_profiles_phone ON user_profiles(phone_number);
        CREATE INDEX IF NOT EXISTS idx_user_profiles_updated ON user_profiles(updated_at);
        
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON conversation_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON conversation_sessions(created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON conversation_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_sessions_stage ON conversation_sessions(current_stage);
        CREATE INDEX IF NOT EXISTS idx_sessions_lead_score ON conversation_sessions(lead_score_category);
        
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_messages_user_id ON conversation_messages(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_intent ON conversation_messages(intent);
        CREATE INDEX IF NOT EXISTS idx_messages_sentiment ON conversation_messages(sentiment);
        
        -- GIN indexes for JSONB fields (ML feature queries)
        CREATE INDEX IF NOT EXISTS idx_sessions_features ON conversation_sessions USING gin(session_features);
        CREATE INDEX IF NOT EXISTS idx_messages_features ON conversation_messages USING gin(features);
        CREATE INDEX IF NOT EXISTS idx_messages_entities ON conversation_messages USING gin(entities);
        
        -- Full-text search indexes
        CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON conversation_messages USING gin(to_tsvector('portuguese', content));
        
        -- Table partitioning by month for conversation_messages (better performance)
        -- Note: This would be handled by migration scripts in production
        """
        
        async with self.postgres_pool.acquire() as conn:
            await conn.execute(schema_sql)
            app_logger.info("Database schema initialized successfully")
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    @circuit_breaker(failure_threshold=2, recovery_timeout=15, name="memory_create_session")
    async def create_session(
        self, 
        phone_number: str, 
        user_name: Optional[str] = None,
        initial_message: Optional[str] = None
    ) -> ConversationSession:
        """Create a new conversation session"""
        
        try:
            # Get or create user profile
            user_profile = await self._get_or_create_user_profile(phone_number, user_name)
            
            # Create conversation session
            session = create_conversation_session(phone_number, user_profile)
            
            # Add initial message if provided
            if initial_message:
                initial_msg = ConversationMessage(
                    message_id=f"msg_{session.session_id}_001",
                    conversation_id=session.session_id,
                    user_id=session.user_id,
                    timestamp=datetime.now(timezone.utc),
                    content=initial_message,
                    is_from_user=True,
                    conversation_stage=session.current_stage,
                    conversation_step=session.current_step
                )
                session.add_message(initial_msg)
            
            # Store in Redis for fast access
            await self._store_session_in_redis(session)
            
            # Queue for PostgreSQL batch write
            await self._queue_session_write(session)
            
            app_logger.info(f"Created conversation session {session.session_id} for user {user_profile.user_id}")
            
            return session
            
        except Exception as e:
            app_logger.error(f"Failed to create session for {phone_number}: {e}")
            raise StorageError(f"Session creation failed: {e}")
    
    @circuit_breaker(failure_threshold=2, recovery_timeout=15, name="memory_get_session")
    async def get_session(self, session_id: str) -> ConversationSession:
        """Get conversation session by ID"""
        
        # Try Redis first (hot cache)
        session = await self._get_session_from_redis(session_id)
        if session:
            return session
        
        # Fallback to PostgreSQL (cold storage)
        session = await self._get_session_from_postgres(session_id)
        if session:
            # Warm up Redis cache
            await self._store_session_in_redis(session)
            return session
        
        raise SessionNotFoundError(f"Session {session_id} not found")
    
    async def get_active_session_by_phone(self, phone_number: str) -> Optional[ConversationSession]:
        """Get active conversation session for phone number"""
        
        try:
            # Get user profile first
            user_profile = await self.get_user_profile_by_phone(phone_number)
            if not user_profile:
                return None
            
            # Check Redis for active session
            active_session_id = await self._get_active_session_id(user_profile.user_id)
            if active_session_id:
                return await self.get_session(active_session_id)
            
            # Query PostgreSQL for recent active session
            async with self.postgres_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT session_id FROM conversation_sessions 
                    WHERE user_id = $1 AND status = 'active'
                    ORDER BY last_activity DESC LIMIT 1
                """, user_profile.user_id)
                
                if row:
                    session = await self.get_session(row['session_id'])
                    # Update Redis cache
                    await self._set_active_session_id(user_profile.user_id, session.session_id)
                    return session
            
            return None
            
        except Exception as e:
            app_logger.error(f"Failed to get active session for {phone_number}: {e}")
            return None
    
    @circuit_breaker(failure_threshold=2, recovery_timeout=15, name="memory_update_session")
    async def update_session(self, session: ConversationSession) -> None:
        """Update conversation session"""
        
        try:
            session.updated_at = datetime.now(timezone.utc)
            session.last_activity = session.updated_at
            
            # Update Redis cache
            await self._store_session_in_redis(session)
            
            # Queue for PostgreSQL batch write
            await self._queue_session_write(session)
            
            # Invalidate client cache
            if self.config.enable_client_side_cache:
                await self._invalidate_cache_key(f"session:{session.session_id}")
            
        except Exception as e:
            app_logger.error(f"Failed to update session {session.session_id}: {e}")
            raise StorageError(f"Session update failed: {e}")
    
    @circuit_breaker(failure_threshold=2, recovery_timeout=15, name="memory_add_message")
    async def add_message_to_session(
        self, 
        session_id: str, 
        content: str, 
        is_from_user: bool = True,
        message_type: str = "text",
        intent: Optional[UserIntent] = None,
        sentiment: Optional[SentimentLabel] = None
    ) -> ConversationMessage:
        """Add message to conversation session"""
        
        try:
            # Get session
            session = await self.get_session(session_id)
            
            # Create message
            message = ConversationMessage(
                message_id=f"msg_{session_id}_{len(session.messages) + 1:03d}",
                conversation_id=session_id,
                user_id=session.user_id,
                timestamp=datetime.now(timezone.utc),
                content=content,
                is_from_user=is_from_user,
                message_type=message_type,
                conversation_stage=session.current_stage,
                conversation_step=session.current_step,
                intent=intent,
                sentiment=sentiment
            )
            
            # Add to session
            session.add_message(message)
            
            # Update session
            await self.update_session(session)
            
            # Queue message for PostgreSQL
            await self._queue_message_write(message)
            
            app_logger.debug(f"Added message to session {session_id}")
            
            return message
            
        except Exception as e:
            app_logger.error(f"Failed to add message to session {session_id}: {e}")
            raise StorageError(f"Message addition failed: {e}")
    
    # ========================================================================
    # USER PROFILE MANAGEMENT  
    # ========================================================================
    
    async def get_user_profile_by_phone(self, phone_number: str) -> Optional[UserProfile]:
        """Get user profile by phone number"""
        
        # Try Redis first
        user_id = await self._get_user_id_by_phone(phone_number)
        if user_id:
            profile = await self._get_user_profile_from_redis(user_id)
            if profile:
                return profile
        
        # Fallback to PostgreSQL
        async with self.postgres_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM user_profiles WHERE phone_number = $1
            """, phone_number)
            
            if row:
                profile = self._row_to_user_profile(row) 
                # Cache in Redis
                await self._store_user_profile_in_redis(profile)
                return profile
        
        return None
    
    async def update_user_profile(self, profile: UserProfile) -> None:
        """Update user profile"""
        
        try:
            profile.last_interaction = datetime.now(timezone.utc)
            
            # Update Redis
            await self._store_user_profile_in_redis(profile)
            
            # Queue for PostgreSQL
            await self._queue_user_profile_write(profile)
            
        except Exception as e:
            app_logger.error(f"Failed to update user profile {profile.user_id}: {e}")
            raise StorageError(f"User profile update failed: {e}")
    
    # ========================================================================
    # ANALYTICS AND ML SUPPORT
    # ========================================================================
    
    async def get_session_analytics(
        self, 
        start_date: datetime, 
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get conversation analytics for specified period"""
        
        cache_key = f"analytics:{start_date.date()}:{end_date.date()}"
        
        # Try cache first
        if self.config.enable_client_side_cache:
            cached = self._client_cache.get(cache_key)
        if cached:
                return cached
        
        # Query PostgreSQL
        async with self.postgres_pool.acquire() as conn:
            # Build dynamic query based on filters
            where_clause = "WHERE created_at BETWEEN $1 AND $2"
            params = [start_date, end_date]
            
            if filters:
                if filters.get('status'):
                    where_clause += f" AND status = ${len(params) + 1}"
                    params.append(filters['status'])
                    
                if filters.get('lead_score_category'):
                    where_clause += f" AND lead_score_category = ${len(params) + 1}"
                    params.append(filters['lead_score_category'])
            
            query = f"""
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_sessions,
                    COUNT(*) FILTER (WHERE status = 'abandoned') as abandoned_sessions,
                    AVG(duration_seconds) as avg_duration,
                    AVG(message_count) as avg_messages,
                    AVG(satisfaction_score) as avg_satisfaction,
                    COUNT(*) FILTER (WHERE conversion_events != '[]'::jsonb) as conversions
                FROM conversation_sessions 
                {where_clause}
            """
            
            result = await conn.fetchrow(query, *params)
            
            analytics = {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "metrics": dict(result) if result else {},
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Cache result
        if self.config.enable_client_side_cache:
                self._client_cache[cache_key] = analytics
                
        return analytics
    
    async def extract_ml_features_bulk(
        self, 
        session_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Extract ML features for multiple sessions"""
        
        features = {}
        
        # Process in batches for memory efficiency
        batch_size = self.config.feature_extraction_batch_size
        for i in range(0, len(session_ids), batch_size):
            batch = session_ids[i:i + batch_size]
            
            for session_id in batch:
                try:
                    session = await self.get_session(session_id)
                    features[session_id] = session.get_ml_features()
                except SessionNotFoundError:
                    app_logger.warning(f"Session {session_id} not found for feature extraction")
                    continue
        
        return features
    
    # ========================================================================
    # REDIS OPERATIONS
    # ========================================================================
    
    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from pool"""
        return redis.Redis(connection_pool=self.redis_pool)
    
    async def _store_session_in_redis(self, session: ConversationSession) -> None:
        """Store session in Redis with TTL"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.SESSION, session_id=session.session_id)
        value = json.dumps(session.to_dict(), default=str)
        await r.setex(key, self.config.active_session_ttl, value)
        
        # Update active sessions set
        if session.status == ConversationStatus.ACTIVE:
            await r.sadd(RedisKeys.ACTIVE_SESSIONS, session.session_id)
            await r.setex(
                RedisKeys.format_key(RedisKeys.USER_SESSIONS, user_id=session.user_id),
                self.config.active_session_ttl,
                session.session_id
            )
    
    async def _get_session_from_redis(self, session_id: str) -> Optional[ConversationSession]:
        """Get session from Redis"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.SESSION, session_id=session_id)
        data = await r.get(key)
        if data:
                session_dict = json.loads(data)
                return self._dict_to_session(session_dict)
        return None
    
    async def _store_user_profile_in_redis(self, profile: UserProfile) -> None:
        """Store user profile in Redis"""
        r = self._get_redis_client()
            # Store profile
        profile_key = RedisKeys.format_key(RedisKeys.USER_PROFILE, user_id=profile.user_id)
        profile_value = json.dumps(profile.to_dict(), default=str)
        await r.setex(profile_key, self.config.user_profile_ttl, profile_value)
            
            # Store phone number mapping
        phone_key = RedisKeys.format_key(RedisKeys.PHONE_TO_USER, phone_number=profile.phone_number)
        await r.setex(phone_key, self.config.user_profile_ttl, profile.user_id)
    
    async def _get_user_profile_from_redis(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile from Redis"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.USER_PROFILE, user_id=user_id)
        data = await r.get(key)
        if data:
                profile_dict = json.loads(data)
                return self._dict_to_user_profile(profile_dict)
        return None
    
    async def _get_user_id_by_phone(self, phone_number: str) -> Optional[str]:
        """Get user ID by phone number from Redis"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.PHONE_TO_USER, phone_number=phone_number)
        return await r.get(key)
    
    async def _get_active_session_id(self, user_id: str) -> Optional[str]:
        """Get active session ID for user"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.USER_SESSIONS, user_id=user_id)
        session_id = await r.get(key)
        return session_id.decode() if session_id else None
    
    async def _set_active_session_id(self, user_id: str, session_id: str) -> None:
        """Set active session ID for user"""
        r = self._get_redis_client()
        key = RedisKeys.format_key(RedisKeys.USER_SESSIONS, user_id=user_id)
        await r.setex(key, self.config.active_session_ttl, session_id)
    
    # ========================================================================
    # POSTGRESQL OPERATIONS
    # ========================================================================
    
    async def _get_session_from_postgres(self, session_id: str) -> Optional[ConversationSession]:
        """Get session from PostgreSQL with related data"""
        async with self.postgres_pool.acquire() as conn:
            # Get session data
            session_row = await conn.fetchrow("""
                SELECT s.*, u.* FROM conversation_sessions s
                JOIN user_profiles u ON s.user_id = u.user_id
                WHERE s.session_id = $1
            """, session_id)
            
            if not session_row:
                return None
            
            # Get messages
            message_rows = await conn.fetch("""
                SELECT * FROM conversation_messages 
                WHERE conversation_id = $1 
                ORDER BY timestamp ASC
            """, session_id)
            
            # Build session object
            session = self._row_to_session(session_row, message_rows)
            return session
    
    # ========================================================================
    # BATCH WRITE OPERATIONS
    # ========================================================================
    
    async def _queue_session_write(self, session: ConversationSession) -> None:
        """Queue session for batch write to PostgreSQL"""
        write_op = {
            "type": "session",
            "data": session,
            "timestamp": time.time()
        }
        self._write_queue.append(write_op)
        
        # Trigger immediate write if queue is full
        if len(self._write_queue) >= self.config.batch_write_size:
            await self._flush_write_queue()
    
    async def _queue_message_write(self, message: ConversationMessage) -> None:
        """Queue message for batch write to PostgreSQL"""
        write_op = {
            "type": "message", 
            "data": message,
            "timestamp": time.time()
        }
        self._write_queue.append(write_op)
    
    async def _queue_user_profile_write(self, profile: UserProfile) -> None:
        """Queue user profile for batch write to PostgreSQL"""
        write_op = {
            "type": "user_profile",
            "data": profile,
            "timestamp": time.time()
        }
        self._write_queue.append(write_op)
    
    async def _batch_write_worker(self) -> None:
        """Background worker for batch writes"""
        while True:
            try:
                await asyncio.sleep(self.config.batch_write_interval)
                if self._write_queue:
                    await self._flush_write_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                app_logger.error(f"Batch write worker error: {e}")
    
    async def _flush_write_queue(self) -> None:
        """Flush write queue to PostgreSQL"""
        if not self._write_queue:
            return
            
        queue_copy = self._write_queue.copy()
        self._write_queue.clear()
        
        async with self.postgres_pool.acquire() as conn:
            async with conn.transaction():
                for op in queue_copy:
                    try:
                        if op["type"] == "session":
                            await self._write_session_to_postgres(conn, op["data"])
                        elif op["type"] == "message":
                            await self._write_message_to_postgres(conn, op["data"])
                        elif op["type"] == "user_profile":
                            await self._write_user_profile_to_postgres(conn, op["data"])
                    except Exception as e:
                        app_logger.error(f"Failed to write {op['type']}: {e}")
        
        app_logger.debug(f"Flushed {len(queue_copy)} operations to PostgreSQL")
    
    async def _write_session_to_postgres(self, conn: Connection, session: ConversationSession) -> None:
        """Write session to PostgreSQL with upsert"""
        await conn.execute("""
            INSERT INTO conversation_sessions (
                session_id, user_id, phone_number, created_at, updated_at, last_activity, ended_at,
                status, current_stage, current_step, message_count, duration_seconds,
                failed_attempts, sentiment_score_avg, satisfaction_score, lead_score,
                lead_score_category, conversion_probability, estimated_value,
                session_features, predictions, labels, stage_history, conversion_events,
                scheduling_context, schema_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
                $20, $21, $22, $23, $24, $25, $26
            )
            ON CONFLICT (session_id) DO UPDATE SET
                updated_at = EXCLUDED.updated_at,
                last_activity = EXCLUDED.last_activity,
                ended_at = EXCLUDED.ended_at,
                status = EXCLUDED.status,
                current_stage = EXCLUDED.current_stage,
                current_step = EXCLUDED.current_step,
                message_count = EXCLUDED.message_count,
                duration_seconds = EXCLUDED.duration_seconds,
                failed_attempts = EXCLUDED.failed_attempts,
                sentiment_score_avg = EXCLUDED.sentiment_score_avg,
                satisfaction_score = EXCLUDED.satisfaction_score,
                lead_score = EXCLUDED.lead_score,
                lead_score_category = EXCLUDED.lead_score_category,
                conversion_probability = EXCLUDED.conversion_probability,
                estimated_value = EXCLUDED.estimated_value,
                session_features = EXCLUDED.session_features,
                predictions = EXCLUDED.predictions,
                labels = EXCLUDED.labels,
                stage_history = EXCLUDED.stage_history,
                conversion_events = EXCLUDED.conversion_events,
                scheduling_context = EXCLUDED.scheduling_context
        """, 
            session.session_id, session.user_id, session.phone_number,
            session.created_at, session.updated_at, session.last_activity, session.ended_at,
            session.status.value, session.current_stage.value, session.current_step.value,
            session.metrics.message_count, session.calculate_session_duration(),
            session.metrics.failed_attempts, session.metrics.sentiment_score_avg,
            session.metrics.satisfaction_score, session.metrics.lead_score,
            session.lead_score_category.value, session.metrics.conversion_probability,
            session.metrics.estimated_value, json.dumps(session.session_features),
            json.dumps(session.predictions), json.dumps(session.labels), 
            json.dumps(session.stage_history), json.dumps(session.conversion_events),
            json.dumps(session.scheduling_context), session.schema_version
        )
    
    async def _write_message_to_postgres(self, conn: Connection, message: ConversationMessage) -> None:
        """Write message to PostgreSQL"""
        await conn.execute("""
            INSERT INTO conversation_messages (
                message_id, conversation_id, user_id, timestamp, content, is_from_user,
                message_type, intent, intent_confidence, sentiment, sentiment_score,
                entities, conversation_stage, conversation_step, response_time_seconds,
                features, embeddings, schema_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
            )
            ON CONFLICT (message_id) DO NOTHING
        """,
            message.message_id, message.conversation_id, message.user_id, message.timestamp,
            message.content, message.is_from_user, message.message_type,
            message.intent.value if message.intent else None, message.intent_confidence,
            message.sentiment.value if message.sentiment else None, message.sentiment_score,
            json.dumps(message.entities), message.conversation_stage.value,
            message.conversation_step.value, message.response_time_seconds,
            json.dumps(message.features), message.embeddings, "1.0"
        )
    
    async def _write_user_profile_to_postgres(self, conn: Connection, profile: UserProfile) -> None:
        """Write user profile to PostgreSQL with upsert"""
        await conn.execute("""
            INSERT INTO user_profiles (
                user_id, phone_number, created_at, updated_at, last_interaction,
                parent_name, preferred_name, child_name, child_age, program_interests,
                availability_preferences, communication_preferences, total_interactions,
                total_messages, avg_session_duration, conversion_events, engagement_score,
                churn_probability, lifetime_value_prediction, persona_cluster, schema_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
            ON CONFLICT (user_id) DO UPDATE SET
                updated_at = EXCLUDED.updated_at,
                last_interaction = EXCLUDED.last_interaction,
                parent_name = EXCLUDED.parent_name,
                preferred_name = EXCLUDED.preferred_name,
                child_name = EXCLUDED.child_name,
                child_age = EXCLUDED.child_age,
                program_interests = EXCLUDED.program_interests,
                availability_preferences = EXCLUDED.availability_preferences,
                communication_preferences = EXCLUDED.communication_preferences,
                total_interactions = EXCLUDED.total_interactions,
                total_messages = EXCLUDED.total_messages,
                avg_session_duration = EXCLUDED.avg_session_duration,
                conversion_events = EXCLUDED.conversion_events,
                engagement_score = EXCLUDED.engagement_score,
                churn_probability = EXCLUDED.churn_probability,
                lifetime_value_prediction = EXCLUDED.lifetime_value_prediction,
                persona_cluster = EXCLUDED.persona_cluster
        """,
            profile.user_id, profile.phone_number, profile.created_at, profile.updated_at,
            profile.last_interaction, profile.parent_name, profile.preferred_name,
            profile.child_name, profile.child_age, json.dumps(profile.program_interests),
            json.dumps(profile.availability_preferences), json.dumps(profile.communication_preferences),
            profile.total_interactions, profile.total_messages, profile.avg_session_duration,
            json.dumps(profile.conversion_events), profile.engagement_score,
            profile.churn_probability, profile.lifetime_value_prediction,
            profile.persona_cluster, "1.0"
        )
    
    # ========================================================================
    # CACHE INVALIDATION
    # ========================================================================
    
    async def _cache_invalidation_worker(self) -> None:
        """Background worker for cache invalidation"""
        r = self._get_redis_client()
        pubsub = r.pubsub()
        await pubsub.subscribe(self.config.cache_invalidation_channel)
        
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    cache_key = message['data'].decode()
                    self._client_cache.pop(cache_key, None)
                    app_logger.debug(f"Invalidated cache key: {cache_key}")
        except asyncio.CancelledError:
            await pubsub.unsubscribe(self.config.cache_invalidation_channel)
            raise
    
    async def _invalidate_cache_key(self, cache_key: str) -> None:
        """Invalidate specific cache key across all clients"""
        r = self._get_redis_client()
        await r.publish(self.config.cache_invalidation_channel, cache_key)
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_or_create_user_profile(self, phone_number: str, name: Optional[str] = None) -> UserProfile:
        """Get existing user profile or create new one"""
        profile = await self.get_user_profile_by_phone(phone_number)
        if profile:
            # Update last interaction
            profile.last_interaction = datetime.now(timezone.utc)
            if name and not profile.parent_name:
                profile.parent_name = name
            await self.update_user_profile(profile)
            return profile
        
        # Create new profile
        profile = create_user_profile(phone_number, name)
        
        # Write user profile immediately to ensure it exists before session creation
        async with self.postgres_pool.acquire() as conn:
            await self._write_user_profile_to_postgres(conn, profile)
        
        await self._store_user_profile_in_redis(profile)
        return profile
    
    def _dict_to_session(self, data: Dict[str, Any]) -> ConversationSession:
        """Convert dictionary to ConversationSession object"""
        from datetime import datetime, timezone
        
        # Parse timestamps
        created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        last_activity = datetime.fromisoformat(data['last_activity'].replace('Z', '+00:00'))
        ended_at = datetime.fromisoformat(data['ended_at'].replace('Z', '+00:00')) if data.get('ended_at') else None
        
        # Parse user profile
        user_profile_data = data['user_profile']
        user_profile = self._dict_to_user_profile(user_profile_data)
        
        # Parse messages
        messages = []
        for msg_data in data.get('messages', []):
            message = ConversationMessage(
                message_id=msg_data['message_id'],
                conversation_id=msg_data['conversation_id'],
                user_id=msg_data['user_id'],
                timestamp=datetime.fromisoformat(msg_data['timestamp'].replace('Z', '+00:00')),
                content=msg_data['content'],
                is_from_user=msg_data['is_from_user'],
                message_type=msg_data.get('message_type', 'text'),
                conversation_stage=ConversationStage(msg_data['conversation_stage']),
                conversation_step=ConversationStep(msg_data['conversation_step']),
                intent=UserIntent(msg_data['intent']) if msg_data.get('intent') else None,
                intent_confidence=msg_data.get('intent_confidence', 0.0),
                sentiment=SentimentLabel(msg_data['sentiment']) if msg_data.get('sentiment') else None,
                sentiment_score=msg_data.get('sentiment_score', 0.0),
                entities=msg_data.get('entities', []),
                response_time_seconds=msg_data.get('response_time_seconds'),
                features=msg_data.get('features', {}),
                embeddings=msg_data.get('embeddings')
            )
            messages.append(message)
        
        # Parse metrics
        metrics_data = data.get('metrics', {})
        metrics = ConversationMetrics(
            message_count=metrics_data.get('message_count', 0),
            avg_response_time_seconds=metrics_data.get('avg_response_time_seconds', 0.0),
            user_message_length_avg=metrics_data.get('user_message_length_avg', 0.0),
            bot_message_length_avg=metrics_data.get('bot_message_length_avg', 0.0),
            failed_attempts=metrics_data.get('failed_attempts', 0),
            consecutive_confusion=metrics_data.get('consecutive_confusion', 0),
            clarification_requests=metrics_data.get('clarification_requests', 0),
            sentiment_score_avg=metrics_data.get('sentiment_score_avg', 0.0),
            satisfaction_score=metrics_data.get('satisfaction_score', 0.0),
            topic_switches=metrics_data.get('topic_switches', 0),
            repetition_count=metrics_data.get('repetition_count', 0),
            stage_progression_time=metrics_data.get('stage_progression_time', {}),
            lead_score=metrics_data.get('lead_score', 0),
            conversion_probability=metrics_data.get('conversion_probability', 0.0),
            estimated_value=metrics_data.get('estimated_value', 0.0)
        )
        
        # Create session
        session = ConversationSession(
            session_id=data['session_id'],
            user_id=data['user_id'],
            phone_number=data['phone_number'],
            created_at=created_at,
            updated_at=updated_at,
            last_activity=last_activity,
            ended_at=ended_at,
            status=ConversationStatus(data['status']),
            current_stage=ConversationStage(data['current_stage']),
            current_step=ConversationStep(data['current_step']),
            user_profile=user_profile,
            messages=messages,
            stage_history=data.get('stage_history', []),
            metrics=metrics,
            lead_score_category=LeadScore(data.get('lead_score_category', 'unqualified')),
            conversion_events=data.get('conversion_events', []),
            scheduling_context=data.get('scheduling_context', {}),
            session_features=data.get('session_features', {}),
            labels=data.get('labels', {}),
            predictions=data.get('predictions', {}),
            schema_version=data.get('schema_version', '1.0')
        )
        
        return session
    
    def _dict_to_user_profile(self, data: Dict[str, Any]) -> UserProfile:
        """Convert dictionary to UserProfile object"""
        from datetime import datetime, timezone
        
        created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        last_interaction = datetime.fromisoformat(data['last_interaction'].replace('Z', '+00:00'))
        
        return UserProfile(
            user_id=data['user_id'],
            phone_number=data['phone_number'],
            created_at=created_at,
            last_interaction=last_interaction,
            parent_name=data.get('parent_name'),
            preferred_name=data.get('preferred_name'),
            child_name=data.get('child_name'),
            child_age=data.get('child_age'),
            program_interests=data.get('program_interests', []),
            availability_preferences=data.get('availability_preferences', {}),
            communication_preferences=data.get('communication_preferences', {}),
            total_interactions=data.get('total_interactions', 0),
            total_messages=data.get('total_messages', 0),
            avg_session_duration=data.get('avg_session_duration', 0.0),
            conversion_events=data.get('conversion_events', []),
            engagement_score=data.get('engagement_score', 0.0),
            churn_probability=data.get('churn_probability', 0.0),
            lifetime_value_prediction=data.get('lifetime_value_prediction', 0.0),
            persona_cluster=data.get('persona_cluster')
        )
    
    def _row_to_session(self, session_row: Any, message_rows: List[Any]) -> ConversationSession:
        """Convert database rows to ConversationSession object"""
        # Extract user profile from joined data
        user_profile = UserProfile(
            user_id=session_row['user_id'],
            phone_number=session_row['phone_number'],
            created_at=session_row['created_at'],
            last_interaction=session_row['last_interaction'],
            parent_name=session_row['parent_name'],
            preferred_name=session_row['preferred_name'],
            child_name=session_row['child_name'],
            child_age=session_row['child_age'],
            program_interests=json.loads(session_row['program_interests']) if session_row['program_interests'] else [],
            availability_preferences=json.loads(session_row['availability_preferences']) if session_row['availability_preferences'] else {},
            communication_preferences=json.loads(session_row['communication_preferences']) if session_row['communication_preferences'] else {},
            total_interactions=session_row['total_interactions'],
            total_messages=session_row['total_messages'],
            avg_session_duration=float(session_row['avg_session_duration']) if session_row['avg_session_duration'] else 0.0,
            conversion_events=json.loads(session_row['conversion_events']) if session_row['conversion_events'] else [],
            engagement_score=float(session_row['engagement_score']) if session_row['engagement_score'] else 0.0,
            churn_probability=float(session_row['churn_probability']) if session_row['churn_probability'] else 0.0,
            lifetime_value_prediction=float(session_row['lifetime_value_prediction']) if session_row['lifetime_value_prediction'] else 0.0,
            persona_cluster=session_row['persona_cluster']
        )
        
        # Convert messages
        messages = []
        for msg_row in message_rows:
            message = ConversationMessage(
                message_id=msg_row['message_id'],
                conversation_id=msg_row['conversation_id'],
                user_id=msg_row['user_id'],
                timestamp=msg_row['timestamp'],
                content=msg_row['content'],
                is_from_user=msg_row['is_from_user'],
                message_type=msg_row['message_type'],
                conversation_stage=ConversationStage(msg_row['conversation_stage']),
                conversation_step=ConversationStep(msg_row['conversation_step']),
                intent=UserIntent(msg_row['intent']) if msg_row['intent'] else None,
                intent_confidence=float(msg_row['intent_confidence']) if msg_row['intent_confidence'] else 0.0,
                sentiment=SentimentLabel(msg_row['sentiment']) if msg_row['sentiment'] else None,
                sentiment_score=float(msg_row['sentiment_score']) if msg_row['sentiment_score'] else 0.0,
                entities=json.loads(msg_row['entities']) if msg_row['entities'] else [],
                response_time_seconds=float(msg_row['response_time_seconds']) if msg_row['response_time_seconds'] else None,
                features=json.loads(msg_row['features']) if msg_row['features'] else {},
                embeddings=msg_row['embeddings']
            )
            messages.append(message)
        
        # Parse metrics from session data
        metrics = ConversationMetrics(
            message_count=session_row['message_count'],
            failed_attempts=session_row['failed_attempts'],
            sentiment_score_avg=float(session_row['sentiment_score_avg']) if session_row['sentiment_score_avg'] else 0.0,
            satisfaction_score=float(session_row['satisfaction_score']) if session_row['satisfaction_score'] else 0.0,
            lead_score=session_row['lead_score'],
            conversion_probability=float(session_row['conversion_probability']) if session_row['conversion_probability'] else 0.0,
            estimated_value=float(session_row['estimated_value']) if session_row['estimated_value'] else 0.0
        )
        
        # Create session
        session = ConversationSession(
            session_id=session_row['session_id'],
            user_id=session_row['user_id'],
            phone_number=session_row['phone_number'],
            created_at=session_row['created_at'],
            updated_at=session_row['updated_at'],
            last_activity=session_row['last_activity'],
            ended_at=session_row['ended_at'],
            status=ConversationStatus(session_row['status']),
            current_stage=ConversationStage(session_row['current_stage']),
            current_step=ConversationStep(session_row['current_step']),
            user_profile=user_profile,
            messages=messages,
            stage_history=json.loads(session_row['stage_history']) if session_row['stage_history'] else [],
            metrics=metrics,
            lead_score_category=LeadScore(session_row['lead_score_category']),
            conversion_events=json.loads(session_row['conversion_events']) if session_row['conversion_events'] else [],
            scheduling_context=json.loads(session_row['scheduling_context']) if session_row['scheduling_context'] else {},
            session_features=json.loads(session_row['session_features']) if session_row['session_features'] else {},
            labels=json.loads(session_row['labels']) if session_row['labels'] else {},
            predictions=json.loads(session_row['predictions']) if session_row['predictions'] else {},
            schema_version=session_row['schema_version']
        )
        
        return session
    
    def _row_to_user_profile(self, row: Any) -> UserProfile:
        """Convert database row to UserProfile object"""
        return UserProfile(
            user_id=row['user_id'],
            phone_number=row['phone_number'],
            created_at=row['created_at'],
            last_interaction=row['last_interaction'],
            parent_name=row['parent_name'],
            preferred_name=row['preferred_name'],
            child_name=row['child_name'],
            child_age=row['child_age'],
            program_interests=json.loads(row['program_interests']) if row['program_interests'] else [],
            availability_preferences=json.loads(row['availability_preferences']) if row['availability_preferences'] else {},
            communication_preferences=json.loads(row['communication_preferences']) if row['communication_preferences'] else {},
            total_interactions=row['total_interactions'],
            total_messages=row['total_messages'],
            avg_session_duration=float(row['avg_session_duration']) if row['avg_session_duration'] else 0.0,
            conversion_events=json.loads(row['conversion_events']) if row['conversion_events'] else [],
            engagement_score=float(row['engagement_score']) if row['engagement_score'] else 0.0,
            churn_probability=float(row['churn_probability']) if row['churn_probability'] else 0.0,
            lifetime_value_prediction=float(row['lifetime_value_prediction']) if row['lifetime_value_prediction'] else 0.0,
            persona_cluster=row['persona_cluster']
        )

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Global service instance
conversation_memory_service = ConversationMemoryService()

# Context manager for service lifecycle
@asynccontextmanager
async def memory_service_lifespan():
    """Context manager for memory service lifecycle"""
    await conversation_memory_service.initialize()
    try:
        yield conversation_memory_service
    finally:
        await conversation_memory_service.cleanup()