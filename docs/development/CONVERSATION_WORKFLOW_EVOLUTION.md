# Conversation Workflow Evolution Guide

## 📋 Visão Geral

Este documento detalha o processo de evolução do sistema de conversação do Kumon Assistant, migrando de uma arquitetura baseada em prompts hardcoded para um sistema moderno utilizando LangSmith (versionamento de prompts) e LangGraph (orquestração de fluxo com validação).

## 🎯 Objetivos

1. **Versionamento de Prompts**: Gerenciar prompts de forma centralizada com histórico completo
2. **Validação de Respostas**: Implementar agente validador antes de enviar respostas ao usuário
3. **Observabilidade**: Rastrear todas as decisões e transições do agente
4. **Flexibilidade**: Permitir atualizações de prompts sem deploy de código
5. **Qualidade**: Reduzir drasticamente respostas incorretas ou inadequadas

## 🏗️ Arquitetura Atual vs Proposta

### Estado Atual
```
User Message → ConversationFlowManager → Hardcoded Prompts → Direct Response
```

### Arquitetura Proposta
```
User Message → LangGraph State Machine → LangSmith Prompts → Validation Agent → Validated Response
```

## 📚 Tecnologias Utilizadas

### LangSmith
- **Propósito**: Versionamento e gestão de prompts
- **Features**: Tags, commits, diffs, rollback, A/B testing
- **Docs**: https://docs.smith.langchain.com/

### LangGraph
- **Propósito**: Orquestração de fluxo como máquina de estados
- **Features**: State persistence, conditional edges, human-in-the-loop
- **Docs**: https://langchain-ai.github.io/langgraph/

### LangChain
- **Propósito**: Framework base para integração de LLMs
- **Features**: LCEL, chains, memory, callbacks
- **Docs**: https://python.langchain.com/

## 🚀 Plano de Implementação

### Fase 1: Setup e Configuração Inicial

#### 1.1 Instalação de Dependências
```bash
# Adicionar ao requirements.txt
langsmith>=0.1.0
langgraph>=0.1.0
langchain>=0.2.0
langchain-openai>=0.1.0
```

#### 1.2 Configuração de Variáveis de Ambiente
```bash
# Adicionar ao .env
LANGSMITH_API_KEY=your-api-key
LANGSMITH_PROJECT=kumon-assistant
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_TRACING_V2=true
```

#### 1.3 Estrutura de Diretórios
```
app/
├── workflows/
│   ├── __init__.py
│   ├── states.py          # Definição de estados
│   ├── nodes.py           # Nós do grafo
│   ├── edges.py           # Transições condicionais
│   ├── validators.py      # Agentes de validação
│   └── graph.py           # Grafo principal
├── prompts/
│   ├── __init__.py
│   ├── manager.py         # Gerenciador de prompts
│   └── templates.py       # Templates locais (fallback)
```

### Fase 2: Migração de Prompts para LangSmith

#### 2.1 Estrutura de Naming Convention
```
Format: {project}:{stage}:{type}:{version}
Examples:
- kumon:greeting:initial:v1.0.0
- kumon:scheduling:availability:v2.1.0
- kumon:validation:quality_check:v1.0.0
```

#### 2.2 Exemplo de Migração
```python
# ANTES (hardcoded em conversation_flow.py)
greeting_message = f"""Olá! 😊 Bem-vindo ao Kumon Vila A! 
Sou a assistente virtual e estou aqui para ajudar você...
Posso começar sabendo seu nome?"""

# DEPOIS (em LangSmith)
# Nome: kumon:greeting:initial:v1.0.0
# Prompt Template:
"""Olá! 😊 Bem-vindo ao Kumon Vila A! 
Sou a assistente virtual e estou aqui para ajudar você a conhecer nosso método 
e agendar uma visita.

Posso começar sabendo seu nome?

Context:
- Unit: {unit_name}
- Time: {current_time}
- Day: {current_day}"""
```

#### 2.3 Criação do Prompt Manager
```python
# app/prompts/manager.py
from langsmith import Client
from typing import Dict, Optional
import os

class PromptManager:
    def __init__(self):
        self.client = Client()
        self.project = os.getenv("LANGSMITH_PROJECT", "kumon-assistant")
        self.cache = {}
    
    async def get_prompt(
        self, 
        name: str, 
        tag: str = "prod",
        variables: Dict = None
    ) -> str:
        """Busca prompt do LangSmith com fallback para cache local"""
        cache_key = f"{name}:{tag}"
        
        # Verifica cache
        if cache_key in self.cache:
            prompt_template = self.cache[cache_key]
        else:
            # Busca do LangSmith
            prompt_template = await self._fetch_from_langsmith(name, tag)
            self.cache[cache_key] = prompt_template
        
        # Formata com variáveis
        if variables:
            return prompt_template.format(**variables)
        return prompt_template
```

