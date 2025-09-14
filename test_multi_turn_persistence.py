#!/usr/bin/env python3
"""
Teste de integração de múltiplos turnos para validar persistência de estado com LangGraph Checkpoints.

Red Phase (TDD): Este teste deve FALHAR inicialmente porque ainda estamos usando
o sistema manual de estado. Após implementar os checkpoints, deve PASSAR.
"""

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

# Load environment variables from .env-dev
load_dotenv(".env-dev")

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import langgraph_flow


async def test_multi_turn_persistence():
    """
    Teste que valida se o estado persiste entre múltiplos turnos usando thread_id.

    Fluxo:
    1. Turno 1: Enviar cumprimento - deve coletar parent_name
    2. Turno 2: Responder pergunta de qualificação - deve manter parent_name e coletar mais dados
    3. Validar que os dados do Turno 1 estão presentes no Turno 2
    """
    print("=== TESTE DE MÚLTIPLOS TURNOS COM LANGGRAPH CHECKPOINTS ===")

    # ID único da conversa (representa o número de telefone)
    conversation_id = "5551999999999"  # Telefone de teste

    # Configuração que identifica a conversa
    config = {"configurable": {"thread_id": conversation_id}}

    print(f"📞 Conversation ID: {conversation_id}")
    print(f"⚙️  Config: {config}")

    # === TURNO 1: Cumprimento ===
    print("\n🔄 TURNO 1: Enviando cumprimento...")

    initial_state_turn1 = {
        "phone": conversation_id,
        "message_id": "test_msg_001",
        "text": "oi, me chamo Maria",
        "instance": "test_instance",
        "collected_data": {},
    }

    print(f"📤 Estado inicial Turno 1: {initial_state_turn1}")

    try:
        # Chama o grafo com config
        result_turn1 = await langgraph_flow.graph.ainvoke(
            initial_state_turn1, config=config
        )
        print(f"📥 Resultado Turno 1: {result_turn1}")

        # Validar que parent_name foi coletado
        collected_data_turn1 = result_turn1.get("collected_data", {})
        parent_name_turn1 = collected_data_turn1.get("parent_name")

        print(f"👤 Parent name coletado no Turno 1: {parent_name_turn1}")

        if not parent_name_turn1:
            print("❌ ERRO: parent_name não foi coletado no Turno 1")
            return False

    except Exception as e:
        print(f"❌ ERRO no Turno 1: {e}")
        return False

    # Pequena pausa entre turnos
    time.sleep(1)

    # === TURNO 2: Resposta de qualificação ===
    print("\n🔄 TURNO 2: Respondendo pergunta de qualificação...")

    initial_state_turn2 = {
        "phone": conversation_id,
        "message_id": "test_msg_002",
        "text": "meu filho tem 8 anos e quer estudar matemática",
        "instance": "test_instance",
        "collected_data": {},  # Início vazio - deve ser preenchido pelo checkpoint
    }

    print(f"📤 Estado inicial Turno 2: {initial_state_turn2}")

    try:
        # Chama o grafo com MESMO config (mesmo thread_id)
        result_turn2 = await langgraph_flow.graph.ainvoke(
            initial_state_turn2, config=config
        )
        print(f"📥 Resultado Turno 2: {result_turn2}")

        # VALIDAÇÃO CRÍTICA: parent_name do Turno 1 deve estar presente
        collected_data_turn2 = result_turn2.get("collected_data", {})
        parent_name_turn2 = collected_data_turn2.get("parent_name")

        print(f"👤 Parent name no Turno 2: {parent_name_turn2}")
        print(f"📊 Dados coletados completos Turno 2: {collected_data_turn2}")

        # === VALIDAÇÃO FINAL ===
        if parent_name_turn2 == parent_name_turn1:
            print("✅ SUCESSO: Estado persistiu entre turnos!")
            print(
                f"✅ Parent name '{parent_name_turn1}' mantido do Turno 1 para Turno 2"
            )
            return True
        else:
            print("❌ FALHA: Estado NÃO persistiu entre turnos!")
            print(f"❌ Esperado: '{parent_name_turn1}', Recebido: '{parent_name_turn2}'")
            return False

    except Exception as e:
        print(f"❌ ERRO no Turno 2: {e}")
        return False


async def main():
    """Função principal do teste."""
    print("🚀 Iniciando teste de múltiplos turnos...")

    # Verificar se DATABASE_URL está configurada
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("⚠️  WARNING: DATABASE_URL não configurada, usando implementação atual")
    else:
        print(f"📊 DATABASE_URL configurada: {db_url[:50]}...")

    success = await test_multi_turn_persistence()

    if success:
        print("\n🎉 TESTE PASSOU: LangGraph Checkpoints funcionando!")
        sys.exit(0)
    else:
        print("\n💥 TESTE FALHOU: Persistência de estado não funcionou")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
