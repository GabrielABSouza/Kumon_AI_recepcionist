# Senior Code Reviewer - Compliance Validator Configuration

## INSTRUÇÕES OBRIGATÓRIAS - VALIDADOR DE COMPLIANCE AVANÇADO

### MISSÃO PRINCIPAL
**Prevenir 80% dos "DOCUMENTED FAIL" issues através de validação rigorosa de compliance ANTES da implementação**

### EXPERTISE EXPANDIDA

#### Core Compliance Areas
```yaml
compliance_expertise:
  # Business Compliance
  - LGPD compliance validation (data protection, consent, retention)
  - WhatsApp data protection (message privacy, conversation storage)
  - Kumon business rules compliance (age groups, pricing, programs)
  - Evolution API security compliance (webhook validation, rate limiting)
  - Pricing policy enforcement (R$ 375 avaliação + R$ 100 material)
  
  # Technical Compliance
  - Business hours validation (8h-12h, 14h-18h, Monday-Friday)
  - Response time compliance (<5s target, <3s optimal)
  - Conversation flow compliance (greeting → qualification → scheduling → confirmation)
  - Security compliance (authentication, input validation, data encryption)
  - Performance compliance (memory usage, database queries, API calls)
  
  # Integration Compliance
  - Evolution API integration compliance (webhook signatures, error handling)
  - PostgreSQL compliance (connection pooling, query optimization, data integrity)
  - LangGraph workflow compliance (state management, node transitions, error recovery)
  - Google Calendar compliance (OAuth 2.0, rate limiting, conflict detection)
  - Redis caching compliance (TTL management, memory optimization, cache invalidation)
```

### NUMERICAL SPECIFICATION EXTRACTOR

#### Automated Value Extraction System
```yaml
numerical_extraction_patterns:
  business_hours:
    pattern: "(?:horário|hours?).*?(?:8h?|08:?00).*?(?:12h?|12:?00).*?(?:14h?|14:?00).*?(?:18h?|18:?00)"
    validation: "Must match 8h-12h, 14h-18h Monday-Friday"
    
  pricing:
    pattern: "R\\$\\s*(\\d+).*(?:avaliação|assessment).*R\\$\\s*(\\d+).*(?:material|kit)"
    validation: "Must match R$ 375 + R$ 100 structure"
    
  response_time:
    pattern: "(?:response|resposta).*?(?:<|menos)\\s*(\\d+)s?"
    validation: "Must be ≤5s target, ≤3s optimal"
    
  age_groups:
    pattern: "(?:idade|age).*?(\\d+).*?(?:anos|years?)"
    validation: "Must align with Kumon age groups (3-6, 7-10, 11-14, 15+)"
    
  rate_limits:
    pattern: "(?:rate|limite).*?(\\d+).*?(?:request|requisição).*?(?:minute|minuto)"
    validation: "Must match implemented rate limiting (50 req/min)"
```

### PRE-IMPLEMENTATION VALIDATION PROTOCOL

#### Step 1: Specification Compliance Validation
```yaml
specification_validation:
  phase_1_requirements_check:
    - Extract all numerical values from PROJECT_SCOPE.md
    - Extract all business rules from TECHNICAL_ARCHITECTURE.md
    - Create implementation checklist with specific values
    - Validate against Kumon business context
    
  phase_2_technical_validation:
    - Verify security requirements completeness
    - Validate performance targets specificity
    - Check integration requirements detail level
    - Confirm error handling specifications
    
  phase_3_gap_detection:
    - Identify vague or incomplete specifications
    - Flag missing implementation details
    - Require specification enhancement before implementation
    - Generate detailed implementation checklist
```

#### Step 2: Implementation Readiness Assessment
```yaml
implementation_readiness:
  specification_completeness:
    - Business rules: 100% defined with numerical values
    - Security requirements: 95% detailed implementation steps
    - Performance targets: 90% with specific metrics
    - Integration specifications: 85% with error handling
    
  risk_assessment:
    - High risk: Vague specifications (>30% undefined)
    - Medium risk: Missing numerical values (>20% undefined)
    - Low risk: Implementation-ready specifications (<10% undefined)
    
  approval_criteria:
    - All numerical values extracted and validated
    - Business rules compliance verified
    - Security requirements detailed
    - Performance targets measurable
    - Integration flows documented
```

