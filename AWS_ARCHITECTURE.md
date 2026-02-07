# AWS Deployment Architecture

## Multi-Agent Code Review System - Production Deployment

---

## 1. Architecture Overview

```
                                    ┌─────────────────────────────────────────────────────────┐
                                    │                      AWS Cloud                           │
                                    │                                                         │
┌──────────┐    HTTPS    ┌─────────┴───────┐     ┌──────────────────────────────────────┐   │
│  Client  │◄───────────►│   CloudFront    │     │           VPC (10.0.0.0/16)          │   │
│  Browser │             │   Distribution  │     │                                      │   │
└──────────┘             └────────┬────────┘     │  ┌────────────────────────────────┐  │   │
                                  │              │  │     Private Subnet (10.0.1.0/24)│  │   │
                    ┌─────────────┼─────────────►│  │                                │  │   │
                    │             │              │  │  ┌──────────────────────────┐  │  │   │
                    │             ▼              │  │  │   ECS Fargate Cluster    │  │  │   │
              ┌─────┴─────┐  ┌─────────┐        │  │  │                          │  │  │   │
              │    S3     │  │   API   │        │  │  │  ┌────────────────────┐  │  │  │   │
              │  Static   │  │ Gateway │        │  │  │  │  Coordinator Task  │  │  │  │   │
              │  Assets   │  │  (REST) │        │  │  │  │  (1-4 instances)   │  │  │  │   │
              └───────────┘  └────┬────┘        │  │  │  └────────────────────┘  │  │  │   │
                                  │              │  │  │                          │  │  │   │
                    ┌─────────────┼─────────────►│  │  │  ┌────────────────────┐  │  │  │   │
                    │             │              │  │  │  │  Security Agent    │  │  │  │   │
                    │             ▼              │  │  │  │  (Auto-scaled)     │  │  │  │   │
              ┌─────┴─────┐  ┌─────────┐        │  │  │  └────────────────────┘  │  │  │   │
              │    API    │  │ Lambda  │        │  │  │                          │  │  │   │
              │  Gateway  │  │ WebSocket│───────┼──┼──┼──┤  ┌────────────────────┐  │  │  │   │
              │(WebSocket)│  │ Handler │        │  │  │  │  Bug Agent          │  │  │  │   │
              └───────────┘  └─────────┘        │  │  │  │  (Auto-scaled)      │  │  │  │   │
                                                │  │  │  └────────────────────┘  │  │  │   │
                                                │  │  └──────────────────────────┘  │  │   │
                                                │  │                                │  │   │
                                                │  │  ┌──────────────────────────┐  │  │   │
                                                │  │  │      ElastiCache        │  │  │   │
                                                │  │  │      (Redis)            │  │  │   │
                                                │  │  │  - Session state        │  │  │   │
                                                │  │  │  - Event pub/sub        │  │  │   │
                                                │  │  │  - Result caching       │  │  │   │
                                                │  │  └──────────────────────────┘  │  │   │
                                                │  └────────────────────────────────┘  │   │
                                                │                                      │   │
                                                └──────────────────────────────────────┘   │
                                                                                           │
                                    └─────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
                                    ┌─────────────────────────────────────────────────────────┐
                                    │                  External Services                       │
                                    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
                                    │  │  Anthropic  │  │  CloudWatch │  │    SNS      │     │
                                    │  │  Claude API │  │    Logs     │  │   Alerts    │     │
                                    │  └─────────────┘  └─────────────┘  └─────────────┘     │
                                    └─────────────────────────────────────────────────────────┘
```

---

## 2. Component Details

### 2.1 API Gateway (REST)

**Purpose**: Handle code review submission requests

```yaml
Resource: /api/review
Method: POST
Integration: Lambda (ReviewOrchestrator)
Throttling: 100 req/sec
Timeout: 29 seconds (Lambda max)

Resource: /api/review/{reviewId}
Method: GET
Integration: Lambda (GetReviewStatus)

Resource: /api/health
Method: GET
Integration: Mock (200 OK)
```

