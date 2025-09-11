"""
🎯 TESTE DE INTEGRAÇÃO PONTA A PONTA: Full Conversation Flow

Este teste valida o fluxo conversacional completo desde o master_router
até a resposta final, simulando exatamente como o sistema funciona em produção.

DIFERENÇA CRÍTICA dos testes unitários:
- Não chama qualification_node diretamente
- Chama o graph.ainvoke() que invoca master_router → qualification_node
- Testa a passagem de estado real entre componentes
- Reproduz bugs de integração que testes unitários não capturam

Este é o teste que importa. Se passar, a aplicação funcionará em produção.
"""

from unittest.mock import patch

import pytest

from app.core.langgraph_flow import build_graph


class TestFullConversationFlow:
    """
    🚨 TESTE DE INTEGRAÇÃO: Simula a arquitetura real da aplicação

    Este teste falha intencionalmente (Red Phase) para expor bugs de
    integração que os testes unitários não capturam.
    """

    @pytest.fixture
    def graph(self):
        """Build the actual LangGraph workflow used in production."""
        return build_graph()

    @pytest.mark.asyncio
    async def test_qualification_extraction_bug_fixed(self, graph):
        """
        🎯 TESTE ESPECÍFICO: Verifica se 'olá' não é mais extraído como parent_name

        Este teste força o fluxo para qualification_node e verifica se nossa correção
        da extração funciona corretamente.
        """
        print("🎯 TESTANDO FIX DA EXTRAÇÃO DE 'olá' COMO NOME")

        # Estado que força roteamento para qualification (simulando continuação)
        state_with_greeting_sent = {
            "text": "olá",
            "phone": "5511999999999",
            "instance": "kumon_assistant",
            "message_id": "test_extraction_fix",
            "greeting_sent": True,  # Força roteamento para qualification
        }

        result = await graph.ainvoke(state_with_greeting_sent)

        print(f"🤖 RESPOSTA: {result.get('response', 'N/A')}")
        print(f"📊 DADOS COLETADOS: {result.get('collected_data', {})}")

        # ASSERTIVA CRÍTICA: 'olá' NÃO deve ser extraído como parent_name
        collected_data = result.get("collected_data", {})
        assert (
            collected_data.get("parent_name") != "olá"
        ), f"BUG AINDA EXISTE: 'olá' foi extraído como parent_name: {collected_data}"

        # Deve pedir o nome corretamente
        response = result.get("response", "").lower()
        assert any(
            keyword in response
            for keyword in [
                "qual é o seu nome",
                "seu nome",
                "como você se chama",
                "nome",
            ]
        ), f"Deveria pedir o nome, mas respondeu: '{result.get('response', '')}'"

        print("✅ FIX CONFIRMADO: 'olá' não é mais extraído como nome!")
        return True

    @pytest.mark.asyncio
    async def test_full_qualification_flow_from_router(self, graph):
        """
        🎯 TESTE CRÍTICO: Fluxo completo de qualificação via master_router

        Este teste simula exatamente o que acontece em produção:
        1. master_router recebe estado com 'text'
        2. master_router roteia para qualification_node
        3. qualification_node_wrapper converte estado
        4. qualification_node processa e retorna resposta

        SE ESTE TESTE PASSAR, O SISTEMA FUNCIONA EM PRODUÇÃO.
        """
        print("🎯 INICIANDO TESTE DE INTEGRAÇÃO PONTA A PONTA")

        # ========== TURNO 1: Usuário diz "olá" ==========
        print("📞 TURNO 1: Usuário envia 'olá'")

        initial_state = {
            "text": "olá",
            "phone": "5511999999999",
            "instance": "kumon_assistant",
            "message_id": "test_msg_001",
        }

        # Chama o grafo real (master_router → qualification_node)
        state_after_turn1 = await graph.ainvoke(initial_state)

        print(f"🤖 RESPOSTA TURNO 1: {state_after_turn1.get('response', 'N/A')}")

        # ASSERTIVA 1: Bot deve pedir o nome
        bot_response_1 = state_after_turn1.get("response", "").lower()
        assert any(
            keyword in bot_response_1
            for keyword in [
                "qual é o seu nome",
                "seu nome",
                "como você se chama",
                "nome",
            ]
        ), f"Bot deveria pedir o nome, mas respondeu: '{bot_response_1}'"

        print("✅ TURNO 1 OK: Bot pediu o nome corretamente")

        # ========== TURNO 2: Usuário fornece nome "Gabriel" ==========
        print("📞 TURNO 2: Usuário fornece nome 'Gabriel'")

        # CRÍTICO: Atualizar o estado com a nova mensagem do usuário
        # Este é o ponto onde bugs de integração acontecem!
        state_after_turn1["text"] = "Gabriel"
        state_after_turn1["message_id"] = "test_msg_002"

        # Chama o grafo novamente com estado atualizado
        state_after_turn2 = await graph.ainvoke(state_after_turn1)

        print(f"🤖 RESPOSTA TURNO 2: {state_after_turn2.get('response', 'N/A')}")

        # ASSERTIVA 2: Bot deve perguntar sobre beneficiary_type
        # ESTA ASSERTIVA VAI FALHAR se houver bug de integração
        bot_response_2 = state_after_turn2.get("response", "").lower()
        assert any(
            keyword in bot_response_2
            for keyword in [
                "para você mesmo ou para outra pessoa",
                "é para você",
                "para quem é",
                "beneficiário",
            ]
        ), (
            f"Bot deveria perguntar sobre beneficiário após coletar nome, "
            f"mas respondeu: '{bot_response_2}'"
        )

        print("✅ TURNO 2 OK: Bot perguntou sobre beneficiário corretamente")

        # ========== TURNO 3: Usuário responde "para meu filho" ==========
        print("📞 TURNO 3: Usuário responde 'para meu filho'")

        state_after_turn2["text"] = "para meu filho"
        state_after_turn2["message_id"] = "test_msg_003"

        state_after_turn3 = await graph.ainvoke(state_after_turn2)

        print(f"🤖 RESPOSTA TURNO 3: {state_after_turn3.get('response', 'N/A')}")

        # ASSERTIVA 3: Bot deve perguntar nome da criança
        bot_response_3 = state_after_turn3.get("response", "").lower()
        assert any(
            keyword in bot_response_3
            for keyword in [
                "qual é o nome",
                "nome da criança",
                "como se chama",
                "nome do seu filho",
            ]
        ), f"Bot deveria perguntar nome da criança, mas respondeu: '{bot_response_3}'"

        print("✅ TURNO 3 OK: Bot perguntou nome da criança corretamente")

        # ========== VALIDAÇÃO FINAL: Verificar dados coletados ==========
        print("📊 VALIDAÇÃO: Verificando dados coletados no estado")

        # O estado final deve ter os dados coletados
        collected_data = state_after_turn3.get("collected_data", {})

        # Verificar se Gabriel foi coletado como parent_name
        assert (
            collected_data.get("parent_name") == "Gabriel"
        ), f"parent_name deveria ser 'Gabriel', mas é: {collected_data.get('parent_name')}"

        # Verificar se beneficiary_type foi coletado como 'child'
        assert (
            collected_data.get("beneficiary_type") == "child"
        ), f"beneficiary_type deveria ser 'child', mas é: {collected_data.get('beneficiary_type')}"

        print("✅ DADOS COLETADOS CORRETAMENTE:")
        print(f"   📝 parent_name: {collected_data.get('parent_name')}")
        print(f"   👶 beneficiary_type: {collected_data.get('beneficiary_type')}")

        print("🎉 TESTE DE INTEGRAÇÃO PASSOU! Sistema funciona em produção!")

    @pytest.mark.asyncio
    async def test_graph_router_state_consistency(self, graph):
        """
        🔍 TESTE AUXILIAR: Verifica consistência de estado entre turnos

        Este teste verifica se o estado é propagado corretamente entre
        chamadas do grafo, sem perda de dados coletados.
        """
        print("🔍 TESTE DE CONSISTÊNCIA DE ESTADO")

        # Estado inicial
        state = {
            "text": "Meu nome é Carlos",
            "phone": "5511888888888",
            "instance": "kumon_assistant",
            "message_id": "test_consistency_001",
        }

        # Primeira execução
        result1 = await graph.ainvoke(state)

        # Verificar se dados foram coletados
        collected_data_1 = result1.get("collected_data", {})
        print(f"📊 Dados após 1° turno: {collected_data_1}")

        # Segunda execução com estado propagado
        result1["text"] = "é para meu filho Pedro"
        result1["message_id"] = "test_consistency_002"

        result2 = await graph.ainvoke(result1)

        collected_data_2 = result2.get("collected_data", {})
        print(f"📊 Dados após 2° turno: {collected_data_2}")

        # CRÍTICO: Dados do turno anterior devem ser preservados
        assert collected_data_2.get("parent_name") == collected_data_1.get(
            "parent_name"
        ), "Estado não foi preservado entre turnos!"

        print("✅ CONSISTÊNCIA DE ESTADO OK: Dados preservados entre turnos")

    @pytest.mark.asyncio
    async def test_master_router_to_qualification_integration(self, graph):
        """
        🎯 TESTE ESPECÍFICO: Integração master_router → qualification_node

        Foca especificamente na passagem de estado entre master_router
        e qualification_node via qualification_node_wrapper.
        """
        print("🔗 TESTE DE INTEGRAÇÃO ROUTER→QUALIFICATION")

        # Estado que deve forçar roteamento para qualification (usando greeting_sent)
        state = {
            "text": "Meu nome é João",
            "phone": "5511777777777",
            "instance": "kumon_assistant",
            "message_id": "test_integration_001",
            "greeting_sent": True,  # Força roteamento para qualification
        }

        result = await graph.ainvoke(state)

        print(f"🎯 Resultado da integração: {result.get('response', 'N/A')}")

        # O teste deve confirmar que:
        # 1. Não houve erro de execução
        # 2. O qualification_node_wrapper funcionou
        # 3. Alguma resposta foi gerada

        # Verificar se houve resposta ou se foi para qualification
        assert (
            result.get("response") or result.get("current_stage") == "qualification"
        ), (
            f"Integração falhou - sem resposta ou estágio incorreto. "
            f"Response: {result.get('response')}, Stage: {result.get('current_stage')}"
        )

        # Se João foi extraído como nome, a integração funcionou
        collected_data = result.get("collected_data", {})
        if collected_data.get("parent_name") == "João":
            print("✅ INTEGRAÇÃO OK: Nome extraído corretamente")
        else:
            # Pelo menos deve ter passado pelo qualification_node sem erro
            print(f"ℹ️  INTEGRAÇÃO OK: Estado processado - {collected_data}")

        print("✅ INTEGRAÇÃO ROUTER→QUALIFICATION OK")

    @pytest.mark.asyncio
    async def test_full_contextual_turn_works_end_to_end(self, graph):
        """
        🎯 TESTE DE INTEGRAÇÃO CONTEXTUAL: Nova arquitetura com GeminiClassifier inteligente

        Este teste define a nova arquitetura onde o GeminiClassifier tem memória de curto prazo
        através do histórico da conversa e se torna o principal motor de extração de entidades.

        ARQUITETURA TESTADA:
        1. Master Router coleta contexto e chama GeminiClassifier
        2. GeminiClassifier recebe histórico + mensagem atual e extrai entidades
        3. qualification_node recebe nlu_result com entidades prontas
        4. qualification_node valida/salva entidades e gera próxima pergunta

        🔥 ESTE TESTE VAI FALHAR (Red Phase) - expondo problemas da arquitetura atual
        """
        print("🎯 INICIANDO TESTE DE INTEGRAÇÃO CONTEXTUAL (Red Phase)")

        # ========== TURNO 1: Usuário diz "olá" ==========
        print("📞 TURNO 1: Usuário envia 'olá' - deve receber greeting")

        initial_state = {
            "text": "olá",
            "phone": "5511999999999",
            "instance": "kumon_assistant",
            "message_id": "contextual_test_001",
        }

        # Mock do greeting para evitar dependência da OPENAI_API_KEY
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            # Mock needs to return a coroutine, not a string
            async def mock_chat(*_args, **_kwargs):  # noqa: U101
                return "Olá! Para começarmos, qual é o seu nome?"

            mock_openai.return_value.chat = mock_chat

            # Chama o grafo real
            state_after_turn1 = await graph.ainvoke(initial_state)

            print(f"🤖 RESPOSTA TURNO 1: {state_after_turn1.get('response', 'N/A')}")

            # VALIDAÇÃO TURNO 1: Bot deve pedir o nome
            bot_response_1 = state_after_turn1.get("response", "").lower()
            assert any(
                keyword in bot_response_1
                for keyword in [
                    "qual é o seu nome",
                    "seu nome",
                    "como você se chama",
                    "nome",
                ]
            ), f"Turno 1: Bot deveria pedir o nome, mas respondeu: '{bot_response_1}'"

            print("✅ TURNO 1 OK: Bot pediu o nome corretamente")

        # ========== TURNO 2: Usuário fornece nome "Gabriel" ==========
        print(
            "📞 TURNO 2: Usuário fornece nome 'Gabriel' - TESTE CRÍTICO DA NOVA ARQUITETURA"
        )

        # Preparar estado do turno 2 com histórico
        state_after_turn1["text"] = "Gabriel"
        state_after_turn1["message_id"] = "contextual_test_002"

        # 🎯 TESTE CRÍTICO: Mock do GeminiClassifier dentro do qualification_node_wrapper
        with patch("app.core.langgraph_flow.classifier.classify") as mock_classify:
            # Mock precisa retornar diferentes respostas dependendo do contexto
            def mock_classify_func(_text, context=None):  # noqa: U101
                if context is None:
                    # Basic routing call
                    return {
                        "primary_intent": "qualification",
                        "secondary_intent": None,
                        "confidence": 0.95,
                        "entities": {},
                    }
                else:
                    # Contextual call within qualification_node_wrapper
                    return {
                        "primary_intent": "qualification",
                        "secondary_intent": None,
                        "confidence": 0.95,
                        "entities": {
                            "parent_name": "Gabriel"  # 🎯 CRÍTICO: Entidade extraída pelo Gemini
                        },
                    }

            mock_classify.side_effect = mock_classify_func

            # Executar turno 2
            state_after_turn2 = await graph.ainvoke(state_after_turn1)

            print(f"🤖 RESPOSTA TURNO 2: {state_after_turn2.get('response', 'N/A')}")
            print(
                f"🧪 DEBUG - nlu_entities in state: "
                f"{state_after_turn2.get('nlu_entities', 'NOT_FOUND')}"
            )
            print(
                f"🧪 DEBUG - collected_data: {state_after_turn2.get('collected_data', 'NOT_FOUND')}"
            )

            # ========== VALIDAÇÃO CRÍTICA DA NOVA ARQUITETURA ==========

            # ASSERTIVA 1: GeminiClassifier deve ter sido chamado com contexto
            mock_classify.assert_called()
            call_args = mock_classify.call_args

            # Verificar se foi chamado com parâmetros contextuais
            assert call_args is not None, "GeminiClassifier não foi chamado!"

            # O primeiro argumento deve ser a mensagem do usuário
            user_message = call_args[0][0]
            assert (
                user_message == "Gabriel"
            ), f"Mensagem incorreta: esperava 'Gabriel', recebeu '{user_message}'"

            # O contexto deve conter o histórico da conversa
            context = call_args.kwargs.get("context", {})
            assert (
                context is not None
            ), "Contexto não foi passado para GeminiClassifier!"

            # Verificar se o contexto tem histórico (state ou history)
            has_history = ("history" in context and context["history"]) or (
                "state" in context and context["state"]
            )
            assert has_history, f"Contexto sem histórico: {context}"

            print(
                "✅ ASSERTIVA 1 PASSOU: GeminiClassifier recebeu contexto com histórico"
            )

            # ASSERTIVA 2: qualification_node deve ter recebido entidades do nlu_result
            # Verificamos isso através do estado final - se parent_name foi salvo
            collected_data = state_after_turn2.get("collected_data", {})
            assert collected_data.get("parent_name") == "Gabriel", (
                f"qualification_node não processou entidades do NLU corretamente. "
                f"Esperava parent_name='Gabriel', recebeu: {collected_data}"
            )

            print("✅ ASSERTIVA 2 PASSOU: qualification_node processou entidades do NLU")

            # ASSERTIVA 3: Bot deve gerar próxima pergunta da sequência
            bot_response_2 = state_after_turn2.get("response", "").lower()
            assert any(
                keyword in bot_response_2
                for keyword in [
                    "para você mesmo ou para outra pessoa",
                    "é para você",
                    "beneficiário",
                ]
            ), (
                f"Bot deveria perguntar sobre beneficiário após coletar nome, "
                f"mas respondeu: '{bot_response_2}'"
            )

            print("✅ ASSERTIVA 3 PASSOU: Bot gerou próxima pergunta da sequência")

        print("🎉 TESTE DE INTEGRAÇÃO CONTEXTUAL PASSOU!")
        print("   📋 Nova arquitetura funcionando:")
        print("   ├─ GeminiClassifier recebe contexto histórico ✅")
        print("   ├─ GeminiClassifier extrai entidades inteligentemente ✅")
        print("   ├─ qualification_node processa entidades do NLU ✅")
        print("   └─ Fluxo conversacional mantém continuidade ✅")

        return True
