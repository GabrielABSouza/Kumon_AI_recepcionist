"""
LangGraph Workflow Nodes for Kumon Assistant

This module contains specialized nodes for each stage of the conversation workflow.
Each node handles specific aspects of the conversation and integrates with LangSmith
for prompt management and response generation.
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from langchain.schema import BaseMessage, HumanMessage, SystemMessage

from ..core.config import settings
from ..core.logger import app_logger
from ..prompts.manager import prompt_manager
from ..core.service_factory import get_langchain_rag_service
from ..services.langgraph_llm_adapter import langgraph_llm_adapter, kumon_llm_service
from ..clients.google_calendar import GoogleCalendarClient
from .states import (
    ConversationState, 
    WorkflowStage, 
    ConversationStep, 
    UserContext,
    update_state_metrics
)
from .context_manager import context_manager
from .intelligent_fallback import intelligent_fallback
from ..services.business_metrics_service import (
    track_lead, 
    track_qualified_lead, 
    track_scheduled_appointment,
    track_response_time
)


# Initialize LLM with new Production LLM Service
llm = langgraph_llm_adapter

# Initialize calendar client
calendar_client = GoogleCalendarClient()


async def greeting_node(state: ConversationState) -> ConversationState:
    """
    Handle greeting stage conversations
    
    This node manages the initial welcome, name collection, and interest identification.
    It uses LangSmith prompts with Cecília personality.
    """
    app_logger.info(f"Processing greeting for {state['phone_number']}")
    start_time = datetime.now()
    
    try:
        user_message = state["user_message"].lower().strip()
        user_context = state["user_context"]
        step = state["step"]
        phone_number = state["phone_number"]
        
        # Determine which greeting prompt to use based on conversation step
        if step == ConversationStep.WELCOME and not user_context.parent_name:
            # Initial welcome message - track as new lead
            await track_lead(phone_number, metadata={
                "source": "whatsapp",
                "stage": "welcome",
                "timestamp": start_time.isoformat()
            })
            
            prompt_name = "kumon:greeting:welcome:initial"
            prompt = await prompt_manager.get_prompt(prompt_name)
            
            response = prompt
            next_step = ConversationStep.COLLECT_NAME
            
        elif step == ConversationStep.COLLECT_NAME or not user_context.parent_name:
            # Extract name from user message
            name_match = re.search(r'(?:me chamo|meu nome é|sou|eu sou)\s+([a-záêéôõâîçü\s]+)', user_message, re.IGNORECASE)
            if not name_match:
                # Try simpler patterns
                name_match = re.search(r'\b([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*)\b', state["user_message"])
            
            if name_match:
                user_context.parent_name = name_match.group(1).strip().title()
                
                # Ask about interest type
                prompt_name = "kumon:greeting:collection:parent_name"
                prompt = await prompt_manager.get_prompt(
                    prompt_name, 
                    variables={"parent_name": user_context.parent_name}
                )
                response = prompt
                next_step = ConversationStep.IDENTIFY_INTEREST
            else:
                # Ask for name again
                response = "Desculpe, não consegui entender seu nome. Pode me dizer novamente? 😊"
                next_step = ConversationStep.COLLECT_NAME
                
        elif step == ConversationStep.IDENTIFY_INTEREST:
            # Determine if it's for child or self
            if any(word in user_message for word in ["filho", "filha", "criança", "child"]):
                user_context.interest_type = "child"
                # Track as qualified lead - they showed specific interest
                await track_qualified_lead(phone_number, metadata={
                    "interest_type": "child",
                    "parent_name": user_context.parent_name,
                    "stage": "interest_identification"
                })
                prompt_name = "kumon:greeting:response:child_interest"
                next_stage = WorkflowStage.INFORMATION
                next_step = ConversationStep.PROVIDE_PROGRAM_INFO
            elif any(word in user_message for word in ["eu", "mim", "para mim", "myself", "me"]):
                user_context.interest_type = "self"
                # Track as qualified lead - they showed specific interest
                await track_qualified_lead(phone_number, metadata={
                    "interest_type": "self",
                    "parent_name": user_context.parent_name,
                    "stage": "interest_identification"
                })
                prompt_name = "kumon:greeting:response:self_interest"
                next_stage = WorkflowStage.INFORMATION  
                next_step = ConversationStep.PROVIDE_PROGRAM_INFO
            else:
                # Unclear intent, ask for clarification
                response = "Você está interessado no Kumon para você mesmo ou para seu filho(a)? 🤔"
                next_stage = WorkflowStage.GREETING
                next_step = ConversationStep.IDENTIFY_INTEREST
                
            if 'prompt_name' in locals():
                prompt = await prompt_manager.get_prompt(
                    prompt_name,
                    variables={"parent_name": user_context.parent_name}
                )
                response = prompt
        else:
            # Fallback
            response = "Vamos para a próxima etapa! Como posso ajudá-lo com informações sobre o Kumon? 😊"
            next_stage = WorkflowStage.INFORMATION
            next_step = ConversationStep.PROVIDE_PROGRAM_INFO
        
        # Update state
        updated_state = {
            **state,
            "ai_response": response,
            "user_context": user_context,
            "validation_passed": True,
            "prompt_used": locals().get('prompt_name', 'hardcoded'),
        }
        
        # Update stage/step if needed
        if 'next_stage' in locals():
            updated_state["stage"] = next_stage
        if 'next_step' in locals():
            updated_state["step"] = next_step
        
        # Track response time
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(response_time_ms, {
            "node": "greeting",
            "step": step.value,
            "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****"
        })
            
        return update_state_metrics(updated_state, stage_transition=f"greeting_{step.value}")
        
    except Exception as e:
        app_logger.error(f"Error in greeting_node: {e}")
        return {
            **state,
            "ai_response": "Desculpe, tive um problema técnico. Pode repetir sua mensagem? 😊",
            "last_error": str(e),
            "validation_passed": False
        }


async def information_node(state: ConversationState) -> ConversationState:
    """
    Handle information gathering and program explanation
    
    This node provides details about Kumon programs, methodology, and pricing
    using LangSmith prompts with educational focus.
    """
    app_logger.info(f"Processing information request for {state['phone_number']}")
    start_time = datetime.now()
    
    try:
        user_message = state["user_message"].lower().strip()
        user_context = state["user_context"]
        phone_number = state["phone_number"]
        
        # Detect what information is being requested
        if any(word in user_message for word in ["matemática", "math", "cálculo", "número"]):
            prompt_name = "kumon:information:response:program_mathematics"
            user_context.programs_interested.append("matemática")
            
        elif any(word in user_message for word in ["português", "leitura", "escrita", "redação", "port"]):
            prompt_name = "kumon:information:response:program_portuguese"
            user_context.programs_interested.append("português")
            
        elif any(word in user_message for word in ["preço", "valor", "custa", "quanto", "investimento", "$", "r$"]):
            prompt_name = "kumon:information:response:pricing"
            
        elif any(word in user_message for word in ["agendar", "visita", "conhecer", "apresentação", "appointment"]):
            # User wants to schedule - track transition to scheduling
            await track_qualified_lead(phone_number, metadata={
                "transition": "information_to_scheduling",
                "intent": "direct_booking_request",
                "programs_discussed": user_context.programs_interested
            })
            
            return {
                **state,
                "stage": WorkflowStage.SCHEDULING,
                "step": ConversationStep.SUGGEST_APPOINTMENT,
                "next_action": "schedule_appointment",
                "user_context": user_context
            }
            
        else:
            # Use RAG to answer general questions
            try:
                langchain_rag_service = await get_langchain_rag_service()
                rag_result = await langchain_rag_service.query(
                    question=state["user_message"],
                    search_kwargs={"score_threshold": 0.6},
                    include_sources=False
                )
                response = rag_result.answer
                prompt_name = "rag_response"
                
            except Exception as e:
                app_logger.error(f"RAG query failed: {e}")
                # Fallback to general information
                response = """Posso te ajudar com informações sobre:

