# tests/integration/test_realistic_scenarios.py

import pytest
import app
from unittest.mock import patch

# Importe o 'workflow' compilado do seu fluxo principal e o criador de estado
# O caminho pode precisar de ajuste dependendo da sua estrutura de pastas
from app.core.langgraph_flow import workflow as graph
from app.core.state.models import create_initial_cecilia_state


@pytest.mark.asyncio
async def test_handles_complex_initial_message_end_to_end(patch_redis, mock_delivery, mock_gemini, mock_openai):
    """
    🧪 TESTE DE INTEGRAÇÃO DE PONTA A PONTA (Cenário Realista)

    Este teste valida o fluxo completo para a mensagem complexa:
    "olá, meu nome é Gabriel, gostaria de informações sobre o kumon de matemática"

    Ele garante que:
    1. O roteador e o classificador trabalhem juntos para extrair todas as entidades.
    2. O nó correto (`information_node`) seja ativado.
    3. O estado seja corretamente preenchido com as entidades extraídas.
    4. A resposta final seja uma "resposta combinada" inteligente, respondendo à
       pergunta e continuando a qualificação.
    """
    print("\n--- 🧪 INICIANDO TESTE DE CENÁRIO REALISTA ---")

    # --- ARRANGE (Preparação) ---

    # 1. A mensagem complexa do usuário
    user_message = "olá, meu nome é Gabriel, gostaria de informações sobre o kumon de matemática"

    # 2. O estado inicial da conversa, como se viesse de um novo webhook
    initial_state = create_initial_cecilia_state(
        phone_number="5511999999999",
        user_message=user_message,
        instance="test_instance",
    )
    # Adicionamos campos necessários para compatibilidade com o grafo
    initial_state['text'] = user_message
    initial_state['phone'] = "5511999999999"
    initial_state['message_id'] = "test_msg_123"

    # --- ACT (Execução) ---

    # 3. Invocamos o grafo completo, da mesma forma que a aplicação faria
    # Usamos um patch para garantir que o LLM não seja chamado de verdade,
    # tornando o teste mais rápido e previsível. Simulamos uma resposta ideal.
    with patch('app.core.llm.openai_adapter.OpenAIClient.chat') as mock_llm_chat:
        # Simulamos a resposta da IA para a "resposta combinada" final
        mock_llm_chat.return_value = (
            "Olá Gabriel! O Kumon de Matemática é um método individualizado que fortalece o raciocínio. "
            "Para que eu possa te ajudar melhor, o Kumon é para você mesmo ou para outra pessoa?"
        )

        final_state = await graph.ainvoke(initial_state)

    # --- ASSERT (Verificação) ---

    print(f"\n✅ DADOS EXTRAÍDOS NO ESTADO FINAL: {final_state.get('collected_data')}")
    print(f"✅ RESPOSTA FINAL DO BOT: {final_state.get('last_bot_response')}")

    # 4. Verificamos se as entidades foram extraídas corretamente
    # Esta é a prova de que o GeminiClassifier funcionou.
    collected_data = final_state.get("collected_data", {})
    assert collected_data.get("parent_name") == "Gabriel", \
        "Deveria ter extraído 'Gabriel' como parent_name"
    
    assert "Matemática" in collected_data.get("program_interests", []), \
        "Deveria ter extraído 'Matemática' como program_interests"

    # 5. Verificamos se a resposta final é a "resposta combinada" inteligente
    # Esta é a prova de que o information_node (ou o nó que foi ativado) funcionou.
    final_response = final_state.get("last_bot_response", "").lower()
    
    # Garante que a parte informativa da resposta está presente
    assert "método individualizado" in final_response, \
        "A resposta deveria conter a informação solicitada sobre o Kumon."

    # Garante que a parte de continuação da qualificação está presente
    assert "para você mesmo ou para outra pessoa" in final_response, \
        "A resposta deveria continuar a qualificação perguntando sobre o beneficiário."

    print("\n--- 🎯 TESTE DE CENÁRIO REALISTA CONCLUÍDO COM SUCESSO ---")