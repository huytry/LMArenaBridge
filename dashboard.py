import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import threading
import time

from session_manager import session_manager, SessionMode, SessionStatus

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class CreateSessionRequest(BaseModel):
    name: str
    mode: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    battle_target: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    battle_target: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    session_id: str
    message_id: str
    name: str
    mode: str
    battle_target: Optional[str]
    created_at: str
    last_activity: str
    status: str
    request_count: int
    error_count: int
    last_error: Optional[str]
    metadata: Dict[str, Any]

class StatsResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    error_sessions: int
    total_requests: int
    total_errors: int
    error_rate: float

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove disconnected clients
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Create FastAPI app
app = FastAPI(title="LMArena Session Dashboard", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Helper functions
def session_to_response(session) -> SessionResponse:
    return SessionResponse(
        session_id=session.session_id,
        message_id=session.message_id,
        name=session.name,
        mode=session.mode.value,
        battle_target=session.battle_target,
        created_at=session.created_at.isoformat(),
        last_activity=session.last_activity.isoformat(),
        status=session.status.value,
        request_count=session.request_count,
        error_count=session.error_count,
        last_error=session.last_error,
        metadata=session.metadata
    )

# API Endpoints
@app.get("/")
async def get_dashboard():
    """Serve the main dashboard HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LMArena Session Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            .session-card {
                transition: all 0.3s ease;
            }
            .session-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            .status-active { color: #28a745; }
            .status-error { color: #dc3545; }
            .status-idle { color: #ffc107; }
            .status-disconnected { color: #6c757d; }
            .stats-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .real-time-indicator {
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
                <div class="container-fluid">
                    <span class="navbar-brand">
                        <i class="bi bi-cpu"></i> LMArena Session Dashboard
                        <span class="real-time-indicator ms-2">
                            <i class="bi bi-circle-fill text-success"></i>
                        </span>
                    </span>
                    <div class="navbar-nav ms-auto">
                        <button class="btn btn-outline-light btn-sm" onclick="refreshData()">
                            <i class="bi bi-arrow-clockwise"></i> Refresh
                        </button>
                    </div>
                </div>
            </nav>

            <div class="row mt-3">
                <div class="col-12">
                    <div class="row" id="stats-container">
                        <!-- Stats cards will be populated here -->
                    </div>
                </div>
            </div>

            <div class="row mt-3">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">
                                <i class="bi bi-list-ul"></i> Active Sessions
                            </h5>
                            <button class="btn btn-primary btn-sm" onclick="showCreateSessionModal()">
                                <i class="bi bi-plus-circle"></i> New Session
                            </button>
                        </div>
                        <div class="card-body">
                            <div class="row" id="sessions-container">
                                <!-- Session cards will be populated here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Create Session Modal -->
        <div class="modal fade" id="createSessionModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Create New Session</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="createSessionForm">
                            <div class="mb-3">
                                <label class="form-label">Session Name</label>
                                <input type="text" class="form-control" id="sessionName" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Mode</label>
                                <select class="form-select" id="sessionMode" required>
                                    <option value="direct_chat">Direct Chat</option>
                                    <option value="battle">Battle</option>
                                </select>
                            </div>
                            <div class="mb-3" id="battleTargetGroup" style="display: none;">
                                <label class="form-label">Battle Target</label>
                                <select class="form-select" id="battleTarget">
                                    <option value="A">A</option>
                                    <option value="B">B</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Session ID (Optional)</label>
                                <input type="text" class="form-control" id="sessionId" placeholder="Auto-generated if empty">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Message ID (Optional)</label>
                                <input type="text" class="form-control" id="messageId" placeholder="Auto-generated if empty">
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="createSession()">Create</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Delete Confirmation Modal -->
        <div class="modal fade" id="deleteSessionModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Confirm Delete</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Are you sure you want to delete session "<span id="deleteSessionName"></span>"?</p>
                        <p class="text-danger">This action cannot be undone.</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-danger" onclick="confirmDeleteSession()">Delete</button>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let currentSessionToDelete = null;
            let ws = null;

            // WebSocket connection
            function connectWebSocket() {
                ws = new WebSocket(`ws://${window.location.host}/ws`);
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === 'session_update') {
                        refreshData();
                    }
                };
                ws.onclose = function() {
                    setTimeout(connectWebSocket, 1000);
                };
            }

            // Initialize
            document.addEventListener('DOMContentLoaded', function() {
                connectWebSocket();
                refreshData();
                setInterval(refreshData, 5000); // Refresh every 5 seconds
            });

            // Session mode change handler
            document.getElementById('sessionMode').addEventListener('change', function() {
                const battleGroup = document.getElementById('battleTargetGroup');
                if (this.value === 'battle') {
                    battleGroup.style.display = 'block';
                } else {
                    battleGroup.style.display = 'none';
                }
            });

            async function refreshData() {
                try {
                    const [statsResponse, sessionsResponse] = await Promise.all([
                        fetch('/api/stats'),
                        fetch('/api/sessions')
                    ]);
                    
                    const stats = await statsResponse.json();
                    const sessions = await sessionsResponse.json();
                    
                    updateStats(stats);
                    updateSessions(sessions);
                } catch (error) {
                    console.error('Error refreshing data:', error);
                }
            }

            function updateStats(stats) {
                const container = document.getElementById('stats-container');
                container.innerHTML = `
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.total_sessions}</h3>
                                <p class="mb-0">Total Sessions</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.active_sessions}</h3>
                                <p class="mb-0">Active</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.error_sessions}</h3>
                                <p class="mb-0">Errors</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.total_requests}</h3>
                                <p class="mb-0">Total Requests</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.total_errors}</h3>
                                <p class="mb-0">Total Errors</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>${stats.error_rate.toFixed(1)}%</h3>
                                <p class="mb-0">Error Rate</p>
                            </div>
                        </div>
                    </div>
                `;
            }

            function updateSessions(sessions) {
                const container = document.getElementById('sessions-container');
                if (sessions.length === 0) {
                    container.innerHTML = `
                        <div class="col-12 text-center text-muted">
                            <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                            <p class="mt-3">No sessions found. Create your first session to get started.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = sessions.map(session => `
                    <div class="col-md-6 col-lg-4 mb-3">
                        <div class="card session-card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">${session.name}</h6>
                                <span class="badge bg-${getStatusColor(session.status)}">${session.status}</span>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-6">
                                        <small class="text-muted">Mode:</small><br>
                                        <strong>${session.mode}</strong>
                                    </div>
                                    <div class="col-6">
                                        <small class="text-muted">Requests:</small><br>
                                        <strong>${session.request_count}</strong>
                                    </div>
                                </div>
                                <div class="row mt-2">
                                    <div class="col-6">
                                        <small class="text-muted">Errors:</small><br>
                                        <strong class="text-danger">${session.error_count}</strong>
                                    </div>
                                    <div class="col-6">
                                        <small class="text-muted">Last Activity:</small><br>
                                        <strong>${formatTime(session.last_activity)}</strong>
                                    </div>
                                </div>
                                ${session.battle_target ? `
                                <div class="row mt-2">
                                    <div class="col-12">
                                        <small class="text-muted">Battle Target:</small><br>
                                        <strong>${session.battle_target}</strong>
                                    </div>
                                </div>
                                ` : ''}
                                ${session.last_error ? `
                                <div class="row mt-2">
                                    <div class="col-12">
                                        <small class="text-muted">Last Error:</small><br>
                                        <small class="text-danger">${session.last_error}</small>
                                    </div>
                                </div>
                                ` : ''}
                            </div>
                            <div class="card-footer">
                                <div class="btn-group w-100" role="group">
                                    <button class="btn btn-outline-primary btn-sm" onclick="setDefaultSession('${session.session_id}')">
                                        <i class="bi bi-star"></i> Set Default
                                    </button>
                                    <button class="btn btn-outline-danger btn-sm" onclick="deleteSession('${session.session_id}', '${session.name}')">
                                        <i class="bi bi-trash"></i> Delete
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            function getStatusColor(status) {
                switch (status) {
                    case 'active': return 'success';
                    case 'error': return 'danger';
                    case 'idle': return 'warning';
                    case 'disconnected': return 'secondary';
                    default: return 'secondary';
                }
            }

            function formatTime(timeStr) {
                const date = new Date(timeStr);
                const now = new Date();
                const diff = now - date;
                
                if (diff < 60000) return 'Just now';
                if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
                if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
                return date.toLocaleDateString();
            }

            function showCreateSessionModal() {
                const modal = new bootstrap.Modal(document.getElementById('createSessionModal'));
                modal.show();
            }

            async function createSession() {
                const formData = {
                    name: document.getElementById('sessionName').value,
                    mode: document.getElementById('sessionMode').value,
                    session_id: document.getElementById('sessionId').value || null,
                    message_id: document.getElementById('messageId').value || null,
                    battle_target: document.getElementById('sessionMode').value === 'battle' ? 
                        document.getElementById('battleTarget').value : null
                };

                try {
                    const response = await fetch('/api/sessions', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(formData)
                    });

                    if (response.ok) {
                        bootstrap.Modal.getInstance(document.getElementById('createSessionModal')).hide();
                        document.getElementById('createSessionForm').reset();
                        refreshData();
                    } else {
                        const error = await response.json();
                        alert('Error creating session: ' + error.detail);
                    }
                } catch (error) {
                    alert('Error creating session: ' + error.message);
                }
            }

            async function setDefaultSession(sessionId) {
                try {
                    const response = await fetch(`/api/sessions/${sessionId}/default`, {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        refreshData();
                    } else {
                        alert('Error setting default session');
                    }
                } catch (error) {
                    alert('Error setting default session: ' + error.message);
                }
            }

            function deleteSession(sessionId, sessionName) {
                currentSessionToDelete = sessionId;
                document.getElementById('deleteSessionName').textContent = sessionName;
                const modal = new bootstrap.Modal(document.getElementById('deleteSessionModal'));
                modal.show();
            }

            async function confirmDeleteSession() {
                if (!currentSessionToDelete) return;

                try {
                    const response = await fetch(`/api/sessions/${currentSessionToDelete}`, {
                        method: 'DELETE'
                    });
                    
                    if (response.ok) {
                        bootstrap.Modal.getInstance(document.getElementById('deleteSessionModal')).hide();
                        currentSessionToDelete = null;
                        refreshData();
                    } else {
                        alert('Error deleting session');
                    }
                } catch (error) {
                    alert('Error deleting session: ' + error.message);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/stats")
async def get_stats() -> StatsResponse:
    """Get session statistics."""
    stats = session_manager.get_session_stats()
    return StatsResponse(**stats)

@app.get("/api/sessions")
async def get_sessions() -> List[SessionResponse]:
    """Get all sessions."""
    sessions = session_manager.list_sessions()
    return [session_to_response(session) for session in sessions]

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> SessionResponse:
    """Get a specific session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_to_response(session)

@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    """Create a new session."""
    try {
        mode = SessionMode(request.mode)
        session = session_manager.create_session(
            name=request.name,
            mode=mode,
            session_id=request.session_id,
            message_id=request.message_id,
            battle_target=request.battle_target,
            metadata=request.metadata
        )
        
        # Broadcast update to WebSocket clients
        await manager.broadcast(json.dumps({
            "type": "session_update",
            "action": "created",
            "session_id": session.session_id
        }))
        
        return session_to_response(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Broadcast update to WebSocket clients
    await manager.broadcast(json.dumps({
        "type": "session_update",
        "action": "deleted",
        "session_id": session_id
    }))
    
    return {"message": "Session deleted successfully"}

@app.post("/api/sessions/{session_id}/default")
async def set_default_session(session_id: str):
    """Set a session as default."""
    success = session_manager.set_default_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Broadcast update to WebSocket clients
    await manager.broadcast(json.dumps({
        "type": "session_update",
        "action": "default_changed",
        "session_id": session_id
    }))
    
    return {"message": "Default session updated successfully"}

@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str):
    """Export session data for external use."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    export_data = {
        "session_id": session.session_id,
        "message_id": session.message_id,
        "mode": session.mode.value
    }
    if session.battle_target:
        export_data["battle_target"] = session.battle_target
    
    return export_data

@app.post("/api/sessions/import")
async def import_sessions(model_endpoint_map: Dict[str, Any]):
    """Import sessions from model_endpoint_map.json format."""
    try {
        session_manager.import_from_model_endpoint_map(model_endpoint_map)
        
        # Broadcast update to WebSocket clients
        await manager.broadcast(json.dumps({
            "type": "session_update",
            "action": "imported"
        }))
        
        return {"message": "Sessions imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/sessions/cleanup")
async def cleanup_sessions(max_idle_hours: int = 24):
    """Clean up idle sessions."""
    session_manager.cleanup_idle_sessions(max_idle_hours)
    
    # Broadcast update to WebSocket clients
    await manager.broadcast(json.dumps({
        "type": "session_update",
        "action": "cleanup"
    }))
    
    return {"message": "Cleanup completed"}

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)