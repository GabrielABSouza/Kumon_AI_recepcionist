"""
OpenAI stubs for deterministic testing of LangGraph nodes.
"""
import asyncio
from typing import Any, Dict


class OpenAIStub:
    """Mock OpenAI client for testing."""

    def __init__(self):
        self.responses: Dict[str, Any] = {
            "greeting": [
                "Olá! Seja bem-vindo ao Kumon. Como posso ajudá-lo hoje?",
                "Oi! Bem-vindo à nossa unidade Kumon. Em que posso ajudar?",
                "Olá! É um prazer recebê-lo no Kumon. Como posso auxiliar?",
            ],
            "information": {
                "preço": (
                    "A mensalidade do Kumon é de R$ 450,00 por disciplina, com "
                    "material incluso. Gostaria de agendar uma visita para "
                    "conhecer nossa unidade?"
                ),
                "método": (
                    "O método Kumon desenvolve autodidatismo através de estudo "
                    "diário com material individualizado. Cada aluno progride no "
                    "seu ritmo. Posso agendar uma avaliação diagnóstica gratuita?"
                ),
                "horário": (
                    "Temos aulas às terças e quintas, com horários das 14h às "
                    "18h. O aluno frequenta 2x por semana. Gostaria de conhecer "
                    "nossa unidade?"
                ),
                "material": (
                    "O material é individualizado e desenvolvido especialmente "
                    "para cada nível. Está incluso na mensalidade. Quer agendar "
                    "uma visita?"
                ),
                "idade": (
                    "Atendemos desde os 3 anos até o ensino médio. O importante "
                    "é a avaliação diagnóstica. Posso agendar para seu filho?"
                ),
                "local": (
                    "Estamos na Rua das Flores, 123, Centro. Fácil acesso e "
                    "estacionamento. Quer agendar uma visita?"
                ),
                "geral": (
                    "O Kumon oferece matemática, português e inglês com método "
                    "individualizado. Posso dar mais detalhes em uma visita. "
                    "Gostaria de agendar?"
                ),
            },
            "qualification": {
                "missing_all": (
                    "Para fazer a matrícula, preciso de algumas informações: "
                    "nome do aluno, idade e disciplina de interesse. Pode me "
                    "informar?"
                ),
                "missing_name": "Ótimo! Só preciso do nome do aluno para completar o cadastro.",
                "missing_age": "Perfeito! Qual a idade do aluno?",
                "missing_subject": (
                    "Excelente! Qual disciplina tem interesse? Temos "
                    "matemática, português e inglês."
                ),
                "complete": (
                    "Perfeito! Tenho todas as informações. Vamos agendar sua "
                    "avaliação diagnóstica gratuita?"
                ),
            },
            "scheduling": {
                "initial": (
                    "Ótimo! Para a avaliação diagnóstica, temos horários na "
                    "terça às 14h ou quinta às 16h. Qual prefere?"
                ),
                "confirmation": (
                    "Agendado! Terça-feira às 14h. Enviarei a confirmação por "
                    "WhatsApp. Endereço: Rua das Flores, 123."
                ),
                "reschedule": (
                    "Sem problemas! Temos também quarta às 15h ou sexta às "
                    "14h. Qual fica melhor?"
                ),
                "followup": (
                    "Anotado! Confirmarei o agendamento e enviarei um lembrete "
                    "na véspera. Alguma dúvida?"
                ),
            },
            "fallback": [
                (
                    "Desculpe, não entendi. Você quer saber sobre valores, "
                    "método ou agendar visita?"
                ),
                (
                    "Perdão, pode reformular? Posso ajudar com informações ou "
                    "agendamento."
                ),
                (
                    "Não compreendi. Estou aqui para informações sobre o Kumon "
                    "ou agendar sua visita."
                ),
            ],
        }

        self.call_count = 0
        self.last_prompt = None
        self.behavior = "deterministic"  # deterministic, random, error
        self.delay_ms = 10

    async def generate(self, node_type: str, context: Dict[str, Any]) -> str:
        """Generate response for node type with context."""
        self.call_count += 1
        self.last_prompt = (node_type, context)

        # Simulate delay
        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.behavior == "error":
            raise Exception("OpenAI API error simulation")

        # Get appropriate response based on node type
        if node_type == "greeting":
            return self.responses["greeting"][0]

        elif node_type == "information":
            topic = context.get("topic", "geral")
            return self.responses["information"].get(
                topic, self.responses["information"]["geral"]
            )

        elif node_type == "qualification":
            # Check what's missing
            missing = []
            if "student_name" not in context:
                missing.append("name")
            if "student_age" not in context:
                missing.append("age")
            if "subject" not in context:
                missing.append("subject")

            if not missing:
                return self.responses["qualification"]["complete"]
            elif len(missing) == 3:
                return self.responses["qualification"]["missing_all"]
            elif "name" in missing:
                return self.responses["qualification"]["missing_name"]
            elif "age" in missing:
                return self.responses["qualification"]["missing_age"]
            else:
                return self.responses["qualification"]["missing_subject"]

        elif node_type == "scheduling":
            if context.get("has_preference"):
                return self.responses["scheduling"]["confirmation"]
            elif context.get("needs_reschedule"):
                return self.responses["scheduling"]["reschedule"]
            else:
                return self.responses["scheduling"]["initial"]

        elif node_type == "fallback":
            return self.responses["fallback"][0]

        else:
            return self.responses["fallback"][0]

    def set_response(self, node_type: str, response: str):
        """Override response for specific node type."""
        if node_type in ["greeting", "fallback"]:
            self.responses[node_type][0] = response
        elif node_type == "information":
            self.responses[node_type]["geral"] = response
        elif node_type == "qualification":
            self.responses[node_type]["complete"] = response
        elif node_type == "scheduling":
            self.responses[node_type]["initial"] = response

    def reset(self):
        """Reset stub to initial state."""
        self.call_count = 0
        self.last_prompt = None
        self.behavior = "deterministic"
        self.delay_ms = 10


