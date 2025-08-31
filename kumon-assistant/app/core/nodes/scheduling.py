from typing import Dict, Any, List
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field, increment_metric
from ..state.managers import StateManager
from ...clients.google_calendar import GoogleCalendarClient  # Real Google Calendar integration
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SchedulingNode:
    """
    Node de agendamento completo
    Coleta preferências e agenda no Google Calendar
    """
    
    def __init__(self):
        # Real Google Calendar integration
        try:
            self.calendar_service = GoogleCalendarClient()
            logger.info("Google Calendar service initialized successfully")
        except Exception as e:
            logger.warning(f"Google Calendar service failed to initialize: {e}")
            self.calendar_service = None
        
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Processa agendamento"""
        logger.info(f"Processing scheduling for {state['phone_number']} - step: {state['current_step']}")
        
        user_message = state["last_user_message"]
        current_step = state["current_step"]
        
        # ========== DATE_PREFERENCE - Escolher período ==========
        if current_step == ConversationStep.DATE_PREFERENCE:
            return await self._handle_date_preference(state, user_message)
        
        # ========== TIME_SELECTION - Horários específicos ==========
        elif current_step == ConversationStep.TIME_SELECTION:
            return await self._handle_time_selection(state, user_message)
        
        # ========== EMAIL_COLLECTION - Coletar email ==========
        elif current_step == ConversationStep.EMAIL_COLLECTION:
            return await self._handle_email_collection(state, user_message)
        
        # ========== EVENT_CREATION - Finalizar agendamento ==========
        elif current_step == ConversationStep.EVENT_CREATION:
            return await self._handle_event_creation(state, user_message)
        
        # Default - início do agendamento
        else:
            return await self._start_scheduling(state)
    
    async def _start_scheduling(self, state: CeciliaState) -> Dict[str, Any]:
        """Inicia processo de agendamento"""
        parent_name = get_collected_field(state, "parent_name") or ""
        child_name = get_collected_field(state, "child_name") or ""
        is_for_self = get_collected_field(state, "is_for_self") or False
        
        student_ref = "você" if is_for_self else child_name
        
        response = (
            f"Perfeito, {parent_name}! Vamos agendar a apresentação para {student_ref}! 📅\n\n"
            "Durante a visita você poderá:\n"
            "• 📚 Conhecer nossa metodologia na prática\n"
            "• 📝 Fazer uma avaliação diagnóstica gratuita\n"
            "• 👩‍🏫 Conversar com nossa orientadora educacional\n"
            "• 📋 Ver nossos materiais didáticos exclusivos\n\n"
            "Qual período é melhor para você?\n\n"
            "**🌅 MANHÃ** (9h às 12h)\n"
            "**🌆 TARDE** (14h às 17h)\n\n"
            "Digite **MANHÃ** ou **TARDE** 😊"
        )
        
        updates = {
            "current_step": ConversationStep.DATE_PREFERENCE
        }
        
        return self._create_response(state, response, updates)
    
    async def _handle_date_preference(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Processa preferência de período"""
        message_lower = user_message.lower().strip()
        
        # Saturday scheduling restriction (Legacy analysis requirement)
        if any(word in message_lower for word in ['sábado', 'sabado', 'saturday']):
            # Verificar se SmartRouter permite uso de templates
            routing_info = state.get("routing_info", {})
            threshold_action = routing_info.get("threshold_action", "fallback_level1")
            
            if threshold_action in ["proceed", "enhance_with_llm"]:
                try:
                    response = await prompt_manager.get_prompt(
                        name="kumon:scheduling:restriction:saturday_unavailable",
                        variables={},
                        conversation_state=state
                    )
                    logger.info(f"✅ Using PromptManager for saturday_restriction (threshold_action={threshold_action})")
                except Exception as e:
                    logger.warning(f"⚠️ PromptManager failed for scheduling:saturday_restriction, using fallback: {e}")
                    response = self._get_hardcoded_saturday_restriction()
            else:
                logger.info(f"⚡ Using hardcoded response (threshold_action={threshold_action})")
                response = self._get_hardcoded_saturday_restriction()
            updates = {}
            return self._create_response(state, response, updates)
        
        # Detectar preferência
        if any(word in message_lower for word in ['manhã', 'manha', 'morning', '9', '10', '11']):
            preference = "manhã"
            time_options = [
                {"time": "09:00", "display": "9h00", "available": True},
                {"time": "09:30", "display": "9h30", "available": True},
                {"time": "10:00", "display": "10h00", "available": True},
                {"time": "10:30", "display": "10h30", "available": True},
                {"time": "11:00", "display": "11h00", "available": True},
                {"time": "11:30", "display": "11h30", "available": True}
            ]
        elif any(word in message_lower for word in ['tarde', 'afternoon', '14', '15', '16', '17']):
            preference = "tarde"
            time_options = [
                {"time": "14:00", "display": "14h00", "available": True},
                {"time": "14:30", "display": "14h30", "available": True},
                {"time": "15:00", "display": "15h00", "available": True},
                {"time": "15:30", "display": "15h30", "available": True},
                {"time": "16:00", "display": "16h00", "available": True},
                {"time": "16:30", "display": "16h30", "available": True},
                {"time": "17:00", "display": "17h00", "available": True},
                {"time": "17:30", "display": "17h30", "available": True}
            ]
        else:
            # Não entendeu a preferência
            response = (
                "Poderia escolher entre:\n\n"
                "**🌅 MANHÃ** (9h às 12h) ou\n"
                "**🌆 TARDE** (14h às 17h)?\n\n"
                "Digite simplesmente **MANHÃ** ou **TARDE** 😊"
            )
            updates = {}
            return self._create_response(state, response, updates)
        
        # Gerar horários disponíveis (mock - seria consulta real ao Google Calendar)
        available_dates = self._generate_available_dates(preference, time_options)
        
        # Gerar resposta com opções
        response_lines = [
            f"Ótima escolha! Aqui estão os horários disponíveis para a **{preference.upper()}**: 📅\n"
        ]
        
        for i, slot in enumerate(available_dates[:5], 1):  # Mostrar até 5 opções
            response_lines.append(
                f"**{i}.** {slot['date_formatted']} às {slot['time_formatted']}"
            )
        
        response_lines.append(
            "\nDigite o **número** da opção desejada (exemplo: **1**) 😊"
        )
        
        response = "\n".join(response_lines)
        
        updates = {
            "current_step": ConversationStep.TIME_SELECTION,
            "date_preferences": {
                "preference": preference,
                "available_dates": available_dates[:5]
            }
        }
        
        return self._create_response(state, response, updates)
    
    async def _handle_time_selection(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Processa seleção de horário específico"""
        available_dates = get_collected_field(state, "date_preferences") or {}
        available_dates = available_dates.get("available_dates", [])
        
        # Extrair número da opção
        option_match = re.search(r'\b([1-9])\b', user_message.strip())
        
        if option_match:
            option_number = int(option_match.group(1))
            
            if 1 <= option_number <= len(available_dates):
                selected_slot = available_dates[option_number - 1]
                
                # Verificar se ainda precisa coletar email
                if not get_collected_field(state, "contact_email"):
                    response = (
                        f"Perfeito! Agendamento selecionado:\n\n"
                        f"📅 **{selected_slot['date_formatted']}**\n"
                        f"🕐 **{selected_slot['time_formatted']}**\n\n"
                        "Para confirmar, preciso do seu **email** para enviar os detalhes da visita.\n\n"
                        "Qual é o seu email? 📧"
                    )
                    
                    updates = {
                        "current_step": ConversationStep.EMAIL_COLLECTION,
                        "selected_slot": selected_slot
                    }
                else:
                    # Já tem email - pode finalizar
                    updates = {
                        "current_step": ConversationStep.EVENT_CREATION,
                        "selected_slot": selected_slot
                    }
                    
                    # Ir direto para criação do evento
                    return await self._handle_event_creation(state, user_message, updates)
            else:
                response = (
                    f"Por favor, escolha uma opção entre **1** e **{len(available_dates)}** 😊\n\n"
                    "Digite apenas o **número** da opção desejada."
                )
                updates = {}
        else:
            response = (
                "Não consegui identificar sua escolha! 🤔\n\n"
                "Digite apenas o **número** da opção (exemplo: **1**, **2**, **3**...) 😊"
            )
            updates = {}
        
        return self._create_response(state, response, updates)
    
    async def _handle_email_collection(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Coleta e valida email - BUSINESS CRITICAL: Email obrigatório (PROJECT_SCOPE.md)"""
        email = user_message.strip().lower()
        
        # Enhanced email validation pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, email):
            # Email válido - increment success metrics
            increment_metric(state, "successful_email_collections")
            
            # BUSINESS CRITICAL: Store email in collected_data
            set_collected_field(state, "contact_email", email)
            
            # Log email collection for business analytics
            logger.info(f"Email collected successfully: {email} for {state['phone_number']}")
            
            updates = {
                "current_step": ConversationStep.EVENT_CREATION
            }
            
            # Ir para criação do evento
            return await self._handle_event_creation(state, user_message, updates)
        else:
            # Email inválido - increment failure metrics
            increment_metric(state, "failed_email_validations")
            
            failed_attempts = state["conversation_metrics"].get("failed_attempts", 0) + 1
            
            if failed_attempts >= 3:
                # BUSINESS CRITICAL: After 3 failed attempts, require human contact
                response = (
                    "Vejo que está com dificuldades com o email. 🤔\n\n"
                    "Para agilizar seu agendamento, entre em contato diretamente:\n\n"
                    "📞 **WhatsApp**: (51) 99692-1999\n"
                    "📧 **Email**: kumonvilaa@gmail.com\n"
                    "🕐 **Horário**: Segunda a Sexta, 8h às 18h\n\n"
                    "Nossa equipe fará seu agendamento imediatamente! ✨"
                )
                
                updates = {
                    "current_stage": ConversationStage.COMPLETED,
                    "current_step": ConversationStep.CONVERSATION_ENDED
                }
            else:
                response = (
                    "⚠️ **Email inválido!** Por favor, digite um email válido 📧\n\n"
                    "**Formato correto**: seuemail@gmail.com\n"
                    "**Exemplos válidos**:\n"
                    "• maria@gmail.com ✅\n"
                    "• joao.silva@hotmail.com ✅\n"
                    "• contato@empresa.com.br ✅\n\n"
                    "🔒 **O email é OBRIGATÓRIO** para:\n"
                    "• Enviar confirmação do agendamento\n"
                    "• Enviar localização da unidade\n"
                    "• Comunicações importantes\n\n"
                    "Digite novamente seu email 😊"
                )
                
                updates = {
                    "failed_attempts": failed_attempts
                }
            
            return self._create_response(state, response, updates)
    
    async def _handle_event_creation(self, state: CeciliaState, user_message: str, custom_updates: Dict[str, Any] = None) -> Dict[str, Any]:
        """Finaliza agendamento criando evento no Google Calendar"""
        
        # Aplicar updates customizados se fornecidos
        if custom_updates:
            state.update(custom_updates)
        
        selected_slot = get_collected_field(state, "selected_slot") or {}
        parent_name = get_collected_field(state, "parent_name") or ""
        child_name = get_collected_field(state, "child_name") or ""
        child_age = get_collected_field(state, "student_age") or ""
        email = get_collected_field(state, "contact_email") or ""
        phone = state["phone_number"]
        is_for_self = get_collected_field(state, "is_for_self") or False
        
        # Tentar criar evento no Google Calendar (real integration)
        event_created = await self._create_calendar_event(state, selected_slot)
        
        if event_created:
            student_info = f"você ({child_age} anos)" if is_for_self else f"{child_name} ({child_age} anos)"
            
            response = (
                f"🎉 **AGENDAMENTO CONFIRMADO!** 🎉\n\n"
                f"📋 **Detalhes da Visita:**\n"
                f"👤 Responsável: {parent_name}\n"
                f"👶 Aluno(a): {student_info}\n"
                f"📅 Data: {selected_slot['date_formatted']}\n"
                f"🕐 Horário: {selected_slot['time_formatted']}\n"
                f"📧 Email: {email}\n\n"
                f"📍 **Local:** Kumon Vila A\n"
                f"Rua Amoreira, 571 - Salas 6 e 7\n"
                f"Jardim das Laranjeiras\n\n"
                f"📞 **Contato:** (51) 99692-1999\n\n"
                f"✅ Confirmação enviada para seu email!\n"
                f"✅ Lembre-se: chegue 10 minutos antes\n"
                f"✅ Traga um documento de identidade\n\n"
                f"Estamos ansiosos para conhecê-lo! 😊✨"
            )
            
            updates = {
                "current_stage": ConversationStage.COMPLETED,
                "current_step": ConversationStep.APPOINTMENT_CONFIRMED,
                "calendar_event_id": event_created.get("event_id")
            }
        else:
            # Falha na criação do evento
            response = (
                "Ops! Houve um problema ao confirmar seu agendamento. 😔\n\n"
                "Por favor, entre em contato diretamente conosco:\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "Nossos horários: Segunda a Sexta, 8h às 18h\n\n"
                "Pedimos desculpas pelo inconveniente! 🙏"
            )
            
            updates = {
                "current_stage": ConversationStage.COMPLETED,
                "current_step": ConversationStep.CONVERSATION_ENDED
            }
        
        return self._create_response(state, response, updates)
    
    def _generate_available_dates(self, preference: str, time_options: List[Dict]) -> List[Dict]:
        """Gera horários disponíveis (mock - seria consulta real ao Google Calendar)"""
        available_dates = []
        
        # Gerar próximos 5 dias úteis
        current_date = datetime.now()
        dates_added = 0
        
        while dates_added < 5:
            current_date += timedelta(days=1)
            
            # Pular fins de semana
            if current_date.weekday() >= 5:  # 5 = sábado, 6 = domingo
                continue
            
            # Para cada horário disponível no período
            for time_option in time_options:
                if time_option["available"]:
                    slot_datetime = current_date.replace(
                        hour=int(time_option["time"].split(":")[0]),
                        minute=int(time_option["time"].split(":")[1]),
                        second=0,
                        microsecond=0
                    )
                    
                    available_dates.append({
                        "datetime": slot_datetime,
                        "date_formatted": slot_datetime.strftime("%d/%m/%Y (%A)").replace(
                            "Monday", "Segunda-feira"
                        ).replace(
                            "Tuesday", "Terça-feira"
                        ).replace(
                            "Wednesday", "Quarta-feira"
                        ).replace(
                            "Thursday", "Quinta-feira"
                        ).replace(
                            "Friday", "Sexta-feira"
                        ),
                        "time_formatted": time_option["display"],
                        "time": time_option["time"]
                    })
                    
                    dates_added += 1
                    if dates_added >= 5:
                        break
        
        return available_dates
    
    async def _create_calendar_event(self, state: CeciliaState, selected_slot: Dict) -> Dict[str, Any]:
        """Cria evento no Google Calendar (real integration)"""
        
        try:
            if not self.calendar_service:
                logger.error("Google Calendar service not available")
                return None
            
            # Extract event details
            parent_name = get_collected_field(state, "parent_name") or "Cliente"
            child_name = get_collected_field(state, "child_name") or ""
            child_age = get_collected_field(state, "student_age") or ""
            email = get_collected_field(state, "contact_email") or ""
            phone = state["phone_number"]
            is_for_self = get_collected_field(state, "is_for_self") or False
            
            # Create event details
            student_info = f"{parent_name} (estudante)" if is_for_self else f"{child_name} ({child_age} anos)"
            
            event_details = {
                "summary": f"Apresentação Kumon - {student_info}",
                "description": (
                    f"Apresentação Kumon Vila A\n\n"
                    f"Responsável: {parent_name}\n"
                    f"Aluno(a): {student_info}\n"
                    f"WhatsApp: {phone}\n"
                    f"Email: {email}\n\n"
                    f"Atividades:\n"
                    f"• Apresentação da metodologia\n"
                    f"• Avaliação diagnóstica gratuita\n"
                    f"• Conversa com orientadora educacional\n"
                    f"• Demonstração dos materiais didáticos"
                ),
                "start": {
                    "dateTime": selected_slot["datetime"].isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "end": {
                    "dateTime": (selected_slot["datetime"] + timedelta(hours=1)).isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "attendees": [
                    {"email": email, "displayName": parent_name}
                ],
                "location": "Kumon Vila A - Rua Amoreira, 571, Salas 6 e 7, Jardim das Laranjeiras",
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 1440},  # 1 day before
                        {"method": "popup", "minutes": 60}     # 1 hour before
                    ]
                }
            }
            
            # Try to create the event
            event_result = await self.calendar_service.create_event(event_details)
            
            if event_result:
                logger.info(f"Calendar event created successfully: {event_result.get('id')}")
                return {
                    "success": True,
                    "event_id": event_result.get("id"),
                    "event_url": event_result.get("htmlLink"),
                    "calendar_data": event_result
                }
            else:
                logger.error("Failed to create calendar event")
                return None
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None
    
    def _get_hardcoded_scheduling_start(self, parent_name: str, student_ref: str) -> str:
        """Resposta hardcoded segura para início do agendamento"""
        return (
            f"Perfeito, {parent_name}! Vamos agendar a apresentação para {student_ref}! 📅\n\n"
            "Durante a visita você poderá:\n"
            "• 📚 Conhecer nossa metodologia na prática\n"
            "• 📝 Fazer uma avaliação diagnóstica gratuita\n"
            "• 👩‍🏫 Conversar com nossa orientadora educacional\n"
            "• 📋 Ver nossos materiais didáticos exclusivos\n\n"
            "Qual período é melhor para você?\n\n"
            "**🌅 MANHÃ** (9h às 12h)\n"
            "**🌆 TARDE** (14h às 17h)\n\n"
            "Digite **MANHÃ** ou **TARDE** 😊"
        )
    
    def _get_hardcoded_saturday_restriction(self) -> str:
        """Resposta hardcoded segura para restrição de sábado"""
        return (
            "😔 Infelizmente **não atendemos aos sábados**.\n\n"
            "Nossos horários de funcionamento são:\n"
            "🕐 **Segunda a Sexta-feira, das 9h às 17h**\n\n"
            "Qual período é melhor para você durante a semana?\n\n"
            "**🌅 MANHÃ** (9h às 12h)\n"
            "**🌆 TARDE** (14h às 17h)\n\n"
            "Digite **MANHÃ** ou **TARDE** 😊"
        )
    
    def _create_response(self, state: CeciliaState, response: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Cria resposta padronizada"""
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "appointment_scheduling"
        }

# Entry point para LangGraph
async def scheduling_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = SchedulingNode()
    result = await node(state)
    
    state.update(result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state