# app/core/langgraph_flow.py

import logging
import os
from typing import Any, Dict

from langgraph.graph import END, StateGraph
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    CHECKPOINTS_AVAILABLE = True
except ImportError:
    CHECKPOINTS_AVAILABLE = False
    print("WARNING: LangGraph checkpoints not available - using fallback")

# Importe os nós e o roteador de seus arquivos dedicados
from app.core.nodes.greeting import greeting_node
from app.core.nodes.information import information_node
from app.core.nodes.master_router import master_router, QUALIFICATION_REQUIRED_VARS
from app.core.nodes.qualification import qualification_node
from app.core.nodes.scheduling import scheduling_node
from app.core.gemini_classifier import GeminiClassifier

logger = logging.getLogger(__name__)

# 🧠 INSTÂNCIA CENTRALIZADA: Criada em um único lugar, eliminando importação circular
gemini_classifier = GeminiClassifier()


# 🔧 WRAPPER: Injeção de Dependência do GeminiClassifier
async def master_router_wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper que injeta a instância do GeminiClassifier no master_router.
    Elimina a dependência circular e centraliza a instanciação.
    """
    return await master_router(state, gemini_classifier)


# Simple fallback node implementation
async def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle fallback for unrecognized intents."""
    print("DEBUG|fallback_node_executed")
    fallback_text = "Desculpe, não compreendi sua solicitação. Como posso ajudá-lo?"

    # Import send_text here to avoid circular imports
    from app.core.delivery import send_text

    try:
        phone = state.get("phone", "")
        instance = state.get("instance", "kumon_assistant")

        delivery_result = await send_text(phone, fallback_text, instance)

        return {
            **state,
            "sent": delivery_result.get("sent", "false"),
            "response": fallback_text,
            "routing_decision": "fallback_node",
        }
    except Exception as e:
        logger.error(f"FALLBACK|error|{str(e)}")
        return {
            **state,
            "sent": "false",
            "response": fallback_text,
            "error_reason": str(e),
            "routing_decision": "fallback_node",
        }


# O "Carteiro" Síncrono e Simples
def route_from_master_router(state: Dict[str, Any]) -> str:
    """
    Lê a decisão de roteamento que o master_router já tomou e a retorna.
    É uma função síncrona, rápida e que apenas lê o estado.
    """
    print(f"DEBUG|route_from_master_router_called|state_keys={list(state.keys())}")
    decision = state.get("routing_decision", "fallback_node")
    print(f"DEBUG|route_from_master_router|decision={decision}")
    logger.info(f"ROUTING|Post-AI Decision|Routing to: {decision}")
    return decision


def build_graph():
    """Constrói o grafo LangGraph com a arquitetura final e robusta."""
    # A CORREÇÃO: Conectar o banco de dados ao grafo
    # Pega a URL do banco de dados das variáveis de ambiente
    db_url = os.getenv("DATABASE_URL")
    checkpointer = None
    
    if db_url and CHECKPOINTS_AVAILABLE:
        try:
            # Garante que a conexão só será feita se a URL existir
            checkpointer = PostgresSaver.from_conn_string(db_url)
            print(f"DEBUG|checkpointer_configured|db_url={db_url[:50]}...")
        except Exception as e:
            print(f"WARNING|checkpointer_failed|error={str(e)}")
            print(f"WARNING|continuing_without_checkpoints")
            checkpointer = None
    else:
        print(f"INFO|checkpoints_unavailable|using_manual_persistence")
        checkpointer = None
    
    workflow = StateGraph(Dict[str, Any])

    # Adiciona os nós, incluindo o master_router_wrapper que injeta o classifier
    workflow.add_node("master_router", master_router_wrapper)
    workflow.add_node("greeting_node", greeting_node)
    workflow.add_node("qualification_node", qualification_node)
    workflow.add_node("information_node", information_node)
    workflow.add_node("scheduling_node", scheduling_node)
    workflow.add_node("fallback_node", fallback_node)

    # Define o ponto de entrada para o ROTEADOR
    workflow.set_entry_point("master_router")

    # A ARESTA CONDICIONAL VEM DEPOIS DO ROTEADOR
    # Ela usa o "Carteiro" síncrono para ler a decisão
    workflow.add_conditional_edges(
        "master_router",
        route_from_master_router,
        {
            "greeting_node": "greeting_node",
            "qualification_node": "qualification_node",
            "information_node": "information_node",
            "scheduling_node": "scheduling_node",
            "fallback_node": "fallback_node",
        },
    )

    # Define que todos os nós de ação terminam o fluxo para este turno
    workflow.add_edge("greeting_node", END)
    workflow.add_edge("qualification_node", END)
    workflow.add_edge("information_node", END)
    workflow.add_edge("scheduling_node", END)
    workflow.add_edge("fallback_node", END)

    # A compilação agora inclui o checkpointer
    return workflow.compile(checkpointer=checkpointer)


# Instância global do grafo
graph = build_graph()
print(f"DEBUG|graph_built|type={type(graph)}")
print(f"DEBUG|graph_built|is_none={graph is None}")


# A função principal que executa o grafo com checkpoints
async def run_flow(state: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Executa o workflow com o estado fornecido e configuração opcional."""
    print(f"DEBUG|run_flow_called|message_id={state.get('message_id')}")
    print(f"PIPELINE|flow_start|message_id={state.get('message_id')}")

    try:
        print("DEBUG|before_ainvoke")
        # A chamada agora aceita config para checkpoints
        if config:
            result = await graph.ainvoke(state, config=config)
            print(f"DEBUG|using_config|thread_id={config.get('configurable', {}).get('thread_id')}")
        else:
            result = await graph.ainvoke(state)
            print("DEBUG|no_config_provided")
            
        print(
            f"DEBUG|after_ainvoke|result_keys={list(result.keys()) if isinstance(result, dict) else 'NOT_DICT'}"
        )
        print(
            f"DEBUG|after_ainvoke|sent={result.get('sent', 'NO_SENT') if isinstance(result, dict) else 'NOT_DICT'}"
        )
        print(
            f"PIPELINE|flow_complete|sent={result.get('sent', 'false') if isinstance(result, dict) else 'false'}"
        )
        return result
    except Exception as e:
        print(f"DEBUG|flow_error|error={str(e)}|type={type(e).__name__}")
        print(f"PIPELINE|flow_error|error={str(e)}")
        logger.error(f"LANGGRAPH_FLOW|FlowError|error={str(e)}", exc_info=True)
        # Retorna um estado de erro
        return {"sent": "false", "error": str(e)}


# API compatibility alias
async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """API compatibility function - calls run_flow internally."""
    print(f"DEBUG|run_called|state_keys={list(state.keys())}")
    print(f"DEBUG|run_called|message_id={state.get('message_id')}")
    return await run_flow(state)
