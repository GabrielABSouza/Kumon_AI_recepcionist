# app/core/intent_patterns_ptbr.py
"""
Intent Patterns PT-BR - High Impact Regex Patterns para Kumon

Patterns otimizados para o contexto Kumon com foco em:
- Scheduling (marcar/remarcar/cancelar)  
- Information (preço/horário/endereço/programa)
- Service specifics (matemática/português/inglês)
- Professional queries (orientador/professor)
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class IntentPattern:
    """Intent pattern with metadata"""
    intent: str
    pattern: str
    confidence_boost: float = 0.0
    priority: int = 1
    description: str = ""
    examples: List[str] = None
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []


class KumonIntentPatternsPTBR:
    """
    High-impact regex patterns para intents Kumon em PT-BR
    
    Prioriza patterns que mais caem em fallback/handoff no shadow traffic
    """
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.compiled_patterns = self._compile_patterns()
    
    def _initialize_patterns(self) -> List[IntentPattern]:
        """Initialize all intent patterns organized by category"""
        
        patterns = []
        
        # ========== SCHEDULING INTENTS (Alta prioridade) ==========
        
        patterns.extend([
            IntentPattern(
                intent="scheduling.book",
                pattern=r'\b(agend(ar|amento)( (um|uma)? (hor[aá]rio|sess[aã]o|aula|avalia[cç][aã]o)|.{0,20}(filh[oa]|crian[cç]a))|marcar (um )?hor[aá]rio|reservar (um|uma)? (hor[aá]rio|sess[aã]o|aula)|consulta|avalia[cç][aã]o gratuita)\b',
                confidence_boost=0.15,
                priority=1,
                description="Agendar nova aula/avaliação",
                examples=[
                    "gostaria de agendar uma avaliação",
                    "posso marcar um horário",
                    "quero reservar uma aula",
                    "agendamento para minha filha"
                ]
            ),
            IntentPattern(
                intent="scheduling.reschedule", 
                pattern=r'\b(reagend(ar|amento)|remarcar|mudar (o )?hor[aá]rio|adiar|antecipar|transfer[ií]r|alterar (o )?agendamento)\b',
                confidence_boost=0.12,
                priority=1,
                description="Reagendar aula existente",
                examples=[
                    "preciso remarcar a aula",
                    "posso mudar o horário", 
                    "reagendar para outro dia",
                    "alterar agendamento"
                ]
            ),
            IntentPattern(
                intent="scheduling.cancel",
                pattern=r'\b(cancel(ar|amento)|desmarcar|n[aã]o vou (poder|conseguir)|n[aã]o posso (ir|comparecer)|desistir|cancelar (a )?aula)\b',
                confidence_boost=0.10,
                priority=1,
                description="Cancelar aula agendada",
                examples=[
                    "preciso cancelar a aula",
                    "não vou poder ir hoje",
                    "desmarcar o horário",
                    "cancelamento da sessão"
                ]
            ),
            IntentPattern(
                intent="scheduling.status",
                pattern=r'\b(confirma[cç][aã]o|confirmad[oa]|confirmar|status (do )?agendamento|minha aula|pr[oó]xim[oa] aula|hor[aá]rio marcado)\b',
                confidence_boost=0.08,
                priority=2,
                description="Status do agendamento",
                examples=[
                    "confirmar minha aula",
                    "qual o status do agendamento",
                    "quando é minha próxima aula"
                ]
            )
        ])
        
        # ========== GREETING/GENERAL INTENTS (Alta prioridade) ==========
        
        patterns.extend([
            IntentPattern(
                intent="greeting.hello",
                pattern=r'\b(ol[aáeé]|oi|bom dia|boa tarde|boa noite|tudo bem)\b',
                confidence_boost=0.08,
                priority=1,
                description="Saudações iniciais",
                examples=[
                    "Olá", "Oi", "Bom dia", "Boa tarde"
                ]
            ),
            IntentPattern(
                intent="information.general",
                pattern=r'\b(informa[cç][oõ]es|sobre o kumon|gostaria de saber|queria saber|me fale sobre|conhecer)\b',
                confidence_boost=0.10,
                priority=1,
                description="Pedidos gerais de informação",
                examples=[
                    "gostaria de informações",
                    "quero saber sobre o Kumon",
                    "me fale sobre o método"
                ]
            )
        ])
        
        # ========== INFORMATION INTENTS (Média-alta prioridade) ==========
        
        patterns.extend([
            IntentPattern(
                intent="information.price",
                pattern=r'\b(pre[cç]o(s)?|valor(es)?|tabela de pre[cç]os|quanto custa|quanto (sai|fica)|mensalidade|custo|investimento|or[cç]amento)\b',
                confidence_boost=0.10,
                priority=2,
                description="Informações de preço",
                examples=[
                    "qual o preço do Kumon",
                    "quanto custa a mensalidade",
                    "valores dos programas",
                    "preciso de um orçamento"
                ]
            ),
            IntentPattern(
                intent="information.hours",
                pattern=r'\b(hor[aá]rios? (de funcionamento|de atendimento|dispon[ií]veis)|que horas (abre|fecha)|expediente|funcionamento)\b',
                confidence_boost=0.08,
                priority=2,
                description="Horários de funcionamento",
                examples=[
                    "horários de funcionamento",
                    "que horas abre a unidade",
                    "horários disponíveis",
                    "expediente do Kumon"
                ]
            ),
            IntentPattern(
                intent="information.address",
                pattern=r'\b(endere[cç]o|local(iza[cç][aã]o)?|onde fica|como chegar|mapa|rua|avenida|n[uú]mero|CEP)\b',
                confidence_boost=0.08,
                priority=2,
                description="Localização da unidade",
                examples=[
                    "qual o endereço do Kumon",
                    "onde fica a unidade",
                    "como chegar aí",
                    "localização do Kumon Vila A"
                ]
            ),
            IntentPattern(
                intent="information.programs",
                pattern=r'\b(programa(s)?|m[eé]todo|metodologia|como funciona|mat[eé]rias?|disciplinas?|o que [eé] o kumon)\b',
                confidence_boost=0.08,
                priority=2,
                description="Informações sobre programas",
                examples=[
                    "como funciona o método",
                    "quais programas vocês têm",
                    "o que é o Kumon",
                    "que matérias têm"
                ]
            )
        ])
        
        # ========== KUMON SPECIFIC SUBJECTS (Média prioridade) ==========
        
        patterns.extend([
            IntentPattern(
                intent="service.math",
                pattern=r'\b(matem[aá]tica|mat|c[aá]lculo|n[uú]meros|aritm[eé]tica|[aá]lgebra|geometria|tabuada)\b',
                confidence_boost=0.06,
                priority=3,
                description="Programa de Matemática",
                examples=[
                    "programa de matemática",
                    "Kumon de mat",
                    "aulas de cálculo",
                    "matemática para crianças"
                ]
            ),
            IntentPattern(
                intent="service.portuguese",
                pattern=r'\b(portugu[eê]s|l[eií]tura|escrita|redação|interpretação|texto|gram[aá]tica)\b',
                confidence_boost=0.06,
                priority=3,
                description="Programa de Português",
                examples=[
                    "programa de português",
                    "aulas de leitura",
                    "português para crianças",
                    "redação e interpretação"
                ]
            ),
            IntentPattern(
                intent="service.english",
                pattern=r'\b(ingl[eê]s|english|l[ií]ngua inglesa|idioma)\b',
                confidence_boost=0.06,
                priority=3,
                description="Programa de Inglês",
                examples=[
                    "programa de inglês",
                    "English do Kumon",
                    "língua inglesa para crianças"
                ]
            )
        ])
        
        # ========== PROFESSIONAL/STAFF INTENTS ==========
        
        patterns.extend([
            IntentPattern(
                intent="staff.orientador",
                pattern=r'\b(orientador(a)?|professor(a)?|instrutor(a)?|educador(a)?|respons[aá]vel|quem (atende|ensina|orienta))\b',
                confidence_boost=0.05,
                priority=3,
                description="Perguntas sobre orientadores",
                examples=[
                    "quem é o orientador",
                    "professora responsável",
                    "quem atende as crianças"
                ]
            )
        ])
        
        # ========== AGE/EDUCATION LEVEL INTENTS ==========
        
        patterns.extend([
            IntentPattern(
                intent="information.age_range",
                pattern=r'\b((a partir de|desde os?|crian[cç]as? de) \d+|idade|faixa et[aá]ria|anos?|educa[cç][aã]o infantil|ensino fundamental|ensino m[eé]dio)\b',
                confidence_boost=0.04,
                priority=4,
                description="Faixas etárias atendidas",
                examples=[
                    "a partir de que idade",
                    "crianças de 5 anos",
                    "ensino fundamental",
                    "qual a faixa etária"
                ]
            )
        ])
        
        # ========== TIME/TEMPORAL EXPRESSIONS ==========
        
        patterns.extend([
            IntentPattern(
                intent="temporal.today",
                pattern=r'\b(hoje|neste momento|agora|j[aá]|ainda hoje)\b',
                confidence_boost=0.05,
                priority=4,
                description="Referência temporal - hoje"
            ),
            IntentPattern(
                intent="temporal.tomorrow",
                pattern=r'\b(amanh[ãa]|dia seguinte)\b',
                confidence_boost=0.05,
                priority=4,
                description="Referência temporal - amanhã"
            ),
            IntentPattern(
                intent="temporal.weekday",
                pattern=r'\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(-feira)?\b',
                confidence_boost=0.05,
                priority=4,
                description="Dias da semana"
            ),
            IntentPattern(
                intent="temporal.time",
                pattern=r'\b\d{1,2}:\d{2}|(\d{1,2}h(\d{2})?)|((de )?manh[ãa]|tarde|noite|meio[- ]dia)\b',
                confidence_boost=0.05,
                priority=4,
                description="Horários específicos"
            )
        ])
        
        # ========== PAYMENT INTENTS ==========
        
        patterns.extend([
            IntentPattern(
                intent="payment.methods",
                pattern=r'\b(forma(s)? de pagamento|pix|cart[aã]o|cr[eé]dito|d[eé]bito|dinheiro|parcel(ar|amento)|boleto)\b',
                confidence_boost=0.05,
                priority=4,
                description="Formas de pagamento",
                examples=[
                    "formas de pagamento",
                    "aceita cartão",
                    "posso pagar no pix",
                    "parcelamento disponível"
                ]
            )
        ])
        
        return patterns
    
    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, IntentPattern]]]:
        """Compile regex patterns for performance"""
        
        compiled = {}
        
        for pattern_obj in self.patterns:
            compiled_regex = re.compile(pattern_obj.pattern, re.IGNORECASE)
            
            intent_category = pattern_obj.intent.split('.')[0]
            if intent_category not in compiled:
                compiled[intent_category] = []
            
            compiled[intent_category].append((compiled_regex, pattern_obj))
        
        # Sort by priority within each category
        for category in compiled:
            compiled[category].sort(key=lambda x: x[1].priority)
        
        return compiled
    
    def extract_intents(self, message: str, min_confidence: float = 0.1) -> List[Dict[str, any]]:
        """
        Extract intents from message using PT-BR patterns
        
        Args:
            message: User message text
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of detected intents with confidence scores
        """
        
        detected_intents = []
        message_lower = message.lower()
        
        # Check each category of patterns
        for category, pattern_list in self.compiled_patterns.items():
            
            for compiled_regex, pattern_obj in pattern_list:
                
                matches = list(compiled_regex.finditer(message_lower))
                
                if matches:
                    # Calculate confidence based on pattern quality and matches
                    base_confidence = 0.6  # Base confidence for regex match
                    boost = pattern_obj.confidence_boost
                    match_density = len(matches) / len(message.split())  # Match density bonus
                    
                    # Priority bonus (higher priority = higher confidence)
                    priority_bonus = (5 - pattern_obj.priority) * 0.02
                    
                    final_confidence = min(0.95, base_confidence + boost + match_density + priority_bonus)
                    
                    if final_confidence >= min_confidence:
                        detected_intents.append({
                            "intent": pattern_obj.intent,
                            "confidence": final_confidence,
                            "pattern_source": "ptbr_regex",
                            "matches": [m.group() for m in matches],
                            "description": pattern_obj.description
                        })
        
        # Sort by confidence descending
        detected_intents.sort(key=lambda x: x["confidence"], reverse=True)
        
        return detected_intents
    
    def get_patterns_by_category(self, category: str) -> List[IntentPattern]:
        """Get patterns by category (scheduling, information, etc.)"""
        
        return [p for p in self.patterns if p.intent.startswith(category)]
    
    def get_high_priority_patterns(self, max_priority: int = 2) -> List[IntentPattern]:
        """Get high priority patterns (1-2 priority level)"""
        
        return [p for p in self.patterns if p.priority <= max_priority]
    
    def test_pattern(self, pattern_intent: str, test_messages: List[str]) -> Dict[str, any]:
        """
        Test specific pattern against test messages
        
        Args:
            pattern_intent: Intent to test (e.g., "scheduling.book")
            test_messages: List of test messages
            
        Returns:
            Test results with matches and misses
        """
        
        # Find pattern
        pattern_obj = None
        for p in self.patterns:
            if p.intent == pattern_intent:
                pattern_obj = p
                break
        
        if not pattern_obj:
            return {"error": f"Pattern {pattern_intent} not found"}
        
        compiled_pattern = re.compile(pattern_obj.pattern, re.IGNORECASE)
        
        matches = []
        misses = []
        
        for message in test_messages:
            detected = self.extract_intents(message)
            intent_detected = any(d["intent"] == pattern_intent for d in detected)
            
            if intent_detected:
                matches.append(message)
            else:
                misses.append(message)
        
        return {
            "pattern": pattern_obj.pattern,
            "total_messages": len(test_messages),
            "matches": len(matches),
            "misses": len(misses),
            "accuracy": len(matches) / len(test_messages) if test_messages else 0,
            "matched_messages": matches[:5],  # Show first 5 matches
            "missed_messages": misses[:5]     # Show first 5 misses
        }
    
    def generate_negative_tests(self) -> List[Tuple[str, str]]:
        """
        Generate negative test cases to avoid false positives
        
        Returns:
            List of (message, should_not_match_intent) tuples
        """
        
        negative_tests = [
            ("horário de almoço do professor", "information.hours"),  # Should not match hours
            ("preço do material escolar", "information.price"),      # Might be ambiguous
            ("cancelar assinatura de e-mail", "scheduling.cancel"),   # Wrong context
            ("agendar entrega", "scheduling.book"),                  # Wrong service type
            ("matemática é difícil", "service.math"),               # Comment, not request
            ("meu filho não gosta de português", "service.portuguese"), # Complaint
            ("professor particular de inglês", "staff.orientador"),  # Different service
            ("horário do shopping", "information.hours"),           # Wrong location
            ("endereço da escola", "information.address")          # Different institution
        ]
        
        return negative_tests


# Global instance
kumon_intent_patterns = KumonIntentPatternsPTBR()