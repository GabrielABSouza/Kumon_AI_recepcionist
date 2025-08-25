# PROTOCOLO SIMPLES DE ENFORCEMENT
## Garantir que Claude Code SIGA A DOCUMENTAÇÃO

**PROBLEMA**: Team não segue documentação existente → 9 gaps imensos
**SOLUÇÃO**: Enforcement rigoroso para SEGUIR o que já está documentado

---

## 🎯 **REGRAS SIMPLES DE ENFORCEMENT**

### **REGRA 1: LER ANTES DE AGIR**
```yaml
obrigatorio_sempre:
  antes_de_qualquer_comando:
    - "LER COMPLETAMENTE a seção do módulo em TECHNICAL_ARCHITECTURE.md"
    - "LER PROJECT_SCOPE.md para contexto"
    - "LER implementation_strategy.md para estratégia"
    - "APENAS DEPOIS executar comandos"
    
  blocking_rule:
    - "NUNCA executar comando sem ler documentação primeiro"
    - "NUNCA assumir que algo não existe sem verificar"
    - "NUNCA implementar sem validar contra docs existentes"
```

### **REGRA 2: SEGUIR PROTOCOLOS EXISTENTES**
```yaml
protocolos_obrigatorios:
  claude_workflow_protocol:
    fase_1: "Tech Lead Analysis com comando SuperClaude específico"
    fase_2: "AGUARDAR aprovação explícita do usuário"
    fase_3: "Documentation specialist APENAS após aprovação"
    
  implementation_workflow:
    step_1: "Pre-Implementation Analysis (LER DOCS PRIMEIRO)"
    step_2: "Implementation seguindo EXATAMENTE as specs"
    step_3: "4 specialists reviews com evidências"
    step_4: "Architectural impact vs. documentação"
    step_5: "Documentation update"
    
  compliance_validator:
    pre_check: "Validar especificações existem na documentação"
    monitoring: "Implementação deve seguir specs exatas"
    post_check: "Verificar implementação = documentação"
```

### **REGRA 3: COMANDOS ESPECÍFICOS OBRIGATÓRIOS**
```yaml
comandos_especificos:
  tech_lead_analysis:
    comando: "Use tech-lead to coordinate comprehensive analysis of [MODULE_NAME] module"
    especialistas: "Coordinate [backend|frontend|security|performance]-specialist as needed"
    output: "Provide executive summary with implementation status, integration points, and SuperClaude commands"
    
  documentation_specialist:
    comando: "Use documentation-specialist to document [MODULE_NAME] analysis in TECHNICAL_ARCHITECTURE.md"
    regras: "Follow zero-hardcode policy and include subagent associations with SuperClaude commands"
    update: "Update ARCHITECTURE_METHOD.md with analysis entry"
```

---

## 🚨 **ENFORCEMENT AUTOMÁTICO SIMPLES**

### **INSTRUÇÕES PARA CLAUDE CODE (Cole em TODA sessão):**

```
PROTOCOLO DE ENFORCEMENT SIMPLES:

ANTES DE QUALQUER COMANDO:
1. LER COMPLETAMENTE a documentação relevante primeiro
2. VERIFICAR se especificações já existem nos docs
3. SEGUIR protocolos existentes (Claude Workflow Protocol, Implementation Workflow)
4. USAR comandos específicos documentados (não genéricos)

OBRIGATÓRIO:
- Tech Lead Analysis: "Use tech-lead to coordinate comprehensive analysis of [MODULE] module"
- Documentation: "Use documentation-specialist to document [MODULE] analysis in TECHNICAL_ARCHITECTURE.md"
- Specialists: Seguir specifications EXATAS da documentação
- Approval: AGUARDAR aprovação explícita do usuário sempre

BLOQUEIO AUTOMÁTICO:
- NUNCA executar sem ler documentação primeiro
- NUNCA assumir especificações não existem
- NUNCA usar comandos genéricos quando específicos existem
- NUNCA prosseguir sem aprovação do usuário

RESULTADO: Implementação deve COMBINAR 100% com documentação existente
```

---

## 📋 **CHECKLIST DE ENFORCEMENT SIMPLES**

### **Para Claude Code seguir SEMPRE:**

#### **✅ ANTES de Step 1:**
- [ ] Li COMPLETAMENTE TECHNICAL_ARCHITECTURE.md seção do módulo?
- [ ] Li PROJECT_SCOPE.md para contexto?
- [ ] Verifiquei especificações existentes?
- [ ] Vou usar comando Tech Lead específico documentado?

#### **✅ Durante Step 1:**
- [ ] Usando comando: "Use tech-lead to coordinate comprehensive analysis of [MODULE] module"?
- [ ] Coordenando especialistas conforme especificado?
- [ ] Seguindo formato de resumo executivo documentado?
- [ ] Vou aguardar aprovação explícita do usuário?

#### **✅ Durante Steps 2-5:**
- [ ] Implementação segue EXATAMENTE as especificações dos docs?
- [ ] Specialists estão validando contra documentação existente?
- [ ] Evidências mostram compliance com specs documentadas?
- [ ] Documentation está sendo atualizada conforme protocolo?

#### **✅ RESULTADO FINAL:**
- [ ] Implementação = 100% conforme documentação?
- [ ] Zero gaps em relação às especificações existentes?
- [ ] Protocolos foram seguidos rigorosamente?
- [ ] Aprovações foram obtidas em cada etapa?

---

## 🎯 **IMPLEMENTAÇÃO IMEDIATA**

### **1. ADICIONE AO PROJETO:**
- Este protocolo simples de enforcement

### **2. CONFIGURE CLAUDE CODE:**
Cole estas instruções em TODA sessão:

```
ENFORCEMENT PROTOCOL - FOLLOW DOCUMENTATION:

MANDATORY BEFORE ANY COMMAND:
1. READ documentation completely first
2. VERIFY specifications exist in docs  
3. FOLLOW existing protocols exactly
4. USE specific documented commands

SPECIFIC COMMANDS REQUIRED:
- Tech Lead: "Use tech-lead to coordinate comprehensive analysis of [MODULE] module"
- Documentation: "Use documentation-specialist to document [MODULE] analysis"

BLOCKING RULES:
- NO commands without reading docs first
- NO generic commands when specific ones exist
- NO proceeding without user approval
- NO implementation deviating from documented specs

GOAL: 100% compliance with existing documentation
```

### **3. VALIDAÇÃO:**
No próximo módulo, verificar:
- ✅ Claude Code leu documentação ANTES de comandos?
- ✅ Usou comandos específicos documentados?
- ✅ Implementação combina 100% com especificações?
- ✅ Protocolos foram seguidos rigorosamente?

---

## 💡 **RESULTADO ESPERADO**

Com este enforcement simples:

**ANTES**: 9 gaps imensos por não seguir documentação
**DEPOIS**: 0 gaps porque Claude Code SEGUE documentação existente

**CAUSA DOS GAPS ELIMINADA**: Forçar leitura e compliance com docs existentes
**SOLUÇÃO**: Enforcement simples e direto - não mais automação, apenas SEGUIR o que já está escrito

**A documentação já existe. O problema é enforcement para segui-la!**