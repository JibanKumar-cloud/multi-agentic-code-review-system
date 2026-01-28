"""
Streaming server for the code review system.
Provides WebSocket and SSE endpoints for real-time event streaming.
"""

import asyncio
import json
import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ..events import EventBus, event_bus as global_event_bus
from ..agents.code_review_workflow import CodeReviewWorkflow

from ..config import config

logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).parent
STATIC_DIR = CURRENT_DIR.parent.parent / "static"


def create_app(event_bus: Optional[EventBus] = None) -> FastAPI:
    app = FastAPI(title="Multi-Agent Code Review System", version="1.0.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    bus = event_bus or global_event_bus
    active_reviews = {}
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = STATIC_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text())
        return HTMLResponse(content=get_embedded_html())
    
    @app.websocket("/ws/review")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        bus.register_websocket(websocket)
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "start_review":
                    code = data.get("code", "")
                    filename = data.get("filename", "code.py")
                    
                    if code:
                        task = asyncio.create_task(run_review(code, filename, bus))
                        review_id = id(task)
                        active_reviews[review_id] = task
                        await websocket.send_json({"type": "review_accepted", "review_id": str(review_id)})
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            bus.unregister_websocket(websocket)
    
    @app.get("/stream/events")
    async def sse_endpoint(request: Request):
        async def event_generator():
            queue = asyncio.Queue()
            async def handler(event): await queue.put(event)
            bus.subscribe("*", handler)
            try:
                while True:
                    if await request.is_disconnected(): break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(event.to_dict())}\n\n"
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
            finally:
                bus.unsubscribe("*", handler)
        return StreamingResponse(event_generator(), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
    
    @app.post("/api/review")
    async def start_review(code: str = Form(...), filename: str = Form("code.py")):
        task = asyncio.create_task(run_review(code, filename, bus))
        return JSONResponse({"status": "started", "review_id": str(id(task))})
    
    @app.post("/api/review/sync")
    async def sync_review(code: str = Form(...), filename: str = Form("code.py")):
        return JSONResponse(await run_review(code, filename, bus))
    
    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "version": "1.0.0"}
    
    return app


async def run_review(code: str, filename: str, event_bus: EventBus) -> dict:
    try:
        config.validate()
        orchestrator = CodeReviewWorkflow(event_bus)
        return await orchestrator.review_code(code, filename)

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


