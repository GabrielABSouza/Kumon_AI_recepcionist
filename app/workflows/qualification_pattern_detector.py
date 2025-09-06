"""
Qualification Pattern Detector - Detecção específica para stage QUALIFICATION

Módulo focado APENAS em detectar padrões durante a qualificação:
- Nome dos pais
- Nome da criança
- Idade
- Série escolar

SIMPLICIDADE > COMPLEXIDADE
"""

import re
from typing import Optional, Dict, Any
from ..core.state.models import ConversationStage, ConversationStep
from ..core.logger import app_logger


class QualificationPatternDetector:
    """
    Detector especializado para o stage QUALIFICATION
    
    Responsabilidade única: detectar e extrair dados durante qualificação
    """
    
    def __init__(self):
        # Padrões APENAS para QUALIFICATION
        self.patterns = {
            ConversationStep.PARENT_NAME_COLLECTION: {
                "name_patterns": [
                    # Nome isolado (mais comum)
                    r"^([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)*)$",
                    # Com introdução
                    r"(?:meu nome é|me chamo|sou)\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)*)",
                    # Versão informal
                    r"(?:é|eh)\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)*)",
                ],
                "expected_type": "parent_name"
            },
            
            ConversationStep.CHILD_NAME_COLLECTION: {
                "name_patterns": [
                    # Nome isolado
                    r"^([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)$",
                    # Com contexto
                    r"(?:nome é|chama|é)\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)",
                    # Ele/Ela se chama
                    r"(?:ele|ela)\s+(?:se\s+)?chama\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]+)",
                ],
                "expected_type": "child_name"
            },
            
            ConversationStep.CHILD_AGE_INQUIRY: {
                "age_patterns": [
                    # Idade com "anos"
                    r"(\d{1,2})\s*anos?",
                    # "tem X"
                    r"tem\s+(\d{1,2})",
                    # Só o número
                    r"^(\d{1,2})$",
                    # "idade é X"
                    r"idade\s+(?:é|eh)?\s*(\d{1,2})",
                ],
                "expected_type": "age"
            },
            
            ConversationStep.CURRENT_SCHOOL_GRADE: {
                "grade_patterns": [
                    # Ano escolar
                    r"(\d)º?\s*ano",
                    # Por extenso
                    r"(primeiro|segundo|terceiro|quarto|quinto|sexto|sétimo|oitavo|nono)",
                    # Pré-escola
                    r"(pré|pre)[\s-]?escola",
                    # Educação infantil
                    r"(jardim|maternal|infantil)",
                    # Ensino fundamental
                    r"fundamental\s*(?:(\d)|I|II)",
                ],
                "expected_type": "school_grade"
            }
        }
    
    def detect_and_extract(
        self, 
        message: str, 
        current_stage: ConversationStage,
        current_step: ConversationStep
    ) -> Dict[str, Any]:
        """
        Detecta e extrai dados baseado no step atual
        
        Args:
            message: Mensagem do usuário
            current_stage: Stage atual (deve ser QUALIFICATION)
            current_step: Step atual
            
        Returns:
            Dict com:
                - detected: bool (se detectou o padrão esperado)
                - confidence: float (0-1)
                - extracted_value: str/int (valor extraído)
                - classification: str (tipo detectado)
        """
        
        # Só processa QUALIFICATION
        if current_stage != ConversationStage.QUALIFICATION:
            return {
                "detected": False,
                "confidence": 0.0,
                "classification": "not_qualification",
                "extracted_value": None
            }
        
        # Busca configuração do step atual
        step_config = self.patterns.get(current_step)
        if not step_config:
            app_logger.warning(f"No patterns configured for step: {current_step}")
            return {
                "detected": False,
                "confidence": 0.0,
                "classification": "unknown_step",
                "extracted_value": None
            }
        
        # Tenta cada padrão do step
        message_clean = message.strip()
        
        # Para PARENT_NAME_COLLECTION
        if current_step == ConversationStep.PARENT_NAME_COLLECTION:
            return self._detect_parent_name(message_clean, step_config)
        
        # Para CHILD_NAME_COLLECTION
        elif current_step == ConversationStep.CHILD_NAME_COLLECTION:
            return self._detect_child_name(message_clean, step_config)
        
        # Para CHILD_AGE_INQUIRY
        elif current_step == ConversationStep.CHILD_AGE_INQUIRY:
            return self._detect_age(message_clean, step_config)
        
        # Para CURRENT_SCHOOL_GRADE
        elif current_step == ConversationStep.CURRENT_SCHOOL_GRADE:
            return self._detect_grade(message_clean, step_config)
        
        # Fallback
        return {
            "detected": False,
            "confidence": 0.0,
            "classification": "no_match",
            "extracted_value": None
        }
    
    def _detect_parent_name(self, message: str, config: dict) -> dict:
        """Detecta nome do pai/mãe"""
        for pattern in config["name_patterns"]:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1) if match.groups() else match.group(0)
                # Validação básica de nome
                if len(name) >= 2 and not name.isdigit():
                    app_logger.info(f"[QUALIFICATION] Parent name detected: {name}")
                    return {
                        "detected": True,
                        "confidence": 0.95,
                        "classification": "parent_name",
                        "extracted_value": name.title()
                    }
        
        # Se parece um nome mas não matchou perfeitamente
        if self._looks_like_name(message):
            return {
                "detected": True,
                "confidence": 0.7,
                "classification": "possible_parent_name",
                "extracted_value": message.title()
            }
        
        return {
            "detected": False,
            "confidence": 0.0,
            "classification": "not_parent_name",
            "extracted_value": None
        }
    
    def _detect_child_name(self, message: str, config: dict) -> dict:
        """Detecta nome da criança"""
        for pattern in config["name_patterns"]:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1) if match.groups() else match.group(0)
                if len(name) >= 2 and not name.isdigit():
                    app_logger.info(f"[QUALIFICATION] Child name detected: {name}")
                    return {
                        "detected": True,
                        "confidence": 0.95,
                        "classification": "child_name",
                        "extracted_value": name.title()
                    }
        
        # Fallback para possível nome
        if self._looks_like_name(message):
            return {
                "detected": True,
                "confidence": 0.7,
                "classification": "possible_child_name",
                "extracted_value": message.title()
            }
        
        return {
            "detected": False,
            "confidence": 0.0,
            "classification": "not_child_name",
            "extracted_value": None
        }
    
    def _detect_age(self, message: str, config: dict) -> dict:
        """Detecta idade da criança"""
        for pattern in config["age_patterns"]:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                age = int(match.group(1))
                # Validação de idade razoável
                if 3 <= age <= 18:
                    app_logger.info(f"[QUALIFICATION] Age detected: {age}")
                    return {
                        "detected": True,
                        "confidence": 0.95,
                        "classification": "age",
                        "extracted_value": age
                    }
        
        return {
            "detected": False,
            "confidence": 0.0,
            "classification": "not_age",
            "extracted_value": None
        }
    
    def _detect_grade(self, message: str, config: dict) -> dict:
        """Detecta série escolar"""
        # Mapeamento de texto para série
        grade_map = {
            "primeiro": "1º ano",
            "segundo": "2º ano",
            "terceiro": "3º ano",
            "quarto": "4º ano",
            "quinto": "5º ano",
            "sexto": "6º ano",
            "sétimo": "7º ano",
            "oitavo": "8º ano",
            "nono": "9º ano",
        }
        
        for pattern in config["grade_patterns"]:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                grade_text = match.group(1) if match.groups() else match.group(0)
                
                # Converte para formato padrão
                if grade_text.isdigit():
                    grade = f"{grade_text}º ano"
                elif grade_text.lower() in grade_map:
                    grade = grade_map[grade_text.lower()]
                else:
                    grade = grade_text
                
                app_logger.info(f"[QUALIFICATION] Grade detected: {grade}")
                return {
                    "detected": True,
                    "confidence": 0.95,
                    "classification": "school_grade",
                    "extracted_value": grade
                }
        
        return {
            "detected": False,
            "confidence": 0.0,
            "classification": "not_grade",
            "extracted_value": None
        }
    
    def _looks_like_name(self, text: str) -> bool:
        """Verifica se texto parece ser um nome"""
        text = text.strip()
        # Critérios simples para possível nome
        return (
            len(text) >= 2 and
            len(text) <= 50 and
            not text.isdigit() and
            not any(char in text for char in ['@', '/', '\\', '?', '!', '#', '$', '%']) and
            text[0].isalpha()
        )


# Singleton instance
qualification_detector = QualificationPatternDetector()