### Fase 3: Implementação do LangGraph State Machine

#### 3.1 Definição de Estados
```python
# app/workflows/states.py
from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum

class ConversationStage(str, Enum):
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"

class AgentState(TypedDict):
    # Identificação
    conversation_id: str
    phone_number: str
    
    # Estado atual
    current_stage: ConversationStage
    current_step: int
    
    # Dados coletados
    user_name: Optional[str]
    parent_name: Optional[str]
    children: List[Dict[str, Any]]
    
    # Histórico
    messages: List[Dict[str, str]]
    
    # Contexto RAG
    last_query: Optional[str]
    retrieved_context: Optional[str]
    
    # Validação
    response_candidate: Optional[str]
    validation_result: Optional[Dict[str, Any]]
    validation_attempts: int
    
    # Métricas
    confusion_count: int
    satisfaction_score: float
    needs_human_handoff: bool
```

#### 3.2 Implementação dos Nós
```python
# app/workflows/nodes.py
from langchain_core.messages import HumanMessage, AIMessage
from .states import AgentState, ConversationStage
from ..prompts.manager import PromptManager

prompt_manager = PromptManager()

async def greeting_node(state: AgentState) -> AgentState:
    """Nó responsável pelo estágio de saudação"""
    
    # Busca prompt apropriado
    if not state.get("user_name"):
        prompt = await prompt_manager.get_prompt(
            "kumon:greeting:initial",
            variables={
                "unit_name": "Kumon Vila A",
                "current_time": get_current_time(),
                "current_day": get_current_day()
            }
        )
    else:
        prompt = await prompt_manager.get_prompt(
            "kumon:greeting:followup",
            variables={"user_name": state["user_name"]}
        )
    
    # Atualiza estado com resposta candidata
    state["response_candidate"] = prompt
    state["validation_attempts"] = 0
    
    return state

async def validation_node(state: AgentState) -> AgentState:
    """Nó que valida a resposta antes de enviar"""
    
    validator_prompt = await prompt_manager.get_prompt(
        "kumon:validation:response_check",
        variables={
            "response": state["response_candidate"],
            "context": state.get("retrieved_context", ""),
            "stage": state["current_stage"],
            "conversation_history": format_history(state["messages"])
        }
    )
    
    # Chama LLM para validar
    validation_result = await validate_response(validator_prompt)
    
    state["validation_result"] = validation_result
    state["validation_attempts"] += 1
    
    return state
```

#### 3.3 Definição de Edges (Transições)
```python
# app/workflows/edges.py
from typing import Literal
from .states import AgentState, ConversationStage

def should_retry_validation(state: AgentState) -> Literal["retry", "approve", "handoff"]:
    """Decide se deve retentar validação, aprovar ou passar para humano"""
    
    result = state.get("validation_result", {})
    attempts = state.get("validation_attempts", 0)
    
    # Se validação passou
    if result.get("is_valid", False):
        return "approve"
    
    # Se muitas tentativas falharam
    if attempts >= 3:
        return "handoff"
    
    # Tentar novamente com mais contexto
    return "retry"

def determine_next_stage(state: AgentState) -> str:
    """Determina próximo estágio baseado no estado atual"""
    
    current = state["current_stage"]
    
    # Detecção de intenção de agendamento direto
    if detect_scheduling_intent(state["last_query"]):
        return ConversationStage.SCHEDULING
    
    # Fluxo normal
    stage_transitions = {
        ConversationStage.GREETING: ConversationStage.QUALIFICATION,
        ConversationStage.QUALIFICATION: ConversationStage.INFORMATION,
        ConversationStage.INFORMATION: ConversationStage.SCHEDULING,
        ConversationStage.SCHEDULING: ConversationStage.CONFIRMATION,
        ConversationStage.CONFIRMATION: ConversationStage.COMPLETED,
    }
    
    return stage_transitions.get(current, current)
```

