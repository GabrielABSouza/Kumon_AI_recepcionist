"""
Intent classification service using OpenAI
"""
from openai import AsyncOpenAI
from typing import Dict, Any
import json

from ..core.config import settings
from ..core.logger import app_logger
from ..models.intent import Intent, IntentType


class IntentClassifier:
    """Classify user intents from WhatsApp messages"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        self.intents = {
            "schedule_appointment": [
                "agendar", "marcar", "consulta", "horário", "disponibilidade",
                "quero agendar", "posso marcar", "tem vaga"
            ],
            "question": [
                "como funciona", "o que é", "qual", "quanto custa", "preço",
                "dúvida", "informação", "explicar"
            ],
            "provide_info": [
                "meu filho", "minha filha", "tem", "anos", "está no",
                "nome é", "estuda", "escola"
            ],
            "greeting": [
                "oi", "olá", "bom dia", "boa tarde", "boa noite", "hello", "buenos dias", "buenas tardes", "buenas noches", "hola"
            ],
            "business_info": [
                "endereço", "localização", "onde fica", "telefone", "horário de funcionamento"
            ],
            "complaint": [
                "reclamação", "problema", "insatisfeito", "ruim", "péssimo"
            ]
        }
    
    async def classify_intent(self, message: str) -> Intent:
        """Classify the intent of a user message"""
        
        try:
            # First try simple keyword matching for common cases
            message_lower = message.lower()
            
            for intent_name, keywords in self.intents.items():
                if any(keyword in message_lower for keyword in keywords):
                    app_logger.info(
                        f"Intent classified via keywords: {intent_name}",
                        extra={"action": "intent_classification"}
                    )
                    return Intent(
                        intent_type=IntentType(intent_name),
                        confidence=0.8,
                        raw_message=message,
                        classification_method="keyword"
                    )
            
            # If no keywords match, use OpenAI for more complex classification
            return await self._classify_with_openai(message)
            
        except Exception as e:
            app_logger.error(f"Intent classification error: {str(e)}")
            return Intent(
                intent_type=IntentType.GENERAL_INQUIRY,
                confidence=0.5,
                raw_message=message,
                classification_method="fallback"
            )
    
    async def _classify_with_openai(self, message: str) -> Intent:
        """Use OpenAI to classify complex intents"""
        
        prompt = f"""
        Classifique a intenção da seguinte mensagem do WhatsApp em uma das categorias:
        
        1. schedule_appointment - usuário quer agendar uma consulta ou avaliação
        2. question - usuário tem dúvidas sobre Kumon, metodologia, preços, etc.
        3. provide_info - usuário está fornecendo informações pessoais (filho, idade, escola)
        4. greeting - cumprimento ou saudação
        5. business_info - usuário quer informações sobre localização, telefone, horários
        6. complaint - usuário tem reclamação ou problema
        7. general_inquiry - outras mensagens gerais
        
        Mensagem: "{message}"
        
        Responda apenas com o nome da categoria em inglês.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um classificador de intenções para um sistema de atendimento do Kumon."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            intent_string = response.choices[0].message.content.strip()
            
            app_logger.info(
                f"Intent classified via OpenAI: {intent_string}",
                extra={"action": "intent_classification_openai"}
            )
            
            # Map to IntentType
            try:
                intent_type = IntentType(intent_string)
            except ValueError:
                intent_type = IntentType.GENERAL_INQUIRY
            
            return Intent(
                intent_type=intent_type,
                confidence=0.9,
                raw_message=message,
                classification_method="openai"
            )
            
        except Exception as e:
            app_logger.error(f"OpenAI classification error: {str(e)}")
            return Intent(
                intent_type=IntentType.GENERAL_INQUIRY,
                confidence=0.5,
                raw_message=message,
                classification_method="fallback"
            ) 