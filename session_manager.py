import json
import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)

class SessionStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    DISCONNECTED = "disconnected"

class SessionMode(Enum):
    DIRECT_CHAT = "direct_chat"
    BATTLE = "battle"

@dataclass
class SessionInfo:
    session_id: str
    message_id: str
    name: str
    mode: SessionMode
    battle_target: Optional[str] = None
    created_at: datetime = None
    last_activity: datetime = None
    status: SessionStatus = SessionStatus.ACTIVE
    request_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_activity is None:
            self.last_activity = datetime.now()
        if self.metadata is None:
            self.metadata = {}

class SessionManager:
    def __init__(self, config_file: str = "session_config.json"):
        self.config_file = config_file
        self.sessions: Dict[str, SessionInfo] = {}
        self.default_session: Optional[str] = None
        self.lock = threading.RLock()
        self.load_sessions()
        
    def load_sessions(self):
        """Load sessions from configuration file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.default_session = data.get('default_session')
                
                for session_data in data.get('sessions', []):
                    session = SessionInfo(
                        session_id=session_data['session_id'],
                        message_id=session_data['message_id'],
                        name=session_data['name'],
                        mode=SessionMode(session_data['mode']),
                        battle_target=session_data.get('battle_target'),
                        created_at=datetime.fromisoformat(session_data['created_at']),
                        last_activity=datetime.fromisoformat(session_data['last_activity']),
                        status=SessionStatus(session_data['status']),
                        request_count=session_data.get('request_count', 0),
                        error_count=session_data.get('error_count', 0),
                        last_error=session_data.get('last_error'),
                        metadata=session_data.get('metadata', {})
                    )
                    self.sessions[session.session_id] = session
                    
            logger.info(f"Loaded {len(self.sessions)} sessions from configuration")
        except FileNotFoundError:
            logger.info("No session configuration file found, starting with empty sessions")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    def save_sessions(self):
        """Save sessions to configuration file."""
        try:
            with self.lock:
                data = {
                    'default_session': self.default_session,
                    'sessions': [
                        {
                            'session_id': session.session_id,
                            'message_id': session.message_id,
                            'name': session.name,
                            'mode': session.mode.value,
                            'battle_target': session.battle_target,
                            'created_at': session.created_at.isoformat(),
                            'last_activity': session.last_activity.isoformat(),
                            'status': session.status.value,
                            'request_count': session.request_count,
                            'error_count': session.error_count,
                            'last_error': session.last_error,
                            'metadata': session.metadata
                        }
                        for session in self.sessions.values()
                    ]
                }
                
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    def create_session(self, name: str, mode: SessionMode, 
                      session_id: Optional[str] = None, 
                      message_id: Optional[str] = None,
                      battle_target: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> SessionInfo:
        """Create a new session."""
        with self.lock:
            if session_id is None:
                session_id = str(uuid.uuid4())
            if message_id is None:
                message_id = str(uuid.uuid4())
            
            session = SessionInfo(
                session_id=session_id,
                message_id=message_id,
                name=name,
                mode=mode,
                battle_target=battle_target,
                metadata=metadata or {}
            )
            
            self.sessions[session_id] = session
            
            # Set as default if it's the first session
            if self.default_session is None:
                self.default_session = session_id
                
            self.save_sessions()
            logger.info(f"Created new session: {name} ({session_id})")
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self.lock:
            if session_id not in self.sessions:
                return False
                
            session = self.sessions.pop(session_id)
            
            # If this was the default session, set a new default
            if self.default_session == session_id:
                self.default_session = next(iter(self.sessions.keys()), None)
                
            self.save_sessions()
            logger.info(f"Deleted session: {session.name} ({session_id})")
            return True
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get a session by ID."""
        with self.lock:
            return self.sessions.get(session_id)
    
    def get_default_session(self) -> Optional[SessionInfo]:
        """Get the default session."""
        with self.lock:
            if self.default_session:
                return self.sessions.get(self.default_session)
            return None
    
    def set_default_session(self, session_id: str) -> bool:
        """Set the default session."""
        with self.lock:
            if session_id not in self.sessions:
                return False
            self.default_session = session_id
            self.save_sessions()
            logger.info(f"Set default session to: {session_id}")
            return True
    
    def list_sessions(self) -> List[SessionInfo]:
        """List all sessions."""
        with self.lock:
            return list(self.sessions.values())
    
    def update_session_activity(self, session_id: str, success: bool = True, error_message: Optional[str] = None):
        """Update session activity and statistics."""
        with self.lock:
            if session_id not in self.sessions:
                return
                
            session = self.sessions[session_id]
            session.last_activity = datetime.now()
            session.request_count += 1
            
            if not success:
                session.error_count += 1
                session.last_error = error_message
                session.status = SessionStatus.ERROR
            else:
                session.status = SessionStatus.ACTIVE
                
            self.save_sessions()
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get overall session statistics."""
        with self.lock:
            total_sessions = len(self.sessions)
            active_sessions = sum(1 for s in self.sessions.values() if s.status == SessionStatus.ACTIVE)
            error_sessions = sum(1 for s in self.sessions.values() if s.status == SessionStatus.ERROR)
            total_requests = sum(s.request_count for s in self.sessions.values())
            total_errors = sum(s.error_count for s in self.sessions.values())
            
            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'error_sessions': error_sessions,
                'total_requests': total_requests,
                'total_errors': total_errors,
                'error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0
            }
    
    def cleanup_idle_sessions(self, max_idle_hours: int = 24):
        """Remove sessions that have been idle for too long."""
        cutoff_time = datetime.now() - timedelta(hours=max_idle_hours)
        sessions_to_remove = []
        
        with self.lock:
            for session_id, session in self.sessions.items():
                if session.last_activity < cutoff_time:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                self.delete_session(session_id)
                
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} idle sessions")
    
    def export_sessions(self) -> Dict[str, Any]:
        """Export sessions for external use (e.g., model_endpoint_map.json format)."""
        with self.lock:
            export_data = {}
            for session in self.sessions.values():
                session_data = {
                    'session_id': session.session_id,
                    'message_id': session.message_id,
                    'mode': session.mode.value
                }
                if session.battle_target:
                    session_data['battle_target'] = session.battle_target
                    
                # Group by session name for model mapping
                if session.name not in export_data:
                    export_data[session.name] = []
                export_data[session.name].append(session_data)
                
            return export_data
    
    def import_from_model_endpoint_map(self, model_endpoint_map: Dict[str, Any]):
        """Import sessions from model_endpoint_map.json format."""
        with self.lock:
            for model_name, mappings in model_endpoint_map.items():
                if isinstance(mappings, list):
                    for mapping in mappings:
                        self.create_session(
                            name=f"{model_name}_{mapping.get('mode', 'default')}",
                            mode=SessionMode(mapping.get('mode', 'direct_chat')),
                            session_id=mapping.get('session_id'),
                            message_id=mapping.get('message_id'),
                            battle_target=mapping.get('battle_target'),
                            metadata={'model_name': model_name, 'imported': True}
                        )
                elif isinstance(mappings, dict):
                    self.create_session(
                        name=f"{model_name}_{mappings.get('mode', 'default')}",
                        mode=SessionMode(mappings.get('mode', 'direct_chat')),
                        session_id=mappings.get('session_id'),
                        message_id=mappings.get('message_id'),
                        battle_target=mappings.get('battle_target'),
                        metadata={'model_name': model_name, 'imported': True}
                    )

# Global session manager instance
session_manager = SessionManager()