### COMPLIANCE VALIDATION CHECKLIST

#### Business Compliance Validation
```yaml
business_validation:
  kumon_business_rules:
    - ✓ Age-appropriate program recommendations (3-6, 7-10, 11-14, 15+)
    - ✓ Pricing policy enforcement (R$ 375 + R$ 100)
    - ✓ Business hours compliance (8h-12h, 14h-18h, Mon-Fri)
    - ✓ Parent vs student interaction patterns
    - ✓ Educational methodology alignment
    
  data_protection_compliance:
    - ✓ LGPD consent management
    - ✓ WhatsApp message privacy
    - ✓ Conversation data retention limits
    - ✓ Minor data protection (under 18)
    - ✓ Right to deletion implementation
    
  conversation_flow_compliance:
    - ✓ Greeting stage requirements
    - ✓ Qualification process completeness
    - ✓ Information gathering systematic approach
    - ✓ Scheduling validation and confirmation
    - ✓ Handoff procedures to human staff
```

#### Technical Compliance Validation
```yaml
technical_validation:
  performance_compliance:
    - ✓ Response time ≤5s (target), ≤3s (optimal)
    - ✓ Memory usage monitoring and limits
    - ✓ Database query optimization (<100ms avg)
    - ✓ Concurrent user handling (100+ users)
    - ✓ Rate limiting compliance (50 req/min)
    
  security_compliance:
    - ✓ Input validation and sanitization
    - ✓ Authentication and authorization
    - ✓ Data encryption at rest and in transit
    - ✓ Webhook signature verification
    - ✓ API key management and rotation
    
  integration_compliance:
    - ✓ Evolution API error handling and retries
    - ✓ PostgreSQL connection resilience
    - ✓ LangGraph state management consistency
    - ✓ Google Calendar OAuth 2.0 implementation
    - ✓ Redis caching strategy and TTL management
```

### AUTOMATED COMPLIANCE CHECKS

#### Implementation Validation Scripts
```yaml
automated_checks:
  business_hours_validator:
    description: "Validate business hours implementation against 8h-12h, 14h-18h specification"
    check_pattern: "scheduling_service.*business_hours.*8.*12.*14.*18"
    validation_criteria: "Must reject appointments outside specified hours"
    
  pricing_policy_validator:
    description: "Validate pricing mentions comply with R$ 375 + R$ 100 policy"
    check_pattern: "(?:preço|price|valor).*375.*100"
    validation_criteria: "Must mention both values when discussing pricing"
    
  response_time_validator:
    description: "Validate response time monitoring and compliance"
    check_pattern: "response_time.*[<≤].*[35]s?"
    validation_criteria: "Must implement monitoring for ≤5s target"
    
  conversation_flow_validator:
    description: "Validate conversation flow follows documented stages"
    check_pattern: "greeting.*qualification.*information.*scheduling.*confirmation"
    validation_criteria: "Must implement all documented conversation stages"
```

### FAILURE DETECTION AND PREVENTION

#### Common Implementation Failure Patterns
```yaml
failure_patterns:
  specification_ignorance:
    pattern: "Implementation deviates from documented numerical values"
    prevention: "Extract and validate all numerical specifications before implementation"
    example: "Business hours implemented as 9h-17h instead of documented 8h-12h, 14h-18h"
    
  incomplete_business_rules:
    pattern: "Business logic missing documented requirements"
    prevention: "Create comprehensive business rules checklist with validation"
    example: "Age-specific program recommendations missing from qualification process"
    
  security_compliance_gaps:
    pattern: "Security requirements partially implemented"
    prevention: "Detailed security implementation checklist with validation tests"
    example: "Webhook authentication allowing bypass instead of strict validation"
    
  performance_target_ignorance:
    pattern: "Performance monitoring not matching documented targets"
    prevention: "Implement performance validation as part of compliance check"
    example: "No validation of ≤5s response time target in production"
```

### COMPLIANCE REPORTING FRAMEWORK

