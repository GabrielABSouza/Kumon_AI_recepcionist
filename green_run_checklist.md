# 🟢 GREEN RUN CHECKLIST - V2 Architecture Acceptance Criteria

Checklist para validar que o V2 está funcionando corretamente em produção.

## ✅ LOGS ESPERADOS (Success Patterns)

### 1. StageResolver Execution
```
✅ StageResolver.apply: resolved stage=greeting for session=<session_id>
✅ StageResolver.apply: resolved stage=qualification for session=<session_id>
✅ StageResolver.apply: resolved stage=information for session=<session_id>
```

### 2. SmartRouter Node Execution  
```
✅ [SMART_ROUTER node] Processing routing decision for session=<session_id>
✅ SmartRouter decision: <target_node> (<threshold_action>)
✅ [SMART_ROUTER node] persisted routing_decision with target=<target>
```

### 3. ResponsePlanner Node Execution
```
✅ [RESPONSE_PLANNER node] Reading routing_decision for session=<session_id>
✅ [RESPONSE_PLANNER node] Generated response for mode=<template|llm_rag|handoff>
✅ [RESPONSE_PLANNER node] persisted intent_result with category=<category>
```

### 4. Delivery Success
```
✅ Delivery processing outbox with <N> messages for session=<session_id>
✅ Delivery success=true for session=<session_id>
```

### 5. V2 Architecture Confirmation
```
✅ V2 Architecture Enabled: Using workflow_migration.py
✅ Pure Universal Edge Router: routing for <phone> 
✅ Pure Universal Edge Router: → <target> (read from routing_decision)
```

## ❌ LOGS QUE NÃO DEVEM APARECER (Failure Patterns)

### 1. V1 Architecture Traces
```
❌ Universal Edge Router: routing & planning…
❌ Step 1: SmartRouter deciding route
❌ Step 2: ResponsePlanner generating response
```

### 2. Missing State Data
```
❌ No routing_decision found in state
❌ No intent_result found in state  
❌ ⚠️ No routing_decision found in state - using fallback to DELIVERY
```

### 3. Method Signature Errors
```
❌ type object 'ResponsePlanner' has no attribute 'plan'
❌ ResponsePlanner.plan() method not found
```

### 4. Variable Name Errors
```
❌ name 'conversation_state' is not defined
❌ NameError: name 'conversation_state' is not defined
```

### 5. Architecture Violations
```
❌ SmartRouterAdapter called from edge function
❌ ResponsePlanner called from edge function
❌ State mutation detected in edge function
```

## 🔧 TESTING COMMANDS

### Enable V2 Architecture
```bash
export WORKFLOW_V2_ENABLED=true
```

### Check Architecture Selection
```bash
# Should show V2 logs
grep -i "V2 Architecture Enabled" logs/cecilia.log
grep -i "Using workflow_migration.py" logs/cecilia.log
```

### Verify Node Execution Sequence
```bash
# Should show proper V2 pipeline
grep -E "(StageResolver|SMART_ROUTER|RESPONSE_PLANNER|Delivery)" logs/cecilia.log | head -20
```

### Validate No V1 Traces
```bash
# Should return empty (no results)
grep -i "Universal Edge Router: routing & planning" logs/cecilia.log
grep -i "SmartRouter deciding route" logs/cecilia.log
```

### Check Error Patterns
```bash
# Should return empty (no errors)
grep -i "conversation_state.*not defined" logs/cecilia.log
grep -i "ResponsePlanner.*no attribute" logs/cecilia.log
```

## 🎯 ROLLBACK CRITERIA

Se qualquer um dos ❌ logs aparecer, execute:

```bash
export WORKFLOW_V2_ENABLED=false
```

E investigue os problemas antes de reativar V2.

## 📊 SUCCESS METRICS

- **0** V1 architecture traces
- **0** method signature errors  
- **0** conversation_state errors
- **100%** V2 pipeline execution (StageResolver → SmartRouter → ResponsePlanner → Delivery)
- **Success rate ≥ 95%** for message delivery

## 🚀 PRODUCTION READINESS CHECKLIST

- [ ] All ✅ patterns appearing in logs
- [ ] All ❌ patterns absent from logs  
- [ ] Response times < 2s per message
- [ ] No error spikes in monitoring
- [ ] WhatsApp delivery success rate ≥ 95%
- [ ] Architectural gates passing: `python3 architectural_gates.py`

---

**🎉 Once all criteria are met, V2 architecture is ready for full production deployment!**