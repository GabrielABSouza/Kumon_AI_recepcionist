# Cache Import Fix - Turn Architecture

## Problema Resolvido

**Erro Original**: `TURN|architecture_error … No module named 'app.cache.redis_manager'; 'app.cache' is not a package`

O fluxo de turno estava falhando por erro de import, impedindo que completasse o caminho: **pré → planner → outbox → delivery**.

## Solução Implementada

### 1. **Unificação de Import do Cache**

✅ **Correções Diretas**:
- `app/api/evolution.py`: `from ..cache.redis_manager` → `from ..core.cache_manager`
- `app/core/outbox_repo_redis.py`: `from ..cache.redis_manager` → `from .cache_manager`

### 2. **Shim de Compatibilidade**

Criado pacote de compatibilidade em `app/cache/` para referências legadas:

**app/cache/__init__.py**:
```python
from ..core.cache_manager import get_redis
__all__ = ["get_redis"]
```

**app/cache/redis_manager.py**:
```python
from ..core.cache_manager import redis_cache as _core_redis_cache, get_redis

# Wrapper de compatibilidade
redis_cache = _core_redis_cache

class CacheManager:
    """Compatibilidade para CacheManager legado"""
    def __init__(self):
        self._redis_cache = redis_cache
```

### 3. **Import Defensivo na Turn Architecture**

Implementado padrão defensivo em `_process_through_turn_architecture`:

```python
# Import defensivo para cache - tolerância a refatores futuros
redis_cache = None
try:
    from ..core.cache_manager import redis_cache
    app_logger.info("CACHE_INIT|source=app.core.cache_manager|success")
except ModuleNotFoundError:
    try:
        from ..cache.redis_manager import redis_cache
        app_logger.info("CACHE_INIT|source=app.cache.redis_manager(shim)|fallback_success")
    except ModuleNotFoundError:
        app_logger.warning("CACHE_INIT|both_sources_failed|continuing_without_cache")
```

### 4. **Turn-Lock com Try/Finally**

✅ **Já Implementado**: O context manager `turn_lock` já possui try/finally para garantir liberação:

```python
try:
    yield True
finally:
    # Release lock
    try:
        redis.delete(lock_key)
        logger.info(f"TURNLOCK|released|key={lock_key}")
    except Exception as e:
        logger.warning(f"TURNLOCK|release_failed|key={lock_key}|error={e}")
```

### 5. **Logs de Observabilidade**

✅ **Implementados**:
- `CACHE_INIT|source=app.core.cache_manager|success`
- `CACHE_INIT|source=app.cache.redis_manager(shim)|fallback_success`
- `TURNLOCK|acquired` → processamento → `TURNLOCK|released`

### 6. **Testes de Smoke**

✅ **Criados**:
- `tests/test_cache_import.py`: Testa imports do cache
- `tests/test_turn_flow_smoke.py`: Testa fluxo de turno sem ModuleNotFoundError

## Como Usar

### Import Preferencial (Recomendado)
```python
# Use sempre que possível
from app.core.cache_manager import redis_cache, get_redis
```

### Import Defensivo (Para Componentes Críticos)
```python
# Para tolerância a refatores futuros
redis_cache = None
try:
    from app.core.cache_manager import redis_cache
except ModuleNotFoundError:
    from app.cache.redis_manager import redis_cache
```

### Compatibilidade Legada
```python
# Para código legado que não pode ser refatorado imediatamente
from app.cache.redis_manager import CacheManager, get_redis_client
```

## Resultados Esperados

✅ **Envio de única resposta por turno** (sem duplicatas)
✅ **Nenhum ModuleNotFoundError** relacionado a app.cache.*
✅ **Log completo**: `TURN|acquired → processamento → outbox → delivery → TURNLOCK|released`
✅ **Sem "PRE-DELIVERY – EMPTY OUTBOX detected"**
✅ **Testes de smoke passam** localmente
✅ **Deploy em Railway** sem crash por import/psycopg/redis

## Arquivos Modificados

- ✅ `app/api/evolution.py` - Import defensivo na Turn Architecture
- ✅ `app/core/outbox_repo_redis.py` - Correção de import
- ✅ `app/core/cache_manager.py` - Logs de observabilidade
- ✅ `app/cache/__init__.py` - Shim de compatibilidade (novo)
- ✅ `app/cache/redis_manager.py` - Shim de compatibilidade (novo)
- ✅ `tests/test_cache_import.py` - Testes de smoke (novo)
- ✅ `tests/test_turn_flow_smoke.py` - Testes de smoke (novo)

## Fluxo de Turno Corrigido

```
1. Webhook recebe mensagem
2. TURNLOCK|acquired (context manager com try/finally)
3. _process_through_turn_architecture:
   - ✅ Import defensivo do cache (sem ModuleNotFoundError)
   - ✅ Planner cria resposta
   - ✅ save_outbox persiste mensagem
   - ✅ delivery_node_turn_based envia resposta
4. TURNLOCK|released (garantido pelo finally)
```

**Resultado**: Uma única resposta por turno, sem erros de import, com observabilidade completa.