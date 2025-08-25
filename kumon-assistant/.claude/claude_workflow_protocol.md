# Claude Workflow Protocol - Documentação Técnica

## PROTOCOLO OBRIGATÓRIO PARA ANÁLISE DE MÓDULOS

### FLUXO OBRIGATÓRIO - NUNCA DESVIAR

1. **FASE 1: Tech Lead Analysis**
   - Chamar Tech Lead para análise coordenada do módulo
   - Usar comando SuperClaude para máxima eficiência
   - Tech Lead deve coordenar especialistas relevantes
   - Retornar com **resumo executivo** da análise

2. **FASE 2: Validação do Usuário**
   - Apresentar resumo executivo ao usuário
   - **AGUARDAR aprovação explícita** do usuário
   - NUNCA prosseguir sem confirmação

3. **FASE 3: Documentation Specialist**
   - APENAS após aprovação do usuário
   - Chamar documentation_specialist
   - Seguir configuração em `.claude/documentation_specialist_config.md`
   - Documentar APENAS análises e comandos SuperClaude + subagents

### COMANDOS SUPERCLAUDE OBRIGATÓRIOS

**Para Tech Lead Analysis:**
```
> Use tech-lead to coordinate comprehensive analysis of [MODULE_NAME] module
> Coordinate [backend-specialist|frontend-specialist|security-specialist|performance-specialist] as needed
> Provide executive summary with implementation status, integration points, and SuperClaude commands
```

**Para Documentation Specialist:**
```
> Use documentation-specialist to document [MODULE_NAME] analysis in TECHNICAL_ARCHITECTURE.md
> Follow zero-hardcode policy and include subagent associations with SuperClaude commands
> Update ARCHITECTURE_METHOD.md with analysis entry
```

### RESUMO EXECUTIVO OBRIGATÓRIO

**Formato do resumo para usuário:**

```
## Resumo Executivo - [MODULE_NAME]

**Status da Implementação**: [COMPLETO|PARCIAL|TODO] - [porcentagem]%
**Especialistas Coordenados**: [lista de especialistas utilizados]
**Pontos de Integração**: [número] pontos mapeados
**Configuração**: [status da configuração encontrada]
**Comandos SuperClaude Sugeridos**: [comandos principais identificados]
**Próximos Passos**: [ações recomendadas]

**Validação**: A análise está aprovada para documentação?
```

### CHECKPOINTS OBRIGATÓRIOS

**Antes de cada fase:**
- [ ] Consultar este protocolo
- [ ] Verificar se estou na fase correta
- [ ] Aguardar aprovação do usuário antes de prosseguir

**Durante Tech Lead Analysis:**
- [ ] Usar comando SuperClaude apropriado
- [ ] Coordenar especialistas relevantes
- [ ] Focar em análise, não implementação
- [ ] Preparar resumo executivo estruturado

**Durante Documentation:**
- [ ] Validar que usuário aprovou a análise
- [ ] Verificar configuração do documentation_specialist
- [ ] Documentar apenas análises e comandos
- [ ] Incluir subagents responsáveis pelas tasks

### ERROS CRÍTICOS A EVITAR

❌ **NUNCA fazer:**
- Pular validação do usuário
- Documentar hardcode
- Misturar fases do protocolo
- Prosseguir sem comando SuperClaude
- Esquecer de incluir subagents nos comandos

✅ **SEMPRE fazer:**
- Seguir sequência: Tech Lead → Validação → Documentation
- Usar comandos SuperClaude apropriados
- Aguardar aprovação explícita do usuário
- Documentar apenas análises e comandos
- Incluir subagents responsáveis

### RECUPERAÇÃO DE ERROS

**Se cometer erro no protocolo:**
1. Parar imediatamente
2. Reconhecer o erro ao usuário
3. Consultar este protocolo novamente
4. Reiniciar na fase correta
5. Seguir o fluxo correto

### ERROS COMUNS E LIÇÕES APRENDIDAS

#### **ERRO CRÍTICO: Comandos Imprecisos para Tech Lead**

**Data**: 2025-08-18
**Erro Cometido**: Comando genérico que gerou "gaps" falsos
**Comando Problemático**: 
```
"Find missing module implementation"
```
**Problema**: Tech Lead interpretou corretamente e encontrou "gaps" inexistentes porque o comando não foi específico sobre o que realmente procurar.

**Comando Correto**:
```
"Verify integration consistency between documented modules [LIST SPECIFIC MODULES] 
focusing on potential conflicts, not implementation completeness"
```

**Lição Aprendida**:
- ✅ **SER ESPECÍFICO**: Definir exatamente o que o Tech Lead deve analisar
- ✅ **ESCOPO CLARO**: "Conflicts" vs "Implementation gaps" vs "Documentation review"
- ✅ **LISTAR MÓDULOS**: Especificar quais módulos devem ser analisados
- ✅ **OBJETIVO DEFINIDO**: "Integration consistency" vs "Missing features"

