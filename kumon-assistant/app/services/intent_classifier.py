"""
Intent classification service using OpenAI
"""
import openai
from typing import Dict, Any
import json

from ..core.config import settings
from ..core.logger import app_logger


class IntentClassifier:
    """Classify user intents from WhatsApp messages"""
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        
        self.intents = {
            "schedule_appointment": [
                "agendar", "marcar", "consulta", "horário", "disponibilidade",
                "quero agendar", "posso marcar", "tem vaga"
            ],
            "ask_question": [
                "como funciona", "o que é", "qual", "quanto custa", "preço",
                "dúvida", "informação", "explicar"
            ],
            "provide_info": [
                "meu filho", "minha filha", "tem", "anos", "está no",
                "nome é", "estuda", "escola"
            ],
            "greeting": [
                "oi", "olá", "bom dia", "boa tarde", "boa noite", "hello"
            ]
        }
    
    async def classify_intent(self, message: str) -> str:
        """Classify the intent of a user message"""
        
        try:
            # First try simple keyword matching for common cases
            message_lower = message.lower()
            
            for intent, keywords in self.intents.items():
                if any(keyword in message_lower for keyword in keywords):
                    app_logger.info(
                        f"Intent classified via keywords: {intent}",
                        extra={"action": "intent_classification"}
                    )
                    return intent
            
            # If no keywords match, use OpenAI for more complex classification
            return await self._classify_with_openai(message)
            
        except Exception as e:
            app_logger.error(f"Intent classification error: {str(e)}")
            return "general_inquiry"
    
    async def _classify_with_openai(self, message: str) -> str:
        """Use OpenAI to classify complex intents"""
        
        prompt = f"""
        Classifique a intenção da seguinte mensagem do WhatsApp em uma das categorias:
        
        1. schedule_appointment - usuário quer agendar uma consulta ou avalização
        2. ask_question - usuário tem dúvidas sobre Kumon, metodologia, preços, etc.
        3. provide_info - usuário está fornecendo informações pessoais (filho, idade, escola)
        4. greeting - cumprimento ou saudação
        5. general_inquiry - outras mensagens gerais
        
        Mensagem: "{message}"
        
        Responda apenas com o nome da categoria em inglês.
        """
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um classificador de intenções para um sistema de atendimento do Kumon."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            intent = response.choices[0].message.content.strip()
            
            app_logger.info(
                f"Intent classified via OpenAI: {intent}",
                extra={"action": "intent_classification_openai"}
            )
            
            return intent if intent in self.intents.keys() or intent == "general_inquiry" else "general_inquiry"
            
        except Exception as e:
            app_logger.error(f"OpenAI classification error: {str(e)}")
            return "general_inquiry" 