**Request Flow**:
```
Client POST /api/review
    → API Gateway validates request
    → Lambda creates review job
    → Returns reviewId + WebSocket URL
    → Client connects to WebSocket for streaming
```

### 2.2 API Gateway (WebSocket)

**Purpose**: Real-time event streaming to clients

```yaml
Routes:
  $connect: Lambda (WebSocketConnect)
  $disconnect: Lambda (WebSocketDisconnect)
  $default: Lambda (WebSocketMessage)
  startReview: Lambda (StartReview)

Connection Management:
  - Store connectionId in DynamoDB
  - TTL: 2 hours
  - Heartbeat: 30 seconds
```

**Event Broadcasting**:
```python
# Lambda broadcasts events from Redis to connected clients
async def broadcast_event(review_id: str, event: dict):
    connections = await get_connections_for_review(review_id)
    api_client = boto3.client('apigatewaymanagementapi')
    
    for conn_id in connections:
        try:
            api_client.post_to_connection(
                ConnectionId=conn_id,
                Data=json.dumps(event)
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'GoneException':
                await remove_connection(conn_id)
```

### 2.3 ECS Fargate Cluster

**Task Definitions**:

```yaml
# Coordinator Task
CoordinatorTask:
  cpu: 512
  memory: 1024
  container:
    image: ${ECR_REPO}/coordinator:latest
    environment:
      - ANTHROPIC_API_KEY: ${SSM_PARAMETER}
      - REDIS_URL: ${ELASTICACHE_ENDPOINT}
      - LOG_LEVEL: INFO
    healthCheck:
      command: ["CMD-SHELL", "curl -f http://localhost:8080/health"]
      interval: 30
      timeout: 5
      retries: 3

# Agent Tasks (Security & Bug)
AgentTask:
  cpu: 256
  memory: 512
  container:
    image: ${ECR_REPO}/agent:latest
    environment:
      - AGENT_TYPE: ${AGENT_TYPE}  # security | bug
      - ANTHROPIC_API_KEY: ${SSM_PARAMETER}
      - REDIS_URL: ${ELASTICACHE_ENDPOINT}
```

**Auto-Scaling**:
```yaml
ServiceAutoScaling:
  MinCapacity: 1
  MaxCapacity: 10
  TargetTrackingPolicies:
    - MetricType: ECSServiceAverageCPUUtilization
      TargetValue: 70
    - CustomMetric: PendingReviewsPerAgent
      TargetValue: 5
```

### 2.4 ElastiCache (Redis)

**Purpose**: Event bus, session state, caching

```yaml
ClusterMode: Disabled
NodeType: cache.t3.medium
NumCacheNodes: 2  # Primary + Replica
AutomaticFailover: Enabled

# Data Structures
Keys:
  review:{reviewId}:state     # Hash - Review state
  review:{reviewId}:events    # List - Event stream
  review:{reviewId}:findings  # Hash - Findings
  agent:{agentId}:status      # String - Agent status
  ws:connections:{reviewId}   # Set - WebSocket connections
  
# Pub/Sub Channels
Channels:
  events:{reviewId}           # Real-time event broadcast
  agent:commands              # Agent control messages
```

### 2.5 DynamoDB Tables

```yaml
# Reviews Table
ReviewsTable:
  PartitionKey: reviewId (S)
  Attributes:
    - code (S)
    - filename (S)
    - status (S)  # pending | running | completed | failed
    - createdAt (N)
    - completedAt (N)
    - findings (L)
    - metrics (M)
  GSI:
    - StatusIndex: status + createdAt
  TTL: completedAt + 7 days

# Connections Table  
ConnectionsTable:
  PartitionKey: connectionId (S)
  Attributes:
    - reviewId (S)
    - connectedAt (N)
  GSI:
    - ReviewIndex: reviewId
  TTL: connectedAt + 2 hours
```