#### 3.4 Construção do Grafo Principal
```python
# app/workflows/graph.py
from langgraph.graph import StateGraph, END
from .states import AgentState, ConversationStage
from .nodes import *
from .edges import *

def create_conversation_graph():
    """Cria o grafo de conversação com LangGraph"""
    
    # Inicializa o grafo
    workflow = StateGraph(AgentState)
    
    # Adiciona nós
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("qualification", qualification_node)
    workflow.add_node("information", information_node)
    workflow.add_node("scheduling", scheduling_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("confirmation", confirmation_node)
    workflow.add_node("send_response", send_response_node)
    workflow.add_node("human_handoff", human_handoff_node)
    
    # Define ponto de entrada
    workflow.set_entry_point("greeting")
    
    # Adiciona edges condicionais
    for stage in ConversationStage:
        if stage != ConversationStage.COMPLETED:
            workflow.add_edge(stage, "validation")
    
    # Edges de validação
    workflow.add_conditional_edges(
        "validation",
        should_retry_validation,
        {
            "retry": determine_next_stage,
            "approve": "send_response",
            "handoff": "human_handoff"
        }
    )
    
    # Edges finais
    workflow.add_edge("send_response", determine_next_stage)
    workflow.add_edge("human_handoff", END)
    
    # Compila o grafo
    return workflow.compile()
```

### Fase 4: Implementação do Validation Agent

#### 4.1 Validador de Respostas
```python
# app/workflows/validators.py
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import Dict, Any
import json

class ResponseValidator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.1
        )
        
    async def validate(self, 
                      response: str, 
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida uma resposta antes de enviar ao usuário"""
        
        validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um validador de qualidade para respostas de chatbot.
            
            Analise a resposta e verifique:
            1. Informações corretas (horários, valores, procedimentos)
            2. Tom apropriado (profissional mas amigável)
            3. Completude (responde à pergunta do usuário)
            4. Coerência com o contexto da conversa
            5. Ausência de alucinações ou informações inventadas
            
            Retorne um JSON com:
            {
                "is_valid": boolean,
                "issues": [lista de problemas encontrados],
                "suggestions": [sugestões de melhoria],
                "confidence": float (0-1)
            }
            """),
            ("human", """
            Contexto da conversa:
            {conversation_context}
            
            Estágio atual: {current_stage}
            
            Resposta a validar:
            {response}
            """)
        ])
        
        result = await self.llm.ainvoke(
            validation_prompt.format_messages(
                conversation_context=context.get("history", ""),
                current_stage=context.get("stage", ""),
                response=response
            )
        )
        
        return json.loads(result.content)
```

#### 4.2 Métricas de Qualidade
```python
# app/workflows/validators.py (continuação)
class QualityMetrics:
    def __init__(self):
        self.thresholds = {
            "min_confidence": 0.8,
            "max_confusion_count": 3,
            "min_satisfaction": 0.7
        }
    
    def should_escalate(self, state: AgentState) -> bool:
        """Determina se deve escalar para humano"""
        
        # Validação falhou múltiplas vezes
        if state.get("validation_attempts", 0) >= 3:
            return True
        
        # Usuário está confuso
        if state.get("confusion_count", 0) >= self.thresholds["max_confusion_count"]:
            return True
        
        # Baixa satisfação detectada
        if state.get("satisfaction_score", 1.0) < self.thresholds["min_satisfaction"]:
            return True
        
        return False
```

### Fase 5: Integração com Sistema Existente

#### 5.1 Adapter para ConversationFlowManager
```python
# app/services/conversation_workflow_adapter.py
from ..workflows.graph import create_conversation_graph
from ..workflows.states import AgentState
from .conversation_flow import ConversationFlowManager

class ConversationWorkflowAdapter:
    """Adapter para integrar o novo workflow com o sistema existente"""
    
    def __init__(self):
        self.graph = create_conversation_graph()
        self.legacy_manager = ConversationFlowManager()
        
    async def process_message(self, 
                            phone_number: str, 
                            message: str) -> str:
        """Processa mensagem usando o novo workflow"""
        
        # Recupera estado existente ou cria novo
        state = await self._get_or_create_state(phone_number)
        
        # Adiciona mensagem atual
        state["messages"].append({
            "role": "user",
            "content": message
        })
        state["last_query"] = message
        
        # Executa o grafo
        result = await self.graph.ainvoke(state)
        
        # Persiste estado atualizado
        await self._save_state(result)
        
        # Retorna resposta final
        return result.get("final_response", "")
```

#### 5.2 Feature Flags para Rollout Gradual
```python
# app/core/config.py (adicionar)
USE_LANGGRAPH_WORKFLOW: bool = False
WORKFLOW_ROLLOUT_PERCENTAGE: float = 0.1  # 10% inicial

# app/services/message_processor.py (modificar)
import random
from .conversation_workflow_adapter import ConversationWorkflowAdapter

async def process_whatsapp_message(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    # ... código existente ...
    
    # Decide qual workflow usar
    use_new_workflow = (
        settings.USE_LANGGRAPH_WORKFLOW and 
        random.random() < settings.WORKFLOW_ROLLOUT_PERCENTAGE
    )
    
    if use_new_workflow:
        adapter = ConversationWorkflowAdapter()
        response = await adapter.process_message(phone_number, message_text)
    else:
        # Usa sistema legado
        response = await conversation_flow.advance_conversation(
            phone_number, message_text
        )
```

