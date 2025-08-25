# Message Postprocessor Integration Guide

## Overview

The Message Postprocessor is a comprehensive service that handles response formatting, Google Calendar integration, and message delivery coordination for the Kumon Assistant system.

## Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LangGraph     │───▶│ Message         │───▶│ Evolution API   │
│   Workflow      │    │ Postprocessor   │    │ Delivery        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │ Google Calendar  │
                       │ Integration      │
                       └──────────────────┘
```

### Key Features

1. **Response Formatting with Template Engine**
   - Business-compliant message templates
   - Dynamic content insertion
   - Redis caching for performance

2. **Google Calendar Integration**
   - Appointment booking confirmations
   - Conflict detection
   - Circuit breaker for reliability

3. **Message Delivery Coordination**
   - Evolution API integration
   - Retry logic with exponential backoff
   - Delivery status tracking

4. **Performance Optimization**
   - <100ms processing time target
   - Template rendering <50ms
   - Redis caching with 3600s TTL

## Integration Points

### Input from LangGraph Workflow

```python
from app.services.message_postprocessor import message_postprocessor
from app.models.message import MessageResponse, MessageType

# Process LangGraph response
response = MessageResponse(
    content="User message content",
    message_type=MessageType.TEXT,
    metadata={"intent": "scheduling", "confidence": 0.95}
)

context = {
    "is_new_lead": True,
    "appointment_date": "2024-01-15",
    "appointment_time": "10:00"
}

# Format and prepare for delivery
formatted_message = await message_postprocessor.process_message(
    response, phone_number, context
)
```

### Output to Evolution API

```python
# Deliver formatted message
delivery_result = await message_postprocessor.deliver_message(
    formatted_message, 
    instance_name="kumonvilaa"
)

# Check delivery status
if delivery_result["success"]:
    message_id = delivery_result["message_id"]
    evolution_id = delivery_result["evolution_message_id"]
else:
    error = delivery_result["error"]
    retry_scheduled = delivery_result["retry_scheduled"]
```

## Configuration

### Required Settings

```python
# Business Configuration
BUSINESS_PHONE = "51996921999"
BUSINESS_EMAIL = "kumonvilaa@gmail.com"
BUSINESS_ADDRESS = "Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras"

# Google Calendar
GOOGLE_CREDENTIALS_PATH = "google-service-account.json"
GOOGLE_CALENDAR_ID = "your-calendar-id@gmail.com"

# Evolution API
EVOLUTION_API_URL = "http://localhost:8080"
AUTHENTICATION_API_KEY = "your-auth-key"

# Redis Cache
MEMORY_REDIS_URL = "redis://localhost:6379/0"
```

### Template Configuration

Templates are defined in the Message Postprocessor initialization:

```python
templates = {
    "appointment_confirmation": {
        "pattern": r"(agend|marca|entrevista|visita|horário)",
        "template": """
✅ {appointment_type} confirmado!

📅 Data: {date}
⏰ Horário: {time}
📍 Local: {location}

📞 Contato: {contact_phone}
💰 Valores: {pricing_info}
        """
    },
    "pricing_info": {
        "pattern": r"(valor|preço|custo|mensalidade)",
        "template": """
💰 Valores do Kumon Vila A:

📚 Mensalidade: {monthly_fee}
📖 Material didático: {material_fee}

📞 Para mais informações: {contact_phone}
        """
    }
}
```

## Performance Targets

### Processing Performance
- **Processing Time**: <100ms per message
- **Template Rendering**: <50ms
- **Cache Hit Rate**: >80%

### Calendar Integration
- **Success Rate**: >99%
- **Conflict Detection**: 100% accurate
- **Circuit Breaker**: 5 failures trigger open state

### Delivery Coordination
- **Delivery Tracking**: 100% accurate
- **Retry Logic**: Exponential backoff
- **Status Monitoring**: Real-time tracking

## Monitoring and Metrics

### Available Metrics

```python
metrics = message_postprocessor.get_performance_metrics()

# Processing Performance
processing_metrics = metrics["processing_performance"]
print(f"Avg processing time: {processing_metrics['avg_processing_time_ms']}ms")
print(f"Cache hit rate: {processing_metrics['cache_hit_rate']}%")

# Delivery Performance  
delivery_metrics = metrics["delivery_performance"]
print(f"Success rate: {delivery_metrics['delivery_success_rate']}%")