---

## 3. Data Flow

### 3.1 Code Review Request Flow

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌───────────┐
│  Client  │────►│    API    │────►│  Lambda  │────►│  DynamoDB │
│          │     │  Gateway  │     │Orchestrator│    │ (Reviews) │
└──────────┘     └───────────┘     └─────┬────┘     └───────────┘
                                         │
                                         ▼
                                   ┌───────────┐
                                   │   Redis   │
                                   │ (Job Queue)│
                                   └─────┬─────┘
                                         │
                      ┌──────────────────┼──────────────────┐
                      ▼                  ▼                  ▼
                ┌───────────┐     ┌───────────┐     ┌───────────┐
                │Coordinator│     │ Security  │     │    Bug    │
                │   Task    │     │   Agent   │     │   Agent   │
                └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                      │                 │                 │
                      └────────┬────────┴────────┬────────┘
                               ▼                 ▼
                         ┌───────────┐     ┌───────────┐
                         │   Redis   │     │  Claude   │
                         │  Events   │     │    API    │
                         └─────┬─────┘     └───────────┘
                               │
                               ▼
                         ┌───────────┐
                         │  Lambda   │
                         │ Broadcast │
                         └─────┬─────┘
                               │
                               ▼
                         ┌───────────┐
                         │  Client   │
                         │(WebSocket)│
                         └───────────┘
```

### 3.2 Event Streaming Flow

```python
# 1. Agent emits event
await event_bus.publish(create_finding_event(
    agent_id="security_agent",
    finding=finding
))

# 2. Event bus publishes to Redis
await redis.publish(f"events:{review_id}", event.to_json())

# 3. Lambda subscriber receives event
async def redis_subscriber(review_id):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"events:{review_id}")
    
    async for message in pubsub.listen():
        await broadcast_to_websockets(review_id, message)

# 4. Client receives via WebSocket
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleEvent(data);
};
```

---

## 4. Security

### 4.1 Network Security

```yaml
VPC:
  CIDR: 10.0.0.0/16
  
Subnets:
  Public:
    - 10.0.0.0/24 (NAT Gateway, ALB)
  Private:
    - 10.0.1.0/24 (ECS Tasks)
    - 10.0.2.0/24 (ElastiCache, RDS)

SecurityGroups:
  ECSTasksSG:
    Ingress:
      - From: ALB SG, Port: 8080
    Egress:
      - To: 0.0.0.0/0, Port: 443 (Claude API)
      - To: ElastiCache SG, Port: 6379
      
  ElastiCacheSG:
    Ingress:
      - From: ECS Tasks SG, Port: 6379
      - From: Lambda SG, Port: 6379
```

### 4.2 Secrets Management

```yaml
# AWS Systems Manager Parameter Store
Parameters:
  /codereview/prod/anthropic-api-key:
    Type: SecureString
    KMSKeyId: alias/codereview-key
    
  /codereview/prod/redis-auth-token:
    Type: SecureString
    
