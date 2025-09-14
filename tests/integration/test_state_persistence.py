# tests/integration/test_state_persistence.py
import pytest
import uuid

# Importe o 'workflow' e a função de criação de estado inicial
from app.core.langgraph_flow import graph

def create_initial_cecilia_state(phone_number: str, user_message: str) -> dict:
    """Helper function to create initial state for testing."""
    return {
        "phone": phone_number,
        "message_id": f"test_msg_{uuid.uuid4()}",
        "text": user_message,
        "instance": "test_instance",
        "collected_data": {},
    }

@pytest.mark.asyncio
async def test_langgraph_checkpoints_persist_state_across_turns():
    """
    🧪 TESTE DE INTEGRAÇÃO DEFINITIVO: Valida a persistência automática
    do estado entre os turnos usando o sistema de Checkpoints do LangGraph.
    """
    # ARRANGE: Define um ID de conversa único para este teste
    conversation_id = f"test-thread-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": conversation_id}}

    # --- TURNO 1: Usuário envia "olá" ---
    print("\n--- 🧪 Executando Turno 1: Greeting ---")
    state_turn_1 = create_initial_cecilia_state(
        phone_number=conversation_id, # Usamos o ID como telefone para consistência
        user_message="olá",
    )
    
    final_state_1 = await graph.ainvoke(state_turn_1, config=config)

    # Assertiva do Turno 1: Verifica se o bot pediu o nome
    assert "qual é o seu nome" in final_state_1.get("last_bot_response", "").lower()
    assert final_state_1.get("greeting_sent") is True

    # --- TURNO 2: Usuário envia o nome "Gabriel" ---
    print("\n--- 🧪 Executando Turno 2: Coleta de Nome ---")
    state_turn_2 = create_initial_cecilia_state(
        phone_number=conversation_id,
        user_message="Gabriel",
    )

    # A mágica do checkpoint: o 'ainvoke' com o mesmo 'thread_id' deve carregar o estado anterior
    final_state_2 = await graph.ainvoke(state_turn_2, config=config)

    # ASSERTIVA CRÍTICA (que irá falhar):
    # O 'collected_data' no estado final do Turno 2 DEVE conter o nome coletado.
    collected_data_2 = final_state_2.get("collected_data", {})
    assert collected_data_2.get("parent_name") == "Gabriel", \
        "O estado do Turno 2 falhou em persistir o 'parent_name' coletado."

    # Assertiva de continuação: Verifica se o bot pediu o próximo passo
    assert "para você mesmo ou para outra pessoa" in final_state_2.get("last_bot_response", "").lower(), \
        "O bot não continuou a qualificação após coletar o nome."

    print("\n--- ✅ SUCESSO: Persistência de estado entre turnos confirmada! ---")