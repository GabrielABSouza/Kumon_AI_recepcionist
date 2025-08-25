# Documentação de Contratos de Interface do Sistema

**Versão:** 1.0
**Data:** 2025-08-24

## 1. Visão Geral

Este documento detalha os contratos de interface críticos entre os microsserviços internos da aplicação Kumon Assistant. A conformidade com estes contratos é essencial para a estabilidade do sistema. A validação destes contratos é realizada em tempo real através do endpoint de health check `/api/v1/health/service-interfaces`.

## 2. Contratos de Serviço

### 2.1. `AdvancedIntentClassifier` -> `ProductionLLMService`

- **Serviço Dependente:** `AdvancedIntentClassifier`
- **Dependência:** `ProductionLLMService`
- **Atributo de Injeção:** `self.llm_service_instance`
- **Métodos Requeridos na Dependência:**
    - `generate_response(request: StandardLLMRequest) -> StandardLLMResponse`

### 2.2. `LangChainRAGService` -> `LangChainRunnableAdapter`

- **Serviço Dependente:** `LangChainRAGService`
- **Dependência:** `LangChainRunnableAdapter` (que encapsula o `ProductionLLMService`)
- **Atributo de Injeção:** `self.llm`
- **Métodos Requeridos na Dependência:**
    - `ainvoke(input: Union[str, Dict[str, Any], List[BaseMessage]], ...)`

## 3. Monitoramento de Compatibilidade de Interface

A compatibilidade das interfaces acima é monitorada continuamente através do seguinte endpoint de health check:

`GET /api/v1/health/service-interfaces`

### Configuração de Monitoramento

- **Ferramenta de Monitoramento:** Qualquer ferramenta capaz de fazer requisições HTTP (ex: Prometheus, UptimeRobot, Healthchecks.io, monitores do Railway).
- **URL para Monitorar:** `https://<SUA_URL_DE_PRODUCAO>/api/v1/health/service-interfaces`
- **Condição de Sucesso:** A resposta HTTP deve ter um status code `200 OK`.
- **Condição de Falha (Alerta):** Qualquer status code diferente de `200` (especialmente `503 Service Unavailable`) indica uma quebra de contrato de interface. O corpo da resposta JSON conterá os detalhes da falha.
- **Frequência de Verificação Recomendada:** A cada 1 a 5 minutos.
