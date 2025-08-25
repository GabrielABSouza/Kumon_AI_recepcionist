"""
Intent-First Router Service for Performance Optimization
======================================================

Backend service providing sub-100ms intent classification and template responses
for 80% of common queries, reducing RAG API calls by 70% and improving user experience.

Architecture:
- Fast keyword-based intent classification (<50ms)
- Hardcoded template library for business critical responses  
- Context-aware dynamic template generation
- Graceful fallback to RAG for complex queries
- Comprehensive error handling and performance monitoring

Performance Targets:
- Template classification: <50ms
- Template response generation: <100ms total
- Cache hit rate: >90%
- Template accuracy: >95%
"""

import time
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..core.logger import app_logger
from ..core.config import settings
from ..core.state.models import CeciliaState


class IntentCategory(str, Enum):
    """Intent categories by priority and processing strategy"""
    BUSINESS_CRITICAL = "business_critical"      # Pricing, contact, hours - highest priority
    PROGRAM_INFO = "program_info"                # Methodology, benefits, processes
    SCHEDULING = "scheduling"                    # Availability, booking, confirmation  
    OBJECTION_HANDLING = "objection_handling"   # Common objections and responses
    GREETING = "greeting"                        # Welcome messages and initial responses
    NO_MATCH = "no_match"                       # Fallback to RAG required


class RouteResult:
    """Result object for template routing decisions"""
    
    def __init__(
        self, 
        matched: bool, 
        response: str = "", 
        confidence: float = 0.0,
        template_id: str = "",
        processing_time_ms: float = 0.0,
        intent_category: IntentCategory = IntentCategory.NO_MATCH,
        context_updates: Optional[Dict[str, Any]] = None,
        requires_rag_fallback: bool = False
    ):
        self.matched = matched
        self.response = response
        self.confidence = confidence
        self.template_id = template_id
        self.processing_time_ms = processing_time_ms
        self.intent_category = intent_category
        self.context_updates = context_updates or {}
        self.requires_rag_fallback = requires_rag_fallback


@dataclass
class TemplateStats:
    """Performance statistics for template matching"""
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    avg_processing_time_ms: float = 0.0
    hit_rate_percentage: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)
    
    def update_hit(self, processing_time_ms: float):
        """Update stats for successful template match"""
        self.total_requests += 1
        self.hits += 1
        self._update_avg_time(processing_time_ms)
        self._calculate_hit_rate()
    
    def update_miss(self, processing_time_ms: float):
        """Update stats for template miss"""
        self.total_requests += 1
        self.misses += 1
        self._update_avg_time(processing_time_ms)
        self._calculate_hit_rate()
    
    def _update_avg_time(self, processing_time_ms: float):
        """Update average processing time with exponential moving average"""
        if self.total_requests == 1:
            self.avg_processing_time_ms = processing_time_ms
        else:
            # Exponential moving average with alpha=0.1
            alpha = 0.1
            self.avg_processing_time_ms = (
                alpha * processing_time_ms + 
                (1 - alpha) * self.avg_processing_time_ms
            )
    
    def _calculate_hit_rate(self):
        """Calculate hit rate percentage"""
        if self.total_requests > 0:
            self.hit_rate_percentage = (self.hits / self.total_requests) * 100


class HardcodedTemplateLibrary:
    """Template library with business critical hardcoded responses"""
    
    def __init__(self):
        self.templates = self._load_templates()
        self.keyword_patterns = self._load_keyword_patterns()
    
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load hardcoded template responses organized by category"""
        return {
            "business_critical": {
                "pricing": f"""💰 **Investimento Kumon Vila A:**

• **Matemática ou Português**: R$ {settings.PRICE_PER_SUBJECT:.2f}/mês por disciplina
• **Inglês**: R$ {settings.PRICE_PER_SUBJECT:.2f}/mês  
• **Taxa de matrícula**: R$ {settings.ENROLLMENT_FEE:.2f} (única vez)

**Incluso em todos os planos:**
• Material didático exclusivo Kumon 📚
• Acompanhamento pedagógico personalizado 👨‍🏫
• Relatórios de progresso detalhados 📊
• 2 aulas semanais na unidade ({settings.BUSINESS_HOURS}) 🕐

