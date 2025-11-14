from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MCPContext:
    """Model Context Protocol - contexto compartilhado entre agentes"""
    
    user_id: str
    session_id: str
    original_question: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    schema_context: Optional[str] = None
    conversation_history: list = field(default_factory=list)
    
    parsed_intent: Optional[Dict[str, Any]] = None
    generated_sql: Optional[str] = None
    validation_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Any] = None
    formatted_response: Optional[str] = None
    
    errors: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, stage: str, error: str):
        self.errors.append({
            'stage': stage,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'original_question': self.original_question,
            'timestamp': self.timestamp.isoformat(),
            'parsed_intent': self.parsed_intent,
            'generated_sql': self.generated_sql,
            'validation_result': self.validation_result,
            'execution_result': self.execution_result,
            'formatted_response': self.formatted_response,
            'errors': self.errors,
            'metadata': self.metadata
        }