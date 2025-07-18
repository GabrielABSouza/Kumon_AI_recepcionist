"""
RAG engine for answering questions using few-shot learning with OpenAI
"""
from openai import AsyncOpenAI
from typing import Dict, Any, List, Optional
import json
import os
from pathlib import Path

from ..core.config import settings
from ..core.logger import app_logger


class FewShotExample:
    """Structure for few-shot examples"""
    
    def __init__(self, question: str, answer: str, category: str = "general", keywords: List[str] = None, context: Dict[str, Any] = None):
        self.question = question
        self.answer = answer
        self.category = category
        self.keywords = keywords or []
        self.context = context or {}


class RAGEngine:
    """RAG engine for question answering using few-shot learning"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.few_shot_examples = self._load_few_shot_examples()
        app_logger.info(f"RAG Engine initialized with {len(self.few_shot_examples)} few-shot examples")
    
    def _load_few_shot_examples(self) -> List[FewShotExample]:
        """Load few-shot examples from JSON file"""
        
        try:
            # Get the path to the JSON file
            current_dir = Path(__file__).parent.parent
            json_file = current_dir / "data" / "few_shot_examples.json"
            
            if not json_file.exists():
                app_logger.warning(f"Few-shot examples file not found: {json_file}")
                return self._get_default_examples()
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            examples = []
            for item in data.get("examples", []):
                example = FewShotExample(
                    question=item.get("question", ""),
                    answer=item.get("answer", ""),
                    category=item.get("category", "general"),
                    keywords=item.get("keywords", []),
                    context=item.get("context", {})
                )
                examples.append(example)
            
            app_logger.info(f"Loaded {len(examples)} few-shot examples from JSON file")
            return examples
            
        except Exception as e:
            app_logger.error(f"Error loading few-shot examples from JSON: {str(e)}")
            return self._get_default_examples()
    
    def _get_default_examples(self) -> List[FewShotExample]:
        """Fallback default examples if JSON loading fails"""
        
        return [
            FewShotExample(
                question="Como funciona a metodologia Kumon?",
                answer="A metodologia Kumon é baseada no aprendizado individualizado e progressivo. Cada aluno avança no seu próprio ritmo, começando em um ponto onde se sente confortável e progredindo gradualmente. Os materiais são autoinstrutivos, permitindo que o aluno desenvolva independência e confiança nos estudos. 📚✨",
                category="methodology",
                keywords=["metodologia", "funciona", "como", "método", "ensino"]
            ),
            FewShotExample(
                question="Com que idade meu filho pode começar no Kumon?",
                answer="O Kumon atende alunos a partir dos 2 anos de idade! Para crianças pequenas, temos atividades lúdicas que desenvolvem coordenação motora e conceitos básicos. Cada idade tem atividades adequadas ao seu desenvolvimento. Que idade tem seu filho? 👶📖",
                category="age_requirements",
                keywords=["idade", "começar", "pequeno", "criança", "mínima"]
            ),
            FewShotExample(
                question="Quanto custa o Kumon?",
                answer="Os valores variam de acordo com as disciplinas selecionadas. Para informações precisas sobre mensalidades e taxas do Kumon Vila A, entre em contato conosco no (51) 99692-1999 ou kumonvilaa@gmail.com. Será um prazer agendar uma consulta gratuita para conhecer melhor nossa proposta! 💰📞",
                category="pricing",
                keywords=["preço", "custa", "valor", "mensalidade", "quanto", "custo"]
            ),
            FewShotExample(
                question="Qual o telefone e endereço da unidade?",
                answer="A unidade Kumon Vila A está localizada na Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras. Nosso telefone é (51) 99692-1999 e nosso e-mail é kumonvilaa@gmail.com. Funcionamos de segunda a sexta das 08:00 às 18:00 e sábado das 08:00 às 12:00. Esperamos sua visita! 📍📞",
                category="contact",
                keywords=["telefone", "endereço", "localização", "contato", "unidade"]
            )
        ]
    
    def _find_similar_examples(self, question: str, max_examples: int = 3) -> List[FewShotExample]:
        """Find similar examples based on keywords and content with improved scoring"""
        
        question_lower = question.lower()
        scored_examples = []
        
        for example in self.few_shot_examples:
            score = 0
            
            # Keyword matching (high weight)
            for keyword in example.keywords:
                if keyword.lower() in question_lower:
                    score += 5
            
            # Question text similarity (medium weight)
            example_words = example.question.lower().split()
            question_words = question_lower.split()
            
            for word in question_words:
                if len(word) > 3:  # Only consider meaningful words
                    if word in example.question.lower():
                        score += 3
                    elif any(word in example_word for example_word in example_words):
                        score += 1
            
            # Category bonus for direct matches
            if any(cat_word in question_lower for cat_word in ["preço", "custa", "valor"] if example.category == "pricing"):
                score += 2
            
            if score > 0:
                scored_examples.append((score, example))
        
        # Sort by score and return top examples
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        return [example for score, example in scored_examples[:max_examples]]
    
    async def answer_question(self, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Answer user question using few-shot learning approach"""
        
        try:
            # Find similar examples
            similar_examples = self._find_similar_examples(question)
            
            app_logger.info(f"Found {len(similar_examples)} similar examples for question", extra={
                "question_preview": question[:50],
                "examples_categories": [ex.category for ex in similar_examples]
            })
            
            if not similar_examples:
                return await self._generate_general_response(question, context)
            
            # Build few-shot prompt
            few_shot_prompt = self._build_few_shot_prompt(question, similar_examples, context)
            
            # Get response from OpenAI using new API
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system", 
                        "content": "Você é uma recepcionista virtual do Kumon, sempre educada, prestativa e entusiasta da educação. Use emojis de forma moderada e mantenha um tom profissional mas amigável. Responda baseado nos exemplos fornecidos."
                    },
                    {
                        "role": "user", 
                        "content": few_shot_prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            answer = response.choices[0].message.content.strip()
            
            app_logger.info(
                f"Question answered using few-shot learning",
                extra={
                    "question_length": len(question),
                    "similar_examples_found": len(similar_examples),
                    "answer_length": len(answer)
                }
            )
            
            return answer
            
        except Exception as e:
            app_logger.error(f"Error in few-shot question answering: {str(e)}")
            return "Desculpe, não consegui processar sua pergunta no momento. Você poderia reformular ou entrar em contato pelo telefone para atendimento direto? 📞"
    
    def _build_few_shot_prompt(self, question: str, examples: List[FewShotExample], context: Optional[Dict[str, Any]] = None) -> str:
        """Build few-shot prompt with examples and context"""
        
        prompt = "Com base nos exemplos abaixo, responda à pergunta do usuário de forma similar, mantendo o mesmo tom e estilo:\n\n"
        
        # Add examples
        for i, example in enumerate(examples, 1):
            prompt += f"Exemplo {i}:\n"
            prompt += f"Pergunta: {example.question}\n"
            prompt += f"Resposta: {example.answer}\n\n"
        
        # Add context information if available
        if context:
            prompt += "Informações adicionais da unidade:\n"
            if context.get("username"):
                prompt += f"- Unidade: {context['username']}\n"
            if context.get("phone"):
                prompt += f"- Telefone: {context['phone']}\n"
            if context.get("address"):
                prompt += f"- Endereço: {context['address']}\n"
            if context.get("operating_hours"):
                prompt += f"- Horário: {context['operating_hours']}\n"
            prompt += "\n"
        
        # Add the actual question
        prompt += f"Agora responda esta pergunta seguindo o mesmo padrão dos exemplos:\n"
        prompt += f"Pergunta: {question}\n"
        prompt += f"Resposta:"
        
        return prompt
    
    async def _generate_general_response(self, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a general response when no similar examples are found"""
        
        context_info = ""
        if context:
            context_info = f"\nInformações da unidade: {context.get('username', 'Kumon')}"
            if context.get('phone'):
                context_info += f"\nTelefone: {context['phone']}"
        
        prompt = f"""
        Você é uma recepcionista virtual do Kumon. Responda à seguinte pergunta de forma educada e prestativa:
        
        Pergunta: {question}
        {context_info}
        
        Se não souber a resposta específica, ofereça agendar uma consulta ou forneça informações de contato.
        Use emojis de forma moderada e mantenha tom profissional mas amigável.
        Seja específica sobre o Kumon e sua metodologia quando possível.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é uma recepcionista virtual do Kumon, sempre educada e prestativa."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.4
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            app_logger.error(f"Error generating general response: {str(e)}")
            return "Obrigada pela sua pergunta! Para uma resposta mais específica, que tal agendarmos uma consulta? Posso ajudar com isso! 😊📞"
    
    def add_few_shot_example(self, question: str, answer: str, category: str = "general", keywords: List[str] = None, context: Dict[str, Any] = None):
        """Add a new few-shot example dynamically"""
        
        new_example = FewShotExample(question, answer, category, keywords or [], context)
        self.few_shot_examples.append(new_example)
        
        app_logger.info(f"Added new few-shot example in category: {category}")
    
    def get_examples_by_category(self, category: str) -> List[FewShotExample]:
        """Get all examples from a specific category"""
        return [example for example in self.few_shot_examples if example.category == category]
    
    def get_all_categories(self) -> List[str]:
        """Get all available categories"""
        return list(set(example.category for example in self.few_shot_examples))
    
    def reload_examples(self):
        """Reload examples from JSON file"""
        self.few_shot_examples = self._load_few_shot_examples()
        app_logger.info(f"Reloaded few-shot examples: {len(self.few_shot_examples)} examples")
    
    def get_example_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded examples"""
        stats = {
            "total_examples": len(self.few_shot_examples),
            "categories": {},
            "average_question_length": 0,
            "average_answer_length": 0
        }
        
        question_lengths = []
        answer_lengths = []
        
        for example in self.few_shot_examples:
            category = example.category
            if category not in stats["categories"]:
                stats["categories"][category] = 0
            stats["categories"][category] += 1
            
            question_lengths.append(len(example.question))
            answer_lengths.append(len(example.answer))
        
        if question_lengths:
            stats["average_question_length"] = sum(question_lengths) / len(question_lengths)
        if answer_lengths:
            stats["average_answer_length"] = sum(answer_lengths) / len(answer_lengths)
        
        return stats

    def _format_business_context(self, context: Dict[str, Any]) -> str:
        """Format business context for the prompt"""
        prompt = "\n=== INFORMAÇÕES DA EMPRESA ===\n"
        prompt += f"- Nome: {context.get('business_name', 'Kumon')}\n"
        prompt += f"- Email: {context.get('business_email', '')}\n"
        prompt += f"- Telefone: {context.get('phone', '')}\n"
        prompt += f"- Endereço: {context.get('address', '')}\n"
        prompt += f"- Horário: {context.get('operating_hours', 'Segunda a Sexta: 8h às 18h')}\n"
        
        # Add unit-specific info if available
        if context.get("username"):
            prompt += f"- Unidade: {context['username']}\n"
        
        return prompt

    def _get_unit_specific_context(self, query: str, context: Dict[str, Any]) -> str:
        """Get unit-specific contextual information"""
        
        # Basic unit context
        context_info = f"\nInformações da unidade: {context.get('username', 'Kumon')}"
        
        if context.get("address"):
            context_info += f"\nEndereço: {context['address']}"
        
        if context.get("operating_hours"):
            context_info += f"\nHorário de funcionamento: {context['operating_hours']}"
        
        if context.get("services"):
            context_info += f"\nServiços: {context['services']}"
        
        return context_info 