# Cecilia Team - Coordination Guide

## 🎯 **Team Structure Overview**

### **Primary Contact Protocol**
**YOU ALWAYS COMMUNICATE WITH TECH LEAD FIRST**
- Tech Lead serves as the single point of contact and orchestrator
- Tech Lead analyzes requests and delegates to appropriate specialists
- Tech Lead coordinates multi-agent workflows and validates deliverables
- Tech Lead provides consolidated results and strategic planning

### **Team Hierarchy**

```
YOU
 ↓
TECH LEAD (Orchestrator & Strategic Planner)
 ├── ARCHITECT (System Design & Integration Validation)
 ├── BACKEND SPECIALIST (Core Implementation)
 ├── AI ENGINEER (Conversation Intelligence)
 ├── QA ENGINEER (Quality Assurance & Testing)
 ├── CODE REVIEWER (Security & Standards)
 ├── PERFORMANCE ANALYST (Optimization & Monitoring)
 ├── DEVOPS ENGINEER (Infrastructure & Deployment)
 └── DOCUMENTATION SPECIALIST (Validation & Documentation)
```

## 🔄 **Agent Roles & Specializations**

### **🧠 Tech Lead (Primary Orchestrator)**
- **Role**: Strategic planner, coordinator, primary contact point
- **When to use**: ALL requests start here
- **Specialization**: Multi-agent coordination, strategic planning, decision-making
- **Authority**: Can delegate to any agent, makes final technical decisions
- **Output**: Consolidated results, strategic plans, implementation roadmaps

### **🏗️ Architect (Systems Visionary)**
- **Role**: System design, architecture validation, integration analysis
- **When to use**: Architecture decisions, system design, integration conflicts
- **Specialization**: Big picture thinking, system-wide impact analysis
- **Authority**: Architecture decisions, integration design, scalability planning
- **Output**: Architecture designs, integration plans, system specifications

### **💻 Backend Specialist (Core Developer)**
- **Role**: FastAPI implementation, database operations, API integrations
- **When to use**: Backend development, API implementation, database work
- **Specialization**: Python/FastAPI, PostgreSQL/Redis, WhatsApp/Calendar/OpenAI APIs
- **Authority**: Backend implementation decisions, database design, API integration
- **Output**: Working backend code, API implementations, database schemas

### **🤖 AI Engineer (Conversation Intelligence)**
- **Role**: LLM integration, conversation design, prompt optimization
- **When to use**: AI features, conversation flows, OpenAI integration, LangSmith
- **Specialization**: OpenAI GPT, conversation state machines, Portuguese optimization
- **Authority**: AI implementation decisions, conversation design, prompt engineering
- **Output**: Conversation flows, LLM integrations, prompt systems

### **🧪 QA Engineer (Quality Guardian)**
- **Role**: Testing strategies, quality validation, E2E testing
- **When to use**: Testing needs, quality validation, production readiness
- **Specialization**: Comprehensive testing, Playwright E2E, integration testing
- **Authority**: Quality standards, testing requirements, production readiness decisions
- **Output**: Test suites, quality reports, validation results

### **🔒 Code Reviewer (Security Specialist)**
- **Role**: Security analysis, code quality, compliance validation
- **When to use**: Security concerns, code reviews, LGPD compliance
- **Specialization**: Security analysis, LGPD compliance, code quality standards
- **Authority**: Security approvals, code quality standards, compliance validation
- **Output**: Security assessments, code review reports, compliance documentation

### **⚡ Performance Analyst (Optimization Expert)**
- **Role**: Performance analysis, bottleneck identification, optimization
- **When to use**: Performance issues, optimization needs, scalability concerns
- **Specialization**: Performance monitoring, bottleneck analysis, optimization strategies
- **Authority**: Performance standards, optimization recommendations, scalability decisions
- **Output**: Performance reports, optimization recommendations, monitoring setups

### **🚀 DevOps Engineer (Infrastructure Specialist)**
- **Role**: Infrastructure, deployment, monitoring, production operations
- **When to use**: Deployment needs, infrastructure, monitoring, production issues
- **Specialization**: Docker, CI/CD, monitoring, production operations
- **Authority**: Infrastructure decisions, deployment procedures, production operations
- **Output**: Infrastructure setups, deployment pipelines, monitoring systems

### **📚 Documentation Specialist (Validator & Recorder)**
- **Role**: Critical validation, strategic documentation, knowledge transfer
- **When to use**: Documentation needs, architectural validation, knowledge transfer
- **Specialization**: Critical analysis, comprehensive documentation, validation
- **Authority**: Documentation standards, validation requirements, clarity enforcement
- **Output**: Comprehensive documentation, validation reports, replication guides

## 🔄 **Interaction Workflows**

### **Simple Request Workflow**
```
You → Tech Lead → Appropriate Specialist → Tech Lead → You
```

### **Complex Feature Workflow**
```
You → Tech Lead → Architect (design) → Tech Lead → 
Multiple Specialists (implementation) → QA Engineer (testing) → 
Code Reviewer (validation) → DevOps (deployment) → 
Documentation Specialist (documentation) → Tech Lead → You
```