# Calendar Integration
calendar_metrics = metrics["calendar_integration"]
print(f"Calendar success rate: {calendar_metrics['success_rate']}%")
```

### Health Checks

```python
# Performance health check
async def check_postprocessor_health():
    metrics = message_postprocessor.get_performance_metrics()
    
    # Check processing time target
    avg_time = metrics["processing_performance"]["avg_processing_time_ms"]
    processing_healthy = avg_time < 100
    
    # Check delivery success rate
    delivery_rate = metrics["delivery_performance"]["delivery_success_rate"]
    delivery_healthy = delivery_rate > 95
    
    # Check calendar integration
    calendar_rate = metrics["calendar_integration"]["success_rate"]
    calendar_healthy = calendar_rate > 99
    
    return {
        "processing_healthy": processing_healthy,
        "delivery_healthy": delivery_healthy,
        "calendar_healthy": calendar_healthy,
        "overall_healthy": all([processing_healthy, delivery_healthy, calendar_healthy])
    }
```

## Error Handling

### Circuit Breaker Pattern

The calendar integration uses a circuit breaker to handle service failures:

```python
calendar_circuit_breaker = {
    "failures": 0,
    "last_failure": None,
    "is_open": False,
    "failure_threshold": 5,
    "recovery_timeout": 300  # 5 minutes
}
```

### Retry Logic

Failed deliveries are automatically retried based on message priority:

| Priority | Max Retries | Retry Delay |
|----------|-------------|-------------|
| URGENT   | 5           | 30 seconds  |
| HIGH     | 3           | 1 minute    |
| NORMAL   | 2           | 5 minutes   |
| LOW      | 1           | 15 minutes  |

### Fallback Mechanisms

1. **Template Fallback**: If template processing fails, use original content
2. **Calendar Fallback**: If calendar integration fails, proceed without calendar
3. **Delivery Fallback**: If primary delivery fails, queue for retry
4. **Cache Fallback**: If cache fails, proceed without caching

## Business Compliance

### Required Information

All messages must include:
- Contact phone: (51) 99692-1999
- Business address when relevant
- Pricing information when requested
- Professional tone with appropriate emojis

### Template Variables

```python
business_config = {
    "phone": "51996921999",
    "contact_info": "(51) 99692-1999",
    "address": "Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras",
    "pricing": {
        "monthly_fee": "R$ 375",
        "material_fee": "R$ 100"
    },
    "reminder_timing": "2 horas antes"
}
```

## Testing

### Unit Tests

```bash
# Run Message Postprocessor tests
pytest tests/test_message_postprocessor.py -v

# Run performance tests
pytest tests/test_message_postprocessor.py::TestMessagePostprocessor::test_performance_target_processing_time -v

# Run integration tests (requires services)
pytest tests/test_message_postprocessor.py -m integration -v
```

### Performance Testing

```python
# Test processing time target
async def test_processing_performance():
    times = []
    for _ in range(100):
        start = time.time()
        await message_postprocessor.process_message(sample_response, phone_number)
        times.append((time.time() - start) * 1000)
    
    avg_time = sum(times) / len(times)
    assert avg_time < 100, f"Average time {avg_time:.2f}ms exceeds target"
```

## Troubleshooting

### Common Issues

1. **High Processing Time**
   - Check Redis cache connectivity
   - Monitor template complexity
   - Verify external service response times

2. **Calendar Integration Failures**
   - Verify Google credentials
   - Check calendar permissions
   - Monitor circuit breaker state

3. **Delivery Failures**
   - Check Evolution API connectivity
   - Verify instance status
   - Monitor retry queue size

### Debugging Commands

```python
# Check current metrics
metrics = message_postprocessor.get_performance_metrics()
print(json.dumps(metrics, indent=2))

# Check circuit breaker status
print(f"Calendar circuit breaker open: {message_postprocessor._is_calendar_circuit_open()}")

# Check retry queue
print(f"Messages in retry queue: {len(message_postprocessor.retry_queue)}")

# Process retry queue manually
await message_postprocessor.process_retry_queue()
```

## Deployment Considerations

### Resource Requirements
- **Memory**: ~50MB for cache and delivery records
- **CPU**: Low usage, mostly I/O bound
- **Network**: Requires access to Google Calendar API and Evolution API

### Scaling
- Stateless design allows horizontal scaling
- Redis cache can be shared across instances
- Delivery records can be persisted to database for multi-instance deployments

### Monitoring
- Set up alerts for processing time > 100ms
- Monitor calendar integration success rate
- Track delivery failure patterns
- Monitor cache performance

## Future Enhancements

1. **Advanced Templates**
   - Dynamic template selection based on user profile
   - Multilingual template support
   - Template A/B testing

2. **Enhanced Calendar Integration**
   - Multiple calendar support
   - Automatic rescheduling
   - Availability checking

3. **Delivery Optimization**
   - Message batching
   - Priority queuing
   - Delivery scheduling

4. **Analytics**
   - Template effectiveness tracking
   - User engagement metrics
   - Performance optimization insights