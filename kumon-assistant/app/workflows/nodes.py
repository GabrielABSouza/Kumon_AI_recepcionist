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
from ..services.langgraph_llm_adapter import KumonLLMService
from ..clients.google_calendar import GoogleCalendarClient
from .states import (
    ConversationState, 
    WorkflowStage, 
    ConversationStep, 
    UserContext
)
from .context_manager import context_manager
# Legacy intelligent_fallback removed - now integrated in threshold handlers
from ..services.business_metrics_service import (
    track_lead, 
    track_qualified_lead, 
    track_scheduled_appointment,
    track_response_time
)


# Initialize LLM with new Production LLM Service
llm = KumonLLMService()

# Initialize calendar client
calendar_client = GoogleCalendarClient()


async def entry_point_node(state: ConversationState) -> ConversationState:
    """
    A simple passthrough node that serves as the graph's entry point
    before intelligent routing.
    """
    app_logger.info(f"Entering workflow for {state['phone_number']}. Routing...")
    return state


async def greeting_node(state: ConversationState) -> ConversationState:
    """
    Handle greeting stage conversations using confidence-based routing.
    
    This node checks the routing action determined by the smart_router.
    - For high-confidence greetings ("proceed"), it uses a static template and skips the LLM.
    - For lower confidence messages, it prepares a prompt for the LLM to handle.
    """
    app_logger.info(f"Processing greeting for {state['phone_number']}")
    start_time = datetime.now()
    
    try:
        # Get the routing action determined by the smart_router in the previous step
        routing_action = state.get("routing_info", {}).get("threshold_action", "enhance_with_llm")
        user_context = state["user_context"]
        phone_number = state["phone_number"]
        prompt_name = "kumon:greeting:unknown" # Default prompt name

        if routing_action == "proceed":
            # FAST PATH: High confidence greeting, skip LLM
            app_logger.info("High confidence greeting. Using static template and skipping LLM.")
            prompt_name = "kumon:greeting:welcome:initial"
            response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
            next_step = ConversationStep.COLLECT_NAME
            
            # Set final response and skip LLM
            updated_state = {
                **state,
                "ai_response": response,
                "skip_llm": True,  # IMPORTANT: Signal to bypass LLM call
                "step": next_step,
                "validation_passed": True,
                "prompt_used": prompt_name,
            }
        
        else:
            # DEFAULT PATH: Low confidence or complex message, use LLM (existing logic)
            app_logger.info(f"Lower confidence action '{routing_action}'. Using LLM-based logic.")
            user_message = state["user_message"].lower().strip()
            step = state["step"]

            # This logic remains for multi-turn greetings after the initial message
            if step == ConversationStep.COLLECT_NAME or not user_context.parent_name:
                # Extract name from user message
                name_match = re.search(r'(?:me chamo|meu nome é|sou|eu sou)\s+([a-záêéôõâîçü\s]+)', user_message, re.IGNORECASE)
                if not name_match:
                    name_match = re.search(r'\b([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*)\b', state["user_message"])
                
                if name_match:
                    user_context.parent_name = name_match.group(1).strip().title()
                    prompt_name = "kumon:greeting:collection:parent_name"
                    response = await prompt_manager.get_prompt(
                        prompt_name, 
                        conversation_state=state,
                        variables={"parent_name": user_context.parent_name}
                    )
                    next_step = ConversationStep.IDENTIFY_INTEREST
                else:
                    prompt_name = "kumon:greeting:error:name_not_found"
                    response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
                    next_step = ConversationStep.COLLECT_NAME
            
            elif step == ConversationStep.IDENTIFY_INTEREST:
                # Determine if it's for child or self
                if any(word in user_message for word in ["filho", "filha", "criança", "child"]):
                    user_context.interest_type = "child"
                    await track_qualified_lead(phone_number, metadata={"interest_type": "child", "parent_name": user_context.parent_name})
                    prompt_name = "kumon:greeting:response:child_interest"
                    next_stage = WorkflowStage.INFORMATION
                    next_step = ConversationStep.PROVIDE_PROGRAM_INFO
                elif any(word in user_message for word in ["eu", "mim", "para mim", "myself", "me"]):
                    user_context.interest_type = "self"
                    await track_qualified_lead(phone_number, metadata={"interest_type": "self", "parent_name": user_context.parent_name})
                    prompt_name = "kumon:greeting:response:self_interest"
                    next_stage = WorkflowStage.INFORMATION  
                    next_step = ConversationStep.PROVIDE_PROGRAM_INFO
                else:
                    prompt_name = "kumon:greeting:clarification:interest_type"
                    response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
                    next_stage = WorkflowStage.GREETING
                    next_step = ConversationStep.IDENTIFY_INTEREST
                    
                if 'prompt_name' in locals() and 'response' not in locals():
                    response = await prompt_manager.get_prompt(
                        prompt_name,
                        conversation_state=state,
                        variables={"parent_name": user_context.parent_name}
                    )
            else:
                # Fallback for any other step within greeting
                prompt_name = "kumon:greeting:clarification:general"
                response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
                next_stage = WorkflowStage.INFORMATION
                next_step = ConversationStep.PROVIDE_PROGRAM_INFO

            # Set prompt for LLM and ensure skip_llm is False
            updated_state = {
                **state,
                "ai_response": response,
                "skip_llm": False,
                "user_context": user_context,
                "validation_passed": True,
                "prompt_used": prompt_name,
            }
            if 'next_stage' in locals():
                updated_state["stage"] = next_stage
            if 'next_step' in locals():
                updated_state["step"] = next_step

        # Track response time
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(response_time_ms, {
            "node": "greeting",
            "step": state["step"].value,
            "phone_number": phone_number[-4:]
        })
            
        return updated_state
        
    except Exception as e:
        app_logger.error(f"Error in greeting_node: {e}", exc_info=True)
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
            response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
        
        # Track response time
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(response_time_ms, {
            "node": "information",
            "prompt_used": prompt_name,
            "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****"
        })
        
        return {
            **state,
            "ai_response": response,
            "user_context": user_context,
            "validation_passed": True,
            "prompt_used": prompt_name,
            "step": ConversationStep.PROVIDE_PROGRAM_INFO
        }
        
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
            response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
            next_step = ConversationStep.COLLECT_PREFERENCES
            
        elif step == ConversationStep.COLLECT_PREFERENCES:
            # Check for weekend requests (not available)
            if any(word in user_message for word in ["sábado", "saturday", "sabado"]):
                prompt_name = "kumon:scheduling:error:saturday_unavailable" 
                response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
                next_step = ConversationStep.COLLECT_PREFERENCES  # Stay in same step
                
            elif any(word in user_message for word in ["domingo", "sunday"]):
                prompt_name = "kumon:scheduling:error:sunday_unavailable"
                response = await prompt_manager.get_prompt(prompt_name, conversation_state=state)
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
        
        return {
            **state,
            "ai_response": response,
            "user_context": user_context,
            "step": next_step if 'next_step' in locals() else step,
            "validation_passed": True,
            "prompt_used": locals().get('prompt_name', 'scheduling_default')
        }
        
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
        # Step 1: Simple confusion analysis (legacy intelligent_fallback replaced)
        confusion_count = state["metrics"].consecutive_confusion
        
        # Step 2: Check if escalation is needed based on simple rules
        should_escalate = confusion_count >= 3 or state.get("requires_human", False)
        
        if should_escalate:
            app_logger.info(f"Escalating to human due to confusion count: {confusion_count}")
            return {
                **state,
                "ai_response": "Vou conectá-lo com nossa equipe para um atendimento personalizado! 📞 WhatsApp: (51) 99692-1999",
                "requires_human": True,
                "stage": WorkflowStage.COMPLETED,
                "step": ConversationStep.CONVERSATION_ENDED,
                "conversation_ended": True,
                "validation_passed": True,
                "prompt_used": "simple_escalation"
            }
        
        # Step 3: Simple recovery response
        metrics = state["metrics"]
        metrics.clarification_attempts += 1
        metrics.consecutive_confusion += 1
        
        # Step 4: Simple fallback response
        updated_state = {
            **state,
            "ai_response": "Desculpe, não consegui entender bem. Pode reformular sua pergunta? 😊",
            "validation_passed": True,
            "prompt_used": "simple_fallback",
            "metrics": metrics
        }
        
        app_logger.info(f"Applied simple fallback recovery")
        
        return updated_state
        
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