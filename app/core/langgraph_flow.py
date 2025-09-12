# app/core/langgraph_flow.py

import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

# Importe os nós e o roteador de seus arquivos dedicados
from app.core.nodes.greeting import greeting_node
from app.core.nodes.information import information_node
from app.core.nodes.master_router import master_router
from app.core.nodes.qualification import qualification_node
from app.core.nodes.scheduling import scheduling_node

logger = logging.getLogger(__name__)


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
    decision = state.get("routing_decision", "fallback_node")
    logger.info(f"ROUTING|Post-AI Decision|Routing to: {decision}")
    return decision


def build_graph():
    """Constrói o grafo LangGraph com a arquitetura final e robusta."""
    workflow = StateGraph(Dict[str, Any])

    # Adiciona os nós, incluindo o master_router como um nó normal
    workflow.add_node("master_router", master_router)
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

    return workflow.compile()


# Instância global do grafo
graph = build_graph()
print(f"DEBUG|graph_built|type={type(graph)}")
print(f"DEBUG|graph_built|is_none={graph is None}")


# A função principal que executa o grafo permanece a mesma
async def run_flow(state: Dict[str, Any]) -> Dict[str, Any]:
    """Executa o workflow com o estado fornecido."""
    print(f"DEBUG|run_flow_called|message_id={state.get('message_id')}")
    print(f"PIPELINE|flow_start|message_id={state.get('message_id')}")

    try:
        print("DEBUG|before_ainvoke")
        result = await graph.ainvoke(state)
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
