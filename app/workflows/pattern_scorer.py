"""
Pattern Scorer - Stage-aware pattern confidence calculation

Extracted from IntentClassifier and enhanced with stage multipliers
following orchestration_flow.md specifications.
"""

import re
from typing import Dict, Any, List
from ..core.logger import app_logger
from ..core.state.models import ConversationStage
from .contracts import PatternScores, STAGE_CONFIDENCE_MULTIPLIERS


class PatternScorer:
    """
    Stage-aware pattern confidence calculator
    
    Computes pattern_confidence via regex/keywords with:
    - Context/entity/recency boosts
    - Stage multipliers based on current_stage
    - Normalized output [0,1]
    """

    def __init__(self):
        # Intent detection patterns (integrated from legacy intent_detection.py)
        self.intent_patterns = {
            "booking": [
                "quero agendar", "vou agendar", "quero marcar", "vou marcar",
                "agendar", "marcar", "scheduling", "appointment",
                "quando posso", "horário", "disponibilidade", "agenda",
                "quero visitar", "gostaria de conhecer", "quero ir"
            ],
            "information_request": [
                "como funciona", "o que é", "quanto custa", "qual o preço",
                "quais são", "como é", "me explica", "pode explicar",
                "quero saber", "gostaria de saber", "preciso entender",
                "metodologia", "material", "método", "diferença"
            ],
            "human_help": [
                "falar com", "atendente", "pessoa", "humano", "representante",
                "não está ajudando", "não entendo", "muito confuso",
                "desisto", "cansei", "chato", "complicado demais"
            ],
            "confusion": [
                "não entendi", "não entendo", "confuso", "como assim",
                "que", "o que", "hein", "não sei", "não ficou claro",
                "explica melhor", "não compreendi"
            ],
            "dissatisfaction": [
                "não ajudou", "não serve", "não é isso", "não quero isso",
                "ruim", "péssimo", "horrível", "não gostei",
                "já falei", "já disse", "repetindo", "de novo"
            ]
        }
        
        # Entity extraction patterns (unified from IntentClassifier and PatternScorer)
        # CENTRALIZED entity extraction - single source of truth for all entity patterns
        self.entity_patterns = {
            # UNIFIED: Using IntentClassifier's superior regex with proper Portuguese accents
            "person_names": [
                r"\b([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*)\b"
            ],
            # Enhanced age patterns from both classes
            "ages": [
                r"\b(\d{1,2})\s+anos?\b", 
                r"\bidade\s+(\d{1,2})\b",
                r"\b(\d{1,2})\s*years?\s*old\b"
            ],
            # Enhanced time patterns  
            "times": [
                r"\b(manhã|tarde|morning|afternoon)\b", 
                r"\b(\d{1,2}h?\d{0,2})\b"
            ],
            # Enhanced date patterns
            "dates": [
                r"\b(\d{1,2}/\d{1,2}(?:/\d{4})?)\b", 
                r"\b(segunda|terça|quarta|quinta|sexta|sábado|domingo)\b"
            ],
            # Enhanced program patterns
            "programs": [
                r"\b(matemática|português|inglês|math|portuguese|english)\b"
            ],
            # Enhanced price patterns
            "prices": [
                r"\b(r\$?\s*\d+(?:,\d{2})?)\b", 
                r"\b(\d+\s+reais?)\b"
            ],
        }

        # Route-specific patterns (from IntentClassifier intent_patterns)
        self.route_patterns = {
            "greeting": {
                "patterns": [
                    r"\b(oi|olá|hello|hi|bom\s*dia|boa\s*tarde|boa\s*noite)\b",
                    r"\b(meu\s+nome\s+é|me\s+chamo|sou\s+o|sou\s+a)\b",
                    r"\b(gostaria\s+de\s+saber|quero\s+conhecer|tenho\s+interesse)\b",
                    # CONTEXT-AWARE: Single name as response (when expecting name collection)
                    r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$",
                ],
                "base_score": 0.7,
                "boost_factors": ["person_names", "polite_greeting", "context_name_collection"]
            },
            "information": {
                "patterns": [
                    r"\b(como\s+funciona|o\s+que\s+é|me\s+explica|gostaria\s+de\s+saber)\b",
                    r"\b(matemática|português|inglês|método|metodologia)\b",
                    r"\b(quanto\s+custa|preço|valor|mensalidade)\b",
                ],
                "base_score": 0.6,
                "boost_factors": ["entity_programs", "question_indicators"]
            },
            "scheduling": {
                "patterns": [
                    r"\b(agendar|marcar|aula\s+experimental|horário|disponibilidade)\b",
                    r"\b(quando\s+posso|que\s+horas|que\s+dia)\b",
                    r"\b(segunda|terça|quarta|quinta|sexta|manhã|tarde)\b",
                ],
                "base_score": 0.8,
                "boost_factors": ["entity_dates", "entity_times"]
            },
            "confirmation": {
                "patterns": [
                    r"\b(confirmo|confirmado|tudo\s+certo|perfeito|ok)\b",
                    r"\b(meu\s+email|e-mail|contato)\b",
                ],
                "base_score": 0.9,
                "boost_factors": ["entity_email", "confirmation_words"]
            },
            "clarification": {
                "patterns": [
                    r"\b(não\s+entendo|não\s+sei|confuso|confusa|como\s+assim)\b",
                    r"\b(pode\s+repetir|não\s+ficou\s+claro|explica\s+de\s+novo)\b",
                ],
                "base_score": 0.8,
                "boost_factors": ["confusion_indicators"]
            },
            "handoff": {
                "patterns": [
                    r"\b(falar\s+com|atendente|pessoa|humano|representante)\b",
                    r"\b(não\s+está\s+ajudando|muito\s+confuso|desisto)\b",
                ],
                "base_score": 0.9,
                "boost_factors": ["human_help_indicators", "dissatisfaction"]
            }
        }

    async def score_patterns(
        self,
        message: str,
        current_stage: ConversationStage,
        collected_data: Dict[str, Any] = None,
        current_step: Any = None
    ) -> PatternScores:
        """
        Calculate stage-aware pattern scores for all routes
        
        Args:
            message: User message to analyze
            current_stage: Current conversation stage
            collected_data: Previously collected data for context boosts
            
        Returns:
            PatternScores with per_route scores and best_route selection
        """
        try:
            # NOVO: Verificação especial para QUALIFICATION
            if current_stage == ConversationStage.QUALIFICATION and current_step:
                from .qualification_pattern_detector import qualification_detector
                
                qual_result = qualification_detector.detect_and_extract(
                    message, current_stage, current_step
                )
                
                if qual_result["detected"]:
                    # Se detectou padrão de qualificação, retorna score alto
                    app_logger.info(
                        f"[PATTERN_SCORER] Qualification pattern detected: {qual_result['classification']} "
                        f"(confidence: {qual_result['confidence']:.2f})"
                    )
                    
                    return PatternScores(
                        per_route={
                            "qualification": qual_result["confidence"],
                            "greeting": 0.05,  # Muito baixo para evitar confusão
                            "information": 0.1,
                            "scheduling": 0.05,
                            "confirmation": 0.05,
                            "clarification": 0.1,
                            "handoff": 0.05
                        },
                        best_route="qualification",
                        pattern_confidence=qual_result["confidence"],
                        stage_multipliers_applied={}
                    )
            
            message_lower = message.lower().strip()
            collected_data = collected_data or {}
            
            # Extract entities for context boosts
            entities = self._extract_entities(message)
            
            # Calculate base scores for each route
            per_route = {}
            
            for route_name, route_config in self.route_patterns.items():
                # STAGE-AWARE LOGIC: Prevent greeting re-classification when already in GREETING
                if route_name == "greeting" and current_stage == ConversationStage.GREETING:
                    # User is already in GREETING stage - don't re-classify name as greeting
                    # Check if this looks like a name response
                    name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                    if re.match(name_pattern, message.strip()):
                        # This is a name response - score as information/response instead
                        per_route[route_name] = 0.1  # Very low greeting score
                        continue
                
                # Base pattern matching
                base_score = self._calculate_base_pattern_score(
                    message_lower, route_config["patterns"], route_config["base_score"]
                )
                
                # Apply context boosts
                boosted_score = self._apply_context_boosts(
                    base_score, route_config["boost_factors"], entities, collected_data
                )
                
                # Apply intent pattern boosts
                intent_boosts = self._calculate_intent_boosts(message_lower)
                if route_name == "scheduling" and intent_boosts.get("booking", 0) > 0:
                    boosted_score = min(1.0, boosted_score + intent_boosts["booking"])
                elif route_name == "information" and intent_boosts.get("information_request", 0) > 0:
                    boosted_score = min(1.0, boosted_score + intent_boosts["information_request"])
                elif route_name == "handoff" and intent_boosts.get("human_help", 0) > 0:
                    boosted_score = min(1.0, boosted_score + intent_boosts["human_help"])
                elif route_name == "clarification" and intent_boosts.get("confusion", 0) > 0:
                    boosted_score = min(1.0, boosted_score + intent_boosts["confusion"])
                
                # STAGE-AWARE BOOST: Name responses in GREETING should boost information score
                if (route_name == "information" and current_stage == ConversationStage.GREETING):
                    name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                    if re.match(name_pattern, message.strip()):
                        # Boost information score for name responses in GREETING
                        boosted_score = min(1.0, boosted_score + 0.6)  # Strong boost
                
                # Apply stage multipliers
                stage_multiplier = STAGE_CONFIDENCE_MULTIPLIERS.get(current_stage, 1.0)
                final_score = boosted_score * stage_multiplier
                
                # Clamp to [0,1]
                per_route[route_name] = max(0.0, min(1.0, final_score))
            
            # Find best route and confidence
            best_route = max(per_route.keys(), key=lambda k: per_route[k])
            pattern_confidence = per_route[best_route]
            
            # Log stage multipliers applied for debugging
            stage_multipliers_applied = {
                route: STAGE_CONFIDENCE_MULTIPLIERS.get(current_stage, 1.0)
                for route in per_route.keys()
            }
            
            # Structured telemetry logging
            from ..core.state.utils import safe_enum_value
            app_logger.info(
                f"[PATTERN_SCORER] Completed pattern scoring",
                extra={
                    "component": "pattern_scorer",
                    "operation": "score_patterns",
                    "best_route": best_route,
                    "pattern_confidence": pattern_confidence,
                    "current_stage": safe_enum_value(current_stage),
                    "stage_multiplier": stage_multipliers_applied[best_route],
                    "routes_analyzed": len(per_route),
                    "per_route_scores": per_route,
                    "entities_extracted": len(entities) if entities else 0
                }
            )
            
            return PatternScores(
                per_route=per_route,
                best_route=best_route,
                pattern_confidence=pattern_confidence,
                stage_multipliers_applied=stage_multipliers_applied
            )
            
        except Exception as e:
            app_logger.error(f"Error in pattern scoring: {e}")
            # Fallback to low confidence
            return PatternScores(
                per_route={"fallback": 0.2},
                best_route="fallback", 
                pattern_confidence=0.2,
                stage_multipliers_applied={}
            )

    def _calculate_base_pattern_score(
        self, message: str, patterns: List[str], base_score: float
    ) -> float:
        """Calculate base pattern match score (adapted from IntentClassifier)"""
        
        best_match_score = 0.0
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                matched_text = match.group(0)
                # Use existing confidence calculation logic
                match_confidence = self._calculate_pattern_confidence(
                    message, matched_text, pattern
                )
                # Combine with base score
                combined_score = (base_score * 0.7) + (match_confidence * 0.3)
                best_match_score = max(best_match_score, combined_score)
        
        return best_match_score

    def _calculate_pattern_confidence(self, message: str, matched_text: str, pattern: str) -> float:
        """
        Calculate confidence score based on match quality (from IntentClassifier)
        """
        # Remove extra whitespace for comparison
        message_clean = message.strip()
        matched_clean = matched_text.strip()

        # Perfect exact matches get maximum confidence
        exact_words = ["oi", "olá", "hi", "hello", "tchau", "obrigado", "obrigada", "valeu"]
        if message_clean in exact_words:
            return 1.0

        # Strong direct matches (message is essentially just the matched part)
        message_words = message_clean.split()
        matched_words = matched_clean.split()

        # If matched text covers most/all of the message
        if len(matched_words) == len(message_words):
            return 0.95

        # If matched text is significant portion of message
        word_ratio = len(matched_words) / len(message_words) if message_words else 0
        if word_ratio >= 0.8:
            return 0.9
        elif word_ratio >= 0.6:
            return 0.8
        elif word_ratio >= 0.4:
            return 0.7
        else:
            # Partial match but still relevant
            return 0.6

    def _apply_context_boosts(
        self, 
        base_score: float,
        boost_factors: List[str], 
        entities: Dict[str, List[str]], 
        collected_data: Dict[str, Any]
    ) -> float:
        """Apply context boosts based on entities and collected data"""
        
        boosted_score = base_score
        
        for factor in boost_factors:
            if factor == "person_names" and entities.get("person_names"):
                boosted_score += 0.1
            elif factor == "entity_programs" and entities.get("programs"):
                boosted_score += 0.15
            elif factor == "entity_dates" and entities.get("dates"):
                boosted_score += 0.2
            elif factor == "entity_times" and entities.get("times"):
                boosted_score += 0.15
            elif factor == "polite_greeting" and any(word in entities.get("person_names", []) for word in ["obrigado", "obrigada", "valeu"]):
                boosted_score += 0.05
            elif factor == "confirmation_words" and collected_data.get("selected_slot"):
                boosted_score += 0.2  # Strong boost if scheduling data exists
            elif factor == "context_name_collection" and entities.get("person_names"):
                # CONTEXT-AWARE: Boost names when we're in greeting stage expecting name
                # This addresses the "Gabriel" scenario where it should be high confidence
                boosted_score += 0.3  # Strong context boost for name collection
        
        return boosted_score

    def extract_entities(self, message: str) -> Dict[str, List[str]]:
        """
        Extract entities from message - PUBLIC method for IntentClassifier
        
        This is the centralized entity extraction method used by both
        PatternScorer and IntentClassifier to ensure consistency.
        
        Args:
            message: User message to analyze
            
        Returns:
            Dict mapping entity types to lists of found entities
        """
        entities = {}

        for entity_type, patterns in self.entity_patterns.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, message, re.IGNORECASE)
                matches.extend(found)

            if matches:
                entities[entity_type] = list(set(matches))  # Remove duplicates

        return entities

    def _extract_entities(self, message: str) -> Dict[str, List[str]]:
        """Private wrapper for backward compatibility"""
        return self.extract_entities(message)
    
    def _calculate_intent_boosts(self, message_lower: str) -> Dict[str, float]:
        """Calculate boost scores based on intent pattern matches"""
        boosts = {}
        
        for intent_type, patterns in self.intent_patterns.items():
            match_count = sum(1 for pattern in patterns if pattern in message_lower)
            if match_count > 0:
                # More matches = higher boost, but capped at 0.3
                boosts[intent_type] = min(0.3, match_count * 0.1)
        
        return boosts