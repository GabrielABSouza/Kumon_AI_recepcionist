"""
Information Disclosure Prevention System for Kumon Assistant

Protects sensitive system information and prevents data leakage:

🚫 BLOCKED INFORMATION:
- System architecture and implementation details
- API keys and authentication tokens  
- Database schemas and connections
- Internal business processes
- Personal data of other users
- Technical configuration details
- Development and hosting information

✅ ALLOWED INFORMATION:
- Public business information (hours, location, contact)
- General Kumon method information
- Public pricing and services
- Educational content information
"""

import re
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json

from ..core.logger import app_logger
from ..core.config import settings


class SensitivityLevel(Enum):
    """Levels of information sensitivity"""
    PUBLIC = "public"                    # Publicly available information
    BUSINESS_INTERNAL = "business_internal"  # Internal business details
    SYSTEM_INTERNAL = "system_internal"      # Technical system information
    CONFIDENTIAL = "confidential"            # Highly sensitive data
    CLASSIFIED = "classified"                # Must never be disclosed


class DisclosureType(Enum):
    """Types of information disclosure attempts"""
    SYSTEM_ARCHITECTURE = "system_architecture"
    API_CREDENTIALS = "api_credentials"
    DATABASE_INFO = "database_info"
    BUSINESS_SECRETS = "business_secrets"
    USER_DATA = "user_data"
    TECHNICAL_CONFIG = "technical_config"
    DEVELOPMENT_INFO = "development_info"
    HOSTING_DETAILS = "hosting_details"
    SECURITY_MEASURES = "security_measures"


@dataclass
class SensitivePattern:
    """Pattern for detecting sensitive information requests"""
    name: str
    keywords: List[str]
    patterns: List[str]
    disclosure_type: DisclosureType
    sensitivity: SensitivityLevel
    severity: float  # Risk score 0.0 to 1.0
    description: str
    examples: List[str] = field(default_factory=list)


@dataclass
class DisclosureResult:
    """Result of information disclosure analysis"""
    is_sensitive_request: bool
    disclosure_type: Optional[DisclosureType] 
    sensitivity_level: SensitivityLevel
    sensitivity_score: float
    confidence: float
    matched_patterns: List[str]
    risk_assessment: str
    safe_alternative_response: Optional[str]


