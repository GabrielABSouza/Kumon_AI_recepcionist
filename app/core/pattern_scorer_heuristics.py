# app/core/pattern_scorer_heuristics.py
"""
Pattern Scorer Heuristics - Destravadores para Combined Score

Pequenas heurísticas que destravam situações onde o score fica baixo:
- Detecção de tempo/datas
- Identificação de profissionais por nome
- Vocabulário específico por categoria  
- Composição multi-intenção com boost
"""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HeuristicResult:
    """Result from heuristic analysis"""
    detected: bool = False
    confidence_boost: float = 0.0
    entities: List[str] = None
    reasoning: str = ""
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []


class PatternScorerHeuristics:
    """
    Heurísticas destravadoras para melhorar combined_score
    
    Foca em situações que o PatternScorer perde:
    - Multi-intenção: scheduling.book + tempo + serviço → boost
    - Entidades específicas: nomes, datas, horários
    - Vocabulário contextual Kumon
    """
    
    def __init__(self):
        self.professional_names = self._load_professional_names()
        self.service_vocabulary = self._load_service_vocabulary()
        self.temporal_patterns = self._compile_temporal_patterns()
        
    def _load_professional_names(self) -> Dict[str, Set[str]]:
        """Load professional names/nicknames by establishment"""
        
        # Configurável por estabelecimento - exemplo para Kumon Vila A
        return {
            "kumon_vila_a": {
                "orientadora", "professora", "ana", "maria", "carla", 
                "tia ana", "teacher", "sensei", "orientador"
            },
            "default": {
                "orientadora", "orientador", "professora", "professor",
                "instrutora", "instrutor", "educadora", "educador"
            }
        }
    
    def _load_service_vocabulary(self) -> Dict[str, Set[str]]:
        """Load vocabulary by service category"""
        
        return {
            "math": {
                "matematica", "mat", "calculo", "numeros", "aritmetica", 
                "algebra", "geometria", "tabuada", "soma", "subtracao",
                "multiplicacao", "divisao", "fracoes", "decimais", "equacoes"
            },
            "portuguese": {
                "portugues", "leitura", "escrita", "redacao", "interpretacao",
                "texto", "gramatica", "ortografia", "pontuacao", "compreensao",
                "vocabulario", "literatura", "verbos", "substantivos"
            },
            "english": {
                "ingles", "english", "lingua inglesa", "idioma", "vocabulary",
                "grammar", "reading", "writing", "speaking", "conversation"
            },
            "general_education": {
                "aprendizado", "desenvolvimento", "cognitivo", "pedagogico",
                "educacional", "didatico", "metodologia", "ensino", "estudo"
            }
        }
    
    def _compile_temporal_patterns(self) -> Dict[str, re.Pattern]:
        """Compile temporal detection patterns"""
        
        patterns = {
            "time_specific": re.compile(r'\b\d{1,2}:\d{2}|\b\d{1,2}h(\d{2})?\b', re.IGNORECASE),
            "time_period": re.compile(r'\b(de manh[ãa]|de tarde|[àa] noite|meio[- ]dia|madrugada)\b', re.IGNORECASE),
            "date_relative": re.compile(r'\b(hoje|amanh[ãa]|depois de amanh[ãa]|ontem|anteontem)\b', re.IGNORECASE),
            "date_weekday": re.compile(r'\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(-feira)?\b', re.IGNORECASE),
            "date_month": re.compile(r'\b(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b', re.IGNORECASE),
            "date_numeric": re.compile(r'\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|\b\d{1,2}-\d{1,2}(-\d{2,4})?\b', re.IGNORECASE),
            "temporal_connectors": re.compile(r'\b(na pr[oó]xima|nesta|nessa|no pr[oó]ximo|neste|nesse|durante|at[eé]|desde|apartir de)\b', re.IGNORECASE)
        }
        
        return patterns
    
    def analyze_message_heuristics(
        self, 
        message: str, 
        detected_intents: List[Dict[str, any]] = None,
        establishment: str = "default"
    ) -> Dict[str, HeuristicResult]:
        """
        Analyze message with all heuristics
        
        Args:
            message: User message
            detected_intents: Previously detected intents
            establishment: Establishment identifier for name matching
            
        Returns:
            Dictionary of heuristic results
        """
        
        results = {}
        
        # Temporal analysis
        results["temporal"] = self.detect_temporal_entities(message)
        
        # Professional name detection
        results["professional"] = self.detect_professional_references(message, establishment)
        
        # Service vocabulary analysis
        results["service"] = self.detect_service_vocabulary(message)
        
        # Multi-intent composition
        results["multi_intent"] = self.analyze_multi_intent_composition(message, detected_intents or [])
        
        # Context coherence
        results["coherence"] = self.analyze_context_coherence(message, detected_intents or [])
        
        # Urgency/priority detection
        results["urgency"] = self.detect_urgency_markers(message)
        
        return results
    
    def detect_temporal_entities(self, message: str) -> HeuristicResult:
        """Detect temporal entities with confidence boost"""
        
        detected_entities = []
        total_boost = 0.0
        
        # Check each temporal pattern
        for pattern_name, pattern in self.temporal_patterns.items():
            matches = pattern.findall(message.lower())
            
            if matches:
                detected_entities.extend(matches)
                
                # Different boosts for different temporal types
                if pattern_name == "time_specific":
                    total_boost += 0.08  # Specific times are strong intent signals
                elif pattern_name == "date_weekday":
                    total_boost += 0.06  # Weekdays suggest scheduling intent
                elif pattern_name == "date_relative":
                    total_boost += 0.05  # Today/tomorrow are actionable
                else:
                    total_boost += 0.03  # Other temporal references
        
        # Cap the boost
        total_boost = min(total_boost, 0.12)
        
        reasoning = f"Found {len(detected_entities)} temporal entities"
        
        return HeuristicResult(
            detected=len(detected_entities) > 0,
            confidence_boost=total_boost,
            entities=detected_entities,
            reasoning=reasoning
        )
    
    def detect_professional_references(self, message: str, establishment: str = "default") -> HeuristicResult:
        """Detect references to professionals/staff"""
        
        # Get names for establishment
        establishment_names = self.professional_names.get(establishment, set())
        default_names = self.professional_names.get("default", set())
        all_names = establishment_names.union(default_names)
        
        detected_names = []
        message_lower = message.lower()
        
        # Check for name matches
        for name in all_names:
            if name in message_lower:
                detected_names.append(name)
        
        # Boost calculation
        boost = 0.0
        if detected_names:
            boost = min(0.05 * len(detected_names), 0.10)  # Up to 0.10 boost
        
        reasoning = f"Found professional references: {detected_names}" if detected_names else "No professional references"
        
        return HeuristicResult(
            detected=len(detected_names) > 0,
            confidence_boost=boost,
            entities=detected_names,
            reasoning=reasoning
        )
    
    def detect_service_vocabulary(self, message: str) -> HeuristicResult:
        """Detect service-specific vocabulary"""
        
        detected_services = []
        total_boost = 0.0
        message_lower = message.lower()
        
        # Check vocabulary for each service category
        for service_name, vocabulary in self.service_vocabulary.items():
            matches = []
            
            for term in vocabulary:
                if term in message_lower:
                    matches.append(term)
            
            if matches:
                detected_services.append({
                    "service": service_name,
                    "terms": matches,
                    "count": len(matches)
                })
                
                # Boost based on service match strength
                service_boost = min(0.02 * len(matches), 0.06)
                total_boost += service_boost
        
        # Cap total boost
        total_boost = min(total_boost, 0.10)
        
        reasoning = f"Found {len(detected_services)} service vocabularies"
        
        return HeuristicResult(
            detected=len(detected_services) > 0,
            confidence_boost=total_boost,
            entities=detected_services,
            reasoning=reasoning
        )
    
    def analyze_multi_intent_composition(self, message: str, detected_intents: List[Dict[str, any]]) -> HeuristicResult:
        """
        Analyze multi-intent compositions with boosting
        
        scheduling.book + temporal + service → significant boost
        """
        
        if len(detected_intents) < 2:
            return HeuristicResult(detected=False, reasoning="Single or no intent detected")
        
        # Extract intent categories
        intent_categories = set()
        for intent_data in detected_intents:
            intent = intent_data.get("intent", "")
            if "." in intent:
                category = intent.split(".")[0]
                intent_categories.add(category)
        
        boost = 0.0
        compositions = []
        
        # High-value compositions
        if "scheduling" in intent_categories and "temporal" in intent_categories:
            boost += 0.08
            compositions.append("scheduling+temporal")
        
        if "scheduling" in intent_categories and "service" in intent_categories:
            boost += 0.06
            compositions.append("scheduling+service")
        
        if "information" in intent_categories and "service" in intent_categories:
            boost += 0.04
            compositions.append("information+service")
        
        # Triple composition bonus
        if len(intent_categories) >= 3:
            boost += 0.03
            compositions.append("triple_intent")
        
        # Cap boost
        boost = min(boost, 0.15)
        
        reasoning = f"Multi-intent composition: {compositions}" if compositions else "No significant compositions"
        
        return HeuristicResult(
            detected=boost > 0,
            confidence_boost=boost,
            entities=compositions,
            reasoning=reasoning
        )
    
    def analyze_context_coherence(self, message: str, detected_intents: List[Dict[str, any]]) -> HeuristicResult:
        """Analyze contextual coherence of the message"""
        
        # Message length coherence
        word_count = len(message.split())
        
        # Coherence factors
        coherence_score = 0.0
        factors = []
        
        # Appropriate length (not too short, not too long)
        if 3 <= word_count <= 30:
            coherence_score += 0.02
            factors.append("appropriate_length")
        
        # Question markers indicate clear intent
        if re.search(r'\?|como|qual|quando|onde|quanto|posso|gostaria|preciso', message.lower()):
            coherence_score += 0.03
            factors.append("question_markers")
        
        # Polite expressions (Brazilian Portuguese)
        if re.search(r'\b(por favor|obrigad[oa]|gostaria|poderia|seria poss[ií]vel)\b', message.lower()):
            coherence_score += 0.02
            factors.append("polite_expressions")
        
        # Educational context markers
        if re.search(r'\b(crian[cç]a|filho|filha|alun[oa]|estudante|aprender|educar)\b', message.lower()):
            coherence_score += 0.02
            factors.append("educational_context")
        
        reasoning = f"Coherence factors: {factors}" if factors else "Low coherence"
        
        return HeuristicResult(
            detected=coherence_score > 0,
            confidence_boost=coherence_score,
            entities=factors,
            reasoning=reasoning
        )
    
    def detect_urgency_markers(self, message: str) -> HeuristicResult:
        """Detect urgency/priority markers"""
        
        urgency_patterns = [
            (r'\b(urgente|urgência|rápido|já|hoje mesmo|agora|imediatamente)\b', 0.05, "high_urgency"),
            (r'\b(preciso|necessário|importante|logo|em breve)\b', 0.03, "medium_urgency"),
            (r'\b(quando possível|sem pressa|qualquer hora)\b', -0.02, "low_urgency")  # Negative boost
        ]
        
        detected_urgency = []
        total_boost = 0.0
        
        for pattern, boost, urgency_type in urgency_patterns:
            if re.search(pattern, message.lower()):
                detected_urgency.append(urgency_type)
                total_boost += boost
        
        reasoning = f"Urgency markers: {detected_urgency}" if detected_urgency else "No urgency markers"
        
        return HeuristicResult(
            detected=len(detected_urgency) > 0,
            confidence_boost=total_boost,
            entities=detected_urgency,
            reasoning=reasoning
        )
    
    def calculate_total_heuristic_boost(self, heuristic_results: Dict[str, HeuristicResult]) -> float:
        """Calculate total confidence boost from all heuristics"""
        
        total_boost = 0.0
        
        for result in heuristic_results.values():
            total_boost += result.confidence_boost
        
        # Apply diminishing returns
        if total_boost > 0.10:
            # Diminishing returns after 0.10
            excess = total_boost - 0.10
            diminished_excess = excess * 0.5  # 50% diminishing
            total_boost = 0.10 + diminished_excess
        
        # Cap at maximum boost
        total_boost = min(total_boost, 0.25)
        
        return total_boost
    
    def generate_heuristic_explanation(self, heuristic_results: Dict[str, HeuristicResult]) -> str:
        """Generate human-readable explanation of heuristic analysis"""
        
        active_heuristics = []
        total_boost = 0.0
        
        for name, result in heuristic_results.items():
            if result.detected and result.confidence_boost > 0:
                active_heuristics.append(f"{name}(+{result.confidence_boost:.3f})")
                total_boost += result.confidence_boost
        
        if not active_heuristics:
            return "No heuristic boosts applied"
        
        final_boost = self.calculate_total_heuristic_boost(heuristic_results)
        
        return f"Heuristics: {', '.join(active_heuristics)} → Total: +{final_boost:.3f}"


# Global instance
pattern_scorer_heuristics = PatternScorerHeuristics()