#!/usr/bin/env python3
"""
FASE 1: Observability Foundation Setup
SuperClaude Framework Implementation Script
"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path


class ObservabilitySetup:
    """
    Setup completo de observabilidade com OpenTelemetry, Prometheus e Grafana
    """
    
    def __init__(self):
        self.config_dir = Path("./infrastructure/observability")
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def create_otel_config(self) -> Dict[str, Any]:
        """Create OpenTelemetry configuration"""
        
        otel_config = {
            "receivers": {
                "otlp": {
                    "protocols": {
                        "grpc": {
                            "endpoint": "0.0.0.0:4317"
                        },
                        "http": {
                            "endpoint": "0.0.0.0:4318"
                        }
                    }
                }
            },
            "processors": {
                "batch": {
                    "timeout": "1s",
                    "send_batch_size": 1024
                },
                "memory_limiter": {
                    "limit_mib": 512,
                    "spike_limit_mib": 128,
                    "check_interval": "5s"
                }
            },
            "exporters": {
                "prometheus": {
                    "endpoint": "0.0.0.0:8888",
                    "namespace": "kumon_assistant"
                },
                "logging": {
                    "loglevel": "info"
                },
                "jaeger": {
                    "endpoint": "jaeger:14250",
                    "tls": {
                        "insecure": True
                    }
                }
            },
            "service": {
                "pipelines": {
                    "traces": {
                        "receivers": ["otlp"],
                        "processors": ["memory_limiter", "batch"],
                        "exporters": ["jaeger", "logging"]
                    },
                    "metrics": {
                        "receivers": ["otlp"],
                        "processors": ["memory_limiter", "batch"],
                        "exporters": ["prometheus", "logging"]
                    }
                }
            }
        }
        
        # Save config
        config_path = self.config_dir / "otel-collector-config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(otel_config, f, default_flow_style=False)
        
        print(f"✅ OpenTelemetry config criado: {config_path}")
        return otel_config
    
    def create_prometheus_config(self):
        """Create Prometheus configuration"""
        
        prometheus_config = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'kumon-assistant'
    environment: 'production'

rule_files:
  - '/etc/prometheus/rules/*.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  # App metrics
  - job_name: 'kumon-assistant-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    
  # OpenTelemetry collector metrics
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8888']
      
  # Redis exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
      
  # PostgreSQL exporter
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']
      
  # Node exporter for system metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
"""
        
        config_path = self.config_dir / "prometheus.yml"
        with open(config_path, 'w') as f:
            f.write(prometheus_config)
        
        print(f"✅ Prometheus config criado: {config_path}")
        return prometheus_config
    
    def create_alerting_rules(self):
        """Create Prometheus alerting rules"""
        
        rules = {
            "groups": [
                {
                    "name": "kumon_assistant_alerts",
                    "interval": "30s",
                    "rules": [
                        {
                            "alert": "HighResponseTime",
                            "expr": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5',
                            "for": "5m",
                            "labels": {
                                "severity": "critical",
                                "team": "backend"
                            },
                            "annotations": {
                                "summary": "High response time detected",
                                "description": "95th percentile response time is above 500ms (current: {{ $value }}s)"
                            }
                        },
                        {
                            "alert": "LowCacheHitRate",
                            "expr": 'rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.7',
                            "for": "10m",
                            "labels": {
                                "severity": "warning",
                                "team": "backend"
                            },
                            "annotations": {
                                "summary": "Cache hit rate below 70%",
                                "description": "Cache hit rate is {{ $value | humanizePercentage }}"
                            }
                        },
                        {
                            "alert": "HighErrorRate",
                            "expr": 'rate(http_requests_total{status=~"5.."}[5m]) > 0.01',
                            "for": "5m",
                            "labels": {
                                "severity": "critical",
                                "team": "backend"
                            },
                            "annotations": {
                                "summary": "Error rate above 1%",
                                "description": "5xx error rate is {{ $value | humanizePercentage }}"
                            }
                        },
                        {
                            "alert": "HighMemoryUsage",
                            "expr": 'process_resident_memory_bytes / node_memory_MemTotal_bytes > 0.85',
                            "for": "5m",
                            "labels": {
                                "severity": "warning",
                                "team": "devops"
                            },
                            "annotations": {
                                "summary": "Memory usage above 85%",
                                "description": "Current memory usage: {{ $value | humanizePercentage }}"
                            }
                        },
                        {
                            "alert": "SecurityThreatDetected",
                            "expr": 'rate(security_threats_detected_total[1m]) > 5',
                            "for": "1m",
                            "labels": {
                                "severity": "critical",
                                "team": "security"
                            },
                            "annotations": {
                                "summary": "High rate of security threats",
                                "description": "{{ $value }} threats per minute detected"
                            }
                        }
                    ]
                }
            ]
        }
        
        rules_dir = self.config_dir / "rules"
        rules_dir.mkdir(exist_ok=True)
        
        rules_path = rules_dir / "alerts.yml"
        with open(rules_path, 'w') as f:
            yaml.dump(rules, f, default_flow_style=False)
        
        print(f"✅ Alerting rules criadas: {rules_path}")
        return rules
    
    def create_grafana_dashboards(self):
        """Create Grafana dashboard configurations"""
        
        # Main performance dashboard
        performance_dashboard = {
            "dashboard": {
                "title": "Kumon Assistant - Performance Dashboard",
                "panels": [
                    {
                        "title": "Response Time (P95)",
                        "targets": [{
                            "expr": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'
                        }],
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                    },
                    {
                        "title": "Requests per Minute",
                        "targets": [{
                            "expr": 'rate(http_requests_total[1m]) * 60'
                        }],
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                    },
                    {
                        "title": "Cache Hit Rate",
                        "targets": [{
                            "expr": 'rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) * 100'
                        }],
                        "type": "gauge",
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8}
                    },
                    {
                        "title": "Error Rate",
                        "targets": [{
                            "expr": 'rate(http_requests_total{status=~"5.."}[5m]) * 100'
                        }],
                        "type": "gauge",
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 8}
                    },
                    {
                        "title": "Active Connections",
                        "targets": [{
                            "expr": 'redis_connected_clients'
                        }],
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8}
                    },
                    {
                        "title": "Memory Usage",
                        "targets": [{
                            "expr": 'process_resident_memory_bytes / 1024 / 1024'
                        }],
                        "type": "stat",
                        "unit": "MB",
                        "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8}
                    }
                ]
            }
        }
        
        # Security dashboard
        security_dashboard = {
            "dashboard": {
                "title": "Kumon Assistant - Security Dashboard",
                "panels": [
                    {
                        "title": "Security Threats",
                        "targets": [{
                            "expr": 'rate(security_threats_detected_total[5m])'
                        }],
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                    },
                    {
                        "title": "Rate Limited Requests",
                        "targets": [{
                            "expr": 'rate(rate_limit_exceeded_total[5m])'
                        }],
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                    },
                    {
                        "title": "Prompt Injection Attempts",
                        "targets": [{
                            "expr": 'sum(prompt_injection_attempts_total)'
                        }],
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 8}
                    },
                    {
                        "title": "Authentication Failures",
                        "targets": [{
                            "expr": 'rate(auth_failures_total[5m])'
                        }],
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 8, "x": 8, "y": 8}
                    },
                    {
                        "title": "Security Score",
                        "targets": [{
                            "expr": 'security_score'
                        }],
                        "type": "gauge",
                        "gridPos": {"h": 8, "w": 8, "x": 16, "y": 8}
                    }
                ]
            }
        }
        
        dashboards_dir = self.config_dir / "dashboards"
        dashboards_dir.mkdir(exist_ok=True)
        
        # Save dashboards
        import json
        
        perf_path = dashboards_dir / "performance.json"
        with open(perf_path, 'w') as f:
            json.dump(performance_dashboard, f, indent=2)
        
        sec_path = dashboards_dir / "security.json"
        with open(sec_path, 'w') as f:
            json.dump(security_dashboard, f, indent=2)
        
        print(f"✅ Grafana dashboards criados:")
        print(f"   - {perf_path}")
        print(f"   - {sec_path}")
        
        return [performance_dashboard, security_dashboard]
    
    def create_docker_compose(self):
        """Create docker-compose for observability stack"""
        
        docker_compose = """version: '3.8'

services:
  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics
    networks:
      - kumon-network

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules:/etc/prometheus/rules
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
      - '--web.enable-lifecycle'
    networks:
      - kumon-network

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    volumes:
      - grafana-data:/var/lib/grafana
      - ./dashboards:/etc/grafana/provisioning/dashboards
      - ./datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    networks:
      - kumon-network

  # Jaeger for distributed tracing
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: jaeger
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # Jaeger UI
      - "14250:14250"  # gRPC
    networks:
      - kumon-network

  # Alertmanager
  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager-data:/alertmanager
    ports:
      - "9093:9093"
    networks:
      - kumon-network

  # Redis Exporter
  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: redis-exporter
    environment:
      - REDIS_ADDR=redis:6379
    ports:
      - "9121:9121"
    networks:
      - kumon-network

  # PostgreSQL Exporter
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    container_name: postgres-exporter
    environment:
      - DATA_SOURCE_NAME=postgresql://kumon_user:password@postgres:5432/kumon_db?sslmode=disable
    ports:
      - "9187:9187"
    networks:
      - kumon-network

  # Node Exporter for system metrics
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    ports:
      - "9100:9100"
    networks:
      - kumon-network

volumes:
  prometheus-data:
  grafana-data:
  alertmanager-data:

networks:
  kumon-network:
    external: true
"""
        
        compose_path = self.config_dir / "docker-compose.observability.yml"
        with open(compose_path, 'w') as f:
            f.write(docker_compose)
        
        print(f"✅ Docker Compose criado: {compose_path}")
        return docker_compose
    
    def create_python_instrumentation(self):
        """Create Python instrumentation code"""
        
        instrumentation_code = '''"""
Observability instrumentation for Kumon Assistant
"""

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
import logging

logger = logging.getLogger(__name__)


def setup_observability(app_name: str = "kumon-assistant"):
    """Setup OpenTelemetry instrumentation"""
    
    # Setup tracing
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()
    
    # Configure OTLP exporter for traces
    otlp_exporter = OTLPSpanExporter(
        endpoint="localhost:4317",
        insecure=True
    )
    
    # Add span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Setup metrics
    metric_reader = PeriodicExportingMetricReader(
        exporter=OTLPMetricExporter(
            endpoint="localhost:4317",
            insecure=True
        ),
        export_interval_millis=60000,  # Export every minute
    )
    
    metrics.set_meter_provider(
        MeterProvider(metric_readers=[metric_reader])
    )
    
    # Get meter for custom metrics
    meter = metrics.get_meter(app_name)
    
    # Create custom metrics
    response_time_histogram = meter.create_histogram(
        name="http_request_duration_seconds",
        description="HTTP request duration",
        unit="s"
    )
    
    cache_hits_counter = meter.create_counter(
        name="cache_hits_total",
        description="Total number of cache hits"
    )
    
    cache_misses_counter = meter.create_counter(
        name="cache_misses_total", 
        description="Total number of cache misses"
    )
    
    security_threats_counter = meter.create_counter(
        name="security_threats_detected_total",
        description="Total security threats detected"
    )
    
    # Auto-instrument libraries
    FastAPIInstrumentor.instrument()
    HTTPXClientInstrumentor.instrument()
    AsyncPGInstrumentor.instrument()
    RedisInstrumentor.instrument()
    
    logger.info(f"✅ Observability setup complete for {app_name}")
    
    return {
        "tracer": trace.get_tracer(app_name),
        "meter": meter,
        "metrics": {
            "response_time": response_time_histogram,
            "cache_hits": cache_hits_counter,
            "cache_misses": cache_misses_counter,
            "security_threats": security_threats_counter
        }
    }


# Usage example in FastAPI
"""
from app.observability import setup_observability

# In your main.py
observability = setup_observability("kumon-assistant")
tracer = observability["tracer"]
metrics = observability["metrics"]

@app.middleware("http")
async def add_observability(request: Request, call_next):
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}"
    ) as span:
        start_time = time.time()
        
        # Add request attributes
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        metrics["response_time"].record(
            duration,
            {"method": request.method, "path": request.url.path}
        )
        
        # Add response attributes
        span.set_attribute("http.status_code", response.status_code)
        
        return response
"""
'''
        
        instrumentation_path = self.config_dir / "instrumentation.py"
        with open(instrumentation_path, 'w') as f:
            f.write(instrumentation_code)
        
        print(f"✅ Python instrumentation criado: {instrumentation_path}")
        return instrumentation_code


def main():
    """Execute observability setup"""
    
    print("🚀 Iniciando setup de Observabilidade...")
    
    setup = ObservabilitySetup()
    
    # Create configurations
    setup.create_otel_config()
    setup.create_prometheus_config()
    setup.create_alerting_rules()
    setup.create_grafana_dashboards()
    setup.create_docker_compose()
    setup.create_python_instrumentation()
    
    print("\n✅ Setup de observabilidade concluído!")
    print("\n📋 Próximos passos:")
    print("1. Revise as configurações em ./infrastructure/observability")
    print("2. Execute: docker-compose -f infrastructure/observability/docker-compose.observability.yml up -d")
    print("3. Acesse:")
    print("   - Grafana: http://localhost:3000 (admin/admin)")
    print("   - Prometheus: http://localhost:9090")
    print("   - Jaeger: http://localhost:16686")
    print("4. Adicione o código de instrumentação ao seu app")
    
    print("\n🎯 Metas de observabilidade:")
    print("- Cobertura de traces: 95%")
    print("- Métricas customizadas: Implementadas")
    print("- Alertas configurados: 5 críticos")
    print("- Dashboards: Performance + Security")


if __name__ == "__main__":
    main()