🔢 **Programa de Matemática**: Desenvolvemos cálculo mental e raciocínio lógico
📖 **Programa de Português**: Focamos em leitura, interpretação e produção textual  
💰 **Valores e investimento**: Informações sobre mensalidades
📅 **Agendamento**: Marcar uma apresentação na unidade

Sobre qual tema você gostaria de saber mais? 😊"""
                prompt_name = "information_menu"
        
        # Get response from LangSmith if prompt_name was set
        if 'prompt_name' in locals() and prompt_name != "rag_response" and prompt_name != "information_menu":
            response = await prompt_manager.get_prompt(prompt_name)
        
        # Track response time
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(response_time_ms, {
            "node": "information",
            "prompt_used": prompt_name,
            "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****"
        })
        
        return update_state_metrics({
            **state,
            "ai_response": response,
            "user_context": user_context,
            "validation_passed": True,
            "prompt_used": prompt_name,
            "step": ConversationStep.PROVIDE_PROGRAM_INFO
        }, stage_transition="information_provided")
        
    except Exception as e:
        app_logger.error(f"Error in information_node: {e}")
        return {
            **state,
            "ai_response": "Desculpe, tive dificuldade em processar sua pergunta. Pode reformular? 😊",
            "last_error": str(e),
            "validation_passed": False
        }


async def scheduling_node(state: ConversationState) -> ConversationState:
    """
    Handle appointment scheduling workflow
    
    This node manages the complete booking process, from initial suggestion
    to final confirmation with calendar integration.
    """
    app_logger.info(f"Processing scheduling for {state['phone_number']}")
    start_time = datetime.now()
    
    try:
        user_message = state["user_message"].lower().strip()
        user_context = state["user_context"]
        step = state["step"]
        phone_number = state["phone_number"]
        
        if step == ConversationStep.SUGGEST_APPOINTMENT:
            # Initial scheduling suggestion
            prompt_name = "kumon:scheduling:welcome:direct_booking"
            response = await prompt_manager.get_prompt(prompt_name)
            next_step = ConversationStep.COLLECT_PREFERENCES
            
        elif step == ConversationStep.COLLECT_PREFERENCES:
            # Check for weekend requests (not available)
            if any(word in user_message for word in ["sábado", "saturday", "sabado"]):
                prompt_name = "kumon:scheduling:error:saturday_unavailable" 
                response = await prompt_manager.get_prompt(prompt_name)
                next_step = ConversationStep.COLLECT_PREFERENCES  # Stay in same step
                
            elif any(word in user_message for word in ["domingo", "sunday"]):
                prompt_name = "kumon:scheduling:error:sunday_unavailable"
                response = await prompt_manager.get_prompt(prompt_name)
                next_step = ConversationStep.COLLECT_PREFERENCES  # Stay in same step
                
            else:
                # Extract time preferences
                if any(word in user_message for word in ["manhã", "morning", "manha"]):
                    user_context.preferred_time = "manhã"
                elif any(word in user_message for word in ["tarde", "afternoon"]):
                    user_context.preferred_time = "tarde"
                
                # Check if we have enough info to book
                if user_context.preferred_time and user_context.parent_name:
                    if not user_context.email:
                        response = f"Perfeito! Agora preciso do seu email para enviar a confirmação do agendamento. 📧"
                        next_step = ConversationStep.COLLECT_PREFERENCES
                    else:
                        # Track scheduled appointment
                        await track_scheduled_appointment(phone_number, metadata={
                            "parent_name": user_context.parent_name,
                            "preferred_time": user_context.preferred_time,
                            "interest_type": user_context.interest_type,
                            "programs_interested": user_context.programs_interested
                        })
                        next_step = ConversationStep.CONFIRM_BOOKING
                else:
                    response = "Para qual período você prefere? Manhã ou tarde? 🕐"
                    next_step = ConversationStep.COLLECT_PREFERENCES
                    
        elif step == ConversationStep.CONFIRM_BOOKING:
            # Final booking confirmation
            try:
                # Generate booking ID
                booking_id = f"KUMON_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                user_context.booking_id = booking_id
                
                # Create calendar event (simplified)
                # In production, this would integrate with Google Calendar
                selected_time = f"Próxima disponibilidade na {user_context.preferred_time}"
                
                prompt_name = "kumon:scheduling:confirmation:booking_success"
                response = await prompt_manager.get_prompt(
                    prompt_name,
                    variables={
                        "selected_time": selected_time,
                        "email": user_context.email or "email_coletado",
                        "booking_id": booking_id
                    }
                )
                
                # Mark conversation as completed
                return {
                    **state,
                    "ai_response": response,
                    "user_context": user_context,
                    "stage": WorkflowStage.COMPLETED,
                    "step": ConversationStep.CONVERSATION_ENDED,
                    "conversation_ended": True,
                    "validation_passed": True,
                    "prompt_used": prompt_name
                }
                
            except Exception as e:
                app_logger.error(f"Booking confirmation failed: {e}")
                response = "Tive um problema ao confirmar o agendamento. Vou conectá-lo com nossa equipe!"
                next_step = ConversationStep.CONFIRM_BOOKING
        
        # Default response handling
        if 'response' not in locals():
            response = "Vamos agendar sua visita! Em que período você prefere: manhã ou tarde? 🕐"
            next_step = ConversationStep.COLLECT_PREFERENCES
        
        # Track response time
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(response_time_ms, {
            "node": "scheduling",
            "step": step.value,
            "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****"
        })
        
        return update_state_metrics({
            **state,
            "ai_response": response,
            "user_context": user_context,
            "step": next_step if 'next_step' in locals() else step,
            "validation_passed": True,
            "prompt_used": locals().get('prompt_name', 'scheduling_default')
        }, stage_transition=f"scheduling_{step.value}")
        
    except Exception as e:
        app_logger.error(f"Error in scheduling_node: {e}")
        return {
            **state,
            "ai_response": "Tive dificuldades com o agendamento. Vou conectá-lo com nossa equipe! 📞",
            "last_error": str(e),
            "requires_human": True,
            "validation_passed": False
        }


async def fallback_node(state: ConversationState) -> ConversationState:
    """
    Phase 4: Enhanced fallback with intelligent confusion analysis and recovery
    
    This node uses advanced confusion classification and recovery strategies
    to provide more effective fallback handling and escalation decisions.
    """
    app_logger.info(f"Processing intelligent fallback for {state['phone_number']}")
    
    try:
        # Step 1: Analyze confusion type and severity
        confusion_analysis = await intelligent_fallback.analyze_confusion(state)
        
        # Step 2: Check if escalation is needed
        escalation_decision = await intelligent_fallback.should_escalate_to_human(
            state, confusion_analysis
        )
        
        if escalation_decision.should_escalate:
            app_logger.info(f"Escalating to human: {escalation_decision.reasoning}")
            return {
                **state,
                "ai_response": escalation_decision.escalation_message,
                "requires_human": True,
                "stage": WorkflowStage.COMPLETED,
                "step": ConversationStep.CONVERSATION_ENDED,
                "conversation_ended": True,
                "validation_passed": True,
                "prompt_used": "intelligent_escalation",
                "escalation_info": {
                    "triggers": [t.value for t in escalation_decision.triggers],
                    "confidence": escalation_decision.confidence,
                    "urgency": escalation_decision.urgency_level
                }
            }
        
        # Step 3: Determine recovery action
        recovery_action = await intelligent_fallback.determine_recovery_action(
            confusion_analysis, state
        )
        
        # Step 4: Update metrics with intelligent feedback
        metrics = state["metrics"]
        metrics.clarification_attempts += 1
        if confusion_analysis.is_recurring:
            metrics.consecutive_confusion += 1
        
        # Step 5: Apply recovery action
        updated_state = {
            **state,
            "ai_response": recovery_action.response,
            "step": recovery_action.next_step,
            "validation_passed": True,
            "prompt_used": "intelligent_recovery",
            "metrics": metrics,
            "confusion_info": {
                "type": confusion_analysis.confusion_type.value,
                "confidence": confusion_analysis.confidence,
                "severity": confusion_analysis.severity,
                "is_recurring": confusion_analysis.is_recurring,
                "strategy": recovery_action.strategy.value,
                "reasoning": recovery_action.reasoning
            }
        }
        
        # Step 6: Reset context if required
        if recovery_action.requires_context_reset:
            # Clear confusion history for fresh start
            updated_state["metrics"].consecutive_confusion = 0
            if recovery_action.strategy.value == "restart":
                updated_state["stage"] = WorkflowStage.GREETING
                updated_state["step"] = ConversationStep.WELCOME
        
        app_logger.info(f"Applied recovery strategy: {recovery_action.strategy.value} "
                       f"for confusion: {confusion_analysis.confusion_type.value}")
        
        return update_state_metrics(updated_state, intelligent_recovery=True)
        
    except Exception as e:
        app_logger.error(f"Error in intelligent fallback_node: {e}")
        # Fallback to simple response
        return {
            **state,
            "ai_response": "Vou conectá-lo com nossa equipe para um atendimento personalizado! 📞 WhatsApp: (51) 99692-1999",
            "requires_human": True,
            "last_error": str(e),
            "validation_passed": False
        }