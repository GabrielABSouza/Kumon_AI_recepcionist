# LangSmith Prompt Naming Convention

## 🏷️ Estrutura de Nomes

### Formato Padrão
```
{project}:{stage}:{type}:{variant}
```

**Exemplos**:
- `kumon:greeting:welcome:initial`
- `kumon:scheduling:confirmation:success`
- `kumon:fallback:handoff:explicit_request`

### Componentes

#### 1. Project (`kumon`)
- Sempre `kumon` para identificar o projeto

#### 2. Stage (Estágio da Conversação)
- `greeting` - Saudação inicial
- `qualification` - Qualificação do lead
- `information` - Coleta de informações
- `scheduling` - Agendamento de visitas
- `confirmation` - Confirmação de dados
- `followup` - Acompanhamento
- `completed` - Conversa finalizada
- `fallback` - Mensagens de erro/escalonamento

#### 3. Type (Tipo de Interação)
- `welcome` - Mensagens de boas-vindas
- `collection` - Coleta de dados (nome, idade, etc.)
- `response` - Respostas a perguntas específicas
- `suggestion` - Sugestões de próximos passos
- `confirmation` - Confirmações de ações
- `clarification` - Pedidos de esclarecimento
- `handoff` - Transferência para humano
- `error` - Mensagens de erro

#### 4. Variant (Variação Específica)
- `initial` - Primeira interação
- `followup` - Continuação
- `success` - Sucesso na ação
- `failure` - Falha na ação
- `retry` - Nova tentativa
- `alternative` - Abordagem alternativa

## 📚 Mapeamento Completo dos Prompts

### GREETING (Saudação)
```
kumon:greeting:welcome:initial
kumon:greeting:collection:parent_name
kumon:greeting:response:child_interest
kumon:greeting:response:self_interest
kumon:greeting:clarification:unclear
kumon:greeting:collection:child_name_correction
kumon:greeting:collection:child_name_confirmed
```

### QUALIFICATION (Qualificação)
```
kumon:qualification:response:age_too_young
kumon:qualification:response:age_ideal
kumon:qualification:response:age_adult
kumon:qualification:error:age_not_identified
kumon:qualification:response:methodology_transition
```

### INFORMATION (Informações)
```
kumon:information:response:program_portuguese
kumon:information:response:program_mathematics
kumon:information:response:program_english
kumon:information:response:materials
kumon:information:response:results_timeline
kumon:information:response:teacher_support
kumon:information:response:progress_evaluation
kumon:information:response:methodology
kumon:information:response:pricing
kumon:information:suggestion:schedule_visit
kumon:information:fallback:complex_question
kumon:information:fallback:first_attempt
kumon:information:clarification:unclear_question
```

### SCHEDULING (Agendamento)
```
kumon:scheduling:welcome:direct_booking
kumon:scheduling:welcome:skip_questions
kumon:scheduling:response:booking_decline
kumon:scheduling:collection:time_preference
kumon:scheduling:error:saturday_unavailable
kumon:scheduling:error:sunday_unavailable
kumon:scheduling:error:evening_unavailable
kumon:scheduling:clarification:preference_unclear
kumon:scheduling:error:no_slots_available
kumon:scheduling:response:slots_found
kumon:scheduling:error:availability_check
kumon:scheduling:clarification:selection_unclear
kumon:scheduling:confirmation:slot_selected
kumon:scheduling:error:invalid_email
kumon:scheduling:confirmation:booking_success
kumon:scheduling:error:booking_saved
kumon:scheduling:error:technical_issue
```

### CONFIRMATION (Confirmação)
```
kumon:confirmation:response:next_steps
```

### FOLLOWUP (Acompanhamento)
```
kumon:followup:response:goodbye
```

### COMPLETED (Finalizada)
```
kumon:completed:welcome:return_user
```

### FALLBACK (Escalonamento)
```
kumon:fallback:handoff:explicit_request
kumon:fallback:handoff:repeated_confusion
kumon:fallback:handoff:conversation_stuck
kumon:fallback:handoff:general
kumon:fallback:clarification:first_attempt
kumon:fallback:clarification:second_attempt
kumon:fallback:clarification:third_attempt
kumon:fallback:response:alternative_approach
kumon:fallback:followup:general
```

## 🏷️ Sistema de Tags

### Tags de Ambiente
- `prod` - Produção
- `staging` - Homologação
- `dev` - Desenvolvimento

### Tags de Versão
- `v1.0.0` - Versão semântica
- `v1.1.0` - Melhorias
- `v2.0.0` - Breaking changes

### Tags de Teste A/B
- `variant-a` - Versão original
- `variant-b` - Versão alternativa
- `winner` - Versão vencedora

### Tags de Contexto
- `requires-name` - Precisa do nome do usuário
- `requires-age` - Precisa da idade
- `requires-child-data` - Precisa de dados da criança
- `business-hours-only` - Apenas horário comercial

## 🎯 Exemplos de Uso

### Busca por Estágio
```python
# Todos os prompts de greeting
prompts = prompt_manager.get_prompts_by_stage("greeting")

# Prompts específicos de agendamento
booking_prompts = prompt_manager.get_prompts_by_pattern("kumon:scheduling:*")
```

### Busca por Tag
```python
# Prompts de produção
prod_prompts = prompt_manager.get_prompts_by_tag("prod")

# Prompts que precisam de nome
name_prompts = prompt_manager.get_prompts_by_tag("requires-name")
```

### Versionamento
```python
# Buscar versão específica
prompt = prompt_manager.get_prompt(
    "kumon:greeting:welcome:initial", 
    tag="v2.0.0"
)

# Buscar versão de produção
prompt = prompt_manager.get_prompt(
    "kumon:scheduling:confirmation:success",
    tag="prod"
)
```

Este sistema garante organização, versionamento e facilita a manutenção dos prompts no LangSmith.