class OpenAIErrorStub(OpenAIStub):
    """Stub that simulates OpenAI errors."""

    def __init__(self, error_type="timeout"):
        super().__init__()
        self.error_type = error_type

    async def generate(
        self, _node_type: str, _context: Dict[str, Any]  # noqa: U101
    ) -> str:
        """Simulate various error conditions."""
        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.error_type == "timeout":
            await asyncio.sleep(2)  # Simulate timeout
            raise asyncio.TimeoutError("OpenAI request timeout")
        elif self.error_type == "rate_limit":
            raise Exception("Rate limit exceeded")
        elif self.error_type == "api_error":
            raise Exception("OpenAI API error: Internal server error")
        else:
            raise Exception(f"Unknown error: {self.error_type}")


class OpenAIMultilingualStub(OpenAIStub):
    """Stub that sometimes returns non-Portuguese responses."""

    def __init__(self):
        super().__init__()
        self.language_mode = "mixed"  # mixed, english, portuguese

    async def generate(self, node_type: str, context: Dict[str, Any]) -> str:
        """Generate responses that may not be in Portuguese."""
        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.language_mode == "english":
            # Return English responses
            english_responses = {
                "greeting": "Hello! Welcome to Kumon. How can I help you?",
                "information": (
                    "The monthly fee is $450. Would you like to schedule a " "visit?"
                ),
                "qualification": (
                    "I need the student's name, age, and subject of interest."
                ),
                "scheduling": "We have slots on Tuesday at 2pm or Thursday at 4pm.",
                "fallback": "Sorry, I didn't understand. Can you please rephrase?",
            }
            return english_responses.get(node_type, "I don't understand.")

        elif self.language_mode == "mixed":
            # Sometimes return English
            import random

            if random.random() < 0.3:  # 30% chance of English
                return await self.generate_english(node_type)
            else:
                return await super().generate(node_type, context)
        else:
            # Portuguese only
            return await super().generate(node_type, context)

    async def generate_english(self, node_type: str) -> str:
        """Generate English response."""
        english = {
            "greeting": "Hello! Welcome to Kumon.",
            "information": "The tuition is $450 per month.",
            "qualification": "What's the student's name?",
            "scheduling": "Tuesday at 2pm works?",
            "fallback": "Sorry, I don't understand.",
        }
        return english.get(node_type, "Can you repeat?")
