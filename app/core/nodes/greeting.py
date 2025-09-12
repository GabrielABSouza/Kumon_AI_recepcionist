import copy
import logging
from typing import Any, Dict

from app.core.delivery import send_text

logger = logging.getLogger(__name__)


async def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envia a mensagem de saudação inicial e prepara o estado para a qualificação.
    Sua única responsabilidade é iniciar a conversa.
    """
    print("DEBUG|greeting_node_executed|CALLED!")
    print(f"DEBUG|greeting_node|state_type={type(state)}")
    # 1. Proteger o estado contra mutações inesperadas
    state = copy.deepcopy(state)
    logger.info(f"Executing simplified greeting_node for phone: {state.get('phone')}")

    # 2. Definir a resposta padrão e única deste nó
    response_text = "Olá! Eu sou a Cecília do Kumon Vila A. Qual é o seu nome?"

    # 3. Enviar a mensagem
    # Garanta que a chamada a send_text esteja com os argumentos corretos (phone, text, instance)
    delivery_result = await send_text(
        phone=state.get("phone"), text=response_text, instance=state.get("instance")
    )

    # 4. Atualizar o estado com as ações executadas
    state["last_bot_response"] = response_text
    state["greeting_sent"] = True  # Flag crucial para o roteador no próximo turno
    
    # CRITICAL FIX: Set sent flag from delivery result
    state["sent"] = delivery_result.get("sent", "false")

    logger.info("Greeting sent and state updated with greeting_sent=True.")

    # 5. Retornar o estado final
    return state
