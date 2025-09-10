"""
Verificar se há dados contaminados no Redis do Railway.
"""
import json
import os

try:
    import redis

    # Tentar conectar com Redis do Railway
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        print("❌ REDIS_URL não encontrada nas variáveis de ambiente")
        print("Variáveis disponíveis:")
        for key in os.environ.keys():
            if "redis" in key.lower() or "cache" in key.lower():
                print(f"  {key}={os.environ[key]}")
        exit(1)

    print(f"🔍 Conectando ao Redis: {redis_url[:20]}...")

    client = redis.Redis.from_url(redis_url, decode_responses=True)

    # Testar conexão
    client.ping()
    print("✅ Conexão com Redis estabelecida")

    # Buscar todas as chaves de conversa
    conversation_keys = client.keys("conversation:*")
    print(f"📊 Total de chaves de conversa: {len(conversation_keys)}")

    contaminated_sessions = []

    for key in conversation_keys:
        try:
            state_json = client.get(key)
            if state_json:
                state = json.loads(state_json)
                parent_name = state.get("parent_name")

                if parent_name in [
                    "Olá",
                    "Oi",
                    "oi",
                    "olá",
                    "Eai",
                    "eai",
                    "Hey",
                    "hey",
                    "Bom",
                    "bom",
                    "Boa",
                    "boa",
                ]:
                    phone = key.replace("conversation:", "")
                    contaminated_sessions.append(
                        {
                            "key": key,
                            "phone": phone,
                            "parent_name": parent_name,
                            "full_state": state,
                        }
                    )
                    print(
                        f"🚨 CONTAMINAÇÃO DETECTADA: {key} -> parent_name='{parent_name}'"
                    )
        except Exception as e:
            print(f"⚠️  Erro ao processar {key}: {e}")

    print(f"\n📋 RESULTADO:")
    print(f"   Total de sessões: {len(conversation_keys)}")
    print(f"   Sessões contaminadas: {len(contaminated_sessions)}")

    if contaminated_sessions:
        print(f"\n🧹 LIMPEZA NECESSÁRIA:")
        for session in contaminated_sessions:
            print(f"   - {session['key']}: parent_name='{session['parent_name']}'")

        # Opção de limpeza automática
        answer = input(
            f"\n❓ Deseja limpar as {len(contaminated_sessions)} sessões contaminadas? (s/n): "
        )
        if answer.lower() == "s":
            for session in contaminated_sessions:
                client.delete(session["key"])
                print(f"🗑️  Removido: {session['key']}")
            print("✅ Limpeza concluída!")
        else:
            print("ℹ️  Limpeza cancelada.")
    else:
        print("✅ Nenhuma contaminação detectada no Redis!")

except ImportError:
    print("❌ Biblioteca redis não instalada: pip install redis")
except redis.ConnectionError as e:
    print(f"❌ Erro de conexão com Redis: {e}")
except Exception as e:
    print(f"❌ Erro inesperado: {e}")