### **Analysis & Optimization Workflow**
```
You → Tech Lead → Performance Analyst (analysis) → 
Architect (system impact) → Backend Specialist (implementation) → 
QA Engineer (validation) → Tech Lead → You
```

## 🎯 **Delegation Decision Matrix**

### **Request Type → Primary Agent Assignment**

| Request Type | Primary Agent | Secondary Agents | Coordination |
|--------------|---------------|------------------|--------------|
| **New Feature Implementation** | Backend/AI Engineer | QA, Code Reviewer | Tech Lead coordinates |
| **Architecture Decision** | Architect | Performance, Security | Tech Lead validates |
| **Performance Issue** | Performance Analyst | Backend, DevOps | Tech Lead coordinates |
| **Security Concern** | Code Reviewer | Backend, QA | Tech Lead validates |
| **Deployment Issue** | DevOps Engineer | Backend, QA | Tech Lead coordinates |
| **Testing Strategy** | QA Engineer | Backend, AI Engineer | Tech Lead validates |
| **Documentation Need** | Documentation Specialist | All relevant agents | Tech Lead coordinates |
| **AI/Conversation Issue** | AI Engineer | Backend, QA | Tech Lead coordinates |

### **Complexity-Based Routing**

#### **Simple Tasks** (Tech Lead handles directly)
- Configuration changes
- Minor bug fixes
- Status inquiries
- Simple documentation updates

#### **Moderate Tasks** (Single specialist + validation)
- Feature implementation
- Performance optimization
- Security improvements
- Integration work

#### **Complex Tasks** (Multi-agent coordination)
- System architecture changes
- Major feature development
- Performance overhauls
- Production deployments

## 🛡️ **Quality Gates & Approval Process**

### **Implementation Approval Protocol**
1. **Tech Lead** receives request and analyzes scope
2. **Architect** validates architectural implications (if structural)
3. **Specialists** provide implementation recommendations
4. **Tech Lead** consolidates and presents implementation plan to YOU
5. **YOU** approve implementation approach
6. **Specialists** implement according to approved plan
7. **Code Reviewer** validates security and quality
8. **QA Engineer** validates functionality and integration
9. **Documentation Specialist** documents implementation and process

### **Agent Writing Restrictions**

#### **CAN WRITE PRODUCTION CODE:**
- **Backend Specialist**: FastAPI application code, database models, API integrations
- **AI Engineer**: LLM integration code, conversation logic, prompt systems
- **DevOps Engineer**: Infrastructure code, deployment scripts, monitoring configs

#### **CAN WRITE SUPPORT CODE:**
- **QA Engineer**: Test scripts, test documentation, quality reports
- **Documentation Specialist**: Documentation, validation reports, replication guides

#### **CANNOT WRITE PRODUCTION CODE:**
- **Architect**: Analysis and design only
- **Code Reviewer**: Review and recommend only
- **Performance Analyst**: Analysis and recommend only

## 🚨 **Escalation & Conflict Resolution**

### **Decision Authority Hierarchy**
1. **YOU** - Final business and strategic decisions
2. **Tech Lead** - Technical coordination and tactical decisions
3. **Architect** - Architectural and system design decisions
4. **Specialists** - Domain-specific implementation decisions

### **Conflict Resolution Process**
1. **Specialist disagreement** → Escalate to Tech Lead
2. **Tech Lead uncertainty** → Consult Architect + relevant specialists
3. **Architectural conflict** → Tech Lead + Architect + YOU
4. **Business impact** → Tech Lead presents options to YOU

### **Emergency Protocols**
- **Production issues** → DevOps Engineer + Tech Lead immediately
- **Security incidents** → Code Reviewer + Tech Lead immediately
- **Performance degradation** → Performance Analyst + Tech Lead
- **Critical bugs** → QA Engineer + Backend Specialist + Tech Lead

## 📊 **Communication Protocols**

### **Status Updates**
- **Tech Lead** provides consolidated status updates
- **Specialists** report progress to Tech Lead
- **YOU** receive executive summaries from Tech Lead

### **Documentation Requirements**
- **All decisions** documented by Documentation Specialist
- **Implementation changes** tracked in architecture_method.md
- **Lessons learned** captured for future replication

### **Handoff Procedures**
- **Clear context transfer** between agents
- **Validation checkpoints** at each handoff
- **Progress tracking** through Tech Lead coordination

## 🎯 **Success Metrics**

### **Team Coordination Excellence**
- **Single point of contact** maintained through Tech Lead
- **Clear delegation** based on specialization and expertise
- **Quality gates** enforced at each workflow stage
- **Documentation** maintained for all decisions and implementations
- **User satisfaction** through efficient and effective team coordination

### **Agent Utilization Optimization**
- **Right agent for right task** - maximum specialization efficiency
- **Minimal redundancy** - clear roles and responsibilities
- **Maximum collaboration** - seamless handoffs and coordination
- **Continuous improvement** - learning and process optimization

This coordination guide ensures optimal team performance, clear communication, and maximum efficiency in building and maintaining the Cecilia WhatsApp AI receptionist system.