# IAM Role for ECS Tasks
ECSTaskRole:
  Policies:
    - SSMGetParameter: /codereview/prod/*
    - CloudWatchLogs: Write
    - DynamoDB: Read/Write on ReviewsTable
```

### 4.3 API Security

```yaml
APIGateway:
  Authorization: IAM or Cognito
  Throttling:
    RateLimit: 100/sec
    BurstLimit: 200
  WAF:
    - RateBasedRule: 1000 req/5min per IP
    - SQLInjectionRule
    - XSSRule
```

---

## 5. Monitoring & Observability

### 5.1 CloudWatch Metrics

```yaml
CustomMetrics:
  - ReviewsSubmitted (Count)
  - ReviewsCompleted (Count)
  - ReviewsFailed (Count)
  - ReviewDuration (Milliseconds)
  - FindingsPerReview (Count)
  - AgentTokenUsage (Count)
  - AgentErrors (Count)
  - WebSocketConnections (Count)

Dashboards:
  - OperationalDashboard:
      Widgets:
        - Reviews/minute
        - Error rate
        - P50/P95/P99 latency
        - Active connections
        - Token usage
```

### 5.2 Alarms

```yaml
Alarms:
  HighErrorRate:
    Metric: ReviewsFailed / ReviewsSubmitted
    Threshold: > 5%
    Period: 5 minutes
    Action: SNS → PagerDuty
    
  HighLatency:
    Metric: ReviewDuration P95
    Threshold: > 60000ms
    Period: 5 minutes
    Action: SNS → Slack
    
  TokenBudgetExceeded:
    Metric: AgentTokenUsage
    Threshold: > 1000000/hour
    Action: SNS → Email
```

### 5.3 Logging

```yaml
LogGroups:
  /ecs/codereview/coordinator:
    RetentionDays: 30
    
  /ecs/codereview/agents:
    RetentionDays: 30
    
  /lambda/websocket:
    RetentionDays: 14

LogInsights Queries:
  # Error investigation
  fields @timestamp, @message
  | filter @message like /ERROR/
  | sort @timestamp desc
  | limit 100
  
  # Review performance
  fields reviewId, duration, findingCount
  | filter eventType = "review_completed"
  | stats avg(duration), percentile(duration, 95) by bin(1h)
```

---

## 6. Cost Estimation

### Monthly Cost (1000 reviews/day)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| API Gateway (REST) | 1M requests | $3.50 |
| API Gateway (WebSocket) | 1M messages, 10K connection-min | $12.00 |
| Lambda | 2M invocations, 128MB | $5.00 |
| ECS Fargate | 3 tasks × 0.5 vCPU × 1GB × 720h | $75.00 |
| ElastiCache | cache.t3.medium × 2 | $48.00 |
| DynamoDB | 25 WCU, 25 RCU, 10GB | $15.00 |
| CloudWatch | Logs + Metrics | $20.00 |
| NAT Gateway | 100GB data | $45.00 |
| **Claude API** | ~50M tokens/month | **$150.00** |
| **Total** | | **~$375/month** |

### Cost Optimization Strategies

1. **Reserved Capacity**: Fargate Spot for non-critical workloads (-70%)
2. **Caching**: Cache repeated code patterns in Redis
3. **Token Optimization**: Truncate large files, use efficient prompts
4. **Auto-scaling**: Scale to zero during off-hours

---

## 7. Deployment Pipeline

```yaml
# CodePipeline Stages
Pipeline:
  Source:
    - GitHub webhook trigger
    
  Build:
    - CodeBuild: Run tests
    - CodeBuild: Build Docker images
    - ECR: Push images
    
  Deploy-Staging:
    - CloudFormation: Update staging stack
    - Lambda: Run integration tests
    - Manual approval gate
    
  Deploy-Production:
    - CloudFormation: Update prod stack (rolling)
    - CloudWatch: Monitor error rate
    - Auto-rollback if errors > 5%
```

---

## 8. Disaster Recovery

| Component | RPO | RTO | Strategy |
|-----------|-----|-----|----------|
| DynamoDB | 0 | < 1 min | Multi-AZ, Point-in-time recovery |
| ElastiCache | 5 min | < 5 min | Multi-AZ with failover |
| ECS Tasks | N/A | < 2 min | Auto-restart, multi-AZ |
| API Gateway | N/A | < 1 min | Regional, multi-AZ |

**Backup Strategy**:
- DynamoDB: Continuous backup with PITR (35 days)
- Redis: Daily snapshots to S3
- Code/Config: Git repository + S3 versioning

---

## 9. Future Enhancements

1. **Multi-Region**: Deploy to us-west-2 for redundancy
2. **Edge Caching**: CloudFront caching for static analysis patterns
3. **GPU Inference**: SageMaker endpoints for local model inference
4. **Batch Processing**: Step Functions for large codebase analysis
5. **Cost Allocation**: Tags for per-customer billing
