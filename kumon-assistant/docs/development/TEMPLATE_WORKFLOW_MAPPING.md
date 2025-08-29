# Template Workflow Mapping

**Mapeamento completo dos templates do sistema Cecília para os estágios do workflow conversacional.**

## Overview

Este documento mapeia todos os templates disponíveis para os estágios específicos do workflow da Cecília, garantindo que cada momento da conversa tenha o template apropriado com as variáveis corretas.

---

## Estrutura do Workflow

### Estados Principais (ConversationStage)
- **GREETING** - Saudação inicial e coleta de dados básicos
- **QUALIFICATION** - Qualificação do lead e coleta de informações do estudante
- **INFORMATION_GATHERING** - Fornecimento de informações sobre o método Kumon
- **SCHEDULING** - Agendamento de conversa presencial
- **CONFIRMATION** - Confirmação do agendamento
- **COMPLETED** - Conversa finalizada

### Sistema de Fallback
- **FALLBACK_LEVEL1** - Recuperação suave (0.30-0.25 confiança)
- **FALLBACK_LEVEL2** - Recuperação agressiva (<0.25 confiança)

---

## Mapeamento por Estágio

### 🤝 GREETING Stage

**Objetivo**: Saudação inicial, coleta do nome do responsável e identificação do interesse

| Step | Template File | Template Path | Variáveis Obrigatórias | Variáveis Opcionais |
|------|---------------|---------------|------------------------|---------------------|
| WELCOME | `welcome_initial.txt` | `greeting/welcome_initial.txt` | - | `gender_self_suffix` |
| COLLECT_NAME | `cecilia_greeting.txt` | `cecilia_greeting.txt` | - | `parent_name` |
| PARENT_NAME_COLLECTION | `collection_parent_name.txt` | `greeting/collection_parent_name.txt` | `parent_name` | `gender_self_suffix` |
| IDENTIFY_INTEREST | `cecilia_qualification_target_person.txt` | `cecilia_qualification_target_person.txt` | `parent_name` | `gender_self_suffix` |

**Dados Coletados**: `parent_name`, `child_name`, `is_for_self`

### 📋 QUALIFICATION Stage

**Objetivo**: Qualificar o lead e coletar informações específicas do estudante

| Step | Template File | Template Path | Variáveis Obrigatórias | Variáveis Opcionais |
|------|---------------|---------------|------------------------|---------------------|
| CHILD_AGE_INQUIRY | `cecilia_qualification_child_student.txt` | `cecilia_qualification_child_student.txt` | `parent_name`, `gender_pronoun` | `child_name` |
| SELF_QUALIFICATION | `cecilia_qualification_self_student.txt` | `cecilia_qualification_self_student.txt` | `parent_name` | `gender_self_suffix` |
| CURRENT_SCHOOL_GRADE | *(pendente)* | - | `student_name`, `student_age` | `education_level` |

**Dados Coletados**: `student_age`, `education_level`

### 📚 INFORMATION_GATHERING Stage

**Objetivo**: Fornecer informações sobre o método Kumon e programas disponíveis

| Step | Template File | Template Path | Variáveis Obrigatórias | Variáveis Opcionais |
|------|---------------|---------------|------------------------|---------------------|
| METHODOLOGY_EXPLANATION | `cecilia_methodology_kumon.txt` | `cecilia_methodology_kumon.txt` | `parent_name` | `student_name` |
| MATH_PROGRAM_INFO | `cecilia_math_method.txt` | `cecilia_math_method.txt` | `parent_name` | `student_age` |
| PORTUGUESE_PROGRAM_INFO | `cecilia_portuguese_method.txt` | `cecilia_portuguese_method.txt` | `parent_name` | `student_age` |
| ENGLISH_PROGRAM_INFO | `cecilia_english_method.txt` | `cecilia_english_method.txt` | `parent_name` | `student_age` |
| ROUTINE_FREQUENCY | `cecilia_routine_frequency.txt` | `cecilia_routine_frequency.txt` | `parent_name` | - |
| PRICING_INFO | `cecilia_pricing.txt` | `information/cecilia_pricing.txt` | - | `parent_name` |

**Dados Coletados**: `programs_of_interest`

### 📅 SCHEDULING Stage

**Objetivo**: Agendar conversa presencial na unidade

| Step | Template File | Template Path | Variáveis Obrigatórias | Variáveis Opcionais |
|------|---------------|---------------|------------------------|---------------------|
| AVAILABILITY_CHECK | `cecilia_scheduling_availability.txt` | `cecilia_scheduling_availability.txt` | `parent_name` | - |
| APPOINTMENT_SUGGESTION | `cecilia_scheduling_suggestion.txt` | `cecilia_scheduling_suggestion.txt` | `parent_name` | `available_slots` |
| EMAIL_COLLECTION | `cecilia_email_collection.txt` | `cecilia_email_collection.txt` | `parent_name` | - |

**Dados Coletados**: `date_preferences`, `available_slots`, `selected_slot`, `contact_email`

### ✅ CONFIRMATION Stage

**Objetivo**: Confirmar agendamento e fornecer informações finais

| Step | Template File | Template Path | Variáveis Obrigatórias | Variáveis Opcionais |
|------|---------------|---------------|------------------------|---------------------|
| APPOINTMENT_CONFIRMED | `cecilia_scheduling_confirmation.txt` | `cecilia_scheduling_confirmation.txt` | `parent_name`, `contact_email` | `selected_slot` |

**Dados Coletados**: *(finalization data)*

---

## Sistema de Fallback

### 🔄 FALLBACK Level 1 (Soft Recovery)
**Confiança**: 0.30 - 0.25  
**Estratégia**: Admitir confusão e pedir esclarecimento