#### **BOAS PRÁTICAS PARA COMANDOS TECH LEAD**

**❌ COMANDOS PROBLEMÁTICOS**:
- "Find problems" (muito genérico)
- "Check implementation" (pode gerar gaps falsos)
- "Missing modules" (pode ignorar documentação existente)
- "What needs to be built" (assume que algo falta)

**✅ COMANDOS PRECISOS**:
- "Verify integration consistency between [Module A] and [Module B]"
- "Check configuration alignment between TECHNICAL_ARCHITECTURE.md and PROJECT_SCOPE.md"
- "Analyze potential conflicts in [specific system area]"
- "Review documentation accuracy for [specific modules list]"

#### **PROTOCOLO ANTI-GAPS FALSOS**

**Antes de pedir análise ao Tech Lead:**
1. **REVISAR** documentação existente primeiro
2. **LISTAR** módulos específicos para análise
3. **DEFINIR** objetivo preciso (conflicts vs gaps vs review)
4. **ESPECIFICAR** escopo exato da análise

**Comando Template Seguro**:
```
"Coordinate analysis of [SPECIFIC MODULE LIST] focusing on [SPECIFIC OBJECTIVE]:
- Integration consistency between modules
- Configuration alignment with PROJECT_SCOPE.md  
- Documentation accuracy verification
- Potential implementation conflicts

DO NOT look for missing implementations - focus on consistency of existing documentation."
```

#### **ERRO CRÍTICO: Análise sem Validação de Documentação Existente**

**Data**: 2025-08-18 
**Erro Cometido**: Fiz análise pré-implementação assumindo que Preprocessor não existia como especificação
**Comando Problemático**: 
```
"Deep Requirements Analysis without reading TECHNICAL_ARCHITECTURE.md first"
```

**Problema**: 
- ❌ Não li completamente TECHNICAL_ARCHITECTURE.md antes da análise
- ❌ Assumi que faltava especificação quando ela já existia
- ❌ Criei "gap arquitetural" falso
- ❌ Violei workflow: "Validate alignment with TECHNICAL_ARCHITECTURE.md"

**Comando Correto**:
```
"Read and validate TECHNICAL_ARCHITECTURE.md Preprocessor section FIRST, then analyze current implementation status vs documented specification"
```

**Lição Aprendida**:
- 🔴 **LEITURA OBRIGATÓRIA**: SEMPRE ler documentação COMPLETA antes de análise
- 🔴 **VALIDAÇÃO PRIMEIRO**: Verificar specs existentes antes de assumir gaps
- 🔴 **WORKFLOW RIGOROSO**: Nunca pular etapa "validate alignment"
- 🔴 **EVIDÊNCIA DOCUMENTAL**: Basear análise em documentação, não suposições

#### **PROTOCOLO ANTI-ERRO DE LEITURA**

**FLUXO OBRIGATÓRIO ANTES DE QUALQUER ANÁLISE:**
1. **READ COMPLETE**: Ler seção completa do módulo em TECHNICAL_ARCHITECTURE.md
2. **READ PROJECT_SCOPE**: Verificar requisitos em PROJECT_SCOPE.md  
3. **VALIDATE ALIGNMENT**: Confirmar que entendi as especificações
4. **THEN ANALYZE**: Só então fazer análise de implementação vs especificação

**CHECKPOINT OBRIGATÓRIO**:
- [ ] Li completamente a documentação do módulo?
- [ ] Entendi as especificações existentes?
- [ ] Posso citar especificações textuais da documentação?
- [ ] Validei alignment antes de assumir qualquer "gap"?

### EXEMPLO PRÁTICO

**Usuário**: "Analise o módulo X"

**Claude**: 
1. **PRIMEIRO**: Lê TECHNICAL_ARCHITECTURE.md seção do módulo X COMPLETA
2. **SEGUNDO**: Lê PROJECT_SCOPE.md requisitos relacionados
3. **TERCEIRO**: Consulta este protocolo
4. **QUARTO**: Chama Tech Lead com comando SuperClaude apropriado baseado em EVIDÊNCIA DOCUMENTAL
5. Retorna resumo executivo estruturado
6. Aguarda aprovação: "A análise está aprovada para documentação?"
7. Após aprovação, chama documentation_specialist
8. Segue configuração para documentar apenas análises

---

**LEMBRETE CONSTANTE**: Este protocolo deve ser consultado ANTES de qualquer análise de módulo. NUNCA assumir gaps sem LER A DOCUMENTAÇÃO COMPLETA PRIMEIRO.