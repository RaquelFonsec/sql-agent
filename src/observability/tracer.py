
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

# Configuração do provedor de trace com identificação do serviço
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create({"service.name": "sql-agent"})
    )
)

# Cria o tracer global
tracer = trace.get_tracer(__name__)

# Exportador para console (exibe spans no terminal)
console_exporter = ConsoleSpanExporter()
span_processor = SimpleSpanProcessor(console_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


class ObservabilityTracer:
    """Classe para observabilidade e logging estruturado"""
    def __init__(self):
        self.tracer = tracer
        self.logs = []

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        return self.tracer.start_as_current_span(name, attributes=attributes or {})

    def log_interaction(self, stage: str, data: Dict[str, Any]):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'stage': stage,
            'data': data
        }
        self.logs.append(log_entry)
        logger.info(f"[{stage}] {json.dumps(data, indent=2)}")

    def log_error(self, stage: str, error: Exception):
        error_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'stage': stage,
            'error': str(error),
            'error_type': type(error).__name__
        }
        self.logs.append(error_entry)
        logger.error(f"[{stage}] Error: {error}")

    def get_logs(self):
        return self.logs

    def clear_logs(self):
        self.logs = []


tracer = ObservabilityTracer()
