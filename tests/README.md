# 🧪 Testes TDD - Arquitetura ONE_TURN

## Estrutura de Testes

```
tests/
  conftest.py                    # Fixtures globais
  utils/
    fakes.py                     # FakeRedis e CallRecorder
    payloads.py                  # Helpers para criar payloads
  test_preprocessor_unit.py      # Testes unitários do preprocessor
  test_webhook_preprocessor.py   # Testes de integração webhook
```

## Executar Testes

```bash
# Instalar dependências
pip install -r requirements-test.txt

# Executar todos os testes
pytest tests/ -v

# Executar apenas unitários
pytest tests/test_preprocessor_unit.py -v

# Executar apenas integração
pytest tests/test_webhook_preprocessor.py -v

# Executar com cobertura
pytest tests/ --cov=app --cov-report=html
```

## Casos de Teste Implementados

### Testes Unitários (Preprocessor)
- ✅ Autenticação com headers válidos
- ✅ Rejeição de headers ausentes
- ✅ Sanitização de scripts e limite de texto
- ✅ Rate limiting permite abaixo do limite
- ✅ Rate limiting bloqueia acima do limite
- ✅ Normalização de emojis e espaços
- ✅ Mensagens fromMe marcadas para ignorar

### Testes de Integração (Webhook)
- ✅ Webhook retorna 200 e processa mensagem
- ✅ Ignora mensagens fromMe
- ✅ Deduplicação previne processamento duplicado
- ✅ Turn lock serializa processamento concorrente
- ✅ Falha de auth não processa mensagem
- ✅ Suporta mensagens não-texto com caption
- ✅ Logs estruturados para eventos do pipeline
- ✅ Rate limiting em integração
- ✅ Degradação graceful sem Redis
- ✅ Warning de segurança para spoofing

## Fixtures Disponíveis

- `app`: Instância do FastAPI
- `async_client`: Cliente HTTP assíncrono para testes
- `patch_redis`: FakeRedis para testes sem Redis real
- `mock_gemini`: Mock do classificador Gemini
- `mock_delivery`: Mock do serviço de entrega
- `mock_openai`: Mock do OpenAI

## Padrão TDD

1. **Red**: Escrever teste que falha
2. **Green**: Implementar código mínimo para passar
3. **Refactor**: Melhorar código mantendo testes verdes

## Próximos Passos

1. Implementar preprocessor real no webhook
2. Adicionar testes para classificação (Gemini)
3. Adicionar testes para nós do LangGraph
4. Testes de performance e carga