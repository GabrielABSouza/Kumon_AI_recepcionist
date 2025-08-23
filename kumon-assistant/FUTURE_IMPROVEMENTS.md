# Documento de Melhorias Futuras

Este documento registra oportunidades de melhoria identificadas durante a análise do projeto. O objetivo é catalogar pontos para desenvolvimento futuro, garantindo que a evolução do sistema seja contínua e robusta.

---

### 1. Fortalecimento da Segurança do Webhook

*   **Área:** Segurança da API (Webhook).
*   **Observação:** A validação do webhook da Evolution API depende de uma chave de API estática.
*   **Risco/Oportunidade:** Esta abordagem é vulnerável a ataques de "replay", onde um atacante reenviaria uma requisição válida interceptada.
*   **Sugestão de Implementação:**
    *   **Timestamp:** Exigir um `timestamp` na requisição do webhook e rejeitar chamadas com mais de 60 segundos de idade.
    *   **Nonce (ID Único):** Implementar um ID único por requisição (`nonce`), armazenando-o temporariamente no Redis para invalidar qualquer tentativa de reuso.

---

### 2. Alinhamento Proativo com a LGPD

*   **Área:** Conformidade e Jurídico.
*   **Observação:** A conformidade total com a LGPD foi adiada para fases futuras.
*   **Risco/Oportunidade:** A ausência de processos básicos de direitos do titular e uma justificativa clara para a retenção de dados pode criar riscos legais.
*   **Sugestão de Implementação:**
    *   **Direito à Exclusão:** Definir e documentar um canal manual (ex: um endereço de e-mail) para que usuários solicitem a remoção de seus dados.
    *   **Política de Retenção:** Justificar formalmente o período de 1 ano de retenção para leads não convertidos, vinculando-o a uma finalidade explícita (ex: uma campanha anual de reengajamento).

---

### 3. Monitoramento da Qualidade do RAG

*   **Área:** Monitoramento e Inteligência Artificial.
*   **Observação:** O monitoramento atual foca em métricas de performance, custo e falhas técnicas.
*   **Risco/Oportunidade:** A base de conhecimento (RAG) pode se tornar obsoleta ou perder relevância, degradando a qualidade das respostas sem gerar um alerta técnico.
*   **Sugestão de Implementação:**
    *   **Alerta de Relevância:** Criar um alerta que seja disparado se a pontuação média de similaridade das buscas no Qdrant cair abaixo de um limiar definido (ex: 0.75) por um período prolongado, indicando a necessidade de revisar a base de conhecimento.

---

### 4. Testes de Adversário (Adversarial Testing)

*   **Área:** Qualidade e Testes.
*   **Observação:** A estratégia de testes atual foca nos fluxos críticos e cenários de falha esperados.
*   **Risco/Oportunidade:** O sistema pode apresentar vulnerabilidades ou comportamentos indesejados quando confrontado com entradas projetadas para confundir o LLM.
*   **Sugestão de Implementação:**
    *   **Checklist de Cenários:** Desenvolver um checklist para testes manuais periódicos com foco em "enganar" o assistente.
    *   **Tipos de Teste:** Incluir perguntas ambíguas, contraditórias, que explorem os limites das regras de negócio ou que tentem induzir o LLM a ignorar suas instruções, garantindo que os mecanismos de validação e handoff sejam acionados corretamente.
