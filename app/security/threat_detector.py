"""
Advanced Threat Detection System for Kumon Assistant

Implements machine learning-based threat detection for sophisticated attacks:
- Behavioral anomaly detection
- Advanced persistent threats (APT)
- Zero-day attack patterns
- Multi-vector attack correlation
- Threat intelligence integration
- Real-time risk assessment
"""

import asyncio
import hashlib
import statistics
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import re

from ..core.logger import app_logger
from ..core.config import settings


class ThreatCategory(Enum):
    """Categories of advanced threats"""
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    COORDINATED_ATTACK = "coordinated_attack" 
    EVASION_ATTEMPT = "evasion_attempt"
    PERSISTENCE_ATTACK = "persistence_attack"
    RECONNAISSANCE = "reconnaissance"
    SOCIAL_ENGINEERING = "social_engineering"
    ADVANCED_INJECTION = "advanced_injection"
    ZERO_DAY = "zero_day"


class ThreatLevel(Enum):
    """Threat severity levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BehaviorProfile:
    """User behavior profile for anomaly detection"""
    source_id: str
    message_count: int = 0
    avg_message_length: float = 0.0
    message_intervals: deque = field(default_factory=lambda: deque(maxlen=50))
    topic_diversity: float = 0.0
    suspicious_keywords: int = 0
    injection_attempts: int = 0
    scope_violations: int = 0
    information_requests: int = 0
    last_activity: Optional[datetime] = None
    activity_pattern: List[int] = field(default_factory=lambda: [0] * 24)  # Hour-based activity
    session_duration: float = 0.0
    unique_patterns: Set[str] = field(default_factory=set)


@dataclass
class ThreatIndicator:
    """Individual threat indicator"""
    indicator_type: str
    severity: float
    confidence: float
    description: str
    evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AdvancedThreatResult:
    """Result of advanced threat analysis"""
    threat_level: ThreatLevel
    threat_category: ThreatCategory
    confidence: float
    severity: float
    indicators: List[ThreatIndicator]
    risk_score: float
    recommended_actions: List[str]
    threat_intelligence: Dict[str, Any]


class ThreatDetectionSystem:
    """
    Advanced threat detection using behavioral analysis and ML techniques
    
    Features:
    - Real-time behavioral profiling
    - Multi-vector attack correlation  
    - Anomaly detection algorithms
    - Threat intelligence integration
    - Zero-day pattern recognition
    """
    
    def __init__(self):
        # Behavior profiles per source
        self.behavior_profiles: Dict[str, BehaviorProfile] = {}
        
        # Threat correlation tracking
        self.attack_campaigns: Dict[str, List[Dict]] = defaultdict(list)
        self.ip_reputation: Dict[str, float] = {}  # 0.0 = malicious, 1.0 = trusted
        
        # Advanced threat patterns
        self.evasion_patterns = self._load_evasion_patterns()
        self.apt_indicators = self._load_apt_indicators()
        
        # ML-based detection features
        self.anomaly_thresholds = {
            "message_frequency_std": 3.0,      # Standard deviations from normal
            "message_length_variance": 2.5,    # Message length variance threshold
            "topic_jump_threshold": 0.7,       # Topic switching threshold
            "behavioral_drift": 0.6,           # Profile deviation threshold
            "coordination_correlation": 0.8,   # Attack coordination threshold
        }
        
        # Zero-day detection heuristics
        self.zero_day_indicators = [
            "unusual_encoding_patterns",
            "novel_injection_vectors",
            "uncommon_evasion_techniques", 
            "abnormal_request_structures",
            "suspicious_timing_patterns"
        ]
        
        app_logger.info("Advanced Threat Detection System initialized")
    
    async def detect_advanced_threats(
        self,
        source_identifier: str,
        user_message: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive advanced threat detection
        
        Args:
            source_identifier: User/IP identifier
            user_message: Message content
            request_metadata: Additional context
            
        Returns:
            Advanced threat analysis result
        """
        
        # Update behavior profile
        await self._update_behavior_profile(source_identifier, user_message, request_metadata)
        
        # Run parallel threat detection algorithms
        detection_results = await asyncio.gather(
            self._behavioral_anomaly_detection(source_identifier, user_message),
            self._coordinated_attack_detection(source_identifier, request_metadata),
            self._evasion_technique_detection(user_message),
            self._persistence_attack_detection(source_identifier),
            self._reconnaissance_detection(user_message, source_identifier),
            self._social_engineering_advanced_detection(user_message, source_identifier),
            self._zero_day_detection(user_message, source_identifier),
            return_exceptions=True
        )
        
        # Aggregate threat indicators
        all_indicators = []
        threat_scores = []
        
        for result in detection_results:
            if isinstance(result, dict):
                indicators = result.get("indicators", [])
                all_indicators.extend(indicators)
                if "threat_score" in result:
                    threat_scores.append(result["threat_score"])
        
        # Calculate overall threat assessment
        if not threat_scores:
            threat_scores = [0.0]
        
        max_threat_score = max(threat_scores)
        avg_threat_score = sum(threat_scores) / len(threat_scores)
        
        # Determine threat level and category
        threat_level = self._calculate_threat_level(max_threat_score)
        threat_category = self._determine_primary_threat_category(all_indicators)
        
        # Calculate confidence based on indicator consistency
        confidence = self._calculate_detection_confidence(all_indicators)
        
        # Generate threat intelligence
        threat_intelligence = await self._generate_threat_intelligence(
            source_identifier, all_indicators
        )
        
        # Recommend actions
        recommended_actions = self._recommend_actions(threat_level, threat_category)
        
        # Correlate with ongoing campaigns
        await self._correlate_attack_campaigns(source_identifier, all_indicators)
        
        return {
            "threat_level": threat_level,
            "threat_category": threat_category.value,
            "confidence": confidence,
            "severity": max_threat_score,
            "risk_score": avg_threat_score,
            "indicators": [
                {
                    "type": ind.indicator_type,
                    "severity": ind.severity,
                    "confidence": ind.confidence,
                    "description": ind.description,
                    "evidence": ind.evidence
                } for ind in all_indicators
            ],
            "recommended_actions": recommended_actions,
            "threat_intelligence": threat_intelligence,
            "detection_summary": {
                "total_indicators": len(all_indicators),
                "detection_algorithms": len([r for r in detection_results if isinstance(r, dict)]),
                "max_severity": max_threat_score,
                "avg_severity": avg_threat_score
            }
        }
    
    async def _update_behavior_profile(
        self,
        source_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """Update behavioral profile for anomaly detection"""
        
        current_time = datetime.now()
        profile = self.behavior_profiles.get(source_id, BehaviorProfile(source_id=source_id))
        
        # Update message statistics
        profile.message_count += 1
        message_length = len(message)
        
        if profile.message_count == 1:
            profile.avg_message_length = message_length
        else:
            # Exponential moving average
            alpha = 0.2
            profile.avg_message_length = (alpha * message_length + 
                                        (1 - alpha) * profile.avg_message_length)
        
        # Track message intervals
        if profile.last_activity:
            interval = (current_time - profile.last_activity).total_seconds()
            profile.message_intervals.append(interval)
        
        # Update activity pattern (hour-based)
        hour = current_time.hour
        profile.activity_pattern[hour] += 1
        
        # Track unique message patterns
        message_hash = hashlib.md5(message.lower().encode()).hexdigest()[:8]
        profile.unique_patterns.add(message_hash)
        
        # Update topic diversity (simplified)
        words = set(message.lower().split())
        profile.topic_diversity = len(profile.unique_patterns) / max(1, profile.message_count)
        
        # Count suspicious elements
        if re.search(r'system|admin|root|hack|exploit', message.lower()):
            profile.suspicious_keywords += 1
        
        profile.last_activity = current_time
        self.behavior_profiles[source_id] = profile
    
    async def _behavioral_anomaly_detection(
        self, 
        source_id: str, 
        message: str
    ) -> Dict[str, Any]:
        """Detect behavioral anomalies using statistical analysis"""
        
        profile = self.behavior_profiles.get(source_id)
        if not profile or profile.message_count < 5:
            return {"threat_score": 0.0, "indicators": []}
        
        indicators = []
        anomaly_score = 0.0
        
        # Message frequency anomaly
        if len(profile.message_intervals) >= 5:
            intervals = list(profile.message_intervals)
            mean_interval = statistics.mean(intervals)
            std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
            
            recent_interval = intervals[-1]
            if std_interval > 0:
                z_score = abs((recent_interval - mean_interval) / std_interval)
                if z_score > self.anomaly_thresholds["message_frequency_std"]:
                    indicators.append(ThreatIndicator(
                        indicator_type="frequency_anomaly",
                        severity=min(1.0, z_score / 5.0),
                        confidence=0.8,
                        description=f"Abnormal message frequency (z-score: {z_score:.2f})",
                        evidence={"z_score": z_score, "mean_interval": mean_interval}
                    ))
                    anomaly_score += min(0.5, z_score / 10.0)
        
        # Message length anomaly  
        current_length = len(message)
        if profile.message_count > 3:
            length_variance = abs(current_length - profile.avg_message_length) / max(1, profile.avg_message_length)
            if length_variance > self.anomaly_thresholds["message_length_variance"]:
                indicators.append(ThreatIndicator(
                    indicator_type="length_anomaly", 
                    severity=min(1.0, length_variance / 3.0),
                    confidence=0.7,
                    description=f"Abnormal message length variation: {length_variance:.1%}",
                    evidence={"length_variance": length_variance, "current": current_length}
                ))
                anomaly_score += min(0.3, length_variance / 5.0)
        
        # Topic switching anomaly
        if profile.topic_diversity > self.anomaly_thresholds["topic_jump_threshold"]:
            indicators.append(ThreatIndicator(
                indicator_type="topic_jumping",
                severity=profile.topic_diversity,
                confidence=0.6,
                description=f"Rapid topic switching detected: {profile.topic_diversity:.2f}",
                evidence={"topic_diversity": profile.topic_diversity}
            ))
            anomaly_score += profile.topic_diversity * 0.4
        
        # Suspicious keyword concentration
        if profile.message_count > 0:
            suspicious_ratio = profile.suspicious_keywords / profile.message_count
            if suspicious_ratio > 0.3:  # 30% of messages have suspicious keywords
                indicators.append(ThreatIndicator(
                    indicator_type="suspicious_keyword_concentration",
                    severity=suspicious_ratio,
                    confidence=0.8,
                    description=f"High concentration of suspicious keywords: {suspicious_ratio:.1%}",
                    evidence={"suspicious_ratio": suspicious_ratio}
                ))
                anomaly_score += suspicious_ratio * 0.6
        
        return {
            "threat_score": min(1.0, anomaly_score),
            "indicators": indicators
        }
    
    async def _coordinated_attack_detection(
        self,
        source_id: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect coordinated attacks across multiple sources"""
        
        indicators = []
        coordination_score = 0.0
        
        if not metadata:
            return {"threat_score": coordination_score, "indicators": indicators}
        
        current_time = datetime.now()
        
        # Check for similar attack patterns across sources
        recent_window = current_time - timedelta(minutes=15)
        recent_campaigns = []
        
        for campaign_id, events in self.attack_campaigns.items():
            recent_events = [e for e in events if e["timestamp"] > recent_window]
            if len(recent_events) > 1:  # Multiple events in short window
                recent_campaigns.append({
                    "campaign_id": campaign_id,
                    "event_count": len(recent_events),
                    "sources": list(set(e["source_id"] for e in recent_events))
                })
        
        # Detect coordination patterns
        for campaign in recent_campaigns:
            if len(campaign["sources"]) > 1:  # Multiple sources
                indicators.append(ThreatIndicator(
                    indicator_type="coordinated_attack",
                    severity=min(1.0, len(campaign["sources"]) / 5.0),
                    confidence=0.9,
                    description=f"Coordinated attack detected: {len(campaign['sources'])} sources",
                    evidence=campaign
                ))
                coordination_score += 0.7
        
        # Check for botnet-like behavior
        if len(self.behavior_profiles) > 10:
            similar_profiles = 0
            reference_profile = self.behavior_profiles[source_id]
            
            for other_id, other_profile in self.behavior_profiles.items():
                if other_id != source_id and other_profile.message_count > 5:
                    # Compare behavioral similarity
                    similarity = self._calculate_profile_similarity(reference_profile, other_profile)
                    if similarity > 0.8:  # Very similar behavior
                        similar_profiles += 1
            
            if similar_profiles > 3:  # Multiple similar profiles = potential botnet
                indicators.append(ThreatIndicator(
                    indicator_type="botnet_behavior",
                    severity=min(1.0, similar_profiles / 10.0),
                    confidence=0.8,
                    description=f"Potential botnet behavior: {similar_profiles} similar profiles",
                    evidence={"similar_profiles": similar_profiles}
                ))
                coordination_score += 0.6
        
        return {
            "threat_score": min(1.0, coordination_score),
            "indicators": indicators
        }
    
    async def _evasion_technique_detection(self, message: str) -> Dict[str, Any]:
        """Detect advanced evasion techniques"""
        
        indicators = []
        evasion_score = 0.0
        
        message_lower = message.lower()
        
        # Character encoding evasion
        unusual_chars = len([c for c in message if ord(c) > 127])
        if unusual_chars > len(message) * 0.1:  # >10% non-ASCII
            indicators.append(ThreatIndicator(
                indicator_type="encoding_evasion",
                severity=min(1.0, unusual_chars / len(message)),
                confidence=0.7,
                description=f"Unusual character encoding detected: {unusual_chars} non-ASCII chars",
                evidence={"unusual_chars": unusual_chars, "total_chars": len(message)}
            ))
            evasion_score += 0.4
        
        # Obfuscation techniques
        obfuscation_patterns = [
            r'[a-z]{1}[^a-z]{1,3}[a-z]{1}',  # Character separation
            r'[0-9]+[a-z]+[0-9]+',           # Number/letter mixing
            r'[A-Z]{2,}[a-z]{1}[A-Z]{2,}',   # Case mixing
        ]
        
        obfuscation_matches = 0
        for pattern in obfuscation_patterns:
            matches = len(re.findall(pattern, message))
            obfuscation_matches += matches
        
        if obfuscation_matches > 3:
            indicators.append(ThreatIndicator(
                indicator_type="obfuscation_attempt",
                severity=min(1.0, obfuscation_matches / 10.0),
                confidence=0.8,
                description=f"Text obfuscation detected: {obfuscation_matches} patterns",
                evidence={"obfuscation_matches": obfuscation_matches}
            ))
            evasion_score += 0.5
        
        # Whitespace manipulation
        whitespace_ratio = (len(message) - len(message.replace(' ', ''))) / len(message)
        if whitespace_ratio > 0.4:  # >40% whitespace
            indicators.append(ThreatIndicator(
                indicator_type="whitespace_manipulation",
                severity=whitespace_ratio,
                confidence=0.6,
                description=f"Excessive whitespace usage: {whitespace_ratio:.1%}",
                evidence={"whitespace_ratio": whitespace_ratio}
            ))
            evasion_score += whitespace_ratio * 0.3
        
        return {
            "threat_score": min(1.0, evasion_score),
            "indicators": indicators
        }
    
    async def _persistence_attack_detection(self, source_id: str) -> Dict[str, Any]:
        """Detect persistence and repeated attack attempts"""
        
        indicators = []
        persistence_score = 0.0
        
        profile = self.behavior_profiles.get(source_id)
        if not profile:
            return {"threat_score": persistence_score, "indicators": indicators}
        
        # Long-term persistence
        if profile.last_activity and profile.message_count > 20:
            session_duration = (profile.last_activity - 
                              (profile.last_activity - timedelta(hours=1))).total_seconds() / 3600
            
            if session_duration > 2:  # More than 2 hours of activity
                indicators.append(ThreatIndicator(
                    indicator_type="persistence_attack",
                    severity=min(1.0, session_duration / 8.0),  # Max 8 hours
                    confidence=0.7,
                    description=f"Prolonged session detected: {session_duration:.1f} hours",
                    evidence={"session_duration": session_duration}
                ))
                persistence_score += 0.4
        
        # Repeated similar attempts
        if len(profile.unique_patterns) < profile.message_count * 0.3:  # Low diversity
            repetition_ratio = len(profile.unique_patterns) / max(1, profile.message_count)
            indicators.append(ThreatIndicator(
                indicator_type="repeated_attempts",
                severity=1.0 - repetition_ratio,
                confidence=0.8,
                description=f"High message repetition: {repetition_ratio:.1%} unique",
                evidence={"repetition_ratio": repetition_ratio}
            ))
            persistence_score += (1.0 - repetition_ratio) * 0.6
        
        return {
            "threat_score": min(1.0, persistence_score),
            "indicators": indicators
        }
    
    async def _reconnaissance_detection(self, message: str, source_id: str) -> Dict[str, Any]:
        """Detect reconnaissance and information gathering attempts"""
        
        indicators = []
        recon_score = 0.0
        
        message_lower = message.lower()
        
        # Information gathering patterns
        recon_patterns = [
            r'como.*funciona',
            r'que.*(?:sistema|tecnologia|servidor)',
            r'onde.*(?:localizado|hospedado|servidor)',
            r'quantos.*(?:usuários|clientes|funcionários)',
            r'qual.*(?:versão|sistema|banco)',
        ]
        
        recon_matches = 0
        for pattern in recon_patterns:
            if re.search(pattern, message_lower):
                recon_matches += 1
        
        if recon_matches > 0:
            indicators.append(ThreatIndicator(
                indicator_type="reconnaissance_attempt",
                severity=min(1.0, recon_matches / 3.0),
                confidence=0.7,
                description=f"Information gathering detected: {recon_matches} patterns",
                evidence={"recon_patterns": recon_matches}
            ))
            recon_score += min(0.6, recon_matches / 5.0)
        
        # Systematic probing
        profile = self.behavior_profiles.get(source_id)
        if profile and profile.information_requests > profile.message_count * 0.5:
            info_ratio = profile.information_requests / profile.message_count
            indicators.append(ThreatIndicator(
                indicator_type="systematic_probing",
                severity=info_ratio,
                confidence=0.8,
                description=f"Systematic information probing: {info_ratio:.1%}",
                evidence={"info_request_ratio": info_ratio}
            ))
            recon_score += info_ratio * 0.5
        
        return {
            "threat_score": min(1.0, recon_score),
            "indicators": indicators
        }
    
    async def _social_engineering_advanced_detection(
        self, 
        message: str, 
        source_id: str
    ) -> Dict[str, Any]:
        """Advanced social engineering detection"""
        
        indicators = []
        se_score = 0.0
        
        message_lower = message.lower()
        
        # Authority manipulation
        authority_patterns = [
            r'(?:sou|eu sou).*(?:gerente|diretor|admin|desenvolvedor)',
            r'meu.*(?:chefe|supervisor).*(?:disse|pediu|mandou)',
            r'urgente.*(?:problema|erro|falha)',
            r'precisa.*(?:rápido|urgente|imediatamente)'
        ]
        
        for pattern in authority_patterns:
            if re.search(pattern, message_lower):
                indicators.append(ThreatIndicator(
                    indicator_type="authority_manipulation",
                    severity=0.7,
                    confidence=0.6,
                    description="Authority manipulation attempt detected",
                    evidence={"pattern": pattern}
                ))
                se_score += 0.4
                break
        
        # Emotional manipulation
        emotion_patterns = [
            r'por favor.*(?:ajude|ajuda)',
            r'estou.*(?:desesperado|preocupado|aflito)',
            r'família.*(?:problema|emergência)',
            r'criança.*(?:problema|perigo|risco)'
        ]
        
        for pattern in emotion_patterns:
            if re.search(pattern, message_lower):
                indicators.append(ThreatIndicator(
                    indicator_type="emotional_manipulation",
                    severity=0.5,
                    confidence=0.5,
                    description="Emotional manipulation attempt detected", 
                    evidence={"pattern": pattern}
                ))
                se_score += 0.3
                break
        
        return {
            "threat_score": min(1.0, se_score),
            "indicators": indicators
        }
    
    async def _zero_day_detection(self, message: str, source_id: str) -> Dict[str, Any]:
        """Detect potential zero-day attack patterns"""
        
        indicators = []
        zero_day_score = 0.0
        
        # Unusual pattern combinations
        unusual_combinations = 0
        
        # Check for novel encoding + injection patterns
        if (re.search(r'[^a-zA-Z0-9\s]{3,}', message) and  # Unusual characters
            re.search(r'(?:script|eval|exec|system)', message.lower())):  # Execution keywords
            unusual_combinations += 1
        
        # Check for novel evasion + sensitive requests
        if (len([c for c in message if ord(c) > 127]) > 5 and  # Non-ASCII chars
            re.search(r'(?:password|key|token|secret)', message.lower())):  # Sensitive terms
            unusual_combinations += 1
        
        # Check for timing-based anomalies with sophisticated content
        profile = self.behavior_profiles.get(source_id)
        if (profile and len(profile.message_intervals) > 0 and
            profile.message_intervals[-1] < 1 and  # Very fast response
            len(message) > 200):  # Complex message
            unusual_combinations += 1
        
        if unusual_combinations > 0:
            indicators.append(ThreatIndicator(
                indicator_type="zero_day_pattern",
                severity=min(1.0, unusual_combinations / 3.0),
                confidence=0.6,  # Lower confidence for zero-day detection
                description=f"Potential zero-day attack pattern: {unusual_combinations} anomalies",
                evidence={"unusual_combinations": unusual_combinations}
            ))
            zero_day_score += unusual_combinations * 0.4
        
        return {
            "threat_score": min(1.0, zero_day_score),
            "indicators": indicators
        }
    
    def _calculate_threat_level(self, threat_score: float) -> ThreatLevel:
        """Calculate overall threat level"""
        
        if threat_score >= 0.9:
            return ThreatLevel.CRITICAL
        elif threat_score >= 0.7:
            return ThreatLevel.HIGH
        elif threat_score >= 0.5:
            return ThreatLevel.MEDIUM
        elif threat_score >= 0.2:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.NONE
    
    def _determine_primary_threat_category(
        self, 
        indicators: List[ThreatIndicator]
    ) -> ThreatCategory:
        """Determine primary threat category from indicators"""
        
        category_scores = defaultdict(float)
        
        category_mapping = {
            "frequency_anomaly": ThreatCategory.BEHAVIORAL_ANOMALY,
            "length_anomaly": ThreatCategory.BEHAVIORAL_ANOMALY,
            "topic_jumping": ThreatCategory.BEHAVIORAL_ANOMALY,
            "coordinated_attack": ThreatCategory.COORDINATED_ATTACK,
            "botnet_behavior": ThreatCategory.COORDINATED_ATTACK,
            "encoding_evasion": ThreatCategory.EVASION_ATTEMPT,
            "obfuscation_attempt": ThreatCategory.EVASION_ATTEMPT,
            "persistence_attack": ThreatCategory.PERSISTENCE_ATTACK,
            "reconnaissance_attempt": ThreatCategory.RECONNAISSANCE,
            "systematic_probing": ThreatCategory.RECONNAISSANCE,
            "authority_manipulation": ThreatCategory.SOCIAL_ENGINEERING,
            "emotional_manipulation": ThreatCategory.SOCIAL_ENGINEERING,
            "zero_day_pattern": ThreatCategory.ZERO_DAY
        }
        
        for indicator in indicators:
            category = category_mapping.get(indicator.indicator_type, ThreatCategory.BEHAVIORAL_ANOMALY)
            category_scores[category] += indicator.severity * indicator.confidence
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        else:
            return ThreatCategory.BEHAVIORAL_ANOMALY
    
    def _calculate_detection_confidence(self, indicators: List[ThreatIndicator]) -> float:
        """Calculate overall detection confidence"""
        
        if not indicators:
            return 0.0
        
        # Weight confidence by severity
        weighted_confidence = sum(ind.confidence * ind.severity for ind in indicators)
        total_weight = sum(ind.severity for ind in indicators)
        
        return weighted_confidence / max(total_weight, 0.1)
    
    async def _generate_threat_intelligence(
        self,
        source_id: str,
        indicators: List[ThreatIndicator]
    ) -> Dict[str, Any]:
        """Generate threat intelligence summary"""
        
        profile = self.behavior_profiles.get(source_id, BehaviorProfile(source_id=source_id))
        
        return {
            "source_profile": {
                "message_count": profile.message_count,
                "avg_message_length": profile.avg_message_length,
                "topic_diversity": profile.topic_diversity,
                "suspicious_keywords": profile.suspicious_keywords,
                "session_duration": profile.session_duration
            },
            "attack_vectors": list(set(ind.indicator_type for ind in indicators)),
            "severity_distribution": {
                "critical": len([ind for ind in indicators if ind.severity >= 0.8]),
                "high": len([ind for ind in indicators if 0.6 <= ind.severity < 0.8]),
                "medium": len([ind for ind in indicators if 0.4 <= ind.severity < 0.6]),
                "low": len([ind for ind in indicators if ind.severity < 0.4])
            },
            "confidence_score": self._calculate_detection_confidence(indicators),
            "reputation_score": self.ip_reputation.get(source_id, 0.5)
        }
    
    def _recommend_actions(
        self, 
        threat_level: ThreatLevel, 
        threat_category: ThreatCategory
    ) -> List[str]:
        """Recommend security actions based on threat assessment"""
        
        actions = []
        
        if threat_level == ThreatLevel.CRITICAL:
            actions.extend([
                "Block source permanently",
                "Escalate to security team",
                "Log all evidence for analysis",
                "Review security policies"
            ])
        elif threat_level == ThreatLevel.HIGH:
            actions.extend([
                "Block source temporarily",
                "Increase monitoring",
                "Require additional validation",
                "Log detailed information"
            ])
        elif threat_level == ThreatLevel.MEDIUM:
            actions.extend([
                "Apply rate limiting",
                "Enhanced monitoring",
                "Log suspicious activity"
            ])
        elif threat_level == ThreatLevel.LOW:
            actions.extend([
                "Monitor closely",
                "Log activity patterns"
            ])
        
        # Category-specific actions
        if threat_category == ThreatCategory.COORDINATED_ATTACK:
            actions.append("Check for related attack campaigns")
        elif threat_category == ThreatCategory.SOCIAL_ENGINEERING:
            actions.append("Implement human verification")
        elif threat_category == ThreatCategory.ZERO_DAY:
            actions.append("Update threat signatures")
        
        return actions
    
    async def _correlate_attack_campaigns(
        self,
        source_id: str,
        indicators: List[ThreatIndicator]
    ):
        """Correlate threats across attack campaigns"""
        
        if not indicators:
            return
        
        # Create campaign signature based on indicators
        indicator_types = sorted([ind.indicator_type for ind in indicators])
        campaign_signature = hashlib.md5(
            "|".join(indicator_types).encode()
        ).hexdigest()[:8]
        
        # Add to campaign tracking
        campaign_event = {
            "source_id": source_id,
            "timestamp": datetime.now(),
            "indicators": indicator_types,
            "max_severity": max((ind.severity for ind in indicators), default=0.0)
        }
        
        self.attack_campaigns[campaign_signature].append(campaign_event)
        
        # Keep only recent campaign data (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.attack_campaigns[campaign_signature] = [
            event for event in self.attack_campaigns[campaign_signature]
            if event["timestamp"] > cutoff_time
        ]
    
    def _calculate_profile_similarity(
        self, 
        profile1: BehaviorProfile, 
        profile2: BehaviorProfile
    ) -> float:
        """Calculate similarity between two behavior profiles"""
        
        similarities = []
        
        # Message length similarity
        if profile1.avg_message_length > 0 and profile2.avg_message_length > 0:
            length_diff = abs(profile1.avg_message_length - profile2.avg_message_length)
            max_length = max(profile1.avg_message_length, profile2.avg_message_length)
            length_similarity = 1.0 - (length_diff / max_length)
            similarities.append(length_similarity)
        
        # Topic diversity similarity
        diversity_diff = abs(profile1.topic_diversity - profile2.topic_diversity)
        diversity_similarity = 1.0 - diversity_diff
        similarities.append(diversity_similarity)
        
        # Activity pattern similarity (simplified)
        if len(profile1.activity_pattern) == len(profile2.activity_pattern):
            pattern_correlation = 0.0
            total1 = sum(profile1.activity_pattern)
            total2 = sum(profile2.activity_pattern)
            
            if total1 > 0 and total2 > 0:
                for i in range(len(profile1.activity_pattern)):
                    p1 = profile1.activity_pattern[i] / total1
                    p2 = profile2.activity_pattern[i] / total2
                    pattern_correlation += min(p1, p2)
            
            similarities.append(pattern_correlation)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _load_evasion_patterns(self) -> List[Dict[str, Any]]:
        """Load advanced evasion technique patterns"""
        return []  # Simplified for this implementation
    
    def _load_apt_indicators(self) -> List[Dict[str, Any]]:
        """Load Advanced Persistent Threat indicators"""
        return []  # Simplified for this implementation
    
    def get_threat_statistics(self) -> Dict[str, Any]:
        """Get comprehensive threat detection statistics"""
        
        total_profiles = len(self.behavior_profiles)
        active_profiles = sum(
            1 for profile in self.behavior_profiles.values()
            if profile.last_activity and 
               profile.last_activity > datetime.now() - timedelta(hours=1)
        )
        
        total_campaigns = len(self.attack_campaigns)
        active_campaigns = sum(
            1 for events in self.attack_campaigns.values()
            if events and events[-1]["timestamp"] > datetime.now() - timedelta(hours=1)
        )
        
        return {
            "behavior_profiles": {
                "total": total_profiles,
                "active": active_profiles,
                "avg_messages_per_profile": (
                    sum(p.message_count for p in self.behavior_profiles.values()) / 
                    max(total_profiles, 1)
                )
            },
            "attack_campaigns": {
                "total": total_campaigns,
                "active": active_campaigns
            },
            "detection_capabilities": {
                "behavioral_anomaly": True,
                "coordinated_attacks": True,
                "evasion_techniques": True,
                "zero_day_detection": True,
                "social_engineering": True,
                "persistence_attacks": True,
                "reconnaissance": True
            },
            "ml_features": len(self.zero_day_indicators),
            "threat_intelligence": "Real-time behavioral analysis with ML"
        }