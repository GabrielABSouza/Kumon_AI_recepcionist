# tests/flow/test_master_router.py

from unittest.mock import patch

import pytest

from app.core.routing.master_router import master_router


@pytest.mark.asyncio
async def test_router_prioritizes_continuation_rule_over_ai():
    """
    🧪 TESTE RED PHASE: Prova que a regra de continuação não tem prioridade sobre IA

    Este teste irá FALHAR até corrigirmos a hierarquia de decisão no master_router.
    A regra de continuação (post_greeting_response) deve ter prioridade sobre a análise da IA.
    """
    # Arrange - Estado que DEVE acionar continuação (greeting_sent = True)
    state = {
        "text": "Gabriel",  # Resposta do usuário fornecendo nome
        "phone": "5511999999999",
        "message_id": "test_123",
        "instance": "test_instance",
        "greeting_sent": True,  # 🎯 CRUCIAL: Flag que deveria acionar continuação
    }

    # Mock GeminiClassifier para retornar decisão INCORRETA da IA
    with patch("app.core.routing.master_router.classifier") as mock_classifier:
        with patch(
            "app.core.routing.master_router.get_conversation_state"
        ) as mock_get_state:
            with patch(
                "app.core.routing.master_router.get_conversation_history"
            ) as mock_get_history:
                # Setup mocks
                mock_get_state.return_value = {"greeting_sent": True}
                mock_get_history.return_value = []

                # 🧠 IA retorna decisão INCORRETA (deveria ser qualification mas retorna greeting)
                mock_classifier.classify.return_value = {
                    "primary_intent": "greeting",  # ❌ DECISÃO INCORRETA da IA
                    "secondary_intent": None,
                    "entities": {"parent_name": "Gabriel"},
                    "confidence": 0.95,
                }

                # Act - Executar master_router
                result = master_router(state)

                # Assert - DEVE priorizar regra de continuação sobre IA
                # ESTE TESTE VAI FALHAR porque o router atual segue a IA cegamente
                assert result == "qualification_node", (
                    f"Com greeting_sent=True, deve ir para qualification_node (regra de continuação), "
                    f"mas foi para {result}. A IA retornou 'greeting' incorretamente, "
                    f"mas a regra de negócio deve ter prioridade."
                )

                # Verificar que o estado foi atualizado com entidades
                assert "nlu_entities" in state
                assert state["nlu_entities"].get("parent_name") == "Gabriel"

                print(f"🔍 Estado final: greeting_sent={state.get('greeting_sent')}")
                print(f"🔍 Decisão da IA: greeting (incorreta)")
                print(f"🔍 Decisão final: {result}")
                print(
                    f"🔍 Resultado esperado: qualification_node (regra de continuação)"
                )


@pytest.mark.asyncio
async def test_router_uses_ai_when_no_continuation_rule():
    """
    🧪 TESTE DE CONTROLE: Verifica que IA é usada quando não há regra de continuação

    Este teste deve PASSAR mesmo com o bug, provando que o problema é específico
    da hierarquia de prioridades.
    """
    # Arrange - Estado SEM regra de continuação
    state = {
        "text": "Olá, boa tarde!",
        "phone": "5511999999999",
        "message_id": "test_456",
        "instance": "test_instance"
        # 🎯 SEM greeting_sent - não há regra de continuação
    }

    # Mock GeminiClassifier para retornar decisão correta da IA
    with patch("app.core.routing.master_router.classifier") as mock_classifier:
        with patch(
            "app.core.routing.master_router.get_conversation_state"
        ) as mock_get_state:
            with patch(
                "app.core.routing.master_router.get_conversation_history"
            ) as mock_get_history:
                # Setup mocks
                mock_get_state.return_value = {}  # Estado vazio
                mock_get_history.return_value = []

                # IA retorna decisão correta
                mock_classifier.classify.return_value = {
                    "primary_intent": "greeting",
                    "secondary_intent": None,
                    "entities": {},
                    "confidence": 0.90,
                }

                # Act
                result = master_router(state)

                # Assert - DEVE seguir a IA quando não há regra de continuação
                assert result == "greeting_node", (
                    f"Sem regra de continuação, deve seguir IA (greeting_node), "
                    f"mas retornou {result}"
                )

                print(f"✅ Sem regra de continuação: seguiu IA corretamente ({result})")