🎓 **É um investimento no futuro do seu filho!**
📅 Quer agendar uma apresentação gratuita?""",

                "contact": f"""📞 **Entre em contato com a {settings.BUSINESS_NAME}:**

• **WhatsApp Direto**: ({settings.BUSINESS_PHONE[0:2]}) {settings.BUSINESS_PHONE[2:7]}-{settings.BUSINESS_PHONE[7:]}
• **Email**: {settings.BUSINESS_EMAIL}  
• **Horário de Atendimento**: {settings.BUSINESS_HOURS}

📍 **Nossa Unidade**: {settings.BUSINESS_ADDRESS}

Nossa equipe pedagógica está pronta para atendê-lo! ✨""",

                "hours": f"""🕐 **Horário de Funcionamento - {settings.BUSINESS_NAME}:**

• **{settings.BUSINESS_HOURS}**
• **Sábados e Domingos**: FECHADO

⚠️ **Importante**: Funcionamos APENAS durante a semana.

📞 **Para agendamentos**: ({settings.BUSINESS_PHONE[0:2]}) {settings.BUSINESS_PHONE[2:7]}-{settings.BUSINESS_PHONE[7:]}"""
            },
            
            "program_info": {
                "methodology": """📚 **Metodologia Kumon - Como Funciona:**

**🎯 Princípio Fundamental:**
Desenvolvimento da autonomia e autoconfiança através do aprendizado individualizado.

**📝 Como aplicamos:**
• Diagnóstico individual do nível do aluno
• Material sequencial e progressivo
• Estudo diário orientado (casa + unidade)
• Evolução no próprio ritmo do aluno

**👨‍🏫 Acompanhamento:**
• 2x por semana na unidade (orientação presencial)
• Correção imediata dos exercícios
• Relatórios de progresso para os pais

**✨ Resultado:** Alunos mais independentes, confiantes e com sólida base acadêmica!

Quer ver na prática? 📅 Agende uma apresentação!""",

                "benefits": """🎓 **Benefícios Comprovados do Kumon:**

**📈 Desenvolvimento Acadêmico:**
• Melhora nas notas escolares
• Base sólida em Matemática/Português/Inglês
• Preparação para vestibulares e concursos

**🧠 Habilidades Cognitivas:**
• Concentração e foco
• Raciocínio lógico
• Resolução de problemas

**💪 Desenvolvimento Pessoal:**
• Autonomia nos estudos
• Autoconfiança e autoestima
• Disciplina e organização
• Persistência e determinação

**📊 Resultados Mensuráveis:**
• Relatórios de progresso regulares
• Avaliações diagnósticas
• Acompanhamento individualizado

Quer conhecer cases de sucesso da nossa unidade? 😊"""
            },
            
            "scheduling": {
                "availability": f"""📅 **Disponibilidade para Apresentação Gratuita:**

**🌅 MANHÃ** ({settings.BUSINESS_HOURS_START}h às 12h):
• Terça-feira
• Quinta-feira 
• Sexta-feira

**🌆 TARDE** (13h às {settings.BUSINESS_HOURS_END}h):
• Segunda-feira
• Quarta-feira
• Sexta-feira

**⏱️ Duração:** Aproximadamente 1 hora

**📋 O que inclui:**
• Apresentação da metodologia
• Avaliação diagnóstica gratuita
• Definição do programa ideal
• Esclarecimento de dúvidas

Qual período prefere? **MANHÃ** ou **TARDE**? 🕐"""
            },
            
            "objection_handling": {
                "price_objection": f"""💭 **Entendo sua preocupação com o investimento!**

**💡 Vamos colocar em perspectiva:**
• R$ {settings.PRICE_PER_SUBJECT:.2f}/mês = R$ {settings.PRICE_PER_SUBJECT/30:.2f} por dia
• Menos que um lanche escolar
• Investimento que dura toda a vida

**🎯 Retorno do Investimento:**
• Melhora imediata nas notas
• Menos gastos com aulas particulares
• Preparação sólida para o futuro
• Desenvolvimento de autonomia

**📊 Comparação com Reforço Escolar:**
• Aula particular: R$ 50-80/hora = R$ 400-640/mês
• Kumon: Material + Método + Acompanhamento = R$ {settings.PRICE_PER_SUBJECT:.2f}/mês

**💡 Dica:** Venha conhecer nossa unidade e veja o valor na prática!
Que tal uma apresentação gratuita? 😊""",

                "time_objection": """⏰ **Preocupado com o tempo de estudo?**

**🎯 Kumon é Eficiência:**
• **Na unidade**: Apenas 2x por semana (30-45 min cada)
• **Em casa**: 15-30 minutos por dia
• **Total semanal**: 2-3 horas apenas!

**📈 Compare com outras atividades:**
• TV/jogos: 3-5 horas por dia
• Kumon: 20 minutos por dia
• **Resultado**: Base sólida para toda vida!

**💡 Organizamos o tempo do aluno:**
• Estudo diário vira rotina
• Melhora na organização geral
• Menos tempo perdido com dificuldades

**✨ A disciplina do Kumon ajuda em TODAS as matérias!**

Quer ver como funciona? Agende uma visita! 😊"""
            },
            
            "greeting": {
                "welcome": f"""Olá! 😊 Seja bem-vindo à {settings.BUSINESS_NAME}!

Sou a Cecília, sua assistente virtual. Estou aqui para ajudá-lo com informações sobre nossa metodologia e agendar sua apresentação gratuita.

Como posso ajudá-lo hoje?

**Posso falar sobre:**
📚 Metodologia Kumon
💰 Valores e investimento  
📅 Agendamento de apresentação
📞 Contato e localização
🎯 Benefícios para seu filho

Digite sua dúvida ou interesse! ✨"""
            }
        }
    
    def _load_keyword_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Load keyword patterns for fast intent classification"""
        return {
            "business_critical": {
                "pricing": [
                    "preço", "valor", "custa", "mensalidade", "investimento", 
                    "quanto", "money", "price", "cost", "pagar", "pagamento",
                    "taxa", "matrícula", "custo", "valores", "barato", "caro"
                ],
                "contact": [
                    "contato", "telefone", "whatsapp", "email", "falar", "ligar",
                    "contact", "phone", "call", "endereço", "localização", "onde fica"
                ],
                "hours": [
                    "horário", "funcionamento", "aberto", "fechado", "fecham", "que horas",
                    "hours", "open", "close", "quando funciona", "atendimento", "abrem"
                ]
            },
            
            "program_info": {
                "methodology": [
                    "como funciona", "metodologia", "método", "ensino",
                    "pedagógico", "didático", "aprendizado", "funciona"
                ],
                "benefits": [
                    "benefícios", "vantagens", "resultados", "melhora", "desenvolvimento",
                    "progress", "benefits", "advantage", "improvement", "beneficios",
                    "quais benefícios", "que benefícios", "vantagem do kumon", "desenvolver",
                    "vai desenvolver", "o que desenvolve", "que desenvolve"
                ]
            },
            
            "scheduling": {
                "availability": [
                    "agendar", "marcar", "consulta", "horário disponível", "disponibilidade",
                    "quero agendar", "posso marcar", "tem vaga", "schedule", "appointment",
                    "apresentação", "visita", "conhecer"
                ]
            },
            
            "objection_handling": {
                "price_objection": [
                    "muito caro", "não posso pagar", "expensive", "too much",
                    "não tenho dinheiro", "não cabe no orçamento", "alto preço",
                    "caro demais", "não tenho condições", "fora do meu orçamento"
                ],
                "time_objection": [
                    "não tenho tempo", "muito tempo", "corrido", "busy", "no time",
                    "ocupado", "tempo para estudar", "muito estudo"
                ]
            },
            
            "greeting": {
                "welcome": [
                    "oi", "olá", "bom dia", "boa tarde", "boa noite", "hello",
                    "hi", "hey", "buenos dias", "buenas tardes", "buenas noches", 
                    "hola", "salve", "e aí", "opa"
                ]
            }
        }
    
    def get_template(self, category: str, template_id: str) -> Optional[str]:
        """Get specific template by category and ID"""
        return self.templates.get(category, {}).get(template_id)


class IntentFirstRouter:
    """
    High-performance intent classifier and template router
    
    Provides sub-100ms responses for 80% of common queries through:
    - Fast keyword-based intent classification
    - Priority-based template matching
    - Context-aware response generation
    - Comprehensive performance monitoring
    """
    
    def __init__(self):
        """Initialize router with template library and performance tracking"""
        self.template_library = HardcodedTemplateLibrary()
        self.stats = TemplateStats()
        
        # Performance thresholds from requirements
        self.classification_target_ms = 50
        self.total_target_ms = 100
        
        # Confidence thresholds for different categories
        self.confidence_thresholds = {
            IntentCategory.BUSINESS_CRITICAL: 0.95,
            IntentCategory.PROGRAM_INFO: 0.90, 
            IntentCategory.SCHEDULING: 0.85,
            IntentCategory.OBJECTION_HANDLING: 0.80,
            IntentCategory.GREETING: 0.90
        }
        
        app_logger.info(
            "IntentFirstRouter initialized",
            extra={
                "classification_target_ms": self.classification_target_ms,
                "total_target_ms": self.total_target_ms,
                "template_categories": len(self.template_library.templates)
            }
        )
    
    async def route_message(
        self, 
        message: str, 
        context: Dict[str, Any], 
        phone_number: str = ""
    ) -> RouteResult:
        """
        Primary routing method - classifies intent and returns appropriate response
        
        Args:
            message: User message to classify and respond to
            context: Context from CeciliaState for personalization
            phone_number: User phone number for logging and stats
            
        Returns:
            RouteResult: Complete routing result with response and metadata
        """
        start_time = time.time()
        
        try:
            # Normalize message for processing
            message_normalized = self._normalize_message(message)
            
            # Priority-based template matching (target: <50ms)
            route_result = await self._match_templates_by_priority(
                message_normalized, context, phone_number
            )
            
            # Calculate total processing time
            route_result.processing_time_ms = (time.time() - start_time) * 1000
            
            # Update performance statistics
            if route_result.matched:
                self.stats.update_hit(route_result.processing_time_ms)
                
                app_logger.info(
                    "Template match successful",
                    extra={
                        "phone_number": phone_number,
                        "template_id": route_result.template_id,
                        "intent_category": route_result.intent_category.value,
                        "confidence": route_result.confidence,
                        "processing_time_ms": route_result.processing_time_ms,
                        "performance_target_met": route_result.processing_time_ms < self.total_target_ms
                    }
                )
            else:
                self.stats.update_miss(route_result.processing_time_ms)
                
                app_logger.debug(
                    "No template match - RAG fallback required",
                    extra={
                        "phone_number": phone_number,
                        "processing_time_ms": route_result.processing_time_ms,
                        "message_length": len(message)
                    }
                )
            
            return route_result
            
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            
            app_logger.error(
                "Intent routing error",
                extra={
                    "phone_number": phone_number,
                    "error": str(e),
                    "processing_time_ms": processing_time_ms,
                    "message_length": len(message)
                },
                exc_info=True
            )
            
            # Return error result requiring RAG fallback
            return RouteResult(
                matched=False,
                response="",
                confidence=0.0,
                template_id="error", 
                processing_time_ms=processing_time_ms,
                intent_category=IntentCategory.NO_MATCH,
                requires_rag_fallback=True
            )
    
    async def _match_templates_by_priority(
        self,
        message: str,
        context: Dict[str, Any],
        phone_number: str
    ) -> RouteResult:
        """Match templates in priority order for optimal performance"""
        
        # Priority 0: Objection Handling (needs to be checked before business critical)
        # This prevents "muito caro" from matching pricing instead of price objection
        objection_result = self._match_objection_handling(message, context)
        if objection_result.matched:
            return objection_result
        
        # Priority 1: Business Critical (pricing, contact, hours)
        business_result = self._match_business_critical(message, context)
        if business_result.matched:
            return business_result
        
        # Priority 2: Greeting (common entry point)
        greeting_result = self._match_greeting(message, context)
        if greeting_result.matched:
            return greeting_result
        
        # Priority 3: Program Information
        program_result = self._match_program_info(message, context)
        if program_result.matched:
            return program_result
        
        # Priority 4: Scheduling
        scheduling_result = self._match_scheduling(message, context)
        if scheduling_result.matched:
            return scheduling_result
        
        # No template match - requires RAG fallback
        return RouteResult(
            matched=False,
            response="",
            confidence=0.0,
            template_id="no_match",
            intent_category=IntentCategory.NO_MATCH,
            requires_rag_fallback=True
        )
    
    def _match_business_critical(self, message: str, context: Dict[str, Any]) -> RouteResult:
        """Match business critical queries (pricing, contact, hours)"""
        
        # Check pricing keywords
        pricing_keywords = self.template_library.keyword_patterns["business_critical"]["pricing"]
        if self._contains_keywords(message, pricing_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("business_critical", "pricing"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.BUSINESS_CRITICAL],
                template_id="pricing",
                intent_category=IntentCategory.BUSINESS_CRITICAL,
                context_updates={"last_template_used": "pricing", "showed_pricing": True}
            )
        
        # Check contact keywords
        contact_keywords = self.template_library.keyword_patterns["business_critical"]["contact"]
        if self._contains_keywords(message, contact_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("business_critical", "contact"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.BUSINESS_CRITICAL],
                template_id="contact",
                intent_category=IntentCategory.BUSINESS_CRITICAL,
                context_updates={"last_template_used": "contact", "showed_contact": True}
            )
        
        # Check hours keywords - but NOT if it's about scheduling availability
        message_lower = message.lower()
        if ("horário disponível" not in message_lower and 
            "tem horário" not in message_lower and
            "disponibilidade" not in message_lower):
            
            hours_keywords = self.template_library.keyword_patterns["business_critical"]["hours"]
            if self._contains_keywords(message, hours_keywords):
                return RouteResult(
                    matched=True,
                    response=self._personalize_response(
                        self.template_library.get_template("business_critical", "hours"),
                        context
                    ),
                    confidence=self.confidence_thresholds[IntentCategory.BUSINESS_CRITICAL],
                    template_id="hours",
                    intent_category=IntentCategory.BUSINESS_CRITICAL,
                    context_updates={"last_template_used": "hours", "showed_hours": True}
                )
        
        return RouteResult(matched=False)
    
    def _match_greeting(self, message: str, context: Dict[str, Any]) -> RouteResult:
        """Match greeting messages"""
        
        greeting_keywords = self.template_library.keyword_patterns["greeting"]["welcome"]
        if self._contains_keywords(message, greeting_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("greeting", "welcome"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.GREETING],
                template_id="welcome",
                intent_category=IntentCategory.GREETING,
                context_updates={"last_template_used": "welcome", "greeted": True}
            )
        
        return RouteResult(matched=False)
    
    def _match_program_info(self, message: str, context: Dict[str, Any]) -> RouteResult:
        """Match program information queries"""
        
        # Check benefits keywords first (more specific)
        benefits_keywords = self.template_library.keyword_patterns["program_info"]["benefits"]
        if self._contains_keywords(message, benefits_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("program_info", "benefits"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.PROGRAM_INFO],
                template_id="benefits",
                intent_category=IntentCategory.PROGRAM_INFO,
                context_updates={"last_template_used": "benefits", "showed_benefits": True}
            )
        
        # Check methodology keywords
        methodology_keywords = self.template_library.keyword_patterns["program_info"]["methodology"]
        if self._contains_keywords(message, methodology_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("program_info", "methodology"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.PROGRAM_INFO],
                template_id="methodology",
                intent_category=IntentCategory.PROGRAM_INFO,
                context_updates={"last_template_used": "methodology", "showed_methodology": True}
            )
        
        return RouteResult(matched=False)
    
    def _match_scheduling(self, message: str, context: Dict[str, Any]) -> RouteResult:
        """Match scheduling and appointment queries"""
        
        availability_keywords = self.template_library.keyword_patterns["scheduling"]["availability"]
        if self._contains_keywords(message, availability_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("scheduling", "availability"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.SCHEDULING],
                template_id="availability",
                intent_category=IntentCategory.SCHEDULING,
                context_updates={"last_template_used": "availability", "showed_availability": True}
            )
        
        return RouteResult(matched=False)
    
    def _match_objection_handling(self, message: str, context: Dict[str, Any]) -> RouteResult:
        """Match common objections and concerns"""
        
        # Check price objection keywords
        price_objection_keywords = self.template_library.keyword_patterns["objection_handling"]["price_objection"]
        if self._contains_keywords(message, price_objection_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("objection_handling", "price_objection"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.OBJECTION_HANDLING],
                template_id="price_objection",
                intent_category=IntentCategory.OBJECTION_HANDLING,
                context_updates={"last_template_used": "price_objection", "handled_price_objection": True}
            )
        
        # Check time objection keywords
        time_objection_keywords = self.template_library.keyword_patterns["objection_handling"]["time_objection"]
        if self._contains_keywords(message, time_objection_keywords):
            return RouteResult(
                matched=True,
                response=self._personalize_response(
                    self.template_library.get_template("objection_handling", "time_objection"),
                    context
                ),
                confidence=self.confidence_thresholds[IntentCategory.OBJECTION_HANDLING],
                template_id="time_objection",
                intent_category=IntentCategory.OBJECTION_HANDLING,
                context_updates={"last_template_used": "time_objection", "handled_time_objection": True}
            )
        
        return RouteResult(matched=False)
    
    def _normalize_message(self, message: str) -> str:
        """Normalize message for consistent keyword matching"""
        if not message:
            return ""
        
        # Convert to lowercase and strip whitespace
        normalized = message.lower().strip()
        
        # Remove extra whitespace and special characters (but keep Portuguese accents)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s\áàâãéèêíìîóòôõúùûç]', ' ', normalized)
        
        return normalized
    
    def _contains_keywords(self, message: str, keywords: List[str]) -> bool:
        """Check if message contains any of the specified keywords"""
        if not message or not keywords:
            return False
        
        message_lower = message.lower()
        
        # For single-character keywords or very short ones, require word boundaries
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # For very short keywords (1-2 chars), require exact word match
            if len(keyword_lower) <= 2:
                import re
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                if re.search(pattern, message_lower):
                    return True
            else:
                # For longer keywords, simple substring match is fine
                if keyword_lower in message_lower:
                    return True
        
        return False
    
    def _personalize_response(self, template: Optional[str], context: Dict[str, Any]) -> str:
        """Personalize template response with context information"""
        if not template:
            return ""
        
        # Extract names from context for personalization
        parent_name = context.get("parent_name", "")
        child_name = context.get("child_name", "")
        
        response = template
        
        # Add personalization if names are available
        if parent_name and child_name:
            greeting = f"Olá {parent_name}! 😊\n\n"
            # Add personalized greeting if not already present
            if not response.startswith("Olá") and not response.startswith("Oi"):
                response = greeting + response
                
            # Personalize for child when relevant
            if "seu filho" in response:
                response = response.replace("seu filho", child_name)
        elif parent_name:
            greeting = f"Olá {parent_name}! 😊\n\n"
            if not response.startswith("Olá") and not response.startswith("Oi"):
                response = greeting + response
        
        return response
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            "total_requests": self.stats.total_requests,
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "hit_rate_percentage": self.stats.hit_rate_percentage,
            "avg_processing_time_ms": self.stats.avg_processing_time_ms,
            "target_processing_time_ms": self.total_target_ms,
            "performance_target_met": self.stats.avg_processing_time_ms < self.total_target_ms,
            "last_reset": self.stats.last_reset.isoformat(),
            "templates_loaded": len(self.template_library.templates)
        }
    
    def reset_stats(self):
        """Reset performance statistics"""
        self.stats = TemplateStats()
        app_logger.info("Intent router statistics reset")


# Global instance for dependency injection
intent_first_router = IntentFirstRouter()