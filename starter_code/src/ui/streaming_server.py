"""
Streaming server for the code review system.
Provides WebSocket and SSE endpoints for real-time event streaming.
"""

import asyncio
import json
import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
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
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Agent Code Review</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; overflow: hidden; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #0d1117; 
            color: #c9d1d9; 
            padding: 8px;
            display: flex;
            flex-direction: column;
        }
        
        /* Header */
        header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 6px 12px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            margin-bottom: 8px;
            flex-shrink: 0;
        }
        h1 { font-size: 16px; color: #f0f6fc; }
        .conn { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
        .conn-on { background: #238636; color: white; }
        .conn-off { background: #da3633; color: white; }
        
        /* Main Container - Allow page scrolling for dynamic content */
        .main { 
            flex: 1; 
            display: flex; 
            flex-direction: column; 
            gap: 8px; 
            overflow-y: auto;
            padding-bottom: 20px;
        }
        
        /* Row 1: Fixed height, taller for better visibility */
        .row1 { 
            min-height: 200px; 
            height: 200px;
            display: flex; 
            gap: 8px; 
            flex-shrink: 0; 
        }
        .row1 .code-panel { width: 25%; }
        .row1 .plan-panel { width: 40%; }
        .row1 .agents-panel { width: 20%; }
        .row1 .metrics-panel { width: 15%; }
        
        /* Row 2: Agent activity with taller thinking sections */
        .row2 { 
            min-height: 320px; 
            height: 320px;
            display: flex; 
            gap: 8px; 
            flex-shrink: 0; 
        }
        .row2 .agent-box { width: 33.33%; }
        
        /* Row 3: Findings - DYNAMIC HEIGHT based on content */
        .row3 { 
            min-height: 300px;
            flex-shrink: 0;
        }
        .row3 .panel {
            height: auto;
            min-height: 280px;
        }
        .row3 .panel-body {
            overflow-y: visible;
            max-height: none;
        }
        
        /* Panel Base */
        .panel { 
            background: #161b22; 
            border: 1px solid #30363d; 
            border-radius: 6px; 
            display: flex; 
            flex-direction: column;
            overflow: hidden;
        }
        .panel-hdr { 
            background: #21262d; 
            padding: 8px 12px; 
            border-bottom: 1px solid #30363d; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            font-weight: 600; 
            font-size: 13px;
            flex-shrink: 0;
        }
        .panel-hdr-info { font-size: 11px; font-weight: normal; color: #8b949e; }
        .panel-body { padding: 10px; flex: 1; overflow-y: auto; min-height: 0; }
        
        /* Code Input */
        textarea { 
            width: 100%; 
            height: calc(100% - 36px);
            background: #0d1117; 
            border: 1px solid #30363d; 
            border-radius: 4px; 
            color: #c9d1d9; 
            padding: 8px; 
            font-family: monospace; 
            font-size: 11px; 
            resize: none;
        }
        textarea:focus { outline: none; border-color: #58a6ff; }
        button { 
            background: #238636; 
            color: white; 
            border: none; 
            padding: 8px 16px; 
            border-radius: 4px; 
            font-weight: 600; 
            cursor: pointer; 
            font-size: 12px; 
            width: 100%;
            margin-top: 6px;
        }
        button:hover { background: #2ea043; }
        button:disabled { background: #21262d; cursor: not-allowed; }
        
        /* Plan Steps */
        .plan-list { display: flex; flex-direction: column; gap: 4px; }
        .plan-item { 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            padding: 8px 12px; 
            font-size: 12px; 
            background: #0d1117;
            border-radius: 4px;
            border-left: 3px solid #30363d;
        }
        .plan-item.running { border-left-color: #1f6feb; background: #1f6feb15; }
        .plan-item.completed { border-left-color: #238636; background: #23863615; }
        .plan-item .check { color: #3fb950; margin-right: 8px; }
        .plan-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: #30363d; }
        
        /* Agent Status */
        .agent-row { 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            padding: 10px; 
            background: #0d1117; 
            border-radius: 4px; 
            margin-bottom: 6px;
        }
        .agent-row:last-child { margin-bottom: 0; }
        .agent-info { flex: 1; }
        .agent-name { font-weight: 600; font-size: 12px; display: flex; align-items: center; gap: 6px; }
        .agent-task { font-size: 10px; color: #8b949e; margin-top: 2px; }
        .agent-badge { font-size: 10px; padding: 3px 8px; border-radius: 10px; white-space: nowrap; }
        .st-idle { background: #21262d; color: #8b949e; }
        .st-running { background: #1f6feb; color: white; }
        .st-thinking { background: #8957e5; color: white; animation: pulse 1s infinite; }
        .st-completed { background: #238636; color: white; }
        .st-error { background: #da3633; color: white; }
        .st-retrying { background: #f0883e; color: white; animation: pulse 1s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
        
        /* Metrics */
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; height: 100%; }
        .metric { 
            background: #0d1117; 
            border: 1px solid #30363d; 
            border-radius: 4px; 
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 8px;
        }
        .metric-val { font-size: 22px; font-weight: 700; color: #58a6ff; }
        .metric-lbl { font-size: 9px; color: #8b949e; margin-top: 2px; }
        
        /* Agent Activity Box */
        .activity-box { 
            display: flex; 
            flex-direction: column; 
            height: 100%;
        }
        .activity-box.coordinator { border-top: 3px solid #58a6ff; }
        .activity-box.bug { border-top: 3px solid #f0883e; }
        .activity-box.security { border-top: 3px solid #da3633; }
        
        .box-hdr { 
            background: #21262d; 
            padding: 8px 12px; 
            font-size: 12px; 
            font-weight: 600; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            border-bottom: 1px solid #30363d;
            flex-shrink: 0;
        }
        .box-hdr .hdr-left { display: flex; align-items: center; gap: 8px; }
        .box-hdr .current { font-weight: normal; color: #f0883e; font-size: 11px; }
        .box-hdr .tool-count { font-size: 10px; color: #8b949e; font-weight: normal; }
        .retry-tag { background: #f0883e; color: white; font-size: 9px; padding: 2px 6px; border-radius: 4px; }
        
        /* Tool Calls List */
        .tools-section { flex: 1; overflow-y: auto; min-height: 0; padding: 8px; }
        .tool-card { 
            background: #0d1117; 
            border: 1px solid #30363d; 
            border-radius: 4px; 
            padding: 8px 10px; 
            margin-bottom: 6px;
            font-size: 11px;
        }
        .tool-card:last-child { margin-bottom: 0; }
        .tool-row1 { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .tool-name { color: #f0883e; font-weight: 600; font-size: 12px; }
        .tool-meta { display: flex; gap: 8px; align-items: center; }
        .tool-time { color: #3fb950; font-size: 11px; }
        .tool-stat { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .tool-stat.ok { background: #238636; color: white; }
        .tool-stat.err { background: #da3633; color: white; }
        .tool-stat.wait { background: #1f6feb; color: white; }
        
        .tool-io { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .tool-io-box { 
            background: #161b22; 
            border: 1px solid #21262d;
            border-radius: 4px; 
            padding: 6px 8px;
        }
        .tool-io-label { font-size: 9px; color: #8b949e; margin-bottom: 4px; font-weight: 600; }
        .tool-io-content { 
            font-family: monospace; 
            font-size: 10px; 
            white-space: pre-wrap; 
            word-break: break-all;
            max-height: 60px;
            overflow-y: auto;
        }
        .tool-io-content.input { color: #79c0ff; }
        .tool-io-content.output { color: #a5d6ff; }
        
        /* Thinking Section */
        .think-section { 
            border-top: 1px solid #30363d; 
            padding: 8px 12px;
            flex-shrink: 0;
            max-height: 150px;
        }
        .think-hdr { font-size: 11px; color: #8b949e; margin-bottom: 4px; font-weight: 600; }
        .think-content { 
            background: #0d1117; 
            border: 1px solid #30363d;
            border-radius: 4px; 
            padding: 8px; 
            font-family: monospace; 
            font-size: 11px; 
            color: #a371f7; 
            height: 100px; 
            overflow-y: auto; 
            white-space: pre-wrap; 
            word-break: break-word;
        }
        .think-content:empty::before { content: 'Waiting for thoughts...'; color: #484f58; font-style: italic; }
        
        /* Findings */
        .findings-hdr-stats { display: flex; gap: 10px; font-size: 11px; }
        .findings-hdr-stats span { padding: 3px 8px; border-radius: 4px; font-weight: 600; }
        .fs-crit { background: #da363333; color: #f85149; }
        .fs-high { background: #f0883e33; color: #f0883e; }
        .fs-med { background: #9e6a0333; color: #d29922; }
        .fs-low { background: #23863633; color: #3fb950; }
        
        .findings-list { display: flex; flex-direction: column; gap: 8px; }
        .finding-card { 
            background: #0d1117; 
            border: 1px solid #30363d; 
            border-radius: 6px; 
            padding: 12px;
        }
        .finding-card.critical { border-left: 4px solid #da3633; }
        .finding-card.high { border-left: 4px solid #f0883e; }
        .finding-card.medium { border-left: 4px solid #9e6a03; }
        .finding-card.low { border-left: 4px solid #238636; }
        
        .find-row1 { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
        .find-title { font-weight: 600; font-size: 13px; color: #f0f6fc; flex: 1; line-height: 1.3; }
        .find-sev { font-size: 10px; padding: 3px 8px; border-radius: 4px; font-weight: 600; margin-left: 10px; }
        .sev-critical { background: #da3633; color: white; }
        .sev-high { background: #f0883e; color: white; }
        .sev-medium { background: #9e6a03; color: white; }
        .sev-low { background: #238636; color: white; }
        
        .find-meta { font-size: 11px; color: #8b949e; margin-bottom: 8px; }
        .find-desc { font-size: 12px; color: #c9d1d9; line-height: 1.5; margin-bottom: 8px; }
        .find-code { 
            background: #161b22; 
            padding: 8px 10px; 
            border-radius: 4px; 
            font-family: monospace; 
            font-size: 11px; 
            border-left: 3px solid #da3633; 
            margin-bottom: 8px; 
            white-space: pre-wrap;
            max-height: 120px;
            overflow-y: auto;
        }
        .find-fix { 
            background: #23863622; 
            padding: 10px 12px; 
            border-radius: 4px; 
            border-left: 3px solid #238636; 
            display: none;
            margin-top: 8px;
        }
        .find-fix.show { display: block; }
        .find-fix-hdr { font-size: 10px; color: #3fb950; font-weight: 600; margin-bottom: 4px; }
        .find-fix-code { font-family: monospace; font-size: 11px; white-space: pre-wrap; max-height: 60px; overflow-y: auto; }
        
        .no-data { color: #484f58; text-align: center; padding: 20px; font-size: 12px; font-style: italic; }
    </style>
</head>
<body>
    <header>
        <h1>🔍 Multi-Agent Code Review</h1>
        <span id="connStatus" class="conn conn-off">Disconnected</span>
    </header>
    
    <div class="main">
        <!-- ROW 1: Code, Plan, Agents, Metrics -->
        <div class="row1">
            <!-- Code Input -->
            <div class="panel code-panel">
                <div class="panel-hdr">📝 Code</div>
                <div class="panel-body">
                    <textarea id="codeInput" placeholder="Paste Python code here..."></textarea>
                    <button id="analyzeBtn">🚀 Analyze Code</button>
                </div>
            </div>
            
            <!-- Plan -->
            <div class="panel plan-panel">
                <div class="panel-hdr">📋 Execution Plan <span class="panel-hdr-info" id="planInfo">Waiting...</span></div>
                <div class="panel-body">
                    <div class="plan-list" id="planList">
                        <div class="no-data">Plan will appear here after analysis starts...</div>
                    </div>
                </div>
            </div>
            
            <!-- Agents -->
            <div class="panel agents-panel">
                <div class="panel-hdr">🤖 Agents</div>
                <div class="panel-body">
                    <div class="agent-row">
                        <div class="agent-info">
                            <div class="agent-name">🎯 Coordinator</div>
                            <div class="agent-task" id="task-coordinator">Waiting...</div>
                        </div>
                        <span class="agent-badge st-idle" id="status-coordinator">Idle</span>
                    </div>
                    <div class="agent-row">
                        <div class="agent-info">
                            <div class="agent-name">🔒 Security</div>
                            <div class="agent-task" id="task-security_agent">Waiting...</div>
                        </div>
                        <span class="agent-badge st-idle" id="status-security_agent">Idle</span>
                    </div>
                    <div class="agent-row">
                        <div class="agent-info">
                            <div class="agent-name">🐛 Bug</div>
                            <div class="agent-task" id="task-bug_agent">Waiting...</div>
                        </div>
                        <span class="agent-badge st-idle" id="status-bug_agent">Idle</span>
                    </div>
                </div>
            </div>
            
            <!-- Metrics -->
            <div class="panel metrics-panel">
                <div class="panel-hdr">📊 Metrics</div>
                <div class="panel-body">
                    <div class="metrics-grid">
                        <div class="metric"><div class="metric-val" id="mTotal">0</div><div class="metric-lbl">Total</div></div>
                        <div class="metric"><div class="metric-val" id="mCrit" style="color:#da3633">0</div><div class="metric-lbl">Critical</div></div>
                        <div class="metric"><div class="metric-val" id="mHigh" style="color:#f0883e">0</div><div class="metric-lbl">High</div></div>
                        <div class="metric"><div class="metric-val" id="mFixes" style="color:#238636">0</div><div class="metric-lbl">Fixes</div></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ROW 2: Agent Activity -->
        <div class="row2">
            <!-- Coordinator Activity -->
            <div class="panel agent-box activity-box coordinator">
                <div class="box-hdr">
                    <div class="hdr-left">
                        🎯 Coordinator
                        <span class="retry-tag" id="retry-coordinator" style="display:none"></span>
                    </div>
                    <div>
                        <span class="current" id="cur-coordinator">-</span>
                        <span class="tool-count" id="cnt-coordinator">(0 calls)</span>
                    </div>
                </div>
                <div class="tools-section" id="tools-coordinator"></div>
                <div class="think-section">
                    <div class="think-hdr">💭 Thinking</div>
                    <div class="think-content" id="think-coordinator"></div>
                </div>
            </div>
            
            <!-- Bug Activity -->
            <div class="panel agent-box activity-box bug">
                <div class="box-hdr">
                    <div class="hdr-left">
                        🐛 Bug Detection
                        <span class="retry-tag" id="retry-bug_agent" style="display:none"></span>
                    </div>
                    <div>
                        <span class="current" id="cur-bug_agent">-</span>
                        <span class="tool-count" id="cnt-bug_agent">(0 calls)</span>
                    </div>
                </div>
                <div class="tools-section" id="tools-bug_agent"></div>
                <div class="think-section">
                    <div class="think-hdr">💭 Thinking</div>
                    <div class="think-content" id="think-bug_agent"></div>
                </div>
            </div>
            
            <!-- Security Activity -->
            <div class="panel agent-box activity-box security">
                <div class="box-hdr">
                    <div class="hdr-left">
                        🔒 Security
                        <span class="retry-tag" id="retry-security_agent" style="display:none"></span>
                    </div>
                    <div>
                        <span class="current" id="cur-security_agent">-</span>
                        <span class="tool-count" id="cnt-security_agent">(0 calls)</span>
                    </div>
                </div>
                <div class="tools-section" id="tools-security_agent"></div>
                <div class="think-section">
                    <div class="think-hdr">💭 Thinking</div>
                    <div class="think-content" id="think-security_agent"></div>
                </div>
            </div>
        </div>
        
        <!-- ROW 3: Findings -->
        <div class="row3">
            <div class="panel" style="height: 100%;">
                <div class="panel-hdr">
                    🔎 Findings
                    <div class="findings-hdr-stats">
                        <span class="fs-crit">🔴 <span id="fc">0</span></span>
                        <span class="fs-high">🟠 <span id="fh">0</span></span>
                        <span class="fs-med">🟡 <span id="fm">0</span></span>
                        <span class="fs-low">🟢 <span id="fl">0</span></span>
                    </div>
                </div>
                <div class="panel-body">
                    <div class="findings-list" id="findingsList">
                        <div class="no-data" id="noFindings">Findings will stream here as agents discover issues...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let ws = null, isConnected = false;
        let totalFindings = 0, totalFixes = 0;
        const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
        const toolData = {};
        const agentToolCounts = { coordinator: 0, bug_agent: 0, security_agent: 0 };
        
        function connect() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(proto + '//' + location.host + '/ws/review');
            ws.onopen = () => {
                isConnected = true;
                document.getElementById('connStatus').textContent = 'Connected';
                document.getElementById('connStatus').className = 'conn conn-on';
            };
            ws.onclose = () => {
                isConnected = false;
                document.getElementById('connStatus').textContent = 'Disconnected';
                document.getElementById('connStatus').className = 'conn conn-off';
                setTimeout(connect, 2000);
            };
            ws.onerror = (e) => console.error('WS error:', e);
            ws.onmessage = (e) => { try { handleEvent(JSON.parse(e.data)); } catch(err) { console.error(err); } };
        }
        
        document.getElementById('analyzeBtn').onclick = () => {
            const code = document.getElementById('codeInput').value;
            if (!code.trim()) return alert('Please enter code to analyze');
            if (!isConnected) return alert('Not connected to server');
            resetUI();
            ws.send(JSON.stringify({ type: 'start_review', code, filename: 'code.py' }));
            document.getElementById('analyzeBtn').disabled = true;
            document.getElementById('analyzeBtn').textContent = '⏳ Analyzing...';
        };
        
        function resetUI() {
            totalFindings = totalFixes = 0;
            sevCounts.critical = sevCounts.high = sevCounts.medium = sevCounts.low = 0;
            agentToolCounts.coordinator = agentToolCounts.bug_agent = agentToolCounts.security_agent = 0;
            Object.keys(toolData).forEach(k => delete toolData[k]);
            
            document.getElementById('mTotal').textContent = '0';
            document.getElementById('mCrit').textContent = '0';
            document.getElementById('mHigh').textContent = '0';
            document.getElementById('mFixes').textContent = '0';
            document.getElementById('fc').textContent = '0';
            document.getElementById('fh').textContent = '0';
            document.getElementById('fm').textContent = '0';
            document.getElementById('fl').textContent = '0';
            
            document.getElementById('findingsList').innerHTML = '<div class="no-data" id="noFindings">Findings will stream here as agents discover issues...</div>';
            document.getElementById('planList').innerHTML = '<div class="no-data">Plan will appear here after analysis starts...</div>';
            document.getElementById('planInfo').textContent = 'Waiting...';
            
            ['security_agent', 'bug_agent', 'coordinator'].forEach(a => {
                document.getElementById('tools-' + a).innerHTML = '';
                document.getElementById('think-' + a).textContent = '';
                document.getElementById('cur-' + a).textContent = '-';
                document.getElementById('cnt-' + a).textContent = '(0 calls)';
                document.getElementById('retry-' + a).style.display = 'none';
                setStatus(a, 'idle', 'Waiting...');
            });
        }
        
        function setStatus(agent, status, task) {
            const el = document.getElementById('status-' + agent);
            const tk = document.getElementById('task-' + agent);
            if (el) {
                el.textContent = status.charAt(0).toUpperCase() + status.slice(1);
                el.className = 'agent-badge st-' + status;
            }
            if (tk && task) tk.textContent = task;
        }
        
        function handleEvent(msg) {
            if (['review_accepted', 'keepalive', 'pong'].includes(msg.type)) return;
            const evt = msg.event_type || msg.type;
            const data = msg.data || msg;
            const agent = msg.agent_id || 'coordinator';
            
            switch (evt) {
                case 'agent_started':
                    setStatus(agent, 'running', data.task || 'Starting...');
                    break;
                    
                case 'agent_completed':
                    setStatus(agent, data.success !== false ? 'completed' : 'error', data.summary || 'Done');
                    document.getElementById('cur-' + agent).textContent = data.success !== false ? '✓ Done' : '✗ Failed';
                    document.getElementById('retry-' + agent).style.display = 'none';
                    if (agent === 'coordinator') {
                        document.getElementById('analyzeBtn').disabled = false;
                        document.getElementById('analyzeBtn').textContent = '🚀 Analyze Code';
                    }
                    break;
                    
                case 'agent_error':
                    if (data.will_retry) {
                        setStatus(agent, 'retrying', 'Retry ' + data.attempt + '/' + data.max_attempts);
                        const rt = document.getElementById('retry-' + agent);
                        rt.textContent = 'Retry ' + data.attempt + '/' + data.max_attempts;
                        rt.style.display = 'inline';
                    } else {
                        setStatus(agent, 'error', 'Failed after ' + data.attempt + ' attempts');
                        document.getElementById('cur-' + agent).textContent = '✗ Max retries reached';
                    }
                    break;
                    
                case 'thinking':
                    if (data.chunk) {
                        setStatus(agent, 'thinking', 'Thinking...');
                        appendThink(agent, data.chunk);
                    }
                    break;
                    
                case 'mode_changed':
                    if (data.mode === 'thinking') {
                        setStatus(agent, 'thinking', 'Thinking...');
                    }
                    break;
                    
                case 'thinking_complete':
                    break;
                    
                case 'tool_call_start':
                    setStatus(agent, 'running', data.tool_name);
                    addToolCard(agent, data);
                    break;
                    
                case 'tool_call_result':
                    updateToolCard(data);
                    break;
                    
                case 'finding_discovered':
                    addFinding(data);
                    break;
                    
                case 'fix_proposed':
                    updateFix(data);
                    break;
                    
                case 'plan_created':
                    showPlan(data.steps);
                    break;
                    
                case 'plan_step_started':
                    updatePlan(data.step_id, 'running');
                    break;
                    
                case 'plan_step_completed':
                    updatePlan(data.step_id, 'completed');
                    break;
            }
        }
        
        function appendThink(agent, text) {
            const el = document.getElementById('think-' + agent);
            if (el) {
                el.textContent += text;
                el.scrollTop = el.scrollHeight;
            }
        }
        
        function addToolCard(agent, data) {
            agentToolCounts[agent]++;
            document.getElementById('cnt-' + agent).textContent = '(' + agentToolCounts[agent] + ' calls)';
            
            const id = data.tool_call_id;
            toolData[id] = { agent, start: Date.now(), name: data.tool_name };
            
            document.getElementById('cur-' + agent).textContent = data.tool_name + ' ⏱️';
            
            const list = document.getElementById('tools-' + agent);
            const div = document.createElement('div');
            div.className = 'tool-card';
            div.id = 'tc-' + id;
            
            const inputStr = JSON.stringify(data.input || {}, null, 2);
            
            div.innerHTML = 
                '<div class="tool-row1">' +
                    '<span class="tool-name">' + esc(data.tool_name) + '</span>' +
                    '<span class="tool-meta">' +
                        '<span class="tool-time" id="tt-' + id + '">⏱️ running...</span>' +
                        '<span class="tool-stat wait" id="ts-' + id + '">Pending</span>' +
                    '</span>' +
                '</div>' +
                '<div class="tool-io">' +
                    '<div class="tool-io-box">' +
                        '<div class="tool-io-label">📥 INPUT</div>' +
                        '<div class="tool-io-content input">' + esc(inputStr) + '</div>' +
                    '</div>' +
                    '<div class="tool-io-box">' +
                        '<div class="tool-io-label">📤 OUTPUT</div>' +
                        '<div class="tool-io-content output" id="to-' + id + '">Waiting...</div>' +
                    '</div>' +
                '</div>';
            
            list.insertBefore(div, list.firstChild);
        }
        
        function updateToolCard(data) {
            const id = data.tool_call_id;
            const td = toolData[id];
            if (!td) return;
            
            const dur = data.duration_ms || (Date.now() - td.start);
            const ok = data.success;
            
            const tt = document.getElementById('tt-' + id);
            if (tt) tt.textContent = dur + 'ms';
            
            const ts = document.getElementById('ts-' + id);
            if (ts) {
                ts.textContent = ok ? 'Success' : 'Error';
                ts.className = 'tool-stat ' + (ok ? 'ok' : 'err');
            }
            
            const to = document.getElementById('to-' + id);
            if (to) {
                let out = data.error || data.output;
                let outStr = typeof out === 'object' ? JSON.stringify(out, null, 2) : String(out || '(empty)');
                to.textContent = outStr;
            }
            
            document.getElementById('cur-' + td.agent).textContent = td.name + ' ' + dur + 'ms ' + (ok ? '✓' : '✗');
        }
        
        function addFinding(f) {
            document.getElementById('noFindings').style.display = 'none';
            
            totalFindings++;
            const sev = (f.severity || 'medium').toLowerCase();
            const fid = f.finding_id || ('f' + totalFindings);
            
            sevCounts[sev]++;
            document.getElementById('fc').textContent = sevCounts.critical;
            document.getElementById('fh').textContent = sevCounts.high;
            document.getElementById('fm').textContent = sevCounts.medium;
            document.getElementById('fl').textContent = sevCounts.low;
            document.getElementById('mTotal').textContent = totalFindings;
            if (sev === 'critical') document.getElementById('mCrit').textContent = sevCounts.critical;
            if (sev === 'high') document.getElementById('mHigh').textContent = sevCounts.high;
            
            const list = document.getElementById('findingsList');
            const div = document.createElement('div');
            div.className = 'finding-card ' + sev;
            div.id = 'find-' + fid;
            
            const line = f.location ? f.location.line_start : '?';
            const snippet = f.location ? (f.location.code_snippet || '') : '';
            
            div.innerHTML = 
                '<div class="find-row1">' +
                    '<span class="find-title">' + esc(f.title || 'Finding') + '</span>' +
                    '<span class="find-sev sev-' + sev + '">' + sev.toUpperCase() + '</span>' +
                '</div>' +
                '<div class="find-meta">' + esc(f.category || 'Unknown') + ' • Line ' + line + '</div>' +
                '<div class="find-desc">' + esc(f.description || 'No description') + '</div>' +
                (snippet ? '<div class="find-code">' + esc(snippet) + '</div>' : '') +
                '<div class="find-fix" id="fix-' + fid + '">' +
                    '<div class="find-fix-hdr">✅ SUGGESTED FIX</div>' +
                    '<div class="find-fix-code"></div>' +
                '</div>';
            
            list.appendChild(div);
            list.scrollTop = list.scrollHeight;
        }
        
        function updateFix(data) {
            const fid = data.finding_id;
            const el = document.getElementById('fix-' + fid);
            if (el) {
                el.classList.add('show');
                const code = el.querySelector('.find-fix-code');
                if (code) code.textContent = data.proposed_code || data.explanation || 'See documentation';
                totalFixes++;
                document.getElementById('mFixes').textContent = totalFixes;
            }
        }
        
        function showPlan(steps) {
            const list = document.getElementById('planList');
            list.innerHTML = '';
            document.getElementById('planInfo').textContent = steps.length + ' steps';
            
            steps.forEach((s, i) => {
                const div = document.createElement('div');
                div.className = 'plan-item';
                div.id = 'plan-' + s.step_id;
                const icon = s.agent === 'security' ? '🔒' : s.agent === 'bug' ? '🐛' : '🎯';
                div.innerHTML = 
                    '<span><span class="check" id="check-' + s.step_id + '"></span>' + (i + 1) + '. ' + esc(s.description) + '</span>' +
                    '<span class="plan-badge">' + icon + ' ' + s.agent + '</span>';
                list.appendChild(div);
            });
        }
        
        function updatePlan(id, status) {
            const el = document.getElementById('plan-' + id);
            const check = document.getElementById('check-' + id);
            if (el) {
                el.className = 'plan-item ' + status;
                if (status === 'completed' && check) {
                    check.textContent = '✓ ';
                }
            }
        }
        
        function esc(t) {
            const d = document.createElement('div');
            d.textContent = String(t || '');
            return d.innerHTML;
        }
        
        connect();
        
        document.getElementById('codeInput').value = "import sqlite3\\nimport hashlib\\nimport os\\nimport pickle\\n\\ndef authenticate(username, password):\\n    conn = sqlite3.connect('users.db')\\n    query = f\\"SELECT * FROM users WHERE username = '{username}'\\"\\n    cursor = conn.execute(query)\\n    user = cursor.fetchone()\\n    if user:\\n        if hashlib.md5(password.encode()).hexdigest() == user[2]:\\n            return user\\n    return None\\n\\ndef run_command(cmd):\\n    os.system(f\\"echo {cmd}\\")\\n\\ndef load_data(filepath):\\n    with open(filepath, 'rb') as f:\\n        return pickle.load(f)\\n\\nAPI_KEY = \\"sk-1234567890abcdef\\"\\n\\ndef get_user_profile(user_id):\\n    user = find_user(user_id)\\n    return user.name.upper()\\n";
    </script>
</body>
</html>"""


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
