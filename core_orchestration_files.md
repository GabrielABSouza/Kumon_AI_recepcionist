# Core LangChain/LangGraph Orchestration Files

This document lists the core files responsible for LangChain/LangGraph orchestration in the Kumon Assistant project.

## 1. Adaptadores

### Primary Adapters
- `/app/adapters/langchain_adapter.py` - Main adapter to make ProductionLLMService compatible with LangChain
  - `LangChainProductionLLMAdapter` - Implements BaseLLM interface
  - `LangChainRunnableAdapter` - Implements Runnable interface (lightweight)
  - `create_langchain_adapter()` - Factory function

- `/app/services/langgraph_llm_adapter.py` - LangGraph specific adapter
  - `LangGraphLLMAdapter` - Adapter for LangGraph workflows
  - `KumonLLMService` - Kumon context-specific wrapper
  - **ISSUE**: Missing `create_kumon_llm` function that is being imported

## 2. Serviços

### LLM Services
- `/app/services/production_llm_service.py` - Main LLM service implementation
- `/app/services/langchain_rag.py` - RAG integration with LangChain
- `/app/core/service_factory.py` - Service factory that registers all services and adapters

## 3. Workflows

### Main Workflow Files
- `/app/workflows/graph.py` - Main workflow graph (KumonWorkflow)
- `/app/workflows/secure_conversation_workflow.py` - Secure conversation workflow
  - **ISSUE**: Imports non-existent `create_kumon_llm`
  - **ISSUE**: References `message_history` instead of `messages`
- `/app/workflows/nodes.py` - Workflow nodes
- `/app/workflows/edges.py` - Workflow routing and edges

## 4. Estado

### State Management
- `/app/core/state/models.py` - Defines `CeciliaState` (new state model)
  - Uses `messages` field with annotations
  - Uses `last_user_message` field
- `/app/workflows/states.py` - Workflow-specific states

## Known Issues

1. **Import Error**: `create_kumon_llm` function is imported but not defined in `langgraph_llm_adapter.py`
2. **State Mismatch**: Code references `message_history` but `CeciliaState` uses `messages`
3. **Field Inconsistency**: Mix of `user_message` and `last_user_message` usage
4. **Cache Error**: RAG service throwing "L1" cache errors
