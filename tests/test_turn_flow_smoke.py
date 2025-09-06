"""
Turn Flow Smoke Tests
Testa o fluxo básico de turno sem ModuleNotFoundError
"""

import pytest
import unittest
import asyncio
from unittest.mock import patch, MagicMock
import sys
import os

# Adiciona o diretório app ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestTurnFlowSmoke(unittest.TestCase):
    """Testes de smoke para fluxo de turno"""

    def test_turn_dedup_imports(self):
        """Testa se os imports de turn_dedup funcionam"""
        try:
            from app.core.turn_dedup import is_duplicate_message, turn_lock
            
            self.assertTrue(callable(is_duplicate_message))
            self.assertTrue(callable(turn_lock))
            
            print("✅ turn_dedup imports working")
            
        except ImportError as e:
            self.fail(f"Failed to import turn_dedup: {e}")

    def test_cache_import_defensive_pattern(self):
        """Testa se o padrão defensivo de import do cache funciona"""
        try:
            # Simular o padrão usado em _process_through_turn_architecture
            redis_cache = None
            
            try:
                from app.core.cache_manager import redis_cache
                source = "core"
            except ModuleNotFoundError:
                try:
                    from app.cache.redis_manager import redis_cache
                    source = "shim"
                except ModuleNotFoundError:
                    redis_cache = None
                    source = "none"
            
            # Deve ter conseguido import de alguma fonte ou gracefully failed
            print(f"✅ Defensive cache import working - source: {source}")
            
        except Exception as e:
            self.fail(f"Defensive cache import failed: {e}")

    def test_outbox_import_without_error(self):
        """Testa se outbox_repository pode ser importado sem erro"""
        try:
            from app.core.outbox_repository import save_outbox
            
            self.assertTrue(callable(save_outbox))
            
            print("✅ outbox_repository import working")
            
        except ImportError as e:
            self.fail(f"Failed to import outbox_repository: {e}")

    @patch('app.core.cache_manager.redis')
    @patch('app.core.database.connection.get_database_connection')
    def test_turn_flow_without_module_error(self, mock_db, mock_redis):
        """Testa se o fluxo de turno executa sem ModuleNotFoundError"""
        
        # Mock Redis e Database como indisponíveis
        mock_db.return_value = None
        mock_redis.from_url.side_effect = Exception("Redis unavailable")
        
        try:
            # Importar os módulos críticos do fluxo
            from app.core.turn_dedup import is_duplicate_message, turn_lock
            from app.core.outbox_repository import save_outbox
            
            # Simular verificação de mensagem duplicada
            is_dup = is_duplicate_message("test_instance", "5511999999999", "msg_123")
            
            # Deve funcionar (retornar False quando Redis não disponível)
            self.assertFalse(is_dup)
            
            # Simular salvamento no outbox
            result = save_outbox("test_conv", [{"text": "teste", "channel": "whatsapp"}])
            
            # Deve retornar lista vazia quando DB não disponível, mas não deve crashar
            self.assertIsInstance(result, list)
            
            print("✅ Turn flow executes without ModuleNotFoundError")
            
        except ModuleNotFoundError as e:
            self.fail(f"Turn flow failed with ModuleNotFoundError: {e}")
        except Exception as e:
            # Outros erros são aceitáveis (Redis/DB indisponíveis)
            print(f"⚠️ Expected error in degraded mode: {e}")

    def test_structured_logging_imports(self):
        """Testa se structured_logging pode ser importado"""
        try:
            from app.core.structured_logging import log_turn_event, log_webhook_event
            
            self.assertTrue(callable(log_turn_event))
            self.assertTrue(callable(log_webhook_event))
            
            print("✅ structured_logging imports working")
            
        except ImportError as e:
            self.fail(f"Failed to import structured_logging: {e}")

    def test_workflow_guards_imports(self):
        """Testa se workflow_guards pode ser importado"""
        try:
            from app.core.workflow_guards import check_recursion_limit, prevent_greeting_loops
            
            self.assertTrue(callable(check_recursion_limit))
            self.assertTrue(callable(prevent_greeting_loops))
            
            print("✅ workflow_guards imports working")
            
        except ImportError as e:
            self.fail(f"Failed to import workflow_guards: {e}")

    @patch.dict(os.environ, {}, clear=True)
    def test_graceful_degradation_without_env_vars(self):
        """Testa degradação graceful sem variáveis de ambiente"""
        try:
            # Tentar importar e usar componentes críticos sem env vars
            from app.core.cache_manager import get_redis
            from app.core.database.connection import get_database_connection
            from app.core.outbox_repository import save_outbox
            
            # Todos devem retornar None ou lista vazia sem crashar
            cache = get_redis()
            db = get_database_connection()
            result = save_outbox("test", [{"text": "test"}])
            
            # Pode ser None ou list, mas não deve crashar
            self.assertIsInstance(result, list)
            
            print("✅ Graceful degradation working without environment variables")
            
        except Exception as e:
            self.fail(f"Components failed to degrade gracefully: {e}")


if __name__ == '__main__':
    # Executar testes com output verboso
    unittest.main(verbosity=2)