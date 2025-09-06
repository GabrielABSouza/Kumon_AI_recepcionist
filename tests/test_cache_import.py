"""
Cache Import Smoke Tests
Verifica se os imports do cache funcionam corretamente após refatoração
"""

import pytest
import unittest
import os
from unittest.mock import patch


class TestCacheImport(unittest.TestCase):
    """Testes de smoke para imports do cache"""

    def test_core_cache_manager_import(self):
        """Testa se app.core.cache_manager pode ser importado e instanciado"""
        try:
            from app.core.cache_manager import redis_cache, get_redis
            
            # Verifica se o redis_cache existe
            self.assertIsNotNone(redis_cache)
            
            # Verifica se get_redis é uma função callable
            self.assertTrue(callable(get_redis))
            
            print("✅ app.core.cache_manager imports working correctly")
            
        except ImportError as e:
            self.fail(f"Failed to import app.core.cache_manager: {e}")

    def test_compatibility_shim_import(self):
        """Testa se o shim de compatibilidade app.cache.redis_manager funciona"""
        try:
            from app.cache.redis_manager import redis_cache, CacheManager, get_redis_client
            
            # Verifica se redis_cache existe
            self.assertIsNotNone(redis_cache)
            
            # Verifica se CacheManager pode ser instanciado
            cache_manager = CacheManager()
            self.assertIsNotNone(cache_manager)
            
            # Verifica se get_redis_client é callable
            self.assertTrue(callable(get_redis_client))
            
            print("✅ app.cache.redis_manager(shim) imports working correctly")
            
        except ImportError as e:
            self.fail(f"Failed to import app.cache.redis_manager shim: {e}")

    def test_cache_manager_instantiation_without_redis(self):
        """Testa se CacheManager pode ser instanciado sem Redis disponível"""
        try:
            # Mock Redis não disponível
            with patch.dict(os.environ, {}, clear=True):
                from app.core.cache_manager import RedisManager
                
                manager = RedisManager()
                
                # Deve ser possível instanciar mesmo sem Redis
                self.assertIsNotNone(manager)
                
                # Cliente pode ser None se Redis não disponível
                client = manager.client
                # Não falhamos se client é None - isso é comportamento esperado
                
                print("✅ CacheManager gracefully handles missing Redis")
                
        except Exception as e:
            self.fail(f"CacheManager failed to handle missing Redis gracefully: {e}")

    def test_defensive_import_pattern(self):
        """Testa o padrão de import defensivo usado na Turn Architecture"""
        redis_cache = None
        import_success = False
        
        try:
            # Primeiro tenta app.core.cache_manager
            from app.core.cache_manager import redis_cache
            import_success = True
            source = "app.core.cache_manager"
        except ModuleNotFoundError:
            try:
                # Fallback para app.cache.redis_manager
                from app.cache.redis_manager import redis_cache
                import_success = True
                source = "app.cache.redis_manager"
            except ModuleNotFoundError:
                source = "none"
        
        # Deve ter conseguido importar de pelo menos uma fonte
        self.assertTrue(import_success, "Defensive import pattern failed - neither source available")
        
        if redis_cache:
            # Se importou, deve ter redis_cache disponível
            self.assertIsNotNone(redis_cache)
            
        print(f"✅ Defensive import pattern working - source: {source}")

    def test_legacy_compatibility_functions(self):
        """Testa se as funções de compatibilidade legada funcionam"""
        try:
            from app.cache.redis_manager import get_redis_client, close_redis_client
            
            # Deve ser possível chamar as funções sem erro (mesmo que retornem None)
            client = get_redis_client()
            # Cliente pode ser None se Redis indisponível
            
            # close_redis_client não deve gerar erro
            close_redis_client()
            
            print("✅ Legacy compatibility functions working")
            
        except Exception as e:
            self.fail(f"Legacy compatibility functions failed: {e}")


if __name__ == '__main__':
    # Executar testes com output verboso
    unittest.main(verbosity=2)