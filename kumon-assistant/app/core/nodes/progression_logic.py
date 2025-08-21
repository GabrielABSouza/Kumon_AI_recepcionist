from typing import Dict, Any, List
from ..state.models import CeciliaState

class ProgressionLogic:
    """
    Lógica de progressão para determinar quando pode avançar para agendamento
    """
    
    def can_progress_to_scheduling(self, state: CeciliaState) -> Dict[str, Any]:
        """
        Verifica se pode progredir para agendamento baseado nos dados coletados
        """
        # Campos obrigatórios para agendamento
        required_fields = ["parent_name", "child_name", "child_age"]
        missing_fields = []
        
        # Verificar campos obrigatórios
        if not state.get("parent_name"):
            missing_fields.append("parent_name")
        
        # Para cases where is_for_self=True, child_name pode ser o mesmo que parent_name
        if not state.get("child_name"):
            if state.get("is_for_self"):
                # Se é para si mesmo, usar parent_name como child_name
                if state.get("parent_name"):
                    state["child_name"] = state["parent_name"]
                else:
                    missing_fields.append("parent_name")  # Precisa do nome primeiro
            else:
                missing_fields.append("child_name")
        
        if not state.get("child_age"):
            missing_fields.append("child_age")
        
        can_progress = len(missing_fields) == 0
        
        return {
            "can_progress": can_progress,
            "missing_fields": missing_fields,
            "required_fields": required_fields
        }
    
    def get_missing_data_message(self, missing_fields: List[str], state: CeciliaState) -> str:
        """
        Gera mensagem para coletar dados faltantes
        """
        parent_name = state.get("parent_name", "")
        
        if "parent_name" in missing_fields:
            return "Antes de agendar, pode me dizer seu nome? 😊"
        
        elif "child_name" in missing_fields and not state.get("is_for_self"):
            return f"E qual é o nome da criança que faria o Kumon, {parent_name}?"
        
        elif "child_age" in missing_fields:
            if state.get("is_for_self"):
                return f"Qual é a sua idade, {parent_name}? Isso me ajuda a entender melhor suas necessidades! 🎯"
            else:
                child_name = state.get("child_name", "a criança")
                return f"Quantos anos tem o {child_name}? Isso me ajuda a explicar melhor nossos programas! 📚"
        
        # Fallback genérico
        return "Para agendar, preciso de algumas informações básicas. Pode me ajudar? 😊"