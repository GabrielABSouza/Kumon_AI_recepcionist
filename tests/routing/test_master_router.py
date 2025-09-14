"""
🧪 RED PHASE TEST: Provar AttributeError no GeminiClassifier

Este teste irá provar que existe um AttributeError quando o master_router
chama um método inexistente no GeminiClassifier.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.core.gemini_classifier import GeminiClassifier


@pytest.mark.asyncio
async def test_gemini_classifier_attribute_error():
    """
    🚨 RED PHASE TEST: Este teste deve falhar com AttributeError

    O GeminiClassifier está tentando chamar self._build_nlu_prompt(), mas essa função
    está definida fora da classe. Este teste irá expor o problema diretamente.
    """
    # ARRANGE: Criar uma instância de GeminiClassifier forçadamente habilitada
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key_for_testing"}):
        classifier = GeminiClassifier()

        # Forçar enabled=True mesmo que a API key seja fake
        classifier.enabled = True

        # Mock o modelo Gemini para não fazer chamadas reais
        classifier.model = AsyncMock()
        classifier.model.generate_content_async = AsyncMock(
            return_value=AsyncMock(
                text='{"primary_intent": "greeting", '
                + '"secondary_intent": null, "entities": {}, "confidence": 0.9}'
            )
        )

    # ACT & ASSERT: Deve falhar com AttributeError quando tentar chamar _build_nlu_prompt
    try:
        await classifier.classify("olá", {})
        # Se chegou aqui, o AttributeError foi corrigido
        print("✅ GREEN PHASE: AttributeError foi corrigido!")
    except AttributeError as e:
        if "_build_nlu_prompt" in str(e):
            print("🚨 RED PHASE: Confirmado! AttributeError encontrado:")
            print(f"   Erro: {str(e)}")
            pytest.fail(f"EXPECTED FAILURE (Red Phase): {str(e)}")
        else:
            # Outro AttributeError não relacionado
            raise
    except Exception as e:
        print(f"🔍 Outro erro encontrado: {type(e).__name__}: {str(e)}")
        # Pode ser outro problema relacionado ao mock
        raise
