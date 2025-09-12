# tests/flow/test_master_router.py

from unittest.mock import AsyncMock, patch

import pytest

from app.core.routing.master_router import master_router_async, master_router_sync


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
                mock_classifier.classify = AsyncMock(
                    return_value={
                        "primary_intent": "greeting",  # ❌ DECISÃO INCORRETA da IA
                        "secondary_intent": None,
                        "entities": {"parent_name": "Gabriel"},
                        "confidence": 0.95,
                    }
                )

                # Act - Executar master_router_async
                result = await master_router_async(state)

                # Assert - DEVE priorizar regra de continuação sobre IA
                # ESTE TESTE VAI FALHAR porque o router atual segue a IA cegamente
                assert result == "qualification_node", (
                    f"Com greeting_sent=True, deve ir para qualification_node "
                    f"(regra de continuação), mas foi para {result}. A IA retornou "
                    f"'greeting' incorretamente, mas a regra de negócio deve ter prioridade."
                )

                # Verificar que o estado foi atualizado com entidades
                assert "nlu_entities" in state
                assert state["nlu_entities"].get("parent_name") == "Gabriel"

                print(f"🔍 Estado final: greeting_sent={state.get('greeting_sent')}")
                print("🔍 Decisão da IA: greeting (incorreta)")
                print(f"🔍 Decisão final: {result}")
                print("🔍 Resultado esperado: qualification_node (regra de continuação)")


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
                mock_classifier.classify = AsyncMock(
                    return_value={
                        "primary_intent": "greeting",
                        "secondary_intent": None,
                        "entities": {},
                        "confidence": 0.90,
                    }
                )

                # Act - Executar master_router_async
                result = await master_router_async(state)

                # Assert - DEVE seguir a IA quando não há regra de continuação
                assert result == "greeting_node", (
                    f"Sem regra de continuação, deve seguir IA (greeting_node), "
                    f"mas retornou {result}"
                )

                print(f"✅ Sem regra de continuação: seguiu IA corretamente ({result})")


@pytest.mark.asyncio
async def test_master_router_async_sync_conflict():
    """
    🧪 RED PHASE: Prova o conflito async/sync no master_router

    Este teste irá FALHAR com RuntimeWarning ou TypeError devido ao conflito
    entre o master_router síncrono e o classifier assíncrono.

    PROBLEMA DETECTADO:
    - master_router() é síncrono (def)
    - classifier.classify() é assíncrono (async def)
    - Chamada: nlu_result = classifier.classify() SEM await

    SOLUÇÃO REQUERIDA:
    - master_router deve ser async def
    - Chamada deve usar: nlu_result = await classifier.classify()
    """
    print("\n--- 🧪 RED PHASE: Teste de Conflito Async/Sync ---")

    # Estado simples para processamento
    state = {"text": "olá", "phone": "5511999999999", "message_id": "test_async_123"}

    # Mock do classifier como AsyncMock para simular comportamento real
    with patch("app.core.routing.master_router.classifier") as mock_classifier:
        with patch(
            "app.core.routing.master_router.get_conversation_state"
        ) as mock_get_state:
            with patch(
                "app.core.routing.master_router.get_conversation_history"
            ) as mock_get_history:
                # Setup mocks
                mock_get_state.return_value = {}
                mock_get_history.return_value = []

                # 🎯 CRÍTICO: Mock classifier como função async
                # Isso irá retornar uma corrotina que não será awaited
                mock_classifier.classify = AsyncMock(
                    return_value={
                        "primary_intent": "greeting",
                        "secondary_intent": None,
                        "entities": {},
                        "confidence": 0.95,
                    }
                )

                # Act - Agora master_router é async, então deve funcionar corretamente
                import warnings

                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    result = await master_router_async(state)  # ✅ Agora com await

                    # Verificar se houve RuntimeWarning sobre corrotina não esperada
                    runtime_warnings = [
                        warning
                        for warning in w
                        if issubclass(warning.category, RuntimeWarning)
                    ]
                    coroutine_warnings = [
                        warning
                        for warning in runtime_warnings
                        if "coroutine" in str(warning.message)
                    ]

                    if coroutine_warnings:
                        print("❌ AINDA HÁ CONFLITO ASYNC/SYNC:")
                        for warning in coroutine_warnings:
                            print(f"  📋 {warning.category.__name__}: {warning.message}")

                        raise AssertionError(
                            "GREEN PHASE FALHOU: Ainda há warnings de corrotina após a correção. "
                            f"Resultado: {result}, Warnings: {len(coroutine_warnings)}"
                        )

                    # ✅ GREEN PHASE: Sem warnings e resultado correto
                    print("✅ CONFLITO RESOLVIDO: Sem RuntimeWarnings")
                    print(f"✅ Resultado correto: {result}")
                    print(f"✅ Total warnings: {len(w)} (sem corrotina)")

                    # Validar que o resultado é o esperado (não mais fallback)
                    assert result == "greeting_node", (
                        f"Com o conflito resolvido, deveria rotear corretamente para "
                        f"greeting_node, mas obteve {result}"
                    )

                    print("🎯 GREEN PHASE SUCESSO: master_router agora é async!")
                    return


def test_master_router_sync_wrapper_works():
    """
    🔄 TEST: Verifica que o wrapper síncrono funciona corretamente

    Este teste garante que master_router_sync executa master_router_async
    de forma síncrona, resolvendo o problema com LangGraph 0.0.26.
    """
    print("\n--- 🔄 TESTE: Wrapper Síncrono para LangGraph 0.0.26 ---")

    # Estado simples para processamento
    state = {"text": "olá", "phone": "5511999999999", "message_id": "test_sync_wrapper"}

    # Mock do classifier como AsyncMock
    with patch("app.core.routing.master_router.classifier") as mock_classifier:
        with patch(
            "app.core.routing.master_router.get_conversation_state"
        ) as mock_get_state:
            with patch(
                "app.core.routing.master_router.get_conversation_history"
            ) as mock_get_history:
                # Setup mocks
                mock_get_state.return_value = {}
                mock_get_history.return_value = []

                mock_classifier.classify = AsyncMock(
                    return_value={
                        "primary_intent": "greeting",
                        "secondary_intent": None,
                        "entities": {},
                        "confidence": 0.95,
                    }
                )

                # Act - Executar wrapper SÍNCRONO (sem await)
                result = master_router_sync(state)

                # Assert - Deve funcionar perfeitamente
                print(f"✅ Wrapper síncrono funcionou: {result}")
                assert (
                    result == "greeting_node"
                ), f"Wrapper síncrono deveria retornar greeting_node, mas retornou {result}"

                # Verificar que as entidades foram adicionadas ao estado
                assert "nlu_entities" in state
                print(f"✅ Estado atualizado com NLU: {state.get('nlu_entities')}")

                print(
                    "🎯 WRAPPER SÍNCRONO FUNCIONANDO: Compatível com LangGraph 0.0.26!"
                )
                return
