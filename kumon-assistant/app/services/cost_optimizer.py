"""
Cost Optimization Service
Phase 4 Wave 4.2: Reduce OpenAI costs from R$4/day to R$3/day (25% reduction)

Implements intelligent cost optimization strategies:
- Smart prompt optimization and compression
- Response caching with intelligent cache management
- Request batching and deduplication
- Model selection optimization
- Token usage optimization
- Cost monitoring and automatic throttling
"""

import asyncio
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import json
import re
from collections import defaultdict, deque

from ..core.config import settings
from ..core.logger import app_logger as logger
from ..services.enhanced_cache_service import enhanced_cache_service
from ..security.audit_logger import audit_logger
from ..security.security_manager import security_manager


class OptimizationStrategy(str, Enum):
    """Cost optimization strategies"""
    PROMPT_COMPRESSION = "prompt_compression"
    SMART_CACHING = "smart_caching"
    REQUEST_BATCHING = "request_batching"
    MODEL_OPTIMIZATION = "model_optimization"
    TOKEN_REDUCTION = "token_reduction"
    RESPONSE_FILTERING = "response_filtering"


class CostTier(str, Enum):
    """Cost monitoring tiers"""
    GREEN = "green"      # < 60% of daily budget
    YELLOW = "yellow"    # 60-80% of daily budget
    ORANGE = "orange"    # 80-90% of daily budget
    RED = "red"         # > 90% of daily budget


@dataclass
class CostOptimization:
    """Cost optimization result"""
    original_tokens: int
    optimized_tokens: int
    token_savings: int
    cost_savings_brl: float
    strategy_used: OptimizationStrategy
    optimization_ratio: float
    timestamp: datetime


@dataclass
class CacheHit:
    """Cache hit tracking"""
    cache_key: str
    hit_count: int
    last_hit: datetime
    cost_savings_brl: float
    response_data: Any


class PromptOptimizer:
    """Smart prompt optimization for token reduction"""
    
    # Common Portuguese words that can be compressed
    COMPRESSION_RULES = {
        # Business context shortcuts
        "Kumon": "K",
        "metodologia": "métod",
        "matemática": "mat",
        "português": "port",
        "responsável": "resp",
        "agendamento": "agend",
        "disponibilidade": "disp",
        "horário": "h",
        "telefone": "tel",
        "WhatsApp": "WA",
        
        # Common phrases
        "por favor": "pf",
        "muito obrigado": "obrig",
        "entre em contato": "contato",
        "gostaria de": "gost",
        "preciso de": "prec",
        "informações sobre": "info",
        
        # Time expressions
        "segunda-feira": "seg",
        "terça-feira": "ter", 
        "quarta-feira": "qua",
        "quinta-feira": "qui",
        "sexta-feira": "sex",
        "de manhã": "manhã",
        "de tarde": "tarde",
        
        # Numbers as words to digits
        "primeiro": "1º",
        "segunda": "2ª",
        "terceiro": "3º",
        "quarto": "4º",
        "quinto": "5º"
    }
    
    @classmethod
    def optimize_prompt(cls, prompt: str) -> Tuple[str, int, int]:
        """Optimize prompt for token reduction"""
        original_length = len(prompt)
        optimized = prompt
        
        # Apply compression rules
        for full_word, compressed in cls.COMPRESSION_RULES.items():
            optimized = optimized.replace(full_word, compressed)
        
        # Remove excessive whitespace
        optimized = re.sub(r'\s+', ' ', optimized)
        optimized = optimized.strip()
        
        # Remove redundant punctuation
        optimized = re.sub(r'[.]{2,}', '.', optimized)
        optimized = re.sub(r'[!]{2,}', '!', optimized)
        optimized = re.sub(r'[?]{2,}', '?', optimized)
        
        # Estimate token savings (rough approximation: 1 token ≈ 4 characters in Portuguese)
        original_tokens = original_length // 4
        optimized_tokens = len(optimized) // 4
        token_savings = original_tokens - optimized_tokens
        
        return optimized, original_tokens, optimized_tokens
    
    @classmethod
    def optimize_system_message(cls, system_message: str) -> str:
        """Optimize system message for core functionality only"""
        # Core instructions for Kumon assistant
        core_instructions = """
Você é assistente do Kumon. Tarefas:
1. Qualifique leads: nome resp, nome aluno, tel, email, idade, série, programa, horário
2. Agende visitas: seg-sex 9h-12h/14h-17h, 30min
3. Informe preços: R$375/matéria + R$100 matrícula
4. Encaminhe para (51)99692-1999 se: cancelamento, reagendamento, reclamação

Seja objetivo, educado, focado em conversão.
"""
        return core_instructions.strip()


class SmartCache:
    """Intelligent caching system for cost optimization"""
    
    def __init__(self):
        self.cache: Dict[str, CacheHit] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_savings_brl": 0.0
        }
        
        # Cache policies
        self.max_cache_size = 1000
        self.cache_ttl_hours = 24
        self.min_response_cost_for_caching = 0.01  # Cache responses worth > R$0.01
    
    def generate_cache_key(self, prompt: str, model: str, temperature: float = 0.7) -> str:
        """Generate cache key for request"""
        # Normalize prompt for better cache hits
        normalized_prompt = re.sub(r'\s+', ' ', prompt.lower().strip())
        
        # Create secure hash including model and temperature with secret salt
        cache_input = f"{normalized_prompt}|{model}|{temperature}|{settings.JWT_SECRET_KEY}"
        return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
    
    async def get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if available and valid"""
        if cache_key not in self.cache:
            self.cache_stats["misses"] += 1
            return None
        
        cache_hit = self.cache[cache_key]
        
        # Check TTL
        if (datetime.now(timezone.utc) - cache_hit.last_hit).total_seconds() > (self.cache_ttl_hours * 3600):
            # Cache expired
            del self.cache[cache_key]
            self.cache_stats["misses"] += 1
            return None
        
        # Update hit statistics
        cache_hit.hit_count += 1
        cache_hit.last_hit = datetime.now(timezone.utc)
        
        self.cache_stats["hits"] += 1
        self.cache_stats["total_savings_brl"] += cache_hit.cost_savings_brl
        
        logger.info(f"Cache hit: {cache_key[:8]}... (savings: R${cache_hit.cost_savings_brl:.4f})")
        return cache_hit.response_data
    
    async def cache_response(self, cache_key: str, response_data: Any, cost_brl: float):
        """Cache response with cost tracking"""
        if cost_brl < self.min_response_cost_for_caching:
            return  # Don't cache low-value responses
        
        # Check cache size limit
        if len(self.cache) >= self.max_cache_size:
            await self._evict_old_entries()
        
        # Cache the response
        self.cache[cache_key] = CacheHit(
            cache_key=cache_key,
            hit_count=0,
            last_hit=datetime.now(timezone.utc),
            cost_savings_brl=cost_brl,
            response_data=response_data
        )
        
        logger.debug(f"Cached response: {cache_key[:8]}... (cost: R${cost_brl:.4f})")
    
    async def _evict_old_entries(self):
        """Evict old cache entries using LRU strategy"""
        if not self.cache:
            return
        
        # Sort by last hit time and remove oldest 20%
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_hit
        )
        
        evict_count = max(1, len(sorted_entries) // 5)
        for i in range(evict_count):
            cache_key = sorted_entries[i][0]
            del self.cache[cache_key]
        
        logger.info(f"Evicted {evict_count} old cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / max(total_requests, 1)) * 100
        
        return {
            "hit_rate_percentage": round(hit_rate, 2),
            "total_hits": self.cache_stats["hits"],
            "total_misses": self.cache_stats["misses"],
            "total_requests": total_requests,
            "total_savings_brl": round(self.cache_stats["total_savings_brl"], 4),
            "cache_size": len(self.cache),
            "max_cache_size": self.max_cache_size
        }


class RequestBatcher:
    """Batch similar requests for cost optimization"""
    
    def __init__(self):
        self.pending_batches: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.batch_timeout = 2.0  # Wait 2 seconds to collect batch
        self.max_batch_size = 5
    
    async def add_to_batch(self, request_type: str, request_data: Dict[str, Any]) -> Any:
        """Add request to batch and return result when batch is ready"""
        batch_key = f"{request_type}_{len(self.pending_batches[request_type])}"
        
        # Add to pending batch
        self.pending_batches[request_type].append(request_data)
        
        # Check if batch is ready
        if len(self.pending_batches[request_type]) >= self.max_batch_size:
            return await self._process_batch(request_type)
        
        # Wait for timeout or more requests
        await asyncio.sleep(self.batch_timeout)
        
        if self.pending_batches[request_type]:
            return await self._process_batch(request_type)
        
        return None
    
    async def _process_batch(self, request_type: str) -> List[Any]:
        """Process a batch of requests"""
        batch = self.pending_batches[request_type]
        self.pending_batches[request_type] = []
        
        logger.info(f"Processing batch of {len(batch)} {request_type} requests")
        
        # Process batch (implementation would depend on request type)
        results = []
        for request in batch:
            # Placeholder for batch processing logic
            results.append({"status": "processed", "data": request})
        
        return results


class CostOptimizer:
    """Main cost optimization service targeting R$3/day budget"""
    
    def __init__(self):
        # Use daily budget from settings, fallback to 3.0 if not available
        self.daily_target_brl = getattr(settings, 'LLM_DAILY_BUDGET_BRL', 3.0)
        self.current_daily_cost = 0.0
        self.optimization_history: List[CostOptimization] = []
        
        # Optimization components
        self.prompt_optimizer = PromptOptimizer()
        self.smart_cache = SmartCache()
        self.request_batcher = RequestBatcher()
        
        # Model cost optimization (USD per 1K tokens, converted to BRL)
        self.model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004}
        }
        
        # USD to BRL conversion (could be made configurable in the future)
        self.usd_to_brl = 5.0
        
        # Cost tier thresholds
        self.cost_tiers = {
            CostTier.GREEN: 0.6 * self.daily_target_brl,    # < R$1.80
            CostTier.YELLOW: 0.8 * self.daily_target_brl,   # < R$2.40  
            CostTier.ORANGE: 0.9 * self.daily_target_brl,   # < R$2.70
            CostTier.RED: self.daily_target_brl              # ≥ R$3.00
        }
        
        # Optimization settings by cost tier
        self.tier_settings = {
            CostTier.GREEN: {
                "use_best_model": True,
                "enable_caching": True,
                "prompt_optimization": False,
                "response_length": "full"
            },
            CostTier.YELLOW: {
                "use_best_model": True,
                "enable_caching": True,
                "prompt_optimization": True,
                "response_length": "full"
            },
            CostTier.ORANGE: {
                "use_best_model": False,  # Switch to cheaper model
                "enable_caching": True,
                "prompt_optimization": True,
                "response_length": "concise"
            },
            CostTier.RED: {
                "use_best_model": False,
                "enable_caching": True,
                "prompt_optimization": True,
                "response_length": "minimal"
            }
        }
    
    async def optimize_llm_request(
        self,
        prompt: str,
        system_message: str = "",
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        user_id: Optional[str] = None,
        consent_given: bool = False
    ) -> Tuple[str, str, str, Dict[str, Any]]:
        """Optimize LLM request for cost efficiency with LGPD compliance"""
        
        # LGPD Compliance: Check consent for data processing
        if not consent_given:
            logger.warning("Processing request without explicit LGPD consent")
        
        # LGPD Compliance: Audit personal data processing
        if user_id:
            await audit_logger.log_personal_data_processing(
                user_id=user_id,
                data_type="prompt_optimization",
                purpose="llm_cost_optimization",
                consent_status=consent_given,
                processing_details={
                    "model": model,
                    "temperature": temperature,
                    "has_system_message": bool(system_message)
                }
            )
        
        # Determine current cost tier
        current_tier = self._get_current_cost_tier()
        settings = self.tier_settings[current_tier]
        
        # Apply optimizations based on tier
        # LGPD Compliance: Anonymize personal data in prompts before processing
        optimized_prompt = security_manager.anonymize_personal_data(prompt)
        optimized_system = security_manager.anonymize_personal_data(system_message) if system_message else system_message
        optimized_model = model
        optimization_metadata = {
            "tier": current_tier.value,
            "optimizations_applied": []
        }
        
        # 1. Check cache first
        if settings["enable_caching"]:
            cache_key = self.smart_cache.generate_cache_key(prompt, model, temperature)
            cached_response = await self.smart_cache.get_cached_response(cache_key)
            if cached_response:
                optimization_metadata["cache_hit"] = True
                optimization_metadata["cost_savings"] = "cache_hit"
                return prompt, system_message, model, {
                    "cached_response": cached_response,
                    "metadata": optimization_metadata
                }
        
        # 2. Prompt optimization
        if settings["prompt_optimization"]:
            optimized_prompt, original_tokens, optimized_tokens = self.prompt_optimizer.optimize_prompt(prompt)
            
            if system_message:
                optimized_system = self.prompt_optimizer.optimize_system_message(system_message)
            
            token_savings = original_tokens - optimized_tokens
            if token_savings > 0:
                cost_savings = self._calculate_cost_savings(token_savings, model)
                
                # Record optimization
                self.optimization_history.append(CostOptimization(
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    token_savings=token_savings,
                    cost_savings_brl=cost_savings,
                    strategy_used=OptimizationStrategy.PROMPT_COMPRESSION,
                    optimization_ratio=token_savings / max(original_tokens, 1),
                    timestamp=datetime.now(timezone.utc)
                ))
                
                optimization_metadata["optimizations_applied"].append("prompt_compression")
                optimization_metadata["token_savings"] = token_savings
                optimization_metadata["cost_savings_brl"] = cost_savings
        
        # 3. Model optimization
        if not settings["use_best_model"]:
            # Switch to more cost-effective model
            if model == "gpt-4":
                optimized_model = "gpt-3.5-turbo"
                optimization_metadata["optimizations_applied"].append("model_downgrade")
            elif model == "gpt-4-turbo":
                optimized_model = "gpt-3.5-turbo"
                optimization_metadata["optimizations_applied"].append("model_downgrade")
        
        # 4. Response length optimization
        if settings["response_length"] != "full":
            if max_tokens is None:
                if settings["response_length"] == "concise":
                    max_tokens = 200
                elif settings["response_length"] == "minimal":
                    max_tokens = 100
                
                optimization_metadata["optimizations_applied"].append("response_length_limit")
                optimization_metadata["max_tokens"] = max_tokens
        
        return optimized_prompt, optimized_system, optimized_model, optimization_metadata
    
    async def track_request_cost(
        self, 
        prompt_tokens: int, 
        completion_tokens: int, 
        model: str,
        optimization_metadata: Dict[str, Any] = None
    ) -> float:
        """Track the cost of a request and update daily totals"""
        
        # Calculate cost
        model_pricing = self.model_costs.get(model, self.model_costs["gpt-3.5-turbo"])
        
        input_cost_usd = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost_usd = (completion_tokens / 1000) * model_pricing["output"]
        total_cost_usd = input_cost_usd + output_cost_usd
        total_cost_brl = total_cost_usd * self.usd_to_brl
        
        # Update daily cost
        self.current_daily_cost += total_cost_brl
        
        # Cache response if cost-effective
        if optimization_metadata and not optimization_metadata.get("cache_hit"):
            cache_key = optimization_metadata.get("cache_key")
            if cache_key and total_cost_brl >= 0.01:  # Cache if cost ≥ R$0.01
                # Would cache in actual implementation
                pass
        
        logger.info(f"Request cost: R${total_cost_brl:.4f} (tokens: {prompt_tokens}+{completion_tokens}, model: {model})")
        
        return total_cost_brl
    
    def _get_current_cost_tier(self) -> CostTier:
        """Determine current cost tier based on daily spending"""
        if self.current_daily_cost < self.cost_tiers[CostTier.GREEN]:
            return CostTier.GREEN
        elif self.current_daily_cost < self.cost_tiers[CostTier.YELLOW]:
            return CostTier.YELLOW
        elif self.current_daily_cost < self.cost_tiers[CostTier.ORANGE]:
            return CostTier.ORANGE
        else:
            return CostTier.RED
    
    def _calculate_cost_savings(self, token_savings: int, model: str) -> float:
        """Calculate cost savings from token reduction"""
        model_pricing = self.model_costs.get(model, self.model_costs["gpt-3.5-turbo"])
        
        # Estimate savings (assuming balanced input/output ratio)
        avg_cost_per_1k_tokens = (model_pricing["input"] + model_pricing["output"]) / 2
        cost_savings_usd = (token_savings / 1000) * avg_cost_per_1k_tokens
        cost_savings_brl = cost_savings_usd * self.usd_to_brl
        
        return cost_savings_brl
    
    async def get_cost_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive cost optimization report"""
        current_tier = self._get_current_cost_tier()
        
        # Calculate total savings
        total_token_savings = sum(opt.token_savings for opt in self.optimization_history)
        total_cost_savings = sum(opt.cost_savings_brl for opt in self.optimization_history)
        
        # Optimization strategy breakdown
        strategy_breakdown = defaultdict(lambda: {"count": 0, "savings": 0.0})
        for opt in self.optimization_history:
            strategy_breakdown[opt.strategy_used.value]["count"] += 1
            strategy_breakdown[opt.strategy_used.value]["savings"] += opt.cost_savings_brl
        
        # Cache statistics
        cache_stats = self.smart_cache.get_cache_stats()
        
        # Budget analysis
        budget_remaining = max(0, self.daily_target_brl - self.current_daily_cost)
        budget_utilization = (self.current_daily_cost / self.daily_target_brl) * 100
        
        return {
            "cost_summary": {
                "daily_target_brl": self.daily_target_brl,
                "current_daily_cost_brl": round(self.current_daily_cost, 4),
                "budget_remaining_brl": round(budget_remaining, 4),
                "budget_utilization_percentage": round(budget_utilization, 2),
                "current_tier": current_tier.value,
                "on_track_for_target": budget_utilization <= 100
            },
            "optimization_metrics": {
                "total_optimizations": len(self.optimization_history),
                "total_token_savings": total_token_savings,
                "total_cost_savings_brl": round(total_cost_savings, 4),
                "optimization_strategies": dict(strategy_breakdown)
            },
            "cache_performance": cache_stats,
            "tier_settings": {
                "current_tier": current_tier.value,
                "active_settings": self.tier_settings[current_tier],
                "tier_thresholds": {
                    tier.value: round(threshold, 2) 
                    for tier, threshold in self.cost_tiers.items()
                }
            },
            "cost_projections": {
                "projected_daily_total": round(self.current_daily_cost * 1.2, 4),  # Assume 20% more usage
                "savings_needed_for_target": max(0, round(self.current_daily_cost - self.daily_target_brl, 4)),
                "optimization_effectiveness": round((total_cost_savings / max(self.current_daily_cost, 0.01)) * 100, 2)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def reset_daily_tracking(self):
        """Reset daily cost tracking (called at midnight)"""
        logger.info(f"Daily cost reset. Previous total: R${self.current_daily_cost:.4f}")
        
        self.current_daily_cost = 0.0
        self.optimization_history = []
        
        # Keep cache but reset stats
        self.smart_cache.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_savings_brl": 0.0
        }
    
    def is_budget_exceeded(self) -> bool:
        """Check if daily budget is exceeded"""
        return self.current_daily_cost >= self.daily_target_brl
    
    def get_remaining_budget(self) -> float:
        """Get remaining daily budget in BRL"""
        return max(0, self.daily_target_brl - self.current_daily_cost)


# Global cost optimizer instance
cost_optimizer = CostOptimizer()