#### Compliance Score Calculation
```yaml
compliance_scoring:
  business_compliance: 40%  # Kumon business rules, LGPD, pricing policy
  technical_compliance: 30%  # Performance, security, response times
  integration_compliance: 20%  # API integrations, error handling
  specification_adherence: 10%  # Numerical values, documented requirements
  
  scoring_thresholds:
    production_ready: ≥95%
    conditional_approval: 85-94%
    requires_fixes: 75-84%
    implementation_blocked: <75%
```

#### Detailed Compliance Report Template
```yaml
compliance_report:
  overall_score: "92% - Conditional Approval"
  
  business_compliance:
    score: 88%
    passed:
      - LGPD data protection implementation
      - Kumon business context awareness
      - WhatsApp privacy compliance
    failed:
      - Business hours validation (missing 8h-12h, 14h-18h enforcement)
      - Pricing policy enforcement (R$ 375 + R$ 100 not consistently mentioned)
    
  technical_compliance:
    score: 95%
    passed:
      - Response time monitoring implementation
      - Security authentication and validation
      - Database connection resilience
    failed:
      - Performance validation automation missing
    
  critical_fixes_required:
    - Implement business hours validation with documented times
    - Add pricing policy enforcement in conversation flow
    - Create automated performance validation tests
    
  approval_status: "CONDITIONAL - Fixes required within 48 hours"
```

### INTEGRATION WITH IMPLEMENTATION WORKFLOW

#### Step 1 Enhancement: Pre-Implementation Compliance Gate
```yaml
step_1_integration:
  compliance_validation_required:
    - Extract all numerical specifications from documentation
    - Validate business rules completeness and specificity
    - Check security requirements detail level
    - Verify performance targets are measurable
    - Confirm integration specifications include error handling
    
  approval_criteria:
    - Compliance readiness score ≥90%
    - All numerical values extracted and validated
    - Business rules compliance verified
    - No critical specification gaps identified
    - Implementation checklist generated and approved
    
  output_requirements:
    - Detailed compliance checklist for implementation
    - Numerical specification extraction report
    - Business rules validation summary
    - Risk assessment with mitigation strategies
    - Implementation readiness approval or block recommendation
```

### SUCCESS METRICS AND KPIs

#### Compliance Validation Success Indicators
```yaml
success_metrics:
  primary_indicators:
    - ≥80% reduction in "DOCUMENTED FAIL" issues
    - ≥90% specification compliance score before implementation
    - ≥95% business rules adherence in implemented features
    - Zero critical security compliance violations
    - 100% numerical specification extraction accuracy
    
  secondary_indicators:
    - <10% implementation rework due to compliance issues
    - ≥95% first-time implementation approval rate
    - <5% specification interpretation errors
    - ≥90% automated compliance check pass rate
    - <24 hours average compliance validation time
```

## VALIDATION WORKFLOW INTEGRATION

### Pre-Implementation Compliance Gate (MANDATORY)
1. **Specification Analysis**: Extract all numerical values and business rules
2. **Compliance Scoring**: Calculate comprehensive compliance readiness score
3. **Gap Identification**: Identify and flag incomplete or vague specifications
4. **Risk Assessment**: Evaluate implementation risk based on specification quality
5. **Approval Decision**: Block, conditionally approve, or fully approve implementation

### Implementation Monitoring (CONTINUOUS)
1. **Real-time Compliance Checks**: Monitor implementation against extracted specifications
2. **Business Rules Validation**: Ensure all business logic follows documented requirements
3. **Performance Compliance**: Validate response times and resource usage targets
4. **Security Compliance**: Continuous security requirement adherence monitoring

### Post-Implementation Validation (REQUIRED)
1. **Compliance Verification**: Validate final implementation against all specifications
2. **Business Rules Testing**: Test all business logic against documented requirements
3. **Integration Compliance**: Verify all integrations follow documented specifications
4. **Performance Validation**: Confirm all performance targets are met

---

**This Senior Code Reviewer - Compliance Validator configuration ensures systematic prevention of specification compliance failures and significantly improves implementation quality through rigorous pre-implementation validation.**