class InformationProtectionSystem:
    """
    Advanced information disclosure prevention system
    
    Protects against:
    - Social engineering attempts
    - System information extraction  
    - Technical details disclosure
    - Business intelligence gathering
    - Personal data breaches
    """
    
    def __init__(self):
        # Load sensitive information patterns
        self.sensitive_patterns = self._load_sensitive_patterns()
        self.safe_responses = self._load_safe_responses()
        
        # Information request tracking
        self.disclosure_attempts: Dict[str, List[Dict]] = {}
        
        # Public information that can be safely shared
        self.public_information = self._load_public_information()
        
        # Data classification rules
        self.classification_rules = {
            "public_business_info": {
                "sensitivity": SensitivityLevel.PUBLIC,
                "keywords": ["horario", "endereço", "telefone", "localização", "contato"]
            },
            "kumon_method_info": {
                "sensitivity": SensitivityLevel.PUBLIC,
                "keywords": ["método", "kumon", "ensino", "matemática", "português"]
            },
            "system_info": {
                "sensitivity": SensitivityLevel.CLASSIFIED,
                "keywords": ["sistema", "servidor", "banco de dados", "api", "código"]
            },
            "business_internal": {
                "sensitivity": SensitivityLevel.BUSINESS_INTERNAL,
                "keywords": ["funcionários", "processo interno", "reunião", "estratégia"]
            }
        }
        
        app_logger.info("Information Protection System initialized with data classification")
    
    async def check_information_request(
        self,
        user_message: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if user is requesting sensitive information
        
        Args:
            user_message: User's message content
            request_metadata: Additional request context
            
        Returns:
            Analysis result with sensitivity assessment
        """
        
        # Multi-layer information analysis
        analysis_results = await asyncio.gather(
            self._pattern_based_analysis(user_message),
            self._keyword_sensitivity_analysis(user_message),
            self._social_engineering_detection(user_message),
            self._context_based_analysis(user_message, request_metadata),
            return_exceptions=True
        )
        
        # Combine analysis results
        valid_results = [r for r in analysis_results if isinstance(r, dict)]
        
        if not valid_results:
            # Default to ALLOW simple greetings - only block if there's actual threat evidence
            return self._create_disclosure_result(
                is_sensitive=False,
                sensitivity_level=SensitivityLevel.PUBLIC,
                confidence=0.3,
                message="Simple message - no sensitive information detected"
            )
        
        # Calculate overall sensitivity and confidence
        sensitivity_scores = [r.get("sensitivity_score", 0.0) for r in valid_results]
        confidence_scores = [r.get("confidence", 0.0) for r in valid_results]
        
        disclosure_indicators = []
        for result in valid_results:
            if "disclosures" in result:
                disclosure_indicators.extend(result["disclosures"])
        
        # Overall assessment
        max_sensitivity = max(sensitivity_scores) if sensitivity_scores else 0.0
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Determine if this is a sensitive information request
        is_sensitive_request = max_sensitivity >= 0.6  # 60% threshold
        
        # Find most critical disclosure attempt
        primary_disclosure = None
        if disclosure_indicators:
            most_critical = max(disclosure_indicators, 
                              key=lambda x: x.get("severity", 0.0))
            primary_disclosure = most_critical.get("type")
        
        # Determine sensitivity level
        if max_sensitivity >= 0.9:
            sensitivity_level = SensitivityLevel.CLASSIFIED
        elif max_sensitivity >= 0.7:
            sensitivity_level = SensitivityLevel.CONFIDENTIAL  
        elif max_sensitivity >= 0.5:
            sensitivity_level = SensitivityLevel.SYSTEM_INTERNAL
        elif max_sensitivity >= 0.3:
            sensitivity_level = SensitivityLevel.BUSINESS_INTERNAL
        else:
            sensitivity_level = SensitivityLevel.PUBLIC
        
        # Generate safe response
        safe_response = None
        if is_sensitive_request:
            safe_response = self._generate_safe_response(
                primary_disclosure, user_message
            )
        
        # Track disclosure attempt
        if is_sensitive_request and request_metadata:
            await self._track_disclosure_attempt(
                request_metadata.get("source_identifier", "unknown"),
                primary_disclosure,
                max_sensitivity
            )
        
        return {
            "is_sensitive_request": is_sensitive_request,
            "disclosure_type": primary_disclosure.value if primary_disclosure else None,
            "sensitivity_level": sensitivity_level.value,
            "sensitivity_score": max_sensitivity,
            "confidence": avg_confidence,
            "matched_patterns": [d.get("pattern", "") for d in disclosure_indicators],
            "risk_assessment": self._assess_risk_level(max_sensitivity),
            "safe_alternative_response": safe_response,
            "analysis_details": {
                "disclosure_indicators": len(disclosure_indicators),
                "analysis_layers": len(valid_results),
                "highest_sensitivity": max_sensitivity
            }
        }
    
    async def _pattern_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Pattern-based sensitive information detection"""
        
        message_lower = user_message.lower()
        disclosures = []
        max_sensitivity = 0.0
        
        # Check against all sensitive patterns
        for pattern in self.sensitive_patterns:
            # Check keywords
            keyword_matches = sum(1 for kw in pattern.keywords if kw in message_lower)
            
            # Check regex patterns
            pattern_matches = 0
            for regex_pattern in pattern.patterns:
                if re.search(regex_pattern, message_lower):
                    pattern_matches += 1
            
            # If either keywords or patterns match, it's a potential disclosure
            if keyword_matches > 0 or pattern_matches > 0:
                disclosure_severity = pattern.severity
                if keyword_matches > 1 or pattern_matches > 1:
                    disclosure_severity = min(1.0, disclosure_severity * 1.2)
                
                disclosures.append({
                    "type": pattern.disclosure_type,
                    "severity": disclosure_severity,
                    "pattern": pattern.name,
                    "sensitivity": pattern.sensitivity,
                    "keyword_matches": keyword_matches,
                    "pattern_matches": pattern_matches
                })
                
                max_sensitivity = max(max_sensitivity, disclosure_severity)
        
        return {
            "sensitivity_score": max_sensitivity,
            "confidence": 0.8,  # Pattern matching is quite reliable
            "disclosures": disclosures
        }
    
    async def _keyword_sensitivity_analysis(self, user_message: str) -> Dict[str, Any]:
        """Analyze keywords for sensitivity classification"""
        
        message_lower = user_message.lower()
        sensitivity_scores = []
        disclosures = []
        
        # Check against classification rules
        for category, rule in self.classification_rules.items():
            keyword_matches = sum(1 for kw in rule["keywords"] if kw in message_lower)
            
            if keyword_matches > 0:
                # Map sensitivity levels to scores
                level_scores = {
                    SensitivityLevel.PUBLIC: 0.1,
                    SensitivityLevel.BUSINESS_INTERNAL: 0.4,
                    SensitivityLevel.SYSTEM_INTERNAL: 0.7,
                    SensitivityLevel.CONFIDENTIAL: 0.8,
                    SensitivityLevel.CLASSIFIED: 1.0
                }
                
                score = level_scores.get(rule["sensitivity"], 0.5)
                sensitivity_scores.append(score * (keyword_matches / len(rule["keywords"])))
                
                if score >= 0.6:  # Sensitive categories
                    disclosures.append({
                        "type": DisclosureType.SYSTEM_ARCHITECTURE,  # Generic
                        "severity": score,
                        "pattern": f"keyword_classification_{category}",
                        "keyword_matches": keyword_matches
                    })
        
        max_sensitivity = max(sensitivity_scores) if sensitivity_scores else 0.0
        
        return {
            "sensitivity_score": max_sensitivity,
            "confidence": 0.6,  # Keyword analysis has medium confidence
            "disclosures": disclosures
        }
    
    async def _social_engineering_detection(self, user_message: str) -> Dict[str, Any]:
        """Detect social engineering attempts"""
        
        message_lower = user_message.lower()
        disclosures = []
        sensitivity_score = 0.0
        
        # Authority claims
        if re.search(r'(?:sou|eu sou).*(?:desenvolvedor|administrador|gerente|diretor)', message_lower):
            disclosures.append({
                "type": DisclosureType.SYSTEM_ARCHITECTURE,
                "severity": 0.8,
                "pattern": "false_authority_claim"
            })
            sensitivity_score = max(sensitivity_score, 0.8)
        
        # Urgency tactics
        if re.search(r'urgent|emergência|rápido.*(?:preciso|necessário)', message_lower):
            disclosures.append({
                "type": DisclosureType.BUSINESS_SECRETS,
                "severity": 0.5,
                "pattern": "urgency_tactic"
            })
            sensitivity_score = max(sensitivity_score, 0.5)
        
        # Technical probing
        if re.search(r'como.*(?:funciona|implementado|configurado)', message_lower):
            tech_keywords = len(re.findall(r'sistema|servidor|banco|api|código', message_lower))
            if tech_keywords > 0:
                disclosures.append({
                    "type": DisclosureType.TECHNICAL_CONFIG,
                    "severity": 0.7,
                    "pattern": "technical_probing"
                })
                sensitivity_score = max(sensitivity_score, 0.7)
        
        # Information gathering attempts
        if re.search(r'me (?:conte|fale|explique).*sobre.*(?:sistema|processo|funcionamento)', message_lower):
            disclosures.append({
                "type": DisclosureType.SYSTEM_ARCHITECTURE,
                "severity": 0.6,
                "pattern": "information_gathering"
            })
            sensitivity_score = max(sensitivity_score, 0.6)
        
        return {
            "sensitivity_score": sensitivity_score,
            "confidence": 0.7,
            "disclosures": disclosures
        }
    
    async def _context_based_analysis(
        self, 
        user_message: str, 
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Context-aware information sensitivity analysis"""
        
        sensitivity_score = 0.0
        disclosures = []
        
        # Check for repeated information requests
        if metadata:
            source_id = metadata.get("source_identifier", "unknown")
            recent_attempts = self.disclosure_attempts.get(source_id, [])
            
            # Filter recent attempts (last hour)
            recent_attempts = [
                attempt for attempt in recent_attempts
                if attempt["timestamp"] > datetime.now() - timedelta(hours=1)
            ]
            
            if len(recent_attempts) > 2:  # Multiple attempts in short time
                disclosures.append({
                    "type": DisclosureType.SYSTEM_ARCHITECTURE,
                    "severity": 0.6,
                    "pattern": "repeated_information_requests",
                    "attempt_count": len(recent_attempts)
                })
                sensitivity_score = max(sensitivity_score, 0.6)
        
        # Business hours context
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:  # Outside business hours
            if re.search(r'sistema|servidor|problema|erro', user_message.lower()):
                disclosures.append({
                    "type": DisclosureType.TECHNICAL_CONFIG,
                    "severity": 0.4,
                    "pattern": "off_hours_technical_inquiry"
                })
                sensitivity_score = max(sensitivity_score, 0.4)
        
        return {
            "sensitivity_score": sensitivity_score,
            "confidence": 0.5,
            "disclosures": disclosures
        }
    
    def _assess_risk_level(self, sensitivity_score: float) -> str:
        """Assess risk level based on sensitivity score"""
        
        if sensitivity_score >= 0.9:
            return "CRITICAL - Potential classified information disclosure"
        elif sensitivity_score >= 0.7:
            return "HIGH - Sensitive information request detected"
        elif sensitivity_score >= 0.5:
            return "MEDIUM - Internal information inquiry"
        elif sensitivity_score >= 0.3:
            return "LOW - Business information request"
        else:
            return "MINIMAL - Public information inquiry"
    
    def _generate_safe_response(
        self, 
        disclosure_type: Optional[DisclosureType], 
        user_message: str
    ) -> str:
        """Generate safe response for sensitive information requests"""
        
        if not disclosure_type:
            return self.safe_responses["generic_denial"]
        
        response_key = f"{disclosure_type.value}_response"
        return self.safe_responses.get(response_key, self.safe_responses["generic_denial"])
    
    async def _track_disclosure_attempt(
        self,
        source_identifier: str,
        disclosure_type: Optional[DisclosureType],
        severity: float
    ):
        """Track information disclosure attempts per user"""
        
        attempt = {
            "timestamp": datetime.now(),
            "disclosure_type": disclosure_type.value if disclosure_type else "unknown",
            "severity": severity
        }
        
        self.disclosure_attempts.setdefault(source_identifier, []).append(attempt)
        
        # Keep only recent attempts (last 100)
        if len(self.disclosure_attempts[source_identifier]) > 100:
            self.disclosure_attempts[source_identifier] = \
                self.disclosure_attempts[source_identifier][-100:]
        
        # Log high-severity attempts
        if severity >= 0.8:
            app_logger.warning(
                f"High-severity information disclosure attempt: {source_identifier} - "
                f"{disclosure_type.value if disclosure_type else 'unknown'} (severity: {severity})"
            )
    
    def _create_disclosure_result(
        self,
        is_sensitive: bool,
        sensitivity_level: SensitivityLevel,
        confidence: float,
        message: str,
        disclosure_type: Optional[DisclosureType] = None,
        severity: float = 0.0
    ) -> Dict[str, Any]:
        """Helper to create standardized disclosure results"""
        
        return {
            "is_sensitive_request": is_sensitive,
            "disclosure_type": disclosure_type.value if disclosure_type else None,
            "sensitivity_level": sensitivity_level.value,
            "sensitivity_score": severity,
            "confidence": confidence,
            "matched_patterns": [],
            "risk_assessment": message,
            "safe_alternative_response": self.safe_responses["generic_denial"] if is_sensitive else None
        }
    
    def _load_sensitive_patterns(self) -> List[SensitivePattern]:
        """Load patterns for detecting sensitive information requests"""
        
        return [
            # System architecture inquiries
            SensitivePattern(
                name="system_architecture_inquiry",
                keywords=["sistema", "arquitetura", "servidor", "infraestrutura", "tecnologia"],
                patterns=[
                    r"como.*(?:funciona|implementado|construído).*sistema",
                    r"que.*(?:tecnologia|framework|linguagem).*usa",
                    r"(?:qual|como).*arquitetura.*sistema",
                    r"que.*servidor.*(?:usa|roda|hospeda)"
                ],
                disclosure_type=DisclosureType.SYSTEM_ARCHITECTURE,
                sensitivity=SensitivityLevel.CLASSIFIED,
                severity=0.9,
                description="Attempts to discover system architecture details",
                examples=["como funciona o sistema", "que tecnologia vocês usam"]
            ),
            
            # API and credentials
            SensitivePattern(
                name="api_credentials_inquiry",
                keywords=["api", "chave", "token", "senha", "credencial", "acesso"],
                patterns=[
                    r"(?:qual|me dê).*(?:api key|chave|token)",
                    r"como.*(?:acessar|conectar).*(?:api|sistema)",
                    r"preciso.*(?:credenciais|senha|acesso)",
                    r"token.*(?:de|para).*(?:acesso|autenticação)"
                ],
                disclosure_type=DisclosureType.API_CREDENTIALS,
                sensitivity=SensitivityLevel.CLASSIFIED,
                severity=1.0,
                description="Attempts to obtain API keys or credentials",
                examples=["qual a api key", "preciso das credenciais"]
            ),
            
            # Database information
            SensitivePattern(
                name="database_inquiry",
                keywords=["banco", "database", "dados", "sql", "mysql", "postgresql"],
                patterns=[
                    r"(?:qual|como).*banco.*dados",
                    r"estrutura.*(?:banco|database|dados)",
                    r"tabelas.*(?:do|no).*banco",
                    r"schema.*(?:banco|database)"
                ],
                disclosure_type=DisclosureType.DATABASE_INFO,
                sensitivity=SensitivityLevel.CLASSIFIED,
                severity=0.9,
                description="Attempts to discover database information",
                examples=["qual banco de dados usam", "como é a estrutura do banco"]
            ),
            
            # Development information
            SensitivePattern(
                name="development_inquiry",
                keywords=["código", "github", "repositório", "desenvolvimento", "programação"],
                patterns=[
                    r"(?:onde|qual).*(?:código|repositório)",
                    r"como.*(?:desenvolvido|programado|criado)",
                    r"que.*linguagem.*programação",
                    r"framework.*(?:usado|utilizado)"
                ],
                disclosure_type=DisclosureType.DEVELOPMENT_INFO,
                sensitivity=SensitivityLevel.CONFIDENTIAL,
                severity=0.8,
                description="Attempts to discover development details",
                examples=["onde está o código", "que linguagem usam"]
            ),
            
            # Hosting and infrastructure
            SensitivePattern(
                name="hosting_inquiry", 
                keywords=["hospedagem", "servidor", "cloud", "aws", "google", "azure"],
                patterns=[
                    r"onde.*(?:hospedado|rodando|servidor)",
                    r"que.*(?:cloud|nuvem).*usa",
                    r"(?:aws|google cloud|azure).*(?:usa|utiliza)",
                    r"servidor.*(?:localização|onde)"
                ],
                disclosure_type=DisclosureType.HOSTING_DETAILS,
                sensitivity=SensitivityLevel.CONFIDENTIAL,
                severity=0.7,
                description="Attempts to discover hosting information",
                examples=["onde está hospedado", "usam AWS"]
            ),
            
            # Business secrets
            SensitivePattern(
                name="business_secrets_inquiry",
                keywords=["estratégia", "segredo", "interno", "confidencial", "privado"],
                patterns=[
                    r"informação.*(?:interna|confidencial|secreta)",
                    r"processo.*(?:interno|privado)",
                    r"estratégia.*(?:business|negócio)",
                    r"dados.*(?:confidenciais|privativos)"
                ],
                disclosure_type=DisclosureType.BUSINESS_SECRETS,
                sensitivity=SensitivityLevel.CONFIDENTIAL,
                severity=0.8,
                description="Attempts to access confidential business information",
                examples=["informações internas", "processo confidencial"]
            ),
            
            # Security measures
            SensitivePattern(
                name="security_inquiry",
                keywords=["segurança", "proteção", "firewall", "autenticação", "criptografia"],
                patterns=[
                    r"que.*(?:segurança|proteção).*tem",
                    r"como.*(?:protegido|seguro)",
                    r"(?:firewall|antivirus).*(?:usa|tem)",
                    r"medidas.*segurança"
                ],
                disclosure_type=DisclosureType.SECURITY_MEASURES,
                sensitivity=SensitivityLevel.CLASSIFIED,
                severity=0.9,
                description="Attempts to discover security measures",
                examples=["que segurança tem", "como é protegido"]
            )
        ]
    
    def _load_safe_responses(self) -> Dict[str, str]:
        """Load safe response templates for sensitive information requests"""
        
        return {
            "system_architecture_response": "Não posso fornecer detalhes técnicos do sistema. Posso ajudar com informações sobre o método Kumon ou agendar uma visita! 😊",
            
            "api_credentials_response": "Não compartilho informações de acesso ou credenciais. Como posso ajudar com informações sobre nossos programas educacionais?",
            
            "database_info_response": "Informações técnicas são confidenciais. Posso falar sobre nossos métodos de ensino ou ajudar com agendamentos!",
            
            "development_info_response": "Não discuto detalhes de desenvolvimento. Que tal conhecer como desenvolvemos o potencial dos nossos alunos? 📚",
            
            "hosting_details_response": "Informações de infraestrutura são confidenciais. Posso te contar sobre nossa infraestrutura educacional!",
            
            "business_secrets_response": "Informações internas são confidenciais. Posso compartilhar informações públicas sobre o Kumon!",
            
            "security_measures_response": "Não discuto medidas de segurança. Posso falar sobre a segurança do aprendizado no Kumon! 🔒",
            
            "generic_denial": "Não posso fornecer esse tipo de informação. Como posso ajudar com dúvidas sobre o Kumon ou agendamentos? 😊"
        }
    
    def _load_public_information(self) -> Dict[str, Any]:
        """Load information that can be safely shared"""
        
        return {
            "business_hours": "Segunda a Sexta: 08:00 às 18:00",
            "address": "Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras",
            "phone": "51996921999",
            "email": "kumonvilaa@gmail.com",
            "programs": ["Matemática", "Português"],
            "age_range": "A partir de 3 anos",
            "method_benefits": [
                "Desenvolvimento da concentração",
                "Autodisciplina nos estudos", 
                "Raciocínio lógico",
                "Autoconfiança acadêmica"
            ]
        }
    
    def get_disclosure_stats(self, source_identifier: Optional[str] = None) -> Dict[str, Any]:
        """Get information disclosure attempt statistics"""
        
        if source_identifier:
            attempts = self.disclosure_attempts.get(source_identifier, [])
            recent_attempts = [
                attempt for attempt in attempts
                if attempt["timestamp"] > datetime.now() - timedelta(hours=24)
            ]
            
            disclosure_types = {}
            for attempt in attempts:
                dtype = attempt["disclosure_type"]
                disclosure_types[dtype] = disclosure_types.get(dtype, 0) + 1
            
            return {
                "source": source_identifier,
                "total_attempts": len(attempts),
                "recent_attempts": len(recent_attempts),
                "disclosure_types": disclosure_types,
                "first_attempt": attempts[0]["timestamp"] if attempts else None,
                "last_attempt": attempts[-1]["timestamp"] if attempts else None,
                "highest_severity": max((a["severity"] for a in attempts), default=0.0)
            }
        else:
            total_attempts = sum(len(attempts) for attempts in self.disclosure_attempts.values())
            total_sources = len(self.disclosure_attempts)
            
            # Aggregate disclosure types
            all_disclosure_types = {}
            all_severities = []
            
            for attempts in self.disclosure_attempts.values():
                for attempt in attempts:
                    dtype = attempt["disclosure_type"]
                    all_disclosure_types[dtype] = all_disclosure_types.get(dtype, 0) + 1
                    all_severities.append(attempt["severity"])
            
            return {
                "total_attempts": total_attempts,
                "affected_sources": total_sources,
                "patterns_loaded": len(self.sensitive_patterns),
                "disclosure_types": all_disclosure_types,
                "average_severity": sum(all_severities) / len(all_severities) if all_severities else 0.0,
                "max_severity": max(all_severities) if all_severities else 0.0,
                "protection_level": "Military-grade information security"
            }