def get_embedded_html() -> str:
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Agent Code Review System</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid #30363d;
        }
        h1 { font-size: 24px; color: #f0f6fc; }
        .status-badge { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .status-connected { background: #238636; color: white; }
        .status-disconnected { background: #da3633; color: white; }
        
        .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .full-width { grid-column: 1 / -1; }
        
        .panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }
        .panel-header {
            background: #21262d;
            padding: 12px 16px;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
        }
        .panel-body { padding: 16px; }
        
        textarea {
            width: 100%;
            height: 150px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #c9d1d9;
            padding: 12px;
            font-family: monospace;
            font-size: 13px;
            resize: vertical;
        }
        textarea:focus { outline: none; border-color: #58a6ff; }
        
        button {
            background: #238636;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 12px;
        }
        button:hover { background: #2ea043; }
        button:disabled { background: #21262d; cursor: not-allowed; }
        
        .agents-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        .agent-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }
        .agent-name { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; font-weight: 600; }
        .agent-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
        .status-idle { background: #21262d; color: #8b949e; }
        .status-running { background: #1f6feb; color: white; }
        .status-completed { background: #238636; color: white; }
        .status-error { background: #da3633; color: white; }
        
        /* Execution Plan */
        .plan-steps { display: flex; flex-direction: column; gap: 8px; }
        .plan-step { 
            background: #21262d; 
            padding: 10px 14px; 
            border-radius: 6px; 
            font-size: 13px; 
            border-left: 3px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .plan-step-main { flex: 1; }
        .plan-step-details { font-size: 11px; color: #8b949e; margin-top: 2px; }
        .step-pending { border-left-color: #8b949e; }
        .step-running { border-left-color: #1f6feb; background: #1f6feb22; }
        .step-completed { border-left-color: #238636; }
        .step-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: #30363d; }
        
        /* Agent Activity Sections */
        .activity-container { max-height: 350px; overflow-y: auto; }
        .agent-activity-section { margin-bottom: 12px; }
        .agent-activity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: #21262d;
            border-radius: 6px 6px 0 0;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
        }
        .agent-activity-header:hover { background: #30363d; }
        .agent-activity-header.security { border-left: 3px solid #da3633; }
        .agent-activity-header.bug { border-left: 3px solid #f0883e; }
        .agent-activity-header.coordinator { border-left: 3px solid #58a6ff; }
        .agent-activity-list {
            background: #0d1117;
            border: 1px solid #30363d;
            border-top: none;
            border-radius: 0 0 6px 6px;
            max-height: 200px;
            overflow-y: auto;
            display: none;
        }
        .agent-activity-list.expanded { display: block; }
        .activity-item {
            padding: 10px 12px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .activity-tool { color: #f0883e; font-weight: 600; }
        .activity-purpose { color: #8b949e; font-style: italic; }
        .activity-count { font-size: 11px; color: #8b949e; font-weight: normal; }
        .agent-mode { 
            font-size: 11px; 
            font-weight: normal;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
        }
        .agent-mode.thinking { background: #8957e5; color: white; }
        .agent-mode.streaming { background: #238636; color: white; }
        .thinking-activity { background: rgba(137, 87, 229, 0.1); }
        .thinking-activity .activity-tool { color: #a371f7; }
        .completed-activity { background: rgba(35, 134, 54, 0.1); }
        .completed-activity .activity-tool { color: #3fb950; }
        
        /* Findings */
        .findings-container { max-height: 600px; overflow-y: auto; }
        .severity-section { margin-bottom: 12px; }
        .severity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: #21262d;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 8px;
        }
        .severity-header:hover { background: #30363d; }
        .severity-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
        .severity-count { background: #0d1117; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        .severity-critical .severity-header { border-left: 4px solid #da3633; }
        .severity-high .severity-header { border-left: 4px solid #db6d28; }
        .severity-medium .severity-header { border-left: 4px solid #9e6a03; }
        .severity-low .severity-header { border-left: 4px solid #238636; }
        
        .severity-findings { padding-left: 12px; display: none; }
        .severity-findings.expanded { display: block; }
        
        .finding { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-bottom: 10px; }
        .finding-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
        .finding-title { font-weight: 600; color: #f0f6fc; font-size: 14px; }
        .severity-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
        .badge-critical { background: #da3633; color: white; }
        .badge-high { background: #db6d28; color: white; }
        .badge-medium { background: #9e6a03; color: white; }
        .badge-low { background: #238636; color: white; }
        
        .finding-meta { font-size: 12px; color: #8b949e; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }
        .finding-section { margin-bottom: 12px; }
        .finding-section-title { font-size: 11px; font-weight: 600; color: #58a6ff; margin-bottom: 6px; text-transform: uppercase; }
        .finding-section-content { font-size: 13px; line-height: 1.5; color: #c9d1d9; }
        .code-block { background: #161b22; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-top: 4px; border: 1px solid #30363d; white-space: pre-wrap; }
        .code-block.error-code { border-left: 3px solid #da3633; }
        .code-block.fix-code { border-left: 3px solid #238636; }
        .line-info { font-size: 11px; color: #8b949e; margin-top: 4px; }
        .fix-explanation { margin-bottom: 8px; color: #8b949e; font-style: italic; }
        
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .metric { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; text-align: center; }
        .metric-value { font-size: 28px; font-weight: 700; color: #58a6ff; }
        .metric-label { font-size: 12px; color: #8b949e; margin-top: 4px; }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulsing { animation: pulse 1.5s infinite; }
        .chevron { transition: transform 0.2s; }
        .chevron.expanded { transform: rotate(90deg); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Multi-Agent Code Review System</h1>
            <span id="connectionStatus" class="status-badge status-disconnected">Disconnected</span>
        </header>
        
        <div class="main-grid">
            <div class="panel">
                <div class="panel-header"><span>📝 Code Input</span></div>
                <div class="panel-body">
                    <textarea id="codeInput" placeholder="Paste your Python code here..."></textarea>
                    <button id="analyzeBtn" onclick="startAnalysis()">🚀 Analyze Code</button>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header"><span>🤖 Agent Status</span></div>
                <div class="panel-body">
                    <div class="agents-grid">
                        <div class="agent-card">
                            <div class="agent-name">🎯 Coordinator <span class="agent-status status-idle" id="coordinator-status">Idle</span></div>
                            <div id="coordinator-task" style="font-size: 12px; color: #8b949e;">Waiting...</div>
                        </div>
                        <div class="agent-card">
                            <div class="agent-name">🔒 Security <span class="agent-status status-idle" id="security_agent-status">Idle</span></div>
                            <div id="security_agent-task" style="font-size: 12px; color: #8b949e;">Waiting...</div>
                        </div>
                        <div class="agent-card">
                            <div class="agent-name">🐛 Bug Detection <span class="agent-status status-idle" id="bug_agent-status">Idle</span></div>
                            <div id="bug_agent-task" style="font-size: 12px; color: #8b949e;">Waiting...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="panel full-width">
                <div class="panel-header"><span>📋 Execution Plan</span><span id="planStatus" style="font-size: 12px; color: #8b949e;">Analyzing code...</span></div>
                <div class="panel-body">
                    <div id="planSteps" class="plan-steps">
                        <div style="color: #8b949e; text-align: center; padding: 10px;">Coordinator will analyze code and generate a custom execution plan...</div>
                    </div>
                </div>
            </div>
            
            <div class="panel full-width">
                <div class="panel-header"><span>🧠 Agent Activity</span><span id="activityCount" style="font-size: 12px; color: #8b949e;">0 tool calls</span></div>
                <div class="panel-body">
                    <div id="activityContainer" class="activity-container">
                        <!-- Security Agent Section -->
                        <div class="agent-activity-section" id="section-security_agent" style="display: none;">
                            <div class="agent-activity-header security" onclick="toggleAgentActivity('security_agent')">
                                <span>🔒 Security Agent <span id="mode-security_agent" class="agent-mode"></span></span>
                                <span class="activity-count" id="count-security_agent">0 calls</span>
                            </div>
                            <div class="agent-activity-list expanded" id="list-security_agent"></div>
                        </div>
                        
                        <!-- Bug Agent Section -->
                        <div class="agent-activity-section" id="section-bug_agent" style="display: none;">
                            <div class="agent-activity-header bug" onclick="toggleAgentActivity('bug_agent')">
                                <span>🐛 Bug Detection Agent <span id="mode-bug_agent" class="agent-mode"></span></span>
                                <span class="activity-count" id="count-bug_agent">0 calls</span>
                            </div>
                            <div class="agent-activity-list expanded" id="list-bug_agent"></div>
                        </div>
                        
                        <!-- Coordinator Section -->
                        <div class="agent-activity-section" id="section-coordinator" style="display: none;">
                            <div class="agent-activity-header coordinator" onclick="toggleAgentActivity('coordinator')">
                                <span>🎯 Coordinator <span id="mode-coordinator" class="agent-mode"></span></span>
                                <span class="activity-count" id="count-coordinator">0 calls</span>
                            </div>
                            <div class="agent-activity-list expanded" id="list-coordinator"></div>
                        </div>
                        
                        <div id="noActivity" style="color: #8b949e; text-align: center; padding: 20px;">Tool calls will appear here grouped by agent...</div>
                    </div>
                </div>
            </div>
            
            <div class="panel full-width">
                <div class="panel-header"><span>🔎 Findings</span><span id="findingsCount" style="font-size: 12px; color: #8b949e;">0 findings</span></div>
                <div class="panel-body">
                    <div id="findingsContainer" class="findings-container">
                        <div class="severity-section severity-critical" id="section-critical" style="display: none;">
                            <div class="severity-header" onclick="toggleSeverity('critical')">
                                <div class="severity-title"><span class="chevron" id="chevron-critical">▶</span> 🔴 Critical</div>
                                <span class="severity-count" id="count-critical">0</span>
                            </div>
                            <div class="severity-findings" id="findings-critical"></div>
                        </div>
                        <div class="severity-section severity-high" id="section-high" style="display: none;">
                            <div class="severity-header" onclick="toggleSeverity('high')">
                                <div class="severity-title"><span class="chevron" id="chevron-high">▶</span> 🟠 High</div>
                                <span class="severity-count" id="count-high">0</span>
                            </div>
                            <div class="severity-findings" id="findings-high"></div>
                        </div>
                        <div class="severity-section severity-medium" id="section-medium" style="display: none;">
                            <div class="severity-header" onclick="toggleSeverity('medium')">
                                <div class="severity-title"><span class="chevron" id="chevron-medium">▶</span> 🟡 Medium</div>
                                <span class="severity-count" id="count-medium">0</span>
                            </div>
                            <div class="severity-findings" id="findings-medium"></div>
                        </div>
                        <div class="severity-section severity-low" id="section-low" style="display: none;">
                            <div class="severity-header" onclick="toggleSeverity('low')">
                                <div class="severity-title"><span class="chevron" id="chevron-low">▶</span> 🟢 Low</div>
                                <span class="severity-count" id="count-low">0</span>
                            </div>
                            <div class="severity-findings" id="findings-low"></div>
                        </div>
                        <div id="noFindings" style="color: #8b949e; text-align: center; padding: 20px;">Findings will be grouped by severity...</div>
                    </div>
                </div>
            </div>
            
            <div class="panel full-width">
                <div class="panel-header"><span>📊 Metrics</span></div>
                <div class="panel-body">
                    <div class="metrics-grid">
                        <div class="metric"><div class="metric-value" id="metricTotal">0</div><div class="metric-label">Total Findings</div></div>
                        <div class="metric"><div class="metric-value" id="metricCritical" style="color: #da3633;">0</div><div class="metric-label">Critical</div></div>
                        <div class="metric"><div class="metric-value" id="metricHigh" style="color: #db6d28;">0</div><div class="metric-label">High</div></div>
                        <div class="metric"><div class="metric-value" id="metricFixes" style="color: #238636;">0</div><div class="metric-label">Fixes Proposed</div></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let ws = null;
        let findingsCount = 0;
        let fixesCount = 0;
        let totalToolCalls = 0;
        const planSteps = {};
        const severityCounts = { critical: 0, high: 0, medium: 0, low: 0 };
        const agentToolCounts = { security_agent: 0, bug_agent: 0, coordinator: 0 };
        
        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws/review`);
            ws.onopen = () => {
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').className = 'status-badge status-connected';
            };
            ws.onclose = () => {
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                document.getElementById('connectionStatus').className = 'status-badge status-disconnected';
                setTimeout(connect, 2000);
            };
            ws.onmessage = (event) => handleEvent(JSON.parse(event.data));
        }
        
        function startAnalysis() {
            const code = document.getElementById('codeInput').value;
            if (!code.trim()) { alert('Please enter code'); return; }
            resetUI();
            ws.send(JSON.stringify({ type: 'start_review', code: code, filename: 'code.py' }));
            document.getElementById('analyzeBtn').disabled = true;
            document.getElementById('analyzeBtn').textContent = '⏳ Analyzing...';
        }
        
        function resetUI() {
            findingsCount = fixesCount = totalToolCalls = 0;
            severityCounts.critical = severityCounts.high = severityCounts.medium = severityCounts.low = 0;
            agentToolCounts.security_agent = agentToolCounts.bug_agent = agentToolCounts.coordinator = 0;
            
            document.getElementById('activityCount').textContent = '0 tool calls';
            document.getElementById('findingsCount').textContent = '0 findings';
            document.getElementById('metricTotal').textContent = '0';
            document.getElementById('metricCritical').textContent = '0';
            document.getElementById('metricHigh').textContent = '0';
            document.getElementById('metricFixes').textContent = '0';
            
            ['critical', 'high', 'medium', 'low'].forEach(sev => {
                document.getElementById(`section-${sev}`).style.display = 'none';
                document.getElementById(`count-${sev}`).textContent = '0';
                document.getElementById(`findings-${sev}`).innerHTML = '';
            });
            document.getElementById('noFindings').style.display = 'block';
            
            ['security_agent', 'bug_agent', 'coordinator'].forEach(agent => {
                document.getElementById(`section-${agent}`).style.display = 'none';
                document.getElementById(`count-${agent}`).textContent = '0 calls';
                document.getElementById(`list-${agent}`).innerHTML = '';
            });
            document.getElementById('noActivity').style.display = 'block';
            
            document.getElementById('planSteps').innerHTML = '<div style="color: #8b949e; text-align: center; padding: 10px;">Coordinator will analyze code and generate a custom execution plan...</div>';
            document.getElementById('planStatus').textContent = 'Analyzing code...';
            
            ['coordinator', 'security_agent', 'bug_agent'].forEach(agent => {
                const s = document.getElementById(`${agent}-status`);
                if (s) { s.textContent = 'Idle'; s.className = 'agent-status status-idle'; }
            });
        }
        
        function handleEvent(msg) {
            console.log(msg)
            if (['review_accepted', 'keepalive', 'pong'].includes(msg.type)) return;
            const eventType = msg.event_type || msg.type;
            const data = msg.data || msg;
            const agentId = msg.agent_id || 'coordinator';
            
            // Debug: log tool events
            if (eventType === 'tool_call_start') {
                console.log('Tool call:', agentId, data.tool_name);
            }
            
            switch (eventType) {
                case 'agent_started':
                    updateAgentStatus(agentId, 'running', data.task);
                    break;
                case 'agent_completed':
                    updateAgentStatus(agentId, data.success ? 'completed' : 'error', null);
                    updateAgentMode(agentId, '');  // Clear mode when completed
                    showCompleted(agentId, data.summary);  // Show completed in Agent Activity with summary
                    if (agentId === 'coordinator') {
                        document.getElementById('analyzeBtn').disabled = false;
                        document.getElementById('analyzeBtn').textContent = '🚀 Analyze Code';
                    }
                    break;
                case 'mode_changed':
                    // Show mode in Agent Activity header
                    const mode = data.mode;
                    console.log('Mode changed:', agentId, mode);
                    updateAgentMode(agentId, mode);
                    if (mode === 'thinking') {
                        showThinking(agentId);  // Show thinking in Agent Activity
                    }
                    break;
                case 'thinking':
                    // Legacy thinking event - just update status
                    updateAgentStatus(agentId, 'running', null);
                    break;
                case 'thinking_complete':
                    // Clear thinking mode when complete
                    updateAgentMode(agentId, '');
                    break;
                case 'tool_call_start':
                    // Show Streaming when making tool calls
                    updateAgentMode(agentId, 'streaming');
                    addToolCall(agentId, data);
                    break;
                case 'tool_call_result':
                    updateToolResult(data.tool_call_id, data.success, data.output);
                    break;
                case 'finding_discovered':
                    addFinding(data);
                    break;
                case 'fix_proposed':
                    updateFindingWithFix(data.finding_id, data);
                    fixesCount++;
                    document.getElementById('metricFixes').textContent = fixesCount;
                    break;
                case 'plan_created':
                    showPlan(data.steps);
                    break;
                case 'plan_step_started':
                    updatePlanStep(data.step_id, 'running');
                    break;
                case 'plan_step_completed':
                    updatePlanStep(data.step_id, data.success ? 'completed' : 'error');
                    break;
                case 'findings_consolidated':
                    console.log(findingsCount)
                    console.log(data.total_findings)
                    document.getElementById('metricTotal').textContent = data.total_findings || findingsCount;
                    break;
            }
        }
        
        function updateAgentStatus(agentId, status, task) {
            const s = document.getElementById(`${agentId}-status`);
            const t = document.getElementById(`${agentId}-task`);
            if (s) {
                s.textContent = status.charAt(0).toUpperCase() + status.slice(1);
                s.className = `agent-status status-${status}`;
                if (status === 'running') s.classList.add('pulsing');
                // Clear mode when completed
                if (status === 'completed' || status === 'idle') {
                    updateAgentMode(agentId, '');
                }
            }
            if (t && task) t.textContent = String(task).substring(0, 50);
        }
        
        function updateAgentMode(agentId, mode) {
            // Update mode in Agent Activity header
            const m = document.getElementById(`mode-${agentId}`);
            if (m) {
                m.className = 'agent-mode';
                if (mode === 'thinking') {
                    m.textContent = '🧠 Thinking';
                    m.classList.add('thinking');
                } else if (mode === 'streaming') {
                    m.textContent = '⚡ Streaming';
                    m.classList.add('streaming');
                } else {
                    m.textContent = '';
                }
            }
        }
        
        function toggleAgentActivity(agentId) {
            const list = document.getElementById(`list-${agentId}`);
            list.classList.toggle('expanded');
        }
        
        function showThinking(agentId) {
            const section = document.getElementById(`section-${agentId}`);
            const list = document.getElementById(`list-${agentId}`);
            
            if (!section || !list) return;
            
            document.getElementById('noActivity').style.display = 'none';
            section.style.display = 'block';
            
            // Show thinking indicator in the activity list (prepend, don't replace)
            const existingThinking = list.querySelector('.thinking-activity');
            if (!existingThinking) {
                const thinkingDiv = document.createElement('div');
                thinkingDiv.className = 'activity-item thinking-activity';
                thinkingDiv.innerHTML = `
                    <span class="activity-tool">🧠 Thinking...</span>
                    <span class="activity-purpose">Deep analysis in progress</span>
                `;
                list.insertBefore(thinkingDiv, list.firstChild);
            }
        }
        
        function showCompleted(agentId, summary) {
            const list = document.getElementById(`list-${agentId}`);
            if (!list) return;
            
            // Remove thinking indicator
            const thinkingEl = list.querySelector('.thinking-activity');
            if (thinkingEl) {
                thinkingEl.remove();
            }
            
            // Get task description based on agent
            let taskDesc = 'Analysis finished';
            if (agentId === 'coordinator') {
                taskDesc = 'Creating execution plan';
            } else if (agentId === 'security_agent') {
                taskDesc = 'Security vulnerability analysis';
            } else if (agentId === 'bug_agent') {
                taskDesc = 'Bug detection analysis';
            }
            
            // Create completed item
            const completedDiv = document.createElement('div');
            completedDiv.className = 'activity-item completed-activity';
            completedDiv.innerHTML = `
                <span class="activity-tool">✅ Completed</span>
                <span class="activity-purpose">${taskDesc}${summary ? ' - ' + summary : ''}</span>
            `;
            
            // Add at the end of the list (after tool calls)
            list.appendChild(completedDiv);
        }
        
        function addToolCall(agentId, data) {
            const section = document.getElementById(`section-${agentId}`);
            const list = document.getElementById(`list-${agentId}`);
            const countEl = document.getElementById(`count-${agentId}`);
            
            if (!section || !list) return;
            
            // Update agent status to Running when we see tool calls
            updateAgentStatus(agentId, 'running', null);
            
            document.getElementById('noActivity').style.display = 'none';
            section.style.display = 'block';
            
            totalToolCalls++;
            agentToolCounts[agentId] = (agentToolCounts[agentId] || 0) + 1;
            
            document.getElementById('activityCount').textContent = `${totalToolCalls} tool calls`;
            if (countEl) countEl.textContent = `${agentToolCounts[agentId]} calls`;
            
            // Brief 3-4 word purpose only
            const toolName = data.tool_name;
            let purpose = '';
            
            switch(toolName) {
                case 'search_pattern': purpose = 'Searching patterns'; break;
                case 'find_function_calls': purpose = 'Finding function calls'; break;
                case 'parse_ast': purpose = 'Parsing code'; break;
                case 'check_syntax': purpose = 'Checking syntax'; break;
                case 'analyze_imports': purpose = 'Analyzing imports'; break;
                case 'extract_strings': purpose = 'Finding secrets'; break;
                case 'get_line_context': purpose = 'Getting context'; break;
                case 'verify_fix': purpose = 'Verifying fix'; break;
                case 'execute_code': purpose = 'Executing code'; break;
                default: purpose = 'Processing...';
            }
            
            // Overwrite - show only current tool with brief purpose
            list.innerHTML = `
                <div class="activity-item">
                    <span class="activity-tool">🔧 ${toolName}</span>
                    <span class="activity-purpose">${purpose}</span>
                </div>
            `;
        }
        
        function updateToolResult(toolCallId, success, output) {
            // No-op: we don't show results anymore
        }
        
        function toggleSeverity(sev) {
            const f = document.getElementById(`findings-${sev}`);
            const c = document.getElementById(`chevron-${sev}`);
            f.classList.toggle('expanded');
            c.classList.toggle('expanded');
        }
        
        function addFinding(finding) {
            findingsCount++;
            document.getElementById('findingsCount').textContent = `${findingsCount} findings`;
            document.getElementById('metricTotal').textContent = findingsCount;
            document.getElementById('noFindings').style.display = 'none';
            
            const severity = (finding.severity || 'medium').toLowerCase();
            const findingId = finding.finding_id || `finding-${findingsCount}`;
            
            severityCounts[severity]++;
            document.getElementById(`count-${severity}`).textContent = severityCounts[severity];
            document.getElementById(`section-${severity}`).style.display = 'block';
            
            if (severity === 'critical') document.getElementById('metricCritical').textContent = severityCounts.critical;
            if (severity === 'high') document.getElementById('metricHigh').textContent = severityCounts.high;
            
            const container = document.getElementById(`findings-${severity}`);
            const div = document.createElement('div');
            div.className = 'finding';
            div.id = `finding-${findingId}`;
            
            div.innerHTML = `
                <div class="finding-header">
                    <div class="finding-title">${escapeHtml(finding.title || 'Finding')}</div>
                    <span class="severity-badge badge-${severity}">${severity.toUpperCase()}</span>
                </div>
                <div class="finding-meta">${finding.category || 'Unknown'} | Line ${finding.location?.line_start || '?'}</div>
                <div class="finding-section">
                    <div class="finding-section-title">📋 REASON</div>
                    <div class="finding-section-content">${escapeHtml(finding.description || 'No description')}</div>
                </div>
                <div class="finding-section">
                    <div class="finding-section-title">❌ ERROR CODE</div>
                    <div class="finding-section-content">
                        ${finding.location?.code_snippet ? `<div class="code-block error-code">${escapeHtml(finding.location.code_snippet)}</div>` : '<em>No snippet</em>'}
                        <div class="line-info">Line ${finding.location?.line_start || '?'}</div>
                    </div>
                </div>
                <div class="finding-section">
                    <div class="finding-section-title">✅ SUGGESTED FIX</div>
                    <div class="finding-section-content" id="fix-content-${findingId}"><em style="color: #8b949e;">Waiting for fix...</em></div>
                </div>
            `;
            container.appendChild(div);
            if (severityCounts[severity] === 1) toggleSeverity(severity);
        }
        
        function updateFindingWithFix(findingId, fix) {
            const el = document.getElementById(`fix-content-${findingId}`);
            if (el && fix) {
                const code = fix.proposed_code || fix.code || '';
                const explanation = fix.explanation || 'Apply this fix:';
                el.innerHTML = code 
                    ? `<div class="fix-explanation">${escapeHtml(explanation)}</div><div class="code-block fix-code">${escapeHtml(code)}</div>`
                    : `<div class="fix-explanation">${escapeHtml(explanation)}</div>`;
            }
        }
        
        function showPlan(steps) {
            const container = document.getElementById('planSteps');
            container.innerHTML = '';
            document.getElementById('planStatus').textContent = `${steps.length} steps planned`;
            
            steps.forEach((step, i) => {
                planSteps[step.step_id] = step;
                const div = document.createElement('div');
                div.className = 'plan-step step-pending';
                div.id = `plan-step-${step.step_id}`;
                
                const agentBadge = step.agent === 'security' ? '🔒' : step.agent === 'bug' ? '🐛' : '🎯';
                
                div.innerHTML = `
                    <div class="plan-step-main">
                        <strong>${i + 1}.</strong> ${step.description}
                        ${step.details ? `<div class="plan-step-details">${step.details}</div>` : ''}
                    </div>
                    <span class="step-badge">${agentBadge} ${step.agent}</span>
                `;
                container.appendChild(div);
            });
        }
        
        function updatePlanStep(id, status) {
            const el = document.getElementById(`plan-step-${id}`);
            console.log(`calling from updatePlanStep: id: ${id}, status: ${status}`);
            if (el) {
                el.className = `plan-step step-${status}`;
                if (status === 'completed') {
                    const main = el.querySelector('.plan-step-main');
                    if (main && !main.innerHTML.startsWith('✓')) main.innerHTML = '✓ ' + main.innerHTML;
                }
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = String(text);
            return div.innerHTML;
        }
        
        connect();
        
        document.getElementById('codeInput').value = `import sqlite3
import hashlib
import os
import pickle

def authenticate(username, password):
    conn = sqlite3.connect('users.db')
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor = conn.execute(query)
    user = cursor.fetchone()
    if user:
        if hashlib.md5(password.encode()).hexdigest() == user[2]:
            return user
    return None

def run_command(cmd):
    os.system(f"echo {cmd}")

def load_data(filepath):
    with open(filepath, 'rb') as f:
        return pickle.load(f)

API_KEY = "sk-1234567890abcdef"

def get_user_profile(user_id):
    user = find_user(user_id)
    return user.name.upper()
`;
    </script>
</body>
</html>'''


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)