from typing import Dict, Any, List
from ..state.models import CeciliaState, get_collected_field, set_collected_field
from ..state.managers import StateManager
import logging

logger = logging.getLogger(__name__)

class ValidationNode:
    """
    Node de validação - Valida respostas antes do envio COM INTEGRAÇÃO DE ROBUSTEZ
    """
    
    def __init__(self):
        self.validation_rules = self._load_validation_rules()
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Valida resposta antes do envio CONSIDERANDO CIRCUIT BREAKER"""
        logger.info(f"Validating response for {state['phone_number']}")
        
        response_text = state.get("last_bot_response", "")
        
        # ========== VERIFICAR CIRCUIT BREAKER PRIMEIRO ==========
        circuit_check = StateManager.check_circuit_breaker(state)
        if circuit_check["should_activate"]:
            logger.info(f"Circuit breaker priority - skipping validation for {state['phone_number']}")
            return self._create_validation_bypass(state, "circuit_breaker_priority")
        
        # ========== VERIFICAR CONTEXTO DE ROBUSTEZ ==========
        robustness_context = self._analyze_robustness_context(state)
        
        if robustness_context["should_skip_validation"]:
            logger.info(f"Skipping validation due to robustness context: {robustness_context['reason']}")
            return self._create_validation_bypass(state, robustness_context["reason"])
        
        # ========== VALIDAÇÕES ADAPTATIVAS ==========
        # 1. Validações básicas (sempre executar, mas com tolerância)
        basic_issues = self._basic_validation_adaptive(response_text, state, robustness_context)
        
        # 2. Se validação básica falhou CRITICALLY, bloquear
        critical_issues = [issue for issue in basic_issues if self._is_critical_issue(issue)]
        
        if critical_issues:
            logger.warning(f"Critical validation issues found: {critical_issues}")
            return self._create_validation_failure(state, critical_issues, is_critical=True)
        
        # 3. Para issues não-críticos, verificar contexto
        non_critical_issues = [issue for issue in basic_issues if not self._is_critical_issue(issue)]
        
        if non_critical_issues and robustness_context["validation_tolerance"] == "strict":
            # 4. Validação LLM seria aqui, mas por simplicidade vamos pular
            pass
        
        # 5. Validação passou ou foi tolerada
        return self._create_validation_success(state, non_critical_issues)
    
    def _analyze_robustness_context(self, state: CeciliaState) -> Dict[str, Any]:
        """Analisa contexto de robustez para adaptar validação"""
        
        # Fatores que influenciam tolerância de validação
        metrics = state["conversation_metrics"]
        validation = state["data_validation"]
        
        fallback_level = 0  # Não existe mais - usar metrics
        recovery_attempts = 0  # Não existe mais - usar metrics
        validation_attempts = len(validation["validation_history"])
        stage_message_count = metrics["message_count"]
        escape_route = None  # Não existe mais
        
        # Determinar tolerância baseada no contexto
        if fallback_level >= 2:
            tolerance = "very_loose"
        elif fallback_level >= 1 or recovery_attempts >= 1:
            tolerance = "loose" 
        elif validation_attempts >= 2:
            tolerance = "moderate"
        elif stage_message_count >= 6:
            tolerance = "moderate"
        else:
            tolerance = "strict"
        
        # Condições para pular validação completamente
        should_skip = any([
            escape_route == "circuit_breaker_handoff",  # Já decidiu handoff
            escape_route == "direct_scheduling_bypass",  # Emergency scheduling
            fallback_level >= 3,  # Fallback muito alto
            recovery_attempts >= 3,  # Muitas tentativas de recovery
            validation_attempts >= 4,  # Muitas validações falharam
            stage_message_count >= 10  # Conversa muito longa
        ])
        
        skip_reason = None
        if should_skip:
            if escape_route in ["circuit_breaker_handoff", "direct_scheduling_bypass"]:
                skip_reason = f"emergency_route_{escape_route}"
            elif fallback_level >= 3:
                skip_reason = "high_fallback_level"
            elif recovery_attempts >= 3:
                skip_reason = "too_many_recovery_attempts"
            elif validation_attempts >= 4:
                skip_reason = "validation_loop_prevention"
            else:
                skip_reason = "conversation_too_long"
        
        return {
            "should_skip_validation": should_skip,
            "reason": skip_reason,
            "validation_tolerance": tolerance,
            "fallback_level": fallback_level,
            "recovery_attempts": recovery_attempts,
            "validation_attempts": validation_attempts
        }
    
    def _basic_validation_adaptive(
        self, 
        response: str, 
        state: CeciliaState, 
        context: Dict[str, Any]
    ) -> List[str]:
        """Validações básicas adaptadas ao contexto de robustez"""
        issues = []
        tolerance = context["validation_tolerance"]
        
        # 1. Verificar se não está vazia (sempre crítico)
        if not response or len(response.strip()) < 5:
            issues.append("CRITICAL: Resposta vazia ou muito curta")
        
        # 2. Verificar palavras proibidas (sempre crítico)
        forbidden_words = [
            'ia artificial', 'chatbot', 'sistema', 'simulação',
            'não posso', 'não sou capaz', 'limitações', 'assistente virtual'
        ]
        
        response_lower = response.lower()
        for word in forbidden_words:
            if word in response_lower:
                issues.append(f"CRITICAL: Contém palavra proibida: {word}")
        
        # 3. Verificar personalidade Cecília (tolerância baseada no contexto)
        if tolerance == "strict":
            metrics = state["conversation_metrics"]
            if (metrics["message_count"] == 1 and  # Primeira mensagem
                not any(indicator in response_lower for indicator in ['cecília', 'kumon vila a'])):
                issues.append("WARNING: Primeira mensagem deve se identificar como Cecília")
        
        # 4. Verificar comprimento excessivo (só em modo strict)
        if tolerance == "strict" and len(response) > 1000:
            issues.append("WARNING: Resposta muito longa pode confundir usuário")
        
        # 5. Verificar tom adequado (relaxar em contextos de emergência)
        if tolerance in ["strict", "moderate"]:
            if any(indicator in response_lower for indicator in ['desculpe', 'erro', 'problema']):
                issues.append("WARNING: Tom pode ser muito apologético")
        
        return issues
    
    def _is_critical_issue(self, issue: str) -> bool:
        """Determina se um issue é crítico"""
        return issue.startswith("CRITICAL:")
    
    def _create_validation_bypass(self, state: CeciliaState, reason: str) -> Dict[str, Any]:
        """Cria resposta de bypass da validação"""
        return {
            "validation_result": "bypassed",
            "reason": reason,
            "response": state.get("last_bot_response", ""),
            "updated_state": state
        }
    
    def _create_validation_failure(
        self, 
        state: CeciliaState, 
        issues: List[str], 
        is_critical: bool = False
    ) -> Dict[str, Any]:
        """Cria resposta de falha na validação"""
        # Record validation failure in data_validation subsystem
        StateManager.record_validation_attempt(state, "response_validation", False, str(issues))
        updated_state = state
        
        return {
            "validation_result": "failed",
            "issues": issues,
            "is_critical": is_critical,
            "updated_state": updated_state,
            "response": None  # Bloqueia envio
        }
    
    def _create_validation_success(
        self, 
        state: CeciliaState, 
        warnings: List[str] = None
    ) -> Dict[str, Any]:
        """Cria resposta de sucesso na validação"""
        # Record successful validation
        StateManager.record_validation_attempt(state, "response_validation", True)
        
        return {
            "validation_result": "passed",
            "warnings": warnings or [],
            "response": state.get("last_bot_response", ""),
            "updated_state": state
        }
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Carrega regras de validação"""
        return {
            "forbidden_words": [
                'ia artificial', 'chatbot', 'sistema', 'simulação',
                'não posso', 'não sou capaz', 'limitações', 'assistente virtual'
            ],
            "required_identity": ["cecília", "kumon vila a"],
            "max_length": 1000,
            "min_length": 5
        }

# Função para uso no LangGraph
async def validation_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = ValidationNode()
    result = await node(state)
    
    # Atualizar estado baseado no resultado da validação
    if result["validation_result"] == "failed" and result["is_critical"]:
        # Critical failure - need to regenerate response
        state.update(result["updated_state"])
        state["needs_regeneration"] = True
        state["validation_failure_reason"] = result["issues"]
    else:
        # Success or non-critical - proceed
        state.update(result.get("updated_state", state))
        state["validation_passed"] = True
        if result.get("warnings"):
            state["validation_warnings"] = result["warnings"]
    
    return state