# SuperClaude Tech Lead Orchestration Command

## Command Execution

```bash
/implement @orchestration_fixes.md --wave-mode force --wave-strategy systematic --wave-validation --persona-architect --seq --validate --safe-mode --loop --iterations 8 --interactive --output ORCHESTRATION_PROGRESS.md
```

## Mandatory Workflow Protocol

**TECH LEAD MUST FOLLOW THIS EXACT SEQUENCE FOR EACH WAVE - NO EXCEPTIONS**

### Wave Implementation Protocol

#### Step 1: Wave Implementation
```yaml
Execute Phase: Implementation of ONE priority level only
Scope: Single fix from orchestration_fixes.md priority matrix
Validation: Must complete implementation before proceeding
```

#### Step 2: Multi-Agent QA Review
```yaml
QA Agent Call: /spawn --persona-qa --focus testing --validate
Security Agent Call: /spawn --persona-security --focus security --validate
Code Reviewer Call: /spawn --persona-refactorer --focus quality --validate
```

#### Step 3: Mandatory Decision Gate
```yaml
IF any agent reports issues:
  - STOP immediately
  - Report to user: "WAVE [X] BLOCKED - Issues found by [AGENT_TYPE]"
  - Detail all blocking issues
  - Request user authorization to continue

IF all agents approve:
  - Proceed to Step 4
```

#### Step 4: Documentation Specialist
```yaml
Documentation Agent Call: /spawn --persona-scribe --focus documentation
Tasks:
  - Document completed fix in ORCHESTRATION_PROGRESS.md
  - Update implementation status
  - Record validation results
  - Update todo list with completion status
```

#### Step 5: Wave Completion Validation
```yaml
Confirm:
  - Fix implemented correctly
  - All validations passed
  - Documentation updated
  - Todo list reflects progress
```

### Implementation Waves

#### Wave 1: Emergency Critical Fixes (P0)
**Scope**: Create missing `create_kumon_llm()` function
**File**: `/app/services/langgraph_llm_adapter.py`
**Estimated Time**: 15 minutes
**Risk**: Low

**Implementation Steps**:
1. Add missing factory function to langgraph_llm_adapter.py
2. Implement proper KumonLLMService instantiation
3. Test import resolution in secure_conversation_workflow.py
4. Validate no ImportError occurs

#### Wave 2: State Model Critical Fixes (P0)
**Scope**: Fix `message_history` → `messages` field inconsistencies
**File**: `/app/workflows/secure_conversation_workflow.py`
**Estimated Time**: 30 minutes
**Risk**: Low

**Implementation Steps**:
1. Replace all `message_history` references with `messages`
2. Update field access patterns to match CeciliaState model
3. Validate state consistency across workflow
4. Test conversation flow works correctly

#### Wave 3: Interface Method Addition (P1)
**Scope**: Add missing `generate_response()` method
**File**: `/app/services/production_llm_service.py`
**Estimated Time**: 45 minutes
**Risk**: Medium

**Implementation Steps**:
1. Implement `generate_response()` wrapper method
2. Create proper response collection from streaming
3. Maintain compatibility with existing streaming interface
4. Test LangChain adapter compatibility

#### Wave 4: Interface Standardization (P1)
**Scope**: Standardize LLM service interfaces across adapters
**Files**: All adapter files
**Estimated Time**: 2 hours
**Risk**: Medium

**Implementation Steps**:
1. Define common interface protocol
2. Ensure all adapters implement required methods
3. Add proper method delegation patterns
4. Validate cross-adapter compatibility

#### Wave 5: Service Initialization Improvement (P2)
**Scope**: Improve dependency injection and initialization safety
**File**: `/app/services/langgraph_llm_adapter.py`
**Estimated Time**: 1 hour
**Risk**: Low

**Implementation Steps**:
1. Add safe dependency getter functions
2. Implement proper null checking
3. Add initialization validation
4. Test startup sequence reliability

#### Wave 6: Error Handling Enhancement (P2)
**Scope**: Add comprehensive error handling and recovery
**Files**: All orchestration files
**Estimated Time**: 2 hours
**Risk**: Low

**Implementation Steps**:
1. Implement circuit breaker patterns
2. Add fallback mechanisms for service failures
3. Improve error messages and recovery paths
4. Test error scenarios and recovery

#### Wave 7: Interface Validation System (P3)
**Scope**: Create startup validation for interface compatibility
**Files**: Service factory and validation modules
**Estimated Time**: 2 hours
**Risk**: Low

**Implementation Steps**:
1. Add startup validation for interface contracts
2. Implement health checks for critical methods
3. Create integration tests for service communication
4. Validate monitoring and alerting

#### Wave 8: Documentation & Testing Completion (P3)
**Scope**: Complete documentation and testing infrastructure
**Files**: Documentation and test files
**Estimated Time**: 2 hours
**Risk**: Low

**Implementation Steps**:
1. Document all interface contracts
2. Create comprehensive integration tests
3. Implement monitoring for interface compatibility
4. Validate complete system health

## Mandatory Validation Checklist

**After Each Wave, ALL must pass**:
- [ ] All imports resolve successfully
- [ ] No missing method errors in logs
- [ ] State field access works correctly
- [ ] RAG service can call LLM methods
- [ ] End-to-end message flow works
- [ ] Cost monitoring still functions
- [ ] Failover mechanisms still work
- [ ] Security validation passes
- [ ] Code quality standards met

## Critical Command Flags Explanation

```yaml
--wave-mode force: Forces wave orchestration for systematic implementation
--wave-strategy systematic: Uses methodical wave-by-wave approach
--wave-validation: Enables mandatory validation gates between waves
--persona-architect: Primary tech lead persona for system coordination
--seq: Enables Sequential MCP for complex multi-step analysis
--validate: Forces validation at each step
--safe-mode: Maximum validation with conservative execution
--loop: Enables iterative improvement mode
--iterations 8: Exactly 8 waves as defined in orchestration_fixes.md
--interactive: Requires user confirmation between waves if issues found
```

## Execution Rules

**MANDATORY REQUIREMENTS**:
1. **ONE WAVE AT A TIME**: Never implement multiple waves simultaneously
2. **MANDATORY AGENT CONSULTATION**: QA, Security, and Code Review agents must validate each wave
3. **STOP ON ISSUES**: Any agent reporting issues triggers immediate stop and user notification
4. **DOCUMENTATION REQUIRED**: Every wave completion must update documentation
5. **VALIDATION GATES**: All checklist items must pass before proceeding
6. **USER AUTHORIZATION**: Required when issues are found before continuing

**FORBIDDEN ACTIONS**:
- Skipping validation steps
- Implementing multiple waves without agent approval
- Proceeding with known issues
- Bypassing documentation requirements
- Ignoring failed validation checks

## Success Criteria

**Wave Completion**: All validation agents approve + documentation updated
**Project Completion**: All 8 waves completed + full system validation passes
**Quality Gate**: Zero critical issues + comprehensive test coverage

## Emergency Escalation

**IF CRITICAL ISSUES FOUND**:
1. Stop all implementation immediately
2. Document exact issue details
3. Escalate to user with:
   - Wave number where issue occurred
   - Specific agent that found the issue
   - Detailed description of blocking problem
   - Recommendation for resolution approach
4. Await user authorization before proceeding

This protocol ensures systematic, safe, and thoroughly validated implementation of the orchestration fixes with proper quality gates and documentation at every stage.
