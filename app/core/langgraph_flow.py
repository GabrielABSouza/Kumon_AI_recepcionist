# app/core/langgraph_flow.py

import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

# Importe os nós e o roteador de seus arquivos dedicados
from app.core.nodes.greeting import greeting_node
from app.core.nodes.qualification import qualification_node
# ... importe seus outros nós (information, scheduling, fallback)
from app.core.routing.master_router import master_router

logger = logging.getLogger(__name__)

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
    # ... adicione seus outros nós ...

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
    # Não precisamos de uma aresta para o fallback_node, pois ele já está no mapa condicional

    return workflow.compile()

# Instância global do grafo
graph = build_graph()


# A função principal que executa o grafo permanece a mesma
async def run_flow(state: Dict[str, Any]) -> Dict[str, Any]:
    """Executa o workflow com o estado fornecido."""
    try:
        # A invocação é assíncrona, respeitando a natureza dos nós
        return await graph.ainvoke(state)
    except Exception as e:
        logger.error(f"LANGGRAPH_FLOW|FlowError|error={str(e)}", exc_info=True)
        # Retorna um estado de erro
        return {"error": str(e)}