| Confusion Type | Template File | Template Path | Uso |
|----------------|---------------|---------------|-----|
| CONCEPTUAL | `cecilia_fallback_conceptual.txt` | `fallback/cecilia_fallback_conceptual.txt` | Não entende conceitos |
| PROCEDURAL | `cecilia_fallback_procedural.txt` | `fallback/cecilia_fallback_procedural.txt` | Não sabe como proceder |
| TECHNICAL | `cecilia_fallback_technical.txt` | `fallback/cecilia_fallback_technical.txt` | Problemas técnicos |
| GENERAL | `cecilia_fallback_general.txt` | `fallback/cecilia_fallback_general.txt` | Confusão geral |

### 🆘 FALLBACK Level 2 (Aggressive Recovery)  
**Confiança**: < 0.25  
**Estratégia**: Oferecer menu estruturado ou reset da conversa

| Recovery Type | Template File | Template Path | Uso |
|---------------|---------------|---------------|-----|
| MENU | `cecilia_fallback_level2_menu.txt` | `fallback/cecilia_fallback_level2_menu.txt` | Menu com opções claras |
| REDIRECT | `cecilia_fallback_level2_redirect.txt` | `fallback/cecilia_fallback_level2_redirect.txt` | Redirecionamento suave |
| RESET | `cecilia_fallback_level2_reset.txt` | `fallback/cecilia_fallback_level2_reset.txt` | Reset completo da conversa |

---

## Sistema de Variáveis por Estágio

### GREETING Stage Variables
- **Required**: `parent_name`, `username`
- **Optional**: `child_name`, `student_name`  
- **Generated**: `gender_self_suffix`, `gender_pronoun`

### QUALIFICATION Stage Variables
- **Required**: `parent_name`, `child_name`, `student_name`
- **Optional**: `student_age`, `education_level`
- **Generated**: `gender_pronoun`, `gender_article`, `gender_child_term`

### INFORMATION_GATHERING Stage Variables
- **Required**: `parent_name`, `student_name`
- **Optional**: `student_age`, `programs_of_interest`
- **Generated**: `gender_pronoun`, `gender_possessive`

### SCHEDULING Stage Variables
- **Required**: `parent_name`, `student_name`
- **Optional**: `selected_slot`, `date_preferences`
- **Generated**: `gender_pronoun`

### CONFIRMATION Stage Variables
- **Required**: `parent_name`, `student_name`, `contact_email`
- **Optional**: `selected_slot`
- **Generated**: `gender_pronoun`

---

## Templates Faltantes (Gap Analysis)

### 🚨 Templates Necessários mas Ausentes

1. **QUALIFICATION Stage**
   - `current_school_grade.txt` - Coleta de série escolar
   - `age_validation.txt` - Validação de idade apropriada

2. **INFORMATION_GATHERING Stage**
   - `program_comparison.txt` - Comparação entre programas
   - `benefits_explanation.txt` - Benefícios do método

3. **SCHEDULING Stage**
   - `time_selection.txt` - Seleção de horário específico
   - `reschedule_request.txt` - Reagendamento

4. **ERROR Handling**
   - `invalid_age.txt` - Idade inválida
   - `invalid_email.txt` - Email inválido
   - `scheduling_conflict.txt` - Conflito de agenda

### 📁 Reorganização de Pastas Necessária

**Estrutura Atual vs. Estrutura Ideal**

```
ATUAL:
app/prompts/templates/
├── cecilia_*.txt (vários na raiz)
├── greeting/
├── information/
└── fallback/

IDEAL:
app/prompts/templates/
├── greeting/
├── qualification/      # ← NOVA
├── information/
├── scheduling/         # ← NOVA
├── confirmation/       # ← NOVA
└── fallback/
```

---

## Integração com Sistema de Gênero

### Variáveis de Gênero Disponíveis
- `gender_self_suffix` - "o" / "a" / "o(a)"
- `gender_pronoun` - "ele" / "ela" / "ele(a)"
- `gender_article` - "o" / "a" / "a criança"
- `gender_possessive` - "seu" / "sua" / "seu(a)"
- `gender_child_term` - "filho" / "filha" / "criança"

### Templates que Usam Gênero
- ✅ `cecilia_qualification_target_person.txt` - `{gender_self_suffix}`
- ✅ `cecilia_qualification_child_student.txt` - `{gender_pronoun}`
- 🔄 Outros templates podem ser atualizados para usar variáveis de gênero

---

## Convenções de Nomenclatura

### Pattern de Nomes de Templates
```
{stage}_{action}_{variant}.txt
```

**Exemplos:**
- `greeting_welcome_initial.txt`
- `qualification_child_student.txt` 
- `scheduling_availability_check.txt`
- `fallback_level1_conceptual.txt`

### Pattern de Prompt Names (LangSmith)
```
kumon:{stage}:{action}:{variant}
```

**Exemplos:**
- `kumon:greeting:welcome:initial`
- `kumon:qualification:child:student`
- `kumon:scheduling:availability:check`
- `kumon:fallback:level1:conceptual`

---

## Próximos Passos

1. **Reorganizar templates** nas pastas apropriadas
2. **Criar templates faltantes** identificados na gap analysis
3. **Atualizar sistema de resolução** de templates no `PromptManager`
4. **Adicionar variáveis de gênero** em templates apropriados
5. **Validar mapeamento** com testes funcionais

---

## Histórico de Modificações

| Data | Modificação | Responsável |
|------|-------------|-------------|
| 2024-08-28 | Criação inicial do documento | Claude Code |
| 2024-08-28 | Mapeamento completo dos templates existentes | Claude Code |
| 2024-08-28 | Identificação de gaps e próximos passos | Claude Code |