"""
Booking service with state management and Google Calendar integration
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import uuid
import re

from ..models.booking_request import BookingRequest, BookingStatus, BookingConfirmation
from ..core.logger import app_logger
from ..clients.google_calendar import GoogleCalendarClient
from .availability_service import AvailabilityService


class BookingService:
    """Handle booking workflow with state management"""
    
    def __init__(self):
        self.availability_service = AvailabilityService()
        self.calendar_client = GoogleCalendarClient()
        
        # In-memory storage for active bookings (use database in production)
        self.active_bookings = {}
    
    async def start_booking(self, phone_number: str, initial_message: str = "") -> str:
        """Start a new booking process"""
        
        try:
            # Check if user already has an active booking
            if phone_number in self.active_bookings:
                return "Você já tem um agendamento em andamento. Continue fornecendo as informações solicitadas ou digite 'cancelar' para reiniciar."
            
            # Create new booking request
            booking = BookingRequest(
                id=str(uuid.uuid4()),
                phone_number=phone_number,
                student_name="",
                parent_name="",
                status=BookingStatus.INITIATED
            )
            
            self.active_bookings[phone_number] = booking
            
            # Get available slots to suggest
            available_slots = await self.availability_service.get_available_slots(days_ahead=7)
            
            if available_slots:
                suggestion = self.availability_service.format_availability_message(available_slots)
                response = f"Ótimo! Vou ajudar você a agendar uma consulta. 📅\n\n{suggestion}"
            else:
                response = "Gostaria de agendar uma consulta! No momento não temos horários disponíveis online. Por favor, entre em contato conosco pelo telefone para verificar a disponibilidade."
            
            app_logger.info("Booking process started", extra={
                "phone_number": phone_number,
                "booking_id": booking.id
            })
            
            return response
            
        except Exception as e:
            app_logger.error(f"Error starting booking: {str(e)}")
            return "Desculpe, ocorreu um erro ao iniciar o agendamento. Tente novamente em alguns minutos."
    
    async def initiate_booking(self, phone_number: str):
        """Start a new booking process"""
        pass
    
    async def process_booking_response(self, phone_number: str, user_message: str):
        """Process user's response during booking flow"""
        pass
    
    async def _handle_initial_response(
        self, 
        booking: BookingRequest, 
        message: str
    ) -> Dict[str, Any]:
        """Handle first response - date/time selection or info collection"""
        
        # Try to extract date/time information
        date_time_info = self._extract_datetime_info(message)
        
        if date_time_info:
            booking.requested_date = date_time_info.get('date')
            booking.requested_time = date_time_info.get('time')
            booking.status = BookingStatus.CHECKING_AVAILABILITY
            
            # Check availability
            is_available = await self.availability_service.check_specific_time_availability(
                booking.requested_date, 
                booking.requested_time
            )
            
            if is_available:
                booking.status = BookingStatus.COLLECTING_INFO
                return {
                    "response": "Ótimo! Este horário está disponível. \n\nPara confirmar o agendamento, preciso de algumas informações:\n\n1. Nome do aluno(a)\n2. Nome do responsável\n3. Idade do aluno(a)",
                    "completed": False
                }
            else:
                # Suggest alternative times
                available_slots = await self.availability_service.get_available_slots(days_ahead=7)
                suggestion = self.availability_service.format_availability_message(available_slots)
                
                return {
                    "response": f"Infelizmente este horário não está disponível. \n\n{suggestion}",
                    "completed": False
                }
        else:
            # Start collecting basic info
            booking.status = BookingStatus.COLLECTING_INFO
            return {
                "response": "Para agendar sua consulta, preciso de algumas informações:\n\n1. Nome do aluno(a)\n2. Nome do responsável\n3. Horário preferido",
                "completed": False
            }
    
    async def _handle_info_collection(
        self, 
        booking: BookingRequest, 
        message: str
    ) -> Dict[str, Any]:
        """Handle information collection phase"""
        
        # Extract information from message
        self._extract_personal_info(booking, message)
        
        # Check if we have all required info
        missing_info = []
        if not booking.student_name:
            missing_info.append("nome do aluno(a)")
        if not booking.parent_name:
            missing_info.append("nome do responsável")
        if not booking.requested_date or not booking.requested_time:
            missing_info.append("horário preferido")
        
        if missing_info:
            missing_text = ", ".join(missing_info)
            return {
                "response": f"Ainda preciso do(s): {missing_text}",
                "completed": False
            }
        else:
            # All info collected, move to confirmation
            booking.status = BookingStatus.CONFIRMING
            return await self._prepare_confirmation(booking)
    
    async def _handle_availability_response(
        self, 
        booking: BookingRequest, 
        message: str
    ) -> Dict[str, Any]:
        """Handle response after showing availability"""
        
        # User selected a time slot number
        if message.strip().isdigit():
            slot_number = int(message.strip())
            available_slots = await self.availability_service.get_available_slots(days_ahead=7)
            
            if 1 <= slot_number <= len(available_slots):
                selected_slot = available_slots[slot_number - 1]
                booking.requested_date = selected_slot.date
                booking.requested_time = selected_slot.time
                booking.status = BookingStatus.COLLECTING_INFO
                
                return {
                    "response": f"Perfeito! Agendamento para {selected_slot.date} às {selected_slot.time}.\n\nAgora preciso de:\n1. Nome do aluno(a)\n2. Nome do responsável",
                    "completed": False
                }
        
        # Try to parse custom date/time
        date_time_info = self._extract_datetime_info(message)
        if date_time_info:
            booking.requested_date = date_time_info.get('date')
            booking.requested_time = date_time_info.get('time')
            
            is_available = await self.availability_service.check_specific_time_availability(
                booking.requested_date, 
                booking.requested_time
            )
            
            if is_available:
                booking.status = BookingStatus.COLLECTING_INFO
                return {
                    "response": "Horário disponível! Agora preciso de:\n1. Nome do aluno(a)\n2. Nome do responsável",
                    "completed": False
                }
        
        return {
            "response": "Por favor, escolha uma das opções numeradas ou informe uma data/horário específico.",
            "completed": False
        }
    
    async def _handle_confirmation(
        self, 
        booking: BookingRequest, 
        message: str
    ) -> Dict[str, Any]:
        """Handle final confirmation"""
        
        message_lower = message.lower().strip()
        
        if any(word in message_lower for word in ['sim', 's', 'confirmo', 'ok', 'confirmar']):
            # Create calendar event
            try:
                event_id = await self._create_calendar_event(booking)
                booking.calendar_event_id = event_id
                booking.status = BookingStatus.CONFIRMED
                booking.confirmed_datetime = datetime.now()
                
                # Remove from active bookings
                del self.active_bookings[booking.phone_number]
                
                confirmation_msg = f"""✅ Agendamento confirmado!

📅 Data: {booking.requested_date}
⏰ Horário: {booking.requested_time}
👨‍🎓 Aluno: {booking.student_name}
👥 Responsável: {booking.parent_name}

Aguardamos vocês! Em caso de necessidade de cancelamento ou reagendamento, entre em contato conosco."""

                return {
                    "response": confirmation_msg,
                    "completed": True,
                    "booking_request": booking
                }
                
            except Exception as e:
                app_logger.error(f"Calendar event creation error: {str(e)}")
                return {
                    "response": "Ocorreu um erro ao confirmar o agendamento. Por favor, entre em contato conosco diretamente.",
                    "completed": True
                }
        
        elif any(word in message_lower for word in ['não', 'n', 'cancelar', 'não confirmo']):
            # Cancel booking
            booking.status = BookingStatus.CANCELLED
            del self.active_bookings[booking.phone_number]
            
            return {
                "response": "Agendamento cancelado. Se quiser reagendar, é só me avisar!",
                "completed": True
            }
        
        else:
            return {
                "response": "Por favor, responda 'sim' para confirmar ou 'não' para cancelar o agendamento.",
                "completed": False
            }
    
    async def _prepare_confirmation(self, booking: BookingRequest) -> Dict[str, Any]:
        """Prepare confirmation message with all details"""
        
        confirmation_msg = f"""📋 Confirme os dados do agendamento:

📅 Data: {booking.requested_date}
⏰ Horário: {booking.requested_time}
👨‍🎓 Aluno: {booking.student_name}
👥 Responsável: {booking.parent_name}

Está tudo correto? Digite 'sim' para confirmar ou 'não' para cancelar."""
        
        return {
            "response": confirmation_msg,
            "completed": False
        }
    
    async def _create_calendar_event(self, booking: BookingRequest) -> str:
        """Create Google Calendar event"""
        
        event_details = {
            'summary': f'Consulta Kumon - {booking.student_name}',
            'description': f"""Consulta agendada via WhatsApp

Aluno: {booking.student_name}
Responsável: {booking.parent_name}
Telefone: {booking.phone_number}
Tipo: {booking.appointment_type}""",
            'start_date': booking.requested_date,
            'start_time': booking.requested_time,
            'duration_minutes': 60
        }
        
        return await self.calendar_client.create_event(event_details)
    
    def _extract_datetime_info(self, message: str) -> Optional[Dict[str, str]]:
        """Extract date and time information from message"""
        
        # Simple patterns for Brazilian Portuguese
        # TODO: Implement more sophisticated date/time parsing
        
        date_patterns = [
            r'(\d{1,2})/(\d{1,2})',  # DD/MM
            r'(\d{1,2})-(\d{1,2})',  # DD-MM
        ]
        
        time_patterns = [
            r'(\d{1,2}):(\d{2})',    # HH:MM
            r'(\d{1,2})h',           # HHh
        ]
        
        # This is a simplified implementation
        # In production, use a proper date/time parser
        
        return None  # Placeholder
    
    def _extract_personal_info(self, booking: BookingRequest, message: str):
        """Extract personal information from message"""
        
        message_lower = message.lower()
        
        # Simple keyword-based extraction
        # TODO: Implement more sophisticated NLP extraction
        
        if not booking.student_name and ('aluno' in message_lower or 'nome' in message_lower):
            # Try to extract name after keywords
            words = message.split()
            for i, word in enumerate(words):
                if word.lower() in ['aluno', 'nome', 'criança']:
                    if i + 1 < len(words):
                        booking.student_name = words[i + 1].title()
                        break
        
        if not booking.parent_name and ('responsável' in message_lower or 'pai' in message_lower or 'mãe' in message_lower):
            # Similar logic for parent name
            words = message.split()
            for i, word in enumerate(words):
                if word.lower() in ['responsável', 'pai', 'mãe', 'pais']:
                    if i + 1 < len(words):
                        booking.parent_name = words[i + 1].title()
                        break 