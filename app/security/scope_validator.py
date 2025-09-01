"""
Scope Validation System for Kumon Assistant

Prevents out-of-scope requests (anti-besteiras) and ensures the agent
stays within its defined business purpose:

✅ ALLOWED:
- Kumon method information
- Scheduling appointments  
- Business information
- Academic program details
- Contact information

❌ BLOCKED:
- Recipes and cooking
- Poetry and creative writing
- Medical advice
- Technical tutorials
- General knowledge questions
- Personal opinions
- Entertainment content
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json

from ..core.logger import app_logger
from ..core.config import settings


class ScopeCategory(Enum):
    """Categories for scope validation"""
    KUMON_BUSINESS = "kumon_business"        # Core business topics
    EDUCATIONAL_INFO = "educational_info"    # Academic/educational content
    SCHEDULING = "scheduling"                # Appointment booking
    CONTACT_INFO = "contact_info"           # Business contact details
    OUT_OF_SCOPE = "out_of_scope"          # Explicitly blocked content
    AMBIGUOUS = "ambiguous"                 # Needs further analysis
    HARMFUL = "harmful"                     # Potentially harmful requests


class ViolationType(Enum):
    """Types of scope violations"""
    RECIPE_REQUEST = "recipe_request"
    POETRY_REQUEST = "poetry_request"
    MEDICAL_ADVICE = "medical_advice"
    TECHNICAL_TUTORIAL = "technical_tutorial"
    GENERAL_KNOWLEDGE = "general_knowledge"
    PERSONAL_OPINION = "personal_opinion"
    ENTERTAINMENT = "entertainment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SYSTEM_INFORMATION = "system_information"


@dataclass
class ScopePattern:
    """Pattern for detecting out-of-scope requests"""
    name: str
    keywords: List[str]
    patterns: List[str]
    violation_type: ViolationType
    severity: float  # 0.0 to 1.0
    description: str
    examples: List[str] = field(default_factory=list)


@dataclass 
class ScopeValidationResult:
    """Result of scope validation"""
    is_valid_scope: bool
    category: ScopeCategory
    violation_type: Optional[ViolationType]
    violation_severity: float
    violation_confidence: float
    matched_patterns: List[str]
    suggested_response: Optional[str]
    business_alternative: Optional[str]


class ScopeValidator:
    """
    Advanced scope validation system to prevent out-of-scope requests
    
    Keeps Cecília focused on Kumon business while politely declining
    inappropriate requests with helpful alternatives.
    """
    
    def __init__(self):
        # Load scope patterns and business context
        self.allowed_patterns = self._load_allowed_patterns()
        self.blocked_patterns = self._load_blocked_patterns()
        self.business_context = self._load_business_context()
        
        # Violation tracking per user
        self.violation_history: Dict[str, List[Dict]] = {}
        
        # Response templates
        self.response_templates = self._load_response_templates()
        
        # Machine learning features for scope detection
        self.ml_features = [
            "kumon_keywords",
            "educational_keywords", 
            "scheduling_keywords",
            "out_of_scope_keywords",
            "question_type",
            "intent_indicators"
        ]
        
        app_logger.info("Scope Validator initialized with business focus protection")
    
    async def validate_scope(
        self,
        user_message: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate if user message is within allowed business scope
        
        Args:
            user_message: The user's message content
            request_metadata: Additional request context
            
        Returns:
            Validation result with scope assessment
        """
        
        # Multi-layer scope analysis
        results = await asyncio.gather(
            self._keyword_analysis(user_message),
            self._pattern_matching(user_message),
            self._intent_classification(user_message),
            self._business_context_analysis(user_message),
            return_exceptions=True
        )
        
        keyword_result, pattern_result, intent_result, context_result = results
        
        # Combine analysis results
        validation_results = [r for r in results if isinstance(r, dict)]
        
        if not validation_results:
            # Default to allowing if analysis fails
            return self._create_validation_result(
                is_valid=True,
                category=ScopeCategory.AMBIGUOUS,
                confidence=0.5,
                message="Analysis incomplete - allowing with caution"
            )
        
        # Calculate overall scores
        scope_scores = [r.get("scope_score", 0.5) for r in validation_results]
        confidence_scores = [r.get("confidence", 0.5) for r in validation_results] 
        violation_indicators = []
        
        for result in validation_results:
            if "violations" in result:
                violation_indicators.extend(result["violations"])
        
        # Overall assessment
        avg_scope_score = sum(scope_scores) / len(scope_scores)
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # CORE FIX: ALLOW ambiguous messages without clear violations
        # Only block if there are actual violations with severity > 0.0
        has_real_violations = violation_indicators and any(v.get("severity", 0.0) > 0.0 for v in violation_indicators)
        
        # Allow if no real violations OR if score is reasonable
        is_valid_scope = not has_real_violations or avg_scope_score >= 0.5
        
        # If violations detected, assess severity
        violation_severity = 0.0
        violation_type = None
        
        if violation_indicators:
            # Find most severe violation
            severity_scores = [v.get("severity", 0.0) for v in violation_indicators]
            violation_severity = max(severity_scores)
            
            # Find primary violation type
            most_severe = max(violation_indicators, key=lambda x: x.get("severity", 0.0))
            violation_type = most_severe.get("type")
        
        # Determine category
        category = self._determine_category(avg_scope_score, violation_indicators)
        
        # Generate appropriate response
        suggested_response = None
        business_alternative = None
        
        if not is_valid_scope:
            suggested_response = self._generate_scope_violation_response(
                violation_type, user_message
            )
            business_alternative = self._suggest_business_alternative(
                violation_type, user_message
            )
        
        # Track violation for repeat offender detection
        if not is_valid_scope and request_metadata:
            await self._track_violation(
                request_metadata.get("source_identifier", "unknown"),
                violation_type,
                violation_severity
            )
        
        return {
            "is_valid_scope": is_valid_scope,
            "category": category.value,
            "violation_type": violation_type.value if violation_type else None,
            "violation_severity": violation_severity,
            "violation_confidence": avg_confidence,
            "matched_patterns": [v.get("pattern", "") for v in violation_indicators],
            "suggested_response": suggested_response,
            "business_alternative": business_alternative,
            "analysis_details": {
                "scope_score": avg_scope_score,
                "confidence": avg_confidence,
                "violation_count": len(violation_indicators),
                "analysis_layers": len(validation_results)
            }
        }
    
    async def _keyword_analysis(self, user_message: str) -> Dict[str, Any]:
        """Analyze message keywords for scope determination"""
        
        message_lower = user_message.lower()
        
        # Count business-relevant keywords
        kumon_keywords = sum(1 for kw in self.business_context["kumon_keywords"] 
                           if kw in message_lower)
        
        educational_keywords = sum(1 for kw in self.business_context["educational_keywords"]
                                 if kw in message_lower)
        
        scheduling_keywords = sum(1 for kw in self.business_context["scheduling_keywords"]
                                if kw in message_lower)
        
        # Count out-of-scope keywords
        violations = []
        
        for pattern in self.blocked_patterns:
            matched_keywords = sum(1 for kw in pattern.keywords if kw in message_lower)
            if matched_keywords > 0:
                violations.append({
                    "type": pattern.violation_type,
                    "severity": pattern.severity,
                    "matched_keywords": matched_keywords,
                    "pattern": pattern.name
                })
        
        # Calculate scope score
        business_score = (kumon_keywords * 0.5 + educational_keywords * 0.3 + 
                         scheduling_keywords * 0.2)
        
        violation_penalty = sum(v["severity"] * v["matched_keywords"] for v in violations)
        
        scope_score = max(0.0, min(1.0, business_score - violation_penalty))
        
        return {
            "scope_score": scope_score,
            "confidence": 0.7,  # Keyword analysis is fairly reliable
            "violations": violations,
            "business_indicators": {
                "kumon_keywords": kumon_keywords,
                "educational_keywords": educational_keywords,
                "scheduling_keywords": scheduling_keywords
            }
        }
    
    async def _pattern_matching(self, user_message: str) -> Dict[str, Any]:
        """Pattern-based scope validation"""
        
        violations = []
        scope_score = 1.0  # Start with assuming in-scope
        
        # Check against blocked patterns
        for pattern in self.blocked_patterns:
            for regex_pattern in pattern.patterns:
                if re.search(regex_pattern, user_message, re.IGNORECASE):
                    violations.append({
                        "type": pattern.violation_type,
                        "severity": pattern.severity,
                        "pattern": pattern.name,
                        "description": pattern.description
                    })
                    scope_score -= pattern.severity
        
        # Check against allowed patterns
        business_matches = 0
        for pattern in self.allowed_patterns:
            for regex_pattern in pattern["patterns"]:
                if re.search(regex_pattern, user_message, re.IGNORECASE):
                    business_matches += 1
                    scope_score += 0.3
        
        scope_score = max(0.0, min(1.0, scope_score))
        
        return {
            "scope_score": scope_score,
            "confidence": 0.8,  # Pattern matching is quite reliable
            "violations": violations,
            "business_matches": business_matches
        }
    
    async def _intent_classification(self, user_message: str) -> Dict[str, Any]:
        """Classify user intent for scope validation"""
        
        message_lower = user_message.lower()
        violations = []
        scope_score = 0.5  # Neutral starting point
        
        # Question patterns analysis
        is_question = bool(re.search(r'\?|como|quando|onde|quanto|qual|quem|por que', message_lower))
        
        # Recipe/cooking intent
        if re.search(r'receita|cozinha|ingrediente|preparo|tempero|prato', message_lower):
            violations.append({
                "type": ViolationType.RECIPE_REQUEST,
                "severity": 0.8,
                "pattern": "recipe_intent"
            })
            scope_score = 0.1
        
        # Poetry/creative writing intent
        elif re.search(r'poema|poesia|verso|rima|soneto|escreva|crie.*texto', message_lower):
            violations.append({
                "type": ViolationType.POETRY_REQUEST,
                "severity": 0.7,
                "pattern": "poetry_intent"
            })
            scope_score = 0.2
        
        # Medical advice intent
        elif re.search(r'doença|sintoma|remedio|tratamento|médico|saúde|dor', message_lower):
            violations.append({
                "type": ViolationType.MEDICAL_ADVICE,
                "severity": 0.9,
                "pattern": "medical_intent"
            })
            scope_score = 0.0
        
        # Technical tutorial intent
        elif re.search(r'tutorial|como fazer|passo a passo|programar|código', message_lower):
            violations.append({
                "type": ViolationType.TECHNICAL_TUTORIAL,
                "severity": 0.6,
                "pattern": "technical_intent"
            })
            scope_score = 0.3
        
        # Business/educational intent (positive indicators)
        elif re.search(r'kumon|agendar|horario|matrícula|método|matemática|português', message_lower):
            scope_score = 0.9
        
        # Scheduling intent (positive)
        elif re.search(r'agendar|marcar|horario|disponível|visita|consulta', message_lower):
            scope_score = 0.8
        
        return {
            "scope_score": scope_score,
            "confidence": 0.6,  # Intent classification can be tricky
            "violations": violations,
            "is_question": is_question
        }
    
    async def _business_context_analysis(self, user_message: str) -> Dict[str, Any]:
        """Analyze message in context of Kumon business"""
        
        message_lower = user_message.lower()
        scope_score = 0.5
        violations = []
        
        # Direct business references
        business_terms = ["kumon", "vila a", "matemática", "português", "método", 
                         "orientador", "aluno", "matrícula", "aula"]
        
        business_matches = sum(1 for term in business_terms if term in message_lower)
        
        if business_matches > 0:
            scope_score = min(1.0, 0.6 + (business_matches * 0.1))
        
        # Location/scheduling context
        if re.search(r'avenida|rua|endereço|localização|chegar|horario', message_lower):
            scope_score = max(scope_score, 0.7)
        
        # Educational context
        if re.search(r'aprender|estudar|criança|desenvolvimento|educação', message_lower):
            scope_score = max(scope_score, 0.8)
        
        # General knowledge requests (negative)
        if re.search(r'explique|defina|o que é.*\?|como funciona.*\?', message_lower) and business_matches == 0:
            violations.append({
                "type": ViolationType.GENERAL_KNOWLEDGE,
                "severity": 0.5,
                "pattern": "general_knowledge_request"
            })
            scope_score = min(scope_score, 0.4)
        
        return {
            "scope_score": scope_score,
            "confidence": 0.7,
            "violations": violations,
            "business_matches": business_matches
        }
    
    def _determine_category(
        self, 
        scope_score: float, 
        violations: List[Dict]
    ) -> ScopeCategory:
        """Determine the primary category for the request"""
        
        if scope_score >= 0.8:
            return ScopeCategory.KUMON_BUSINESS
        elif scope_score >= 0.6:
            return ScopeCategory.EDUCATIONAL_INFO
        elif violations:
            # Check for harmful content
            harmful_violations = [v for v in violations if v.get("severity", 0) >= 0.8]
            if harmful_violations:
                return ScopeCategory.HARMFUL
            else:
                return ScopeCategory.OUT_OF_SCOPE
        else:
            return ScopeCategory.AMBIGUOUS
    
    def _generate_scope_violation_response(
        self, 
        violation_type: Optional[ViolationType], 
        user_message: str
    ) -> str:
        """Generate appropriate response for scope violations"""
        
        if not violation_type:
            return self.response_templates["generic_scope_violation"]
        
        template_key = f"{violation_type.value}_response"
        template = self.response_templates.get(template_key, 
                                             self.response_templates["generic_scope_violation"])
        
        return template
    
    def _suggest_business_alternative(
        self, 
        violation_type: Optional[ViolationType], 
        user_message: str
    ) -> Optional[str]:
        """Suggest business-relevant alternative"""
        
        alternatives = {
            ViolationType.RECIPE_REQUEST: "Que tal conhecer nosso método de matemática que pode ajudar com cálculos de proporções e medidas?",
            ViolationType.POETRY_REQUEST: "Nosso programa de português desenvolve habilidades de escrita criativa! Gostaria de saber mais?",
            ViolationType.MEDICAL_ADVICE: "Não posso dar conselhos médicos, mas posso falar sobre como o Kumon desenvolve concentração e disciplina nos estudos.",
            ViolationType.TECHNICAL_TUTORIAL: "Não ensino programação, mas nosso método desenvolve raciocínio lógico essencial para tecnologia!",
            ViolationType.GENERAL_KNOWLEDGE: "Sou especialista em Kumon! Posso explicar nosso método ou ajudar a agendar uma visita."
        }
        
        return alternatives.get(violation_type) if violation_type else None
    
    async def _track_violation(
        self, 
        source_identifier: str, 
        violation_type: Optional[ViolationType],
        severity: float
    ):
        """Track scope violations per user"""
        
        if not violation_type:
            return
        
        violation_entry = {
            "timestamp": datetime.now(),
            "violation_type": violation_type.value,
            "severity": severity
        }
        
        self.violation_history.setdefault(source_identifier, []).append(violation_entry)
        
        # Keep only recent violations (last 50)
        if len(self.violation_history[source_identifier]) > 50:
            self.violation_history[source_identifier] = \
                self.violation_history[source_identifier][-50:]
    
    def _create_validation_result(
        self,
        is_valid: bool,
        category: ScopeCategory,
        confidence: float,
        message: str,
        violation_type: Optional[ViolationType] = None,
        severity: float = 0.0
    ) -> Dict[str, Any]:
        """Helper to create standardized validation results"""
        
        return {
            "is_valid_scope": is_valid,
            "category": category.value,
            "violation_type": violation_type.value if violation_type else None,
            "violation_severity": severity,
            "violation_confidence": confidence,
            "matched_patterns": [],
            "suggested_response": message if not is_valid else None,
            "business_alternative": None
        }
    
    def _load_allowed_patterns(self) -> List[Dict[str, Any]]:
        """Load patterns for allowed business topics"""
        
        return [
            {
                "name": "kumon_method_inquiry",
                "patterns": [
                    r"método kumon",
                    r"como funciona.*kumon",
                    r"kumon.*ensina",
                    r"diferencial.*kumon"
                ]
            },
            {
                "name": "scheduling_request",
                "patterns": [
                    r"agendar.*(?:visita|consulta|horario)",
                    r"marcar.*(?:horario|compromisso)",
                    r"disponível.*(?:hoje|amanhã|semana)",
                    r"que horas.*(?:abre|fecha|atende)"
                ]
            },
            {
                "name": "enrollment_inquiry",
                "patterns": [
                    r"matrícula",
                    r"inscrever.*(?:filho|filha|criança)",
                    r"começar.*kumon",
                    r"valor.*(?:mensalidade|curso)"
                ]
            },
            {
                "name": "business_info",
                "patterns": [
                    r"endereço.*kumon",
                    r"onde.*(?:fica|localiza)",
                    r"telefone.*contato",
                    r"horario.*(?:funcionamento|atendimento)"
                ]
            }
        ]
    
    def _load_blocked_patterns(self) -> List[ScopePattern]:
        """Load patterns for blocked out-of-scope content"""
        
        return [
            # Recipe requests
            ScopePattern(
                name="recipe_requests",
                keywords=["receita", "ingrediente", "cozinha", "preparo", "tempero"],
                patterns=[
                    r"receita\s+de\s+\w+",
                    r"como\s+fazer\s+\w+\s+(?:comida|prato|doce)",
                    r"ingredientes?\s+(?:para|de)",
                    r"modo\s+de\s+preparo"
                ],
                violation_type=ViolationType.RECIPE_REQUEST,
                severity=0.8,
                description="User is requesting cooking recipes",
                examples=["receita de bolo", "como fazer lasanha", "ingredientes para pizza"]
            ),
            
            # Poetry/creative writing
            ScopePattern(
                name="poetry_requests", 
                keywords=["poema", "poesia", "verso", "rima", "soneto"],
                patterns=[
                    r"escreva\s+(?:um\s+)?poema",
                    r"crie\s+(?:uma\s+)?poesia",
                    r"faça\s+(?:uns?\s+)?versos?",
                    r"quero\s+um\s+soneto"
                ],
                violation_type=ViolationType.POETRY_REQUEST,
                severity=0.7,
                description="User is requesting poetry or creative writing",
                examples=["escreva um poema", "crie uma poesia sobre amor"]
            ),
            
            # Medical advice
            ScopePattern(
                name="medical_advice",
                keywords=["doença", "sintoma", "remedio", "tratamento", "médico", "saúde"],
                patterns=[
                    r"(?:tenho|sinto)\s+(?:dor|sintoma)",
                    r"que\s+remedio\s+(?:tomar|usar)",
                    r"(?:é|pode ser)\s+(?:doença|problema)",
                    r"diagnóstico\s+(?:de|para)"
                ],
                violation_type=ViolationType.MEDICAL_ADVICE,
                severity=0.9,
                description="User is seeking medical advice",
                examples=["tenho dor de cabeça", "que remedio tomar para gripe"]
            ),
            
            # Technical tutorials
            ScopePattern(
                name="technical_tutorials",
                keywords=["programar", "código", "tutorial", "desenvolver", "software"],
                patterns=[
                    r"como\s+programar",
                    r"tutorial\s+(?:de|para)\s+\w+",
                    r"ensine\s+(?:a\s+)?(?:programar|codificar)",
                    r"criar\s+(?:um\s+)?(?:programa|software|app)"
                ],
                violation_type=ViolationType.TECHNICAL_TUTORIAL,
                severity=0.6,
                description="User is requesting technical tutorials",
                examples=["como programar em Python", "tutorial de JavaScript"]
            ),
            
            # General knowledge
            ScopePattern(
                name="general_knowledge",
                keywords=["explique", "defina", "o que é", "significado", "história"],
                patterns=[
                    r"o\s+que\s+é\s+(?!kumon|método)",
                    r"explique\s+(?!kumon|método)",
                    r"defina\s+\w+",
                    r"qual\s+(?:é\s+)?o\s+significado"
                ],
                violation_type=ViolationType.GENERAL_KNOWLEDGE,
                severity=0.5,
                description="User is asking general knowledge questions",
                examples=["o que é democracia", "explique a fotossíntese"]
            ),
            
            # Entertainment
            ScopePattern(
                name="entertainment_requests",
                keywords=["piada", "história", "entretenimento", "diversão", "jogo"],
                patterns=[
                    r"conte\s+(?:uma\s+)?(?:piada|história)",
                    r"me\s+divirt[ao]",
                    r"vamos\s+jogar",
                    r"que\s+tal\s+um\s+(?:jogo|quiz)"
                ],
                violation_type=ViolationType.ENTERTAINMENT,
                severity=0.4,
                description="User is seeking entertainment",
                examples=["conte uma piada", "vamos jogar um jogo"]
            )
        ]
    
    def _load_business_context(self) -> Dict[str, List[str]]:
        """Load business context keywords"""
        
        return {
            "kumon_keywords": [
                "kumon", "método kumon", "vila a", "orientador", "planilhas",
                "autodidata", "autodisciplina", "concentração", "raciocínio"
            ],
            "educational_keywords": [
                "matemática", "português", "educação", "aprendizado", "ensino",
                "desenvolvimento", "criança", "aluno", "estudar", "lição"
            ],
            "scheduling_keywords": [
                "agendar", "marcar", "horario", "visita", "consulta", "disponível",
                "compromisso", "reunião", "entrevista", "agendamento"
            ]
        }
    
    def _load_response_templates(self) -> Dict[str, str]:
        """Load response templates for different violation types"""
        
        return {
            "recipe_request_response": "Oi! Eu sou especialista em educação Kumon, não em culinária! 😊 Mas posso te contar como nosso método de matemática ajuda com cálculos de proporções. Que tal agendar uma visita?",
            
            "poetry_request_response": "Que legal seu interesse por criatividade! ✨ Nosso programa de português desenvolve habilidades de escrita, incluindo textos criativos. Gostaria de conhecer nosso método?",
            
            "medical_advice_response": "Não posso dar conselhos médicos, mas posso falar sobre como o Kumon desenvolve concentração e disciplina nos estudos! Isso pode ser muito benéfico. Quer saber mais?",
            
            "technical_tutorial_response": "Não sou especialista em programação, mas nosso método desenvolve o raciocínio lógico essencial para tecnologia! 🧠 Que tal conhecer como funciona?",
            
            "general_knowledge_response": "Sou especialista em Kumon! 📚 Posso explicar nosso método educacional, falar sobre nossos programas ou ajudar a agendar uma visita. Como posso ajudar?",
            
            "entertainment_response": "Que tal a diversão de aprender? 😄 No Kumon, tornamos o aprendizado interessante e engajante! Posso contar mais sobre nossos métodos?",
            
            "generic_scope_violation": "Obrigada pelo interesse! Sou especialista em Kumon e posso ajudar com informações sobre nosso método, agendamentos ou dúvidas educacionais. Como posso ajudar? 😊"
        }
    
    def get_violation_stats(self, source_identifier: Optional[str] = None) -> Dict[str, Any]:
        """Get scope violation statistics"""
        
        if source_identifier:
            violations = self.violation_history.get(source_identifier, [])
            recent_violations = [
                v for v in violations 
                if v["timestamp"] > datetime.now() - timedelta(hours=24)
            ]
            
            violation_types = {}
            for violation in violations:
                vtype = violation["violation_type"]
                violation_types[vtype] = violation_types.get(vtype, 0) + 1
            
            return {
                "source": source_identifier,
                "total_violations": len(violations),
                "recent_violations": len(recent_violations),
                "violation_types": violation_types,
                "first_violation": violations[0]["timestamp"] if violations else None,
                "last_violation": violations[-1]["timestamp"] if violations else None
            }
        else:
            total_violations = sum(len(v) for v in self.violation_history.values())
            total_sources = len(self.violation_history)
            
            # Aggregate violation types
            all_violation_types = {}
            for violations in self.violation_history.values():
                for violation in violations:
                    vtype = violation["violation_type"]
                    all_violation_types[vtype] = all_violation_types.get(vtype, 0) + 1
            
            return {
                "total_violations": total_violations,
                "affected_sources": total_sources,
                "patterns_loaded": len(self.blocked_patterns),
                "violation_types": all_violation_types,
                "business_focus": "Kumon educational services"
            }