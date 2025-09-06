"""
Pipeline Smoke Test
Testa o pipeline completo: preprocess → classify → route → plan → outbox → delivery
"""

import pytest
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Adiciona o diretório app ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestPipelineSmoke(unittest.TestCase):
    """Testes de smoke para o pipeline principal refatorado"""

    def test_feature_flags_pipeline_enabled(self):
        """Testa se as feature flags do pipeline estão ativadas"""
        try:
            from app.core.feature_flags import (
                is_main_pipeline_enabled,
                is_turn_guard_only,
                is_outbox_redis_fallback_enabled
            )
            
            # Todas as flags principais devem estar habilitadas
            self.assertTrue(is_main_pipeline_enabled())
            self.assertTrue(is_turn_guard_only())
            self.assertTrue(is_outbox_redis_fallback_enabled())
            
            print("✅ Feature flags do pipeline configuradas corretamente")
            
        except ImportError as e:
            self.fail(f"Failed to import feature flags: {e}")

    def test_pipeline_components_import(self):
        """Testa se todos os componentes do pipeline podem ser importados"""
        try:
            # Preprocessor
            from app.services.message_preprocessor import message_preprocessor
            self.assertTrue(hasattr(message_preprocessor, 'process_message'))
            
            # Intent Classifier
            from app.workflows.intent_classifier import AdvancedIntentClassifier
            self.assertTrue(callable(AdvancedIntentClassifier))
            
            # Smart Router
            from app.workflows.smart_router import smart_router
            self.assertTrue(hasattr(smart_router, 'make_routing_decision'))
            
            # Response Planner
            from app.core.router.response_planner import ResponsePlanner
            self.assertTrue(callable(ResponsePlanner))
            
            # Delivery
            from app.core.router.delivery_io import delivery_node_turn_based
            self.assertTrue(callable(delivery_node_turn_based))
            
            print("✅ Todos os componentes do pipeline importados com sucesso")
            
        except ImportError as e:
            self.fail(f"Failed to import pipeline components: {e}")

    def test_outbox_persistence_imports(self):
        """Testa se os sistemas de outbox podem ser importados"""
        try:
            # Database outbox
            from app.core.outbox_repository import save_outbox
            self.assertTrue(callable(save_outbox))
            
            # Redis outbox fallback
            from app.core.outbox_repo_redis import outbox_push, outbox_pop_all
            self.assertTrue(callable(outbox_push))
            self.assertTrue(callable(outbox_pop_all))
            
            print("✅ Sistemas de outbox persistence importados com sucesso")
            
        except ImportError as e:
            self.fail(f"Failed to import outbox systems: {e}")

    def test_turn_controller_guardrails_import(self):
        """Testa se os guardrails do Turn Controller estão acessíveis"""
        try:
            # Turn deduplication
            from app.core.turn_dedup import is_duplicate_message, turn_lock
            self.assertTrue(callable(is_duplicate_message))
            self.assertTrue(callable(turn_lock))
            
            # Workflow guards
            from app.core.workflow_guards import check_recursion_limit, prevent_greeting_loops
            self.assertTrue(callable(check_recursion_limit))
            self.assertTrue(callable(prevent_greeting_loops))
            
            print("✅ Guardrails do Turn Controller importados com sucesso")
            
        except ImportError as e:
            self.fail(f"Failed to import Turn Controller guardrails: {e}")

    @patch('app.services.message_preprocessor.message_preprocessor.process_message')
    @patch('app.workflows.intent_classifier.AdvancedIntentClassifier')
    @patch('app.workflows.smart_router.smart_router.make_routing_decision')
    @patch('app.core.router.response_planner.ResponsePlanner')
    @patch('app.core.outbox_repository.save_outbox')
    @patch('app.core.router.delivery_io.delivery_node_turn_based')
    @patch('app.core.structured_logging.log_turn_event')
    async def test_pipeline_execution_flow(self, mock_log, mock_delivery, mock_save_outbox, 
                                         mock_planner_class, mock_router, mock_classifier_class, 
                                         mock_preprocessor):
        """Testa se o fluxo do pipeline executa sem erros críticos"""
        
        # Mock preprocessor
        mock_preprocess_result = MagicMock()
        mock_preprocess_result.success = True
        mock_preprocess_result.message.message = "Olá, quero saber sobre Kumon"
        mock_preprocess_result.message.phone = "5511999999999"
        mock_preprocess_result.processing_time_ms = 50.0
        mock_preprocessor.return_value = mock_preprocess_result
        
        # Mock intent classifier
        mock_classifier_instance = MagicMock()
        mock_intent_result = MagicMock()
        mock_intent_result.category = "information_request"
        mock_intent_result.confidence = 0.85
        mock_intent_result.subcategory = "methodology_info"
        mock_classifier_instance.classify_intent.return_value = mock_intent_result
        mock_classifier_class.return_value = mock_classifier_instance
        
        # Mock smart router
        mock_routing_decision = MagicMock()
        mock_routing_decision.target_node = "information_node"
        mock_routing_decision.threshold_action = "proceed"
        mock_routing_decision.final_confidence = 0.9
        mock_routing_decision.rule_applied = "information_rule"
        mock_router.return_value = mock_routing_decision
        
        # Mock response planner
        mock_planner_instance = MagicMock()
        mock_planner_instance.plan_and_generate = AsyncMock()
        mock_planner_class.return_value = mock_planner_instance
        
        # Mock outbox save
        mock_save_outbox.return_value = ["idem_key_123"]
        
        # Mock delivery
        mock_result_state = {"turn_status": "delivered", "messages_sent": 1}
        mock_delivery.return_value = mock_result_state
        
        try:
            # Import and execute pipeline function
            from app.api.evolution import _process_through_turn_architecture
            
            # Create test message
            test_message = MagicMock()
            test_message.phone = "5511999999999"
            test_message.message = "Olá, quero saber sobre Kumon"
            test_message.message_id = "test_msg_123"
            
            # Execute pipeline
            await _process_through_turn_architecture(test_message)
            
            # Verify each stage was called
            mock_preprocessor.assert_called_once()
            mock_classifier_class.assert_called_once()
            mock_router.assert_called_once()
            mock_planner_instance.plan_and_generate.assert_called_once()
            mock_save_outbox.assert_called_once()
            mock_delivery.assert_called_once()
            
            print("✅ Pipeline executa sem erros críticos")
            
        except Exception as e:
            self.fail(f"Pipeline execution failed: {e}")

    def test_logging_markers_present(self):
        """Testa se os marcadores de log obrigatórios estão presentes no código"""
        try:
            import inspect
            from app.api.evolution import _process_through_turn_architecture
            
            # Lê o código fonte da função
            source = inspect.getsource(_process_through_turn_architecture)
            
            # Verifica se os marcadores obrigatórios estão presentes
            required_markers = [
                "PIPELINE|start",
                "PIPELINE|preprocess_start",
                "PIPELINE|classify_start", 
                "PIPELINE|route_start",
                "PIPELINE|plan_start",
                "PIPELINE|outbox_start",
                "PIPELINE|delivery_start",
                "PIPELINE|guards_start",
                "PIPELINE|complete"
            ]
            
            for marker in required_markers:
                self.assertIn(marker, source, f"Marcador obrigatório '{marker}' não encontrado")
            
            print("✅ Todos os marcadores de log obrigatórios estão presentes")
            
        except Exception as e:
            self.fail(f"Failed to verify logging markers: {e}")

    @patch.dict(os.environ, {}, clear=True)
    def test_graceful_degradation_no_env_vars(self):
        """Testa degradação graceful sem variáveis de ambiente"""
        try:
            # Tenta importar componentes críticos sem env vars
            from app.core.feature_flags import (
                is_main_pipeline_enabled,
                is_turn_guard_only,
                is_outbox_redis_fallback_enabled
            )
            from app.core.cache_manager import get_redis
            from app.core.database.connection import get_database_connection
            
            # Deve funcionar mesmo sem env vars (usando defaults)
            pipeline_enabled = is_main_pipeline_enabled()  # default True
            turn_guard = is_turn_guard_only()  # default True
            redis_fallback = is_outbox_redis_fallback_enabled()  # default True
            
            self.assertIsInstance(pipeline_enabled, bool)
            self.assertIsInstance(turn_guard, bool) 
            self.assertIsInstance(redis_fallback, bool)
            
            # Cache e DB podem ser None mas não devem crashar
            cache = get_redis()  # pode ser None
            db = get_database_connection()  # pode ser None
            
            print("✅ Degradação graceful funcionando sem variáveis de ambiente")
            
        except Exception as e:
            self.fail(f"Components failed graceful degradation: {e}")

    def test_no_emergency_fallback_shortcuts(self):
        """Testa se não há curto-circuitos de fallback que contornam o pipeline"""
        try:
            import inspect
            from app.api.evolution import _process_through_turn_architecture
            
            # Lê o código fonte da função
            source = inspect.getsource(_process_through_turn_architecture)
            
            # Verifica que a mensagem final é apenas o log de sucesso
            self.assertIn("CRITICAL: No emergency fallback", source)
            self.assertIn("pipeline_success=true", source)
            
            # Não deve ter return direto antes do fim da função (exceto early returns de erro)
            lines = source.split('\n')
            return_lines = [line.strip() for line in lines if line.strip().startswith('return') and 'return state' not in line]
            
            # As únicas returns devem ser early returns em caso de erro do preprocessamento ou guardrails
            for return_line in return_lines:
                line_context = source[:source.index(return_line)]
                is_valid_return = (
                    'preprocessing failure' in line_context or
                    'Stop pipeline' in line_context or
                    'preprocess_failed' in line_context or
                    'guards_recursion_exceeded' in line_context or
                    'guards_greeting_loop' in line_context or
                    '# Stop processing' in line_context or
                    'return  # Stop' in return_line
                )
                self.assertTrue(is_valid_return, f"Encontrado return suspeito: {return_line}")
            
            print("✅ Nenhum curto-circuito de fallback encontrado")
            
        except Exception as e:
            self.fail(f"Failed to verify no emergency shortcuts: {e}")


if __name__ == '__main__':
    # Executar testes com output verboso
    unittest.main(verbosity=2)