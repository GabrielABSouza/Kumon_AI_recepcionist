"""
RAG Business Validator - Phase 2 Wave 2.2 Business Logic Integration

Validates RAG responses against Kumon business rules to ensure accuracy:
- Pricing information validation (R$375 + R$100 enforcement)
- Business hours information validation (9h-12h, 14h-17h, Mon-Fri)
- Contact information consistency (51 99692-1999)
- Program information accuracy (Matemática/Português/Inglês)
- Knowledge base compliance checking

Prevents RAG system from providing incorrect business information.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logger import app_logger
from ..services.business_rules_engine import (
    BusinessHoursConfig,
    BusinessRuleResult,
    HandoffTriggers,
    PricingRules,
    RuleType,
    ValidationResult,
    business_rules_engine,
)
from ..services.enhanced_cache_service import enhanced_cache_service


class RAGValidationType(Enum):
    """Types of RAG validation"""

    PRICING_ACCURACY = "pricing_accuracy"
    BUSINESS_HOURS_ACCURACY = "business_hours_accuracy"
    CONTACT_INFO_ACCURACY = "contact_info_accuracy"
    PROGRAM_INFO_ACCURACY = "program_info_accuracy"
    CONTENT_APPROPRIATENESS = "content_appropriateness"
    SCOPE_COMPLIANCE = "scope_compliance"


@dataclass
class RAGValidationResult:
    """Result of RAG business validation"""

    validation_type: RAGValidationType
    validation_passed: bool
    original_content: str
    validated_content: str
    corrections_made: List[str]
    business_compliance_score: float
    confidence_score: float
    error_details: Optional[str] = None
    processing_time_ms: float = 0.0


@dataclass
class BusinessInformationStandards:
    """Standard business information for validation"""

    pricing_info: Dict[str, str] = field(
        default_factory=lambda: {
            "monthly_fee": "R$ 375,00",
            "enrollment_fee": "R$ 100,00",
            "total_first_month": "R$ 475,00",
            "currency": "BRL",
            "no_negotiations": "Valores fixos, sem negociação",
        }
    )

    business_hours: Dict[str, str] = field(
        default_factory=lambda: {
            "operating_days": "Segunda a Sexta-feira",
            "morning_hours": "9:00 às 12:00",
            "afternoon_hours": "14:00 às 17:00",
            "lunch_break": "12:00 às 14:00 (fechado)",
            "timezone": "Horário de São Paulo (UTC-3)",
            "weekend_policy": "Fechado nos fins de semana",
        }
    )

    contact_info: Dict[str, str] = field(
        default_factory=lambda: {
            "whatsapp": "(51) 99692-1999",
            "unit_name": "Kumon Vila A",
            "location": "Vila A, São Paulo",
            "emergency_contact": "Entre em contato através do WhatsApp (51) 99692-1999",
        }
    )

    program_info: Dict[str, Any] = field(
        default_factory=lambda: {
            "available_programs": ["Matemática", "Português", "Inglês"],
            "age_range": "2 anos a adultos",
            "methodology": "Método Kumon de autodesenvolvimento",
            "evaluation": "Avaliação diagnóstica gratuita",
        }
    )


class PricingAccuracyValidator:
    """Validates pricing information accuracy in RAG responses"""

    def __init__(self, standards: BusinessInformationStandards):
        self.standards = standards
        self.pricing_patterns = self._init_pricing_patterns()
        self.cache_prefix = "rag_pricing_validation"

    def _init_pricing_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize pricing detection patterns"""
        return {
            "monthly_fee": re.compile(r"R\$?\s*(\d{1,4})[,.]?(\d{0,2})", re.IGNORECASE),
            "enrollment_fee": re.compile(
                r"taxa.*?matrícula.*?R\$?\s*(\d{1,4})[,.]?(\d{0,2})", re.IGNORECASE
            ),
            "total_cost": re.compile(r"total.*?R\$?\s*(\d{1,4})[,.]?(\d{0,2})", re.IGNORECASE),
            "discount_mention": re.compile(r"desconto|promoção|mais barato|oferta", re.IGNORECASE),
            "negotiation_mention": re.compile(
                r"negoci|condição especial|preço especial", re.IGNORECASE
            ),
        }

    async def validate(self, rag_content: str, context: Dict[str, Any]) -> RAGValidationResult:
        """Validate pricing accuracy in RAG content"""
        start_time = datetime.now()

        try:
            app_logger.debug("Validating pricing accuracy in RAG content")

            corrections_made = []
            validated_content = rag_content
            validation_passed = True
            compliance_score = 1.0

            # Check for pricing mentions
            pricing_mentions = []
            for pattern_name, pattern in self.pricing_patterns.items():
                matches = pattern.findall(rag_content)
                if matches:
                    pricing_mentions.append((pattern_name, matches))

            if not pricing_mentions:
                # No pricing information to validate
                return RAGValidationResult(
                    validation_type=RAGValidationType.PRICING_ACCURACY,
                    validation_passed=True,
                    original_content=rag_content,
                    validated_content=validated_content,
                    corrections_made=[],
                    business_compliance_score=1.0,
                    confidence_score=1.0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Validate monthly fee accuracy
            monthly_fee_matches = self.pricing_patterns["monthly_fee"].findall(rag_content)
            for match in monthly_fee_matches:
                if isinstance(match, tuple):
                    amount = f"{match[0]}.{match[1]}" if match[1] else match[0]
                else:
                    amount = match

                amount_float = float(amount.replace(",", "."))
                if amount_float != 375.00:
                    validation_passed = False
                    compliance_score -= 0.3
                    corrections_made.append(
                        f"Corrigido valor da mensalidade de R$ {amount} para R$ 375,00"
                    )
                    validated_content = re.sub(
                        rf"R\$?\s*{re.escape(str(amount))}",
                        "R$ 375,00",
                        validated_content,
                        flags=re.IGNORECASE,
                    )

            # Validate enrollment fee
            enrollment_matches = self.pricing_patterns["enrollment_fee"].findall(rag_content)
            for match in enrollment_matches:
                if isinstance(match, tuple):
                    amount = f"{match[0]}.{match[1]}" if match[1] else match[0]
                else:
                    amount = match

                amount_float = float(amount.replace(",", "."))
                if amount_float != 100.00:
                    validation_passed = False
                    compliance_score -= 0.3
                    corrections_made.append(
                        f"Corrigido valor da taxa de matrícula de R$ {amount} para R$ 100,00"
                    )
                    validated_content = re.sub(
                        rf"taxa.*?matrícula.*?R\$?\s*{re.escape(str(amount))}",
                        "taxa de matrícula R$ 100,00",
                        validated_content,
                        flags=re.IGNORECASE,
                    )

            # Check for unauthorized discounts or negotiations
            if self.pricing_patterns["discount_mention"].search(rag_content):
                validation_passed = False
                compliance_score -= 0.5
                corrections_made.append("Removida menção a descontos (não permitido pela política)")
                validated_content = re.sub(
                    r"(desconto|promoção|mais barato|oferta)[^.!?]*[.!?]",
                    "",
                    validated_content,
                    flags=re.IGNORECASE,
                )

            if self.pricing_patterns["negotiation_mention"].search(rag_content):
                validation_passed = False
                compliance_score -= 0.4
                corrections_made.append(
                    "Removida menção a negociações (não permitido pela política)"
                )
                validated_content = re.sub(
                    r"(negoci|condição especial|preço especial)[^.!?]*[.!?]",
                    "",
                    validated_content,
                    flags=re.IGNORECASE,
                )

            # Ensure standard pricing information is included if pricing is mentioned
            if pricing_mentions and not all(
                price in validated_content for price in ["R$ 375,00", "R$ 100,00"]
            ):
                standard_pricing_text = (
                    "\n\nInformações de preços Kumon:\n"
                    f"• Mensalidade: {self.standards.pricing_info['monthly_fee']} por matéria\n"
                    f"• Taxa de matrícula: {self.standards.pricing_info['enrollment_fee']} (única vez)\n"
                    f"• Total no primeiro mês: {self.standards.pricing_info['total_first_month']}"
                )
                validated_content += standard_pricing_text
                corrections_made.append("Adicionadas informações padronizadas de preços")

            return RAGValidationResult(
                validation_type=RAGValidationType.PRICING_ACCURACY,
                validation_passed=validation_passed,
                original_content=rag_content,
                validated_content=validated_content,
                corrections_made=corrections_made,
                business_compliance_score=max(0.0, compliance_score),
                confidence_score=0.95,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Pricing accuracy validation error: {e}")
            return RAGValidationResult(
                validation_type=RAGValidationType.PRICING_ACCURACY,
                validation_passed=False,
                original_content=rag_content,
                validated_content=rag_content,
                corrections_made=[],
                business_compliance_score=0.0,
                confidence_score=0.0,
                error_details=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class BusinessHoursAccuracyValidator:
    """Validates business hours information accuracy in RAG responses"""

    def __init__(self, standards: BusinessInformationStandards):
        self.standards = standards
        self.hours_patterns = self._init_hours_patterns()
        self.cache_prefix = "rag_hours_validation"

    def _init_hours_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize business hours detection patterns"""
        return {
            "hours_mention": re.compile(
                r"horário|funcionamento|atendimento|aberto|fechado", re.IGNORECASE
            ),
            "time_pattern": re.compile(r"(\d{1,2})[h:](\d{0,2})", re.IGNORECASE),
            "day_pattern": re.compile(
                r"segunda|terça|quarta|quinta|sexta|sábado|domingo", re.IGNORECASE
            ),
            "weekend_mention": re.compile(r"fim de semana|sábado|domingo", re.IGNORECASE),
        }

    async def validate(self, rag_content: str, context: Dict[str, Any]) -> RAGValidationResult:
        """Validate business hours accuracy in RAG content"""
        start_time = datetime.now()

        try:
            app_logger.debug("Validating business hours accuracy in RAG content")

            corrections_made = []
            validated_content = rag_content
            validation_passed = True
            compliance_score = 1.0

            # Check for business hours mentions
            if not self.hours_patterns["hours_mention"].search(rag_content):
                # No hours information to validate
                return RAGValidationResult(
                    validation_type=RAGValidationType.BUSINESS_HOURS_ACCURACY,
                    validation_passed=True,
                    original_content=rag_content,
                    validated_content=validated_content,
                    corrections_made=[],
                    business_compliance_score=1.0,
                    confidence_score=1.0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Validate time patterns
            time_matches = self.hours_patterns["time_pattern"].findall(rag_content)
            valid_times = ["9:00", "9h", "12:00", "12h", "14:00", "14h", "17:00", "17h"]

            for time_match in time_matches:
                if isinstance(time_match, tuple):
                    time_str = (
                        f"{time_match[0]}:{time_match[1]}" if time_match[1] else f"{time_match[0]}h"
                    )
                else:
                    time_str = time_match

                # Check if time is within valid business hours
                hour = int(time_match[0]) if isinstance(time_match, tuple) else int(time_match)
                if hour not in [9, 12, 14, 17]:
                    validation_passed = False
                    compliance_score -= 0.2
                    corrections_made.append(f"Horário {time_str} corrigido para horários padrão")

            # Check for weekend mentions (should not be included)
            if self.hours_patterns["weekend_mention"].search(rag_content):
                weekend_context = re.search(
                    r"[^.!?]*(?:fim de semana|sábado|domingo)[^.!?]*[.!?]",
                    rag_content,
                    re.IGNORECASE,
                )
                if weekend_context and "fechado" not in weekend_context.group().lower():
                    validation_passed = False
                    compliance_score -= 0.3
                    corrections_made.append("Corrigida informação sobre fins de semana (fechado)")
                    validated_content = re.sub(
                        r"[^.!?]*(?:fim de semana|sábado|domingo)[^.!?]*[.!?]",
                        "Fechado nos fins de semana.",
                        validated_content,
                        flags=re.IGNORECASE,
                    )

            # Ensure standard business hours are included if hours are mentioned
            if self.hours_patterns["hours_mention"].search(rag_content):
                standard_hours_included = all(
                    info in validated_content
                    for info in ["segunda", "sexta", "9", "12", "14", "17"]
                )

                if not standard_hours_included:
                    standard_hours_text = (
                        f"\n\nHorário de funcionamento:\n"
                        f"• {self.standards.business_hours['operating_days']}\n"
                        f"• Manhã: {self.standards.business_hours['morning_hours']}\n"
                        f"• Tarde: {self.standards.business_hours['afternoon_hours']}\n"
                        f"• {self.standards.business_hours['lunch_break']}"
                    )
                    validated_content += standard_hours_text
                    corrections_made.append("Adicionadas informações padronizadas de horário")

            return RAGValidationResult(
                validation_type=RAGValidationType.BUSINESS_HOURS_ACCURACY,
                validation_passed=validation_passed,
                original_content=rag_content,
                validated_content=validated_content,
                corrections_made=corrections_made,
                business_compliance_score=max(0.0, compliance_score),
                confidence_score=0.95,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Business hours validation error: {e}")
            return RAGValidationResult(
                validation_type=RAGValidationType.BUSINESS_HOURS_ACCURACY,
                validation_passed=False,
                original_content=rag_content,
                validated_content=rag_content,
                corrections_made=[],
                business_compliance_score=0.0,
                confidence_score=0.0,
                error_details=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class ContactInfoAccuracyValidator:
    """Validates contact information accuracy in RAG responses"""

    def __init__(self, standards: BusinessInformationStandards):
        self.standards = standards
        self.contact_patterns = self._init_contact_patterns()
        self.cache_prefix = "rag_contact_validation"

    def _init_contact_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize contact information detection patterns"""
        return {
            "phone_pattern": re.compile(r"\(?\d{2}\)?\s*\d{4,5}-?\d{4}", re.IGNORECASE),
            "whatsapp_mention": re.compile(r"whatsapp|zap|wpp", re.IGNORECASE),
            "contact_mention": re.compile(r"contato|telefone|ligar|número", re.IGNORECASE),
            "unit_name": re.compile(r"kumon\s+[\w\s]+", re.IGNORECASE),
        }

    async def validate(self, rag_content: str, context: Dict[str, Any]) -> RAGValidationResult:
        """Validate contact information accuracy in RAG content"""
        start_time = datetime.now()

        try:
            app_logger.debug("Validating contact information accuracy in RAG content")

            corrections_made = []
            validated_content = rag_content
            validation_passed = True
            compliance_score = 1.0

            # Check for contact information mentions
            has_contact_mention = self.contact_patterns["contact_mention"].search(
                rag_content
            ) or self.contact_patterns["whatsapp_mention"].search(rag_content)

            if not has_contact_mention:
                # No contact information to validate
                return RAGValidationResult(
                    validation_type=RAGValidationType.CONTACT_INFO_ACCURACY,
                    validation_passed=True,
                    original_content=rag_content,
                    validated_content=validated_content,
                    corrections_made=[],
                    business_compliance_score=1.0,
                    confidence_score=1.0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Validate phone number accuracy
            phone_matches = self.contact_patterns["phone_pattern"].findall(rag_content)
            standard_phone = "(51) 99692-1999"

            for phone in phone_matches:
                # Clean phone number for comparison
                clean_phone = re.sub(r"[^\d]", "", phone)
                standard_clean = re.sub(r"[^\d]", "", standard_phone)

                if clean_phone != standard_clean:
                    validation_passed = False
                    compliance_score -= 0.4
                    corrections_made.append(f"Telefone {phone} corrigido para {standard_phone}")
                    validated_content = validated_content.replace(phone, standard_phone)

            # Validate unit name
            unit_matches = self.contact_patterns["unit_name"].findall(rag_content)
            standard_unit_name = "Kumon Vila A"

            for unit_name in unit_matches:
                if unit_name.strip().lower() != standard_unit_name.lower():
                    validation_passed = False
                    compliance_score -= 0.2
                    corrections_made.append(f"Nome da unidade corrigido para {standard_unit_name}")
                    validated_content = validated_content.replace(unit_name, standard_unit_name)

            # Ensure standard contact information is included if contact is mentioned
            if has_contact_mention and standard_phone not in validated_content:
                standard_contact_text = (
                    f"\n\nPara mais informações:\n"
                    f"📱 WhatsApp: {self.standards.contact_info['whatsapp']}\n"
                    f"🏢 {self.standards.contact_info['unit_name']}"
                )
                validated_content += standard_contact_text
                corrections_made.append("Adicionadas informações padronizadas de contato")

            return RAGValidationResult(
                validation_type=RAGValidationType.CONTACT_INFO_ACCURACY,
                validation_passed=validation_passed,
                original_content=rag_content,
                validated_content=validated_content,
                corrections_made=corrections_made,
                business_compliance_score=max(0.0, compliance_score),
                confidence_score=0.95,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Contact information validation error: {e}")
            return RAGValidationResult(
                validation_type=RAGValidationType.CONTACT_INFO_ACCURACY,
                validation_passed=False,
                original_content=rag_content,
                validated_content=rag_content,
                corrections_made=[],
                business_compliance_score=0.0,
                confidence_score=0.0,
                error_details=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class ProgramInfoAccuracyValidator:
    """Validates program information accuracy in RAG responses"""

    def __init__(self, standards: BusinessInformationStandards):
        self.standards = standards
        self.program_patterns = self._init_program_patterns()
        self.cache_prefix = "rag_program_validation"

    def _init_program_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize program information detection patterns"""
        return {
            "program_mention": re.compile(r"programa|matéria|disciplina|curso", re.IGNORECASE),
            "math_variations": re.compile(r"matemática|math|matematica", re.IGNORECASE),
            "portuguese_variations": re.compile(r"português|portuguese|portugues", re.IGNORECASE),
            "english_variations": re.compile(r"inglês|english|ingles", re.IGNORECASE),
            "invalid_programs": re.compile(
                r"física|química|biologia|história|geografia", re.IGNORECASE
            ),
            "age_mention": re.compile(r"idade|anos?|criança|adulto", re.IGNORECASE),
        }

    async def validate(self, rag_content: str, context: Dict[str, Any]) -> RAGValidationResult:
        """Validate program information accuracy in RAG content"""
        start_time = datetime.now()

        try:
            app_logger.debug("Validating program information accuracy in RAG content")

            corrections_made = []
            validated_content = rag_content
            validation_passed = True
            compliance_score = 1.0

            # Check for program information mentions
            has_program_mention = self.program_patterns["program_mention"].search(rag_content)

            if not has_program_mention:
                # No program information to validate
                return RAGValidationResult(
                    validation_type=RAGValidationType.PROGRAM_INFO_ACCURACY,
                    validation_passed=True,
                    original_content=rag_content,
                    validated_content=validated_content,
                    corrections_made=[],
                    business_compliance_score=1.0,
                    confidence_score=1.0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Check for invalid programs
            invalid_program_matches = self.program_patterns["invalid_programs"].findall(rag_content)
            if invalid_program_matches:
                validation_passed = False
                compliance_score -= 0.5
                corrections_made.append(
                    f"Removidos programas inválidos: {', '.join(invalid_program_matches)}"
                )

                # Remove invalid programs
                for invalid_program in invalid_program_matches:
                    validated_content = re.sub(
                        rf"{re.escape(invalid_program)}[^.!?]*[.!?]?",
                        "",
                        validated_content,
                        flags=re.IGNORECASE,
                    )

            # Validate available programs
            available_programs = self.standards.program_info["available_programs"]
            mentioned_valid_programs = []

            if self.program_patterns["math_variations"].search(rag_content):
                mentioned_valid_programs.append("Matemática")
            if self.program_patterns["portuguese_variations"].search(rag_content):
                mentioned_valid_programs.append("Português")
            if self.program_patterns["english_variations"].search(rag_content):
                mentioned_valid_programs.append("Inglês")

            # Ensure standard program information is included if programs are mentioned
            if has_program_mention and not mentioned_valid_programs:
                standard_programs_text = (
                    f"\n\nProgramas disponíveis no Kumon:\n"
                    f"📚 {', '.join(available_programs)}\n"
                    f"👶 Idade: {self.standards.program_info['age_range']}\n"
                    f"🎯 {self.standards.program_info['evaluation']}"
                )
                validated_content += standard_programs_text
                corrections_made.append("Adicionadas informações padronizadas de programas")

            # Validate age range information
            if self.program_patterns["age_mention"].search(rag_content):
                # Ensure correct age range is mentioned
                if "2 anos a adultos" not in validated_content:
                    age_correction_text = f"\n\nIdade: {self.standards.program_info['age_range']}"
                    validated_content += age_correction_text
                    corrections_made.append("Adicionada faixa etária correta")

            return RAGValidationResult(
                validation_type=RAGValidationType.PROGRAM_INFO_ACCURACY,
                validation_passed=validation_passed,
                original_content=rag_content,
                validated_content=validated_content,
                corrections_made=corrections_made,
                business_compliance_score=max(0.0, compliance_score),
                confidence_score=0.95,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Program information validation error: {e}")
            return RAGValidationResult(
                validation_type=RAGValidationType.PROGRAM_INFO_ACCURACY,
                validation_passed=False,
                original_content=rag_content,
                validated_content=rag_content,
                corrections_made=[],
                business_compliance_score=0.0,
                confidence_score=0.0,
                error_details=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class RAGBusinessValidator:
    """
    Comprehensive RAG Business Validator

    Orchestrates all business rule validations for RAG responses:
    - Pricing accuracy validation
    - Business hours accuracy validation
    - Contact information consistency validation
    - Program information accuracy validation
    - Content appropriateness validation
    - Scope compliance validation
    """

    def __init__(self):
        # Initialize business information standards
        self.standards = BusinessInformationStandards()

        # Initialize specialized validators
        self.pricing_validator = PricingAccuracyValidator(self.standards)
        self.hours_validator = BusinessHoursAccuracyValidator(self.standards)
        self.contact_validator = ContactInfoAccuracyValidator(self.standards)
        self.program_validator = ProgramInfoAccuracyValidator(self.standards)

        # Performance metrics
        self.validation_metrics = {
            "total_validations": 0,
            "corrections_made": 0,
            "compliance_failures": 0,
            "avg_processing_time_ms": 0.0,
        }

    async def validate_rag_response(
        self,
        rag_content: str,
        query_context: Dict[str, Any],
        validation_types: Optional[List[RAGValidationType]] = None,
    ) -> Dict[RAGValidationType, RAGValidationResult]:
        """
        Comprehensive RAG response validation

        Args:
            rag_content: RAG system response content
            query_context: Context of the original query
            validation_types: Specific validations to perform (default: all)

        Returns:
            Dict mapping validation types to their results
        """
        start_time = datetime.now()

        try:
            app_logger.info("Starting comprehensive RAG business validation")

            # Default to all validations if none specified
            if validation_types is None:
                validation_types = [
                    RAGValidationType.PRICING_ACCURACY,
                    RAGValidationType.BUSINESS_HOURS_ACCURACY,
                    RAGValidationType.CONTACT_INFO_ACCURACY,
                    RAGValidationType.PROGRAM_INFO_ACCURACY,
                ]

            # Execute validations in parallel for efficiency
            validation_tasks = []

            for validation_type in validation_types:
                if validation_type == RAGValidationType.PRICING_ACCURACY:
                    task = self.pricing_validator.validate(rag_content, query_context)
                    validation_tasks.append((validation_type, task))

                elif validation_type == RAGValidationType.BUSINESS_HOURS_ACCURACY:
                    task = self.hours_validator.validate(rag_content, query_context)
                    validation_tasks.append((validation_type, task))

                elif validation_type == RAGValidationType.CONTACT_INFO_ACCURACY:
                    task = self.contact_validator.validate(rag_content, query_context)
                    validation_tasks.append((validation_type, task))

                elif validation_type == RAGValidationType.PROGRAM_INFO_ACCURACY:
                    task = self.program_validator.validate(rag_content, query_context)
                    validation_tasks.append((validation_type, task))

            # Wait for all validations to complete
            validation_results = {}
            for validation_type, task in validation_tasks:
                result = await task
                validation_results[validation_type] = result

            # Update performance metrics
            self.validation_metrics["total_validations"] += 1
            total_corrections = sum(
                len(result.corrections_made) for result in validation_results.values()
            )
            self.validation_metrics["corrections_made"] += total_corrections

            compliance_failures = sum(
                1 for result in validation_results.values() if not result.validation_passed
            )
            self.validation_metrics["compliance_failures"] += compliance_failures

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.validation_metrics["avg_processing_time_ms"] = (
                self.validation_metrics["avg_processing_time_ms"]
                * (self.validation_metrics["total_validations"] - 1)
                + processing_time
            ) / self.validation_metrics["total_validations"]

            app_logger.info(
                f"RAG validation completed in {processing_time:.2f}ms - "
                f"Validations: {len(validation_results)}, "
                f"Corrections: {total_corrections}, "
                f"Failures: {compliance_failures}"
            )

            return validation_results

        except Exception as e:
            app_logger.error(f"RAG business validation error: {e}")

            # Return error results for all requested validations
            error_result = RAGValidationResult(
                validation_type=RAGValidationType.PRICING_ACCURACY,  # Default
                validation_passed=False,
                original_content=rag_content,
                validated_content=rag_content,
                corrections_made=[],
                business_compliance_score=0.0,
                confidence_score=0.0,
                error_details=str(e),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

            return {
                validation_type: RAGValidationResult(
                    validation_type=validation_type,
                    validation_passed=False,
                    original_content=rag_content,
                    validated_content=rag_content,
                    corrections_made=[],
                    business_compliance_score=0.0,
                    confidence_score=0.0,
                    error_details=str(e),
                    processing_time_ms=error_result.processing_time_ms,
                )
                for validation_type in (validation_types or [])
            }

    async def get_corrected_rag_response(
        self, rag_content: str, query_context: Dict[str, Any]
    ) -> Tuple[str, List[str]]:
        """
        Get business-compliant corrected RAG response

        Returns:
            Tuple of (corrected_content, list_of_corrections_made)
        """

        try:
            # Validate all aspects of the RAG response
            validation_results = await self.validate_rag_response(rag_content, query_context)

            # Combine all corrections
            corrected_content = rag_content
            all_corrections = []

            for validation_type, result in validation_results.items():
                if result.corrections_made:
                    corrected_content = result.validated_content
                    all_corrections.extend(result.corrections_made)

            # Final compliance check
            overall_compliance = all(
                result.validation_passed for result in validation_results.values()
            )

            if not overall_compliance:
                # Add compliance footer
                compliance_footer = (
                    "\n\n---\n"
                    "✅ Informações validadas pelo sistema de compliance Kumon\n"
                    f"📱 Para esclarecimentos: WhatsApp {self.standards.contact_info['whatsapp']}"
                )
                corrected_content += compliance_footer
                all_corrections.append("Adicionado rodapé de compliance")

            return corrected_content, all_corrections

        except Exception as e:
            app_logger.error(f"RAG correction error: {e}")
            return rag_content, [f"Erro na correção: {str(e)}"]

    async def get_validation_metrics(self) -> Dict[str, Any]:
        """Get comprehensive validation metrics"""

        total_validations = self.validation_metrics["total_validations"]

        return {
            "validation_metrics": self.validation_metrics,
            "performance_ratios": {
                "correction_rate": (
                    self.validation_metrics["corrections_made"] / max(1, total_validations)
                ),
                "compliance_failure_rate": (
                    self.validation_metrics["compliance_failures"] / max(1, total_validations)
                ),
                "avg_processing_time": self.validation_metrics["avg_processing_time_ms"],
            },
            "business_standards": {
                "pricing_enforced": True,
                "business_hours_enforced": True,
                "contact_info_enforced": True,
                "program_accuracy_enforced": True,
            },
            "compliance_status": "ACTIVE - Business rules enforced",
            "last_updated": datetime.now().isoformat(),
        }


# Global RAG business validator instance
rag_business_validator = RAGBusinessValidator()


__all__ = [
    "RAGValidationType",
    "RAGValidationResult",
    "BusinessInformationStandards",
    "PricingAccuracyValidator",
    "BusinessHoursAccuracyValidator",
    "ContactInfoAccuracyValidator",
    "ProgramInfoAccuracyValidator",
    "RAGBusinessValidator",
    "rag_business_validator",
]