### Fase 6: Monitoramento e Observabilidade

#### 6.1 Setup do LangSmith Tracing
```python
# app/core/tracing.py
from langsmith import Client
from langsmith.run_helpers import traceable
import os

client = Client()

def setup_tracing():
    """Configura tracing para o projeto"""
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "kumon-assistant"
    
    # Callback customizado para métricas
    class KumonTracingCallback:
        def on_chain_start(self, run):
            # Log início da cadeia
            pass
            
        def on_chain_end(self, run):
            # Coleta métricas
            pass
```

#### 6.2 Dashboard de Métricas
```python
# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Métricas do workflow
workflow_executions = Counter(
    'kumon_workflow_executions_total',
    'Total de execuções do workflow',
    ['stage', 'status']
)

validation_attempts = Histogram(
    'kumon_validation_attempts',
    'Número de tentativas de validação por resposta'
)

response_quality_score = Gauge(
    'kumon_response_quality',
    'Score de qualidade das respostas',
    ['stage']
)
```

## 📊 Métricas de Sucesso

### KPIs Principais
1. **Taxa de Validação**: % de respostas aprovadas na primeira tentativa
2. **Tempo de Resposta**: P95 < 3 segundos
3. **Taxa de Handoff**: < 5% das conversas
4. **Satisfação do Usuário**: > 4.5/5
5. **Cobertura de Testes**: > 90%

### Monitoramento Contínuo
- LangSmith Dashboard para traces e performance
- Grafana para métricas operacionais
- Alertas para degradação de qualidade

## 🔧 Ferramentas de Desenvolvimento

### LangGraph Studio
```bash
# Para visualizar e debugar o workflow
pip install langgraph-studio
langgraph studio app/workflows/graph.py
```

### Testing
```python
# tests/test_workflow.py
import pytest
from app.workflows.graph import create_conversation_graph

@pytest.mark.asyncio
async def test_greeting_flow():
    graph = create_conversation_graph()
    
    initial_state = {
        "conversation_id": "test-123",
        "phone_number": "5511999999999",
        "current_stage": "greeting",
        "messages": []
    }
    
    result = await graph.ainvoke(initial_state)
    
    assert result["response_candidate"] is not None
    assert result["validation_result"]["is_valid"] == True
```

## 🚦 Checklist de Implementação

### Fase 1 - Setup Inicial
- [ ] Instalar dependências (langsmith, langgraph)
- [ ] Configurar variáveis de ambiente
- [ ] Criar conta LangSmith e projeto
- [ ] Setup inicial de tracing

### Fase 2 - Migração de Prompts
- [ ] Mapear todos os prompts existentes
- [ ] Criar naming convention
- [ ] Upload inicial para LangSmith
- [ ] Implementar PromptManager

### Fase 3 - LangGraph State Machine
- [ ] Definir AgentState
- [ ] Implementar nodes principais
- [ ] Criar edges e transições
- [ ] Compilar e testar grafo

### Fase 4 - Validation Agent
- [ ] Implementar ResponseValidator
- [ ] Criar métricas de qualidade
- [ ] Integrar com workflow
- [ ] Testar cenários de validação

### Fase 5 - Integração
- [ ] Criar adapter para sistema existente
- [ ] Implementar feature flags
- [ ] Setup de rollout gradual
- [ ] Testes de integração

### Fase 6 - Produção
- [ ] Deploy com 10% de tráfego
- [ ] Monitorar métricas
- [ ] Ajustar e otimizar
- [ ] Rollout completo

## 📚 Recursos Adicionais

### Documentação
- [LangSmith Docs](https://docs.smith.langchain.com/)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
- [LangChain Best Practices](https://python.langchain.com/docs/guides/)

### Exemplos de Código
- [LangGraph Examples](https://github.com/langchain-ai/langgraph/tree/main/examples)
- [Multi-Agent Workflows](https://github.com/langchain-ai/langgraph/tree/main/examples/multi_agent)

### Comunidade
- [LangChain Discord](https://discord.gg/langchain)
- [GitHub Discussions](https://github.com/langchain-ai/langchain/discussions)

## 🎯 Conclusão

Esta evolução transformará o Kumon Assistant em um sistema mais robusto, manutenível e inteligente. O versionamento de prompts permitirá iterações rápidas, enquanto a validação garantirá qualidade consistente nas respostas. O LangGraph fornecerá a estrutura necessária para fluxos complexos com total observabilidade.

---

**Última atualização**: 2025-08-11
**Autor**: Gabriel Bastos
**Status**: Em desenvolvimento