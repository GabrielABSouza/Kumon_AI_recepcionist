# app/core/shadow_metrics_collector.py
"""
Shadow Metrics Collector - Coleta Estruturada JSONL para Calibração

Registra por interação (JSONL) as métricas necessárias para:
- Disagreement rate: v1.next_stage != v2.next_stage  
- Fallback/handoff rate do V2
- Slot completeness: % interações com missing_slots == 0
- Latência p95 por estágio
- Distribuições de combined_score por strategy
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import re
from .feature_flags import feature_flags

logger = logging.getLogger(__name__)


class ShadowMetricsCollector:
    """
    Coleta métricas estruturadas do shadow traffic para calibração de thresholds
    
    Formato JSONL com todas as métricas necessárias para otimização F1 proxy
    """
    
    def __init__(self, metrics_file: Optional[str] = None):
        """Initialize shadow metrics collector"""
        self.metrics_file = Path(metrics_file or "shadow_metrics.jsonl")
        self.ensure_metrics_file()
        
        logger.info(f"ShadowMetricsCollector initialized - file: {self.metrics_file}")
    
    def ensure_metrics_file(self):
        """Ensure metrics file exists and has proper headers"""
        if not self.metrics_file.exists():
            # Create file with JSON schema header as comment
            with open(self.metrics_file, 'w') as f:
                f.write('# Shadow Traffic Metrics - JSONL Format\n')
                f.write('# Schema: session_id, timestamp, utterance, v1_data, v2_data, entity_flags, delivery_outcome, latencies\n')
    
    def collect_interaction_metrics(
        self,
        session_id: str,
        user_message: str,
        v1_result: Dict[str, Any],
        v2_result: Dict[str, Any],
        routing_decision: Optional[Dict[str, Any]] = None,
        latencies: Optional[Dict[str, float]] = None
    ):
        """
        Coleta métricas completas de uma interação shadow
        
        Args:
            session_id: ID da sessão
            user_message: Mensagem do usuário
            v1_result: Resultado do V1 legacy
            v2_result: Resultado do V2 shadow
            routing_decision: Decisão de roteamento V2
            latencies: Tempos de execução por bloco
        """
        
        try:
            # Base metrics
            timestamp = datetime.now().isoformat()
            utterance_hash = self._hash_message(user_message)
            
            # V1 data extraction
            v1_data = self._extract_v1_metrics(v1_result)
            
            # V2 data extraction
            v2_data = self._extract_v2_metrics(v2_result, routing_decision)
            
            # Entity flags (temporal, service, professional)
            entity_flags = self._extract_entity_flags(user_message)
            
            # Delivery outcome classification
            delivery_outcome = self._classify_delivery_outcome(routing_decision, v2_result)
            
            # Latency breakdown
            latency_breakdown = self._process_latencies(latencies or {})
            
            # Slot completeness analysis
            slot_analysis = self._analyze_slot_completeness(v1_result, v2_result)
            
            # Agreement analysis
            agreement_analysis = self._analyze_v1_v2_agreement(v1_data, v2_data)
            
            # Compose full metrics record
            metrics_record = {
                "session_id": session_id,
                "timestamp": timestamp,
                "utterance_hash": utterance_hash,
                
                # V1 Legacy Data
                "v1_next_stage": v1_data["next_stage"],
                "v1_current_step": v1_data["current_step"],
                "v1_strategy": v1_data.get("strategy"),
                
                # V2 Shadow Data
                "v2_intent": v2_data["intent"],
                "v2_intent_score": v2_data["intent_score"],
                "v2_pattern_score": v2_data["pattern_score"],
                "v2_combined_score": v2_data["combined_score"],
                "v2_next_stage": v2_data["next_stage"],
                "v2_strategy": v2_data["strategy"],
                "v2_required_slots": v2_data["required_slots"],
                "v2_missing_slots": v2_data["missing_slots"],
                "v2_threshold_action": v2_data["threshold_action"],
                
                # Entity Detection Flags
                "entity_temporal": entity_flags["temporal"],
                "entity_service": entity_flags["service"],
                "entity_professional": entity_flags["professional"],
                
                # Outcome Classification
                "delivery_outcome": delivery_outcome,
                
                # Latency Breakdown (ms)
                "latency_router_ms": latency_breakdown["router"],
                "latency_node_ms": latency_breakdown["node"], 
                "latency_delivery_ms": latency_breakdown["delivery"],
                "latency_total_ms": latency_breakdown["total"],
                
                # Analysis Flags
                "stage_disagreement": agreement_analysis["stage_disagreement"],
                "v1_slots_complete": slot_analysis["v1_complete"],
                "v2_slots_complete": slot_analysis["v2_complete"],
                "v2_extraction_superior": slot_analysis["v2_superior"],
                "agree_when_v1_template": agreement_analysis["agree_when_v1_template"],
                
                # Quality Proxy Indicators
                "quality_proxy_positive": self._compute_quality_proxy(
                    slot_analysis, agreement_analysis, v1_data, v2_data
                )
            }
            
            # Write to JSONL file
            self._write_metrics_record(metrics_record)
            
            logger.debug(f"Shadow metrics collected for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to collect shadow metrics for {session_id}: {e}")
    
    def _extract_v1_metrics(self, v1_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metrics from V1 legacy result"""
        return {
            "next_stage": v1_result.get("current_stage", "unknown"),
            "current_step": v1_result.get("current_step", "unknown"),
            "strategy": self._infer_v1_strategy(v1_result)
        }
    
    def _extract_v2_metrics(self, v2_result: Dict[str, Any], routing_decision: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract V2 shadow metrics including routing decision"""
        
        routing = routing_decision or {}
        
        return {
            "intent": routing.get("detected_intent", "unknown"),
            "intent_score": routing.get("intent_confidence", 0.0),
            "pattern_score": routing.get("pattern_confidence", 0.0), 
            "combined_score": routing.get("final_confidence", 0.0),
            "next_stage": v2_result.get("current_stage", "unknown"),
            "strategy": routing.get("threshold_action", "unknown"),
            "required_slots": v2_result.get("required_slots", []),
            "missing_slots": v2_result.get("qualification_missing_fields", []),
            "threshold_action": routing.get("threshold_action", "proceed")
        }
    
    def _extract_entity_flags(self, message: str) -> Dict[str, bool]:
        """Extract entity detection flags from user message"""
        
        # Temporal entities
        temporal_patterns = [
            r'\b(hoje|amanha|amanh[ãa]|depois de amanha|ontem)\b',
            r'\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\b',
            r'\b\d{1,2}:\d{2}\b',  # time format
            r'\b\d{1,2}/\d{1,2}\b',  # date format
            r'\b(de manh[ãa]|de tarde|[àa] noite|meio dia)\b'
        ]
        
        # Service entities (Kumon specific)
        service_patterns = [
            r'\b(matem[aá]tica|portugu[eê]s|ingl[eê]s)\b',
            r'\b(kumon|programa|m[eé]todo|metodologia)\b',
            r'\b(avan[cç]ado|intermedi[aá]rio|inicial|b[aá]sico)\b',
            r'\b(ensino fundamental|ensino m[eé]dio|educação infantil)\b'
        ]
        
        # Professional entities (generic education)
        professional_patterns = [
            r'\b(professor|professora|orientador|orientadora)\b',
            r'\b(instrutor|instrutora|educador|educadora)\b',
            r'\b(coordenador|coordenadora|respons[aá]vel)\b'
        ]
        
        return {
            "temporal": self._has_pattern(message, temporal_patterns),
            "service": self._has_pattern(message, service_patterns),
            "professional": self._has_pattern(message, professional_patterns)
        }
    
    def _classify_delivery_outcome(self, routing_decision: Optional[Dict[str, Any]], v2_result: Dict[str, Any]) -> str:
        """Classify delivery outcome based on routing decision"""
        
        if not routing_decision:
            return "unknown"
        
        threshold_action = routing_decision.get("threshold_action", "proceed")
        
        if threshold_action in ["template", "use_template"]:
            return "template"
        elif threshold_action in ["llm_rag", "use_llm"]:
            return "llm_rag"
        elif threshold_action in ["handoff", "fallback", "human_handoff"]:
            return "handoff"
        else:
            return "fallback"
    
    def _process_latencies(self, latencies: Dict[str, float]) -> Dict[str, float]:
        """Process and normalize latency measurements"""
        
        router_time = latencies.get("routing_ms", 0.0)
        node_time = latencies.get("node_ms", 0.0)
        delivery_time = latencies.get("delivery_ms", 0.0)
        total_time = latencies.get("total_ms", router_time + node_time + delivery_time)
        
        return {
            "router": router_time,
            "node": node_time,
            "delivery": delivery_time,
            "total": total_time
        }
    
    def _analyze_slot_completeness(self, v1_result: Dict[str, Any], v2_result: Dict[str, Any]) -> Dict[str, bool]:
        """Analyze slot completeness for V1 vs V2"""
        
        # V1 completeness (basic heuristic)
        v1_complete = self._is_v1_slots_complete(v1_result)
        
        # V2 completeness
        missing_slots = v2_result.get("qualification_missing_fields", [])
        v2_complete = len(missing_slots) == 0
        
        # V2 superior extraction (extracted data V1 missed)
        v2_superior = self._is_v2_extraction_superior(v1_result, v2_result)
        
        return {
            "v1_complete": v1_complete,
            "v2_complete": v2_complete,
            "v2_superior": v2_superior
        }
    
    def _analyze_v1_v2_agreement(self, v1_data: Dict[str, Any], v2_data: Dict[str, Any]) -> Dict[str, bool]:
        """Analyze agreement between V1 and V2 decisions"""
        
        stage_disagreement = v1_data["next_stage"] != v2_data["next_stage"]
        
        # Agreement when V1 is in template mode (good proxy)
        v1_template_mode = v1_data.get("strategy") == "template"
        agree_when_v1_template = not stage_disagreement and v1_template_mode
        
        return {
            "stage_disagreement": stage_disagreement,
            "agree_when_v1_template": agree_when_v1_template
        }
    
    def _compute_quality_proxy(
        self, 
        slot_analysis: Dict[str, bool], 
        agreement_analysis: Dict[str, bool],
        v1_data: Dict[str, Any],
        v2_data: Dict[str, Any]
    ) -> bool:
        """
        Compute quality proxy for F1 optimization
        
        Positive = "boa decisão" = alta slot completeness AND (acordo com V1 OR extração superior à V1)
        """
        
        high_slot_completeness = slot_analysis["v2_complete"]
        agree_with_v1 = not agreement_analysis["stage_disagreement"]
        superior_extraction = slot_analysis["v2_superior"]
        
        # Good decision criteria
        good_decision = high_slot_completeness and (agree_with_v1 or superior_extraction)
        
        return good_decision
    
    def _infer_v1_strategy(self, v1_result: Dict[str, Any]) -> Optional[str]:
        """Infer V1 strategy from result (heuristic)"""
        
        # Heuristic based on V1 patterns
        if v1_result.get("greeting_status") == "completed":
            return "template"
        elif v1_result.get("qualification_status") == "completed":
            return "template"
        else:
            return "proceed"
    
    def _is_v1_slots_complete(self, v1_result: Dict[str, Any]) -> bool:
        """Check if V1 has complete slots (heuristic)"""
        
        # Basic completeness check for V1
        has_parent_name = bool(v1_result.get("parent_name"))
        has_child_name = bool(v1_result.get("child_name"))
        
        stage = v1_result.get("current_stage", "greeting")
        
        if stage == "greeting":
            return has_parent_name
        elif stage == "qualification":
            return has_parent_name and has_child_name
        else:
            return False
    
    def _is_v2_extraction_superior(self, v1_result: Dict[str, Any], v2_result: Dict[str, Any]) -> bool:
        """Check if V2 extracted data that V1 missed"""
        
        # Compare key extractions
        v1_child_name = bool(v1_result.get("child_name"))
        v2_child_name = bool(v2_result.get("child_name"))
        
        v1_student_age = bool(v1_result.get("student_age"))
        v2_student_age = bool(v2_result.get("student_age"))
        
        # V2 superior if it extracted something V1 didn't
        return (v2_child_name and not v1_child_name) or (v2_student_age and not v1_student_age)
    
    def _has_pattern(self, message: str, patterns: list) -> bool:
        """Check if message matches any of the patterns"""
        
        message_lower = message.lower()
        
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _hash_message(self, message: str) -> str:
        """Create hash of user message for PII-free logging"""
        if not message:
            return "empty"
        return hashlib.sha256(message.encode('utf-8')).hexdigest()[:16]
    
    def _write_metrics_record(self, record: Dict[str, Any]):
        """Write metrics record to JSONL file"""
        
        try:
            with open(self.metrics_file, 'a') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write metrics record: {e}")
    
    def load_metrics_for_analysis(self, hours_back: Optional[int] = None) -> list:
        """
        Load metrics records for analysis
        
        Args:
            hours_back: Load only records from last N hours
            
        Returns:
            List of metrics records
        """
        
        if not self.metrics_file.exists():
            return []
        
        records = []
        cutoff_time = None
        
        if hours_back:
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        try:
            with open(self.metrics_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        
                        # Filter by time if specified
                        if cutoff_time:
                            record_time = datetime.fromisoformat(record["timestamp"])
                            if record_time < cutoff_time:
                                continue
                        
                        records.append(record)
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse metrics record: {e}")
                        continue
            
            logger.info(f"Loaded {len(records)} metrics records for analysis")
            return records
            
        except Exception as e:
            logger.error(f"Failed to load metrics records: {e}")
            return []


# Global instance
shadow_metrics_collector = ShadowMetricsCollector()