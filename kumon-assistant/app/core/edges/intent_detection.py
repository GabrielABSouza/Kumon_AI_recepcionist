"""
Intent Detection for Conversation Routing

Implementa detecção de intenções do usuário para roteamento inteligente.
Migrado das funções de detecção do conversation_flow.py conforme documentação.
"""

import re
from typing import List
import logging

logger = logging.getLogger(__name__)


class IntentDetector:
    """
    Detecta intenções específicas do usuário para roteamento
    MIGRAR: Todas as funções de detecção do conversation_flow.py
    """
    
    def detect_booking_intent(self, user_message: str) -> bool:
        """
        Detecta intenção de agendamento direto
        MIGRAR: _detect_booking_intent() do conversation_flow.py
        """
        message_lower = user_message.lower()
        
        booking_patterns = [
            # Diretos
            "quero agendar", "vou agendar", "quero marcar", "vou marcar",
            "agendar", "marcar", "scheduling", "appointment",
            "quando posso", "horário", "disponibilidade", "agenda",
            
            # Indiretos  
            "quero visitar", "gostaria de conhecer", "quero ir",
            "posso ir", "quando vocês", "que horas", "funciona quando",
            
            # Com qualificadores
            "quero ver", "quero saber na prática", "quero conhecer pessoalmente",
            "gostaria de uma visita", "posso fazer uma visita"
        ]
        
        return any(pattern in message_lower for pattern in booking_patterns)
    
    def detect_information_request(self, user_message: str) -> bool:
        """
        Detecta solicitação de informações
        MIGRAR: _detect_information_request() do conversation_flow.py
        """
        message_lower = user_message.lower()
        
        info_patterns = [
            # Perguntas diretas
            "como funciona", "o que é", "quanto custa", "qual o preço",
            "quais são", "como é", "me explica", "pode explicar",
            
            # Curiosidade
            "quero saber", "gostaria de saber", "preciso entender",
            "não sei", "não conheço", "nunca ouvi",
            
            # Específicos do Kumon
            "metodologia", "material", "método", "diferença",
            "vantagem", "benefício", "resultado"
        ]
        
        return any(pattern in message_lower for pattern in info_patterns)
    
    def detect_skip_questions(self, user_message: str) -> bool:
        """
        Detecta intenção de pular perguntas e ir direto ao agendamento
        MIGRAR: _detect_skip_questions() linha 920 aprox
        """
        message_lower = user_message.lower()
        
        skip_patterns = [
            # Diretos
            "pular", "pula", "vai direto", "sem perguntas", "só agendar",
            "não precisa", "já sei", "dispensa", "pode pular",
            
            # Com negação
            "não quero", "não preciso", "não vou", "não vamos",
            
            # Pressa
            "tenho pressa", "rápido", "direto", "urgente",
            "sem enrolação", "objetivo"
        ]
        
        # Padrão "não" + "quero agendar"
        if re.search(r'\b(não|nao).*(quero|vou|preciso).*(agendar|marcar)\b', message_lower):
            return True
        
        return any(pattern in message_lower for pattern in skip_patterns)
    
    def detect_human_help_request(self, user_message: str) -> bool:
        """
        Detecta solicitação de ajuda humana
        MIGRAR: _detect_human_help_request() linha 950 aprox
        """
        message_lower = user_message.lower()
        
        human_help_patterns = [
            # Diretos
            "falar com", "atendente", "pessoa", "humano", "representante",
            "funcionário", "funcionaria", "alguém", "operador",
            
            # Indiretos
            "não está ajudando", "não entendo", "muito confuso",
            "não serve", "quero ajuda", "preciso de ajuda",
            
            # Frustração
            "desisto", "cansei", "chato", "complicado demais",
            "não funciona", "não resolve", "péssimo"
        ]
        
        return any(pattern in message_lower for pattern in human_help_patterns)
    
    def detect_dissatisfaction(self, user_message: str) -> bool:
        """
        Detecta insatisfação do usuário
        MIGRAR: _detect_dissatisfaction() linha 980 aprox
        """
        message_lower = user_message.lower()
        
        dissatisfaction_patterns = [
            # Confusão
            "não entendi", "não entendo", "confuso", "não ficou claro",
            "não sei", "como assim", "o que", "hein", "que",
            
            # Feedback negativo
            "não ajudou", "não serve", "não é isso", "não quero isso",
            "ruim", "péssimo", "horrível", "não gostei",
            
            # Repetição
            "já falei", "já disse", "repetindo", "de novo",
            "outra vez", "sempre a mesma",
            
            # Frustração
            "irritante", "chato", "cansativo", "demora",
            "não funciona", "não adianta", "inútil"
        ]
        
        return any(pattern in message_lower for pattern in dissatisfaction_patterns)
    
    def detect_confusion(self, user_message: str) -> bool:
        """
        Detecta confusão do usuário
        MIGRAR: _detect_confusion() linha 1100 aprox
        """
        message_lower = user_message.lower()
        
        confusion_indicators = [
            "não entendi", "não entendo", "confuso", "como assim",
            "que", "o que", "hein", "não sei", "não ficou claro",
            "explica melhor", "não compreendi"
        ]
        
        # Verificar indicadores
        if any(indicator in message_lower for indicator in confusion_indicators):
            return True
        
        # Mensagens muito curtas
        if len(user_message.strip()) < 3:
            return True
        
        # Só pontuação
        if user_message.strip() in ["?", "!", ".", "...", "??", "!!", "???"]:
            return True
        
        # Só números sem contexto
        if user_message.strip().isdigit() and len(user_message.strip()) < 3:
            return True
        
        return False
    
    def detect_engagement_question(self, user_message: str) -> bool:
        """
        Detecta pergunta de engajamento
        MIGRAR: _is_engagement_question() linha 2050 aprox
        """
        message_lower = user_message.lower()
        
        engagement_indicators = [
            "quando", "como começar", "matrícula", "inscrição", "interesse",
            "quero saber mais", "gostaria de", "preciso de", "como funciona na prática"
        ]
        
        return any(indicator in message_lower for indicator in engagement_indicators)
    
    def extract_program_interest(self, user_message: str) -> List[str]:
        """Extrai interesse em programas específicos"""
        programs = []
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ['matemática', 'matematica', 'mat', 'cálculo']):
            programs.append('matematica')
        if any(word in message_lower for word in ['português', 'portugues', 'redação']):
            programs.append('portugues')
        if any(word in message_lower for word in ['inglês', 'ingles', 'english']):
            programs.append('ingles')
        
        return programs
    
    def extract_age(self, user_message: str) -> int:
        """Extrai idade da mensagem"""
        age_patterns = [
            r'\b(\d{1,2})\s*anos?\b',
            r'\bidade\s*(\d{1,2})\b',
            r'\btem\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*a\b'
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, user_message.lower())
            if match:
                age = int(match.group(1))
                if 2 <= age <= 70:  # Validação
                    return age
        
        return None
    
    def extract_email(self, user_message: str) -> str:
        """Extrai email da mensagem"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, user_message)
        return match.group(0) if match else None