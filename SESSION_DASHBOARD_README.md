# LMArena Session Management Dashboard

## 概述

LMArena Session Management Dashboard 是一个用于管理多个并发会话的现代化 Web 界面。它提供了实时会话监控、统计信息、会话创建/删除等功能，支持 Direct Chat 和 Battle 两种模式。

## 主要功能

### 🎯 核心功能
- **多会话管理**: 支持同时管理多个 LMArena 会话
- **实时监控**: WebSocket 实时更新会话状态和统计信息
- **会话统计**: 详细的请求统计、错误率分析
- **自动会话创建**: API 调用时自动创建会话记录
- **会话清理**: 自动清理长时间空闲的会话

### 📊 监控功能
- **实时状态**: 会话状态实时更新（活跃、错误、空闲、断开）
- **请求统计**: 每个会话的请求次数和错误次数
- **错误追踪**: 记录最后一次错误信息
- **活动时间**: 跟踪会话的最后活动时间

### 🔧 管理功能
- **会话创建**: 通过 Web 界面创建新会话
- **会话删除**: 安全删除不需要的会话
- **默认会话设置**: 设置系统默认会话
- **批量导入**: 从现有配置文件导入会话
- **数据导出**: 导出会话数据用于外部使用

## 系统架构

### 组件结构
```
session_manager.py      # 会话管理核心模块
dashboard.py           # Web 仪表板应用
api_server.py          # 主 API 服务器（已集成）
init_sessions.py       # 会话初始化脚本
```

### 数据流
1. **API 请求** → `api_server.py` → `session_manager.py`
2. **会话更新** → WebSocket 广播 → 实时仪表板更新
3. **配置同步** → 自动保存到 `session_config.json`

## 安装和使用

### 1. 初始化会话管理器
```bash
python init_sessions.py
```
这将从现有的 `config.jsonc` 和 `model_endpoint_map.json` 导入会话数据。

### 2. 启动主 API 服务器
```bash
python api_server.py
```
主服务器现在集成了会话管理功能，运行在端口 5102。

### 3. 启动会话仪表板（可选）
```bash
python dashboard.py
```
独立的仪表板应用运行在端口 8080，提供更丰富的管理界面。

### 4. 访问仪表板
- 主 API 服务器: http://localhost:5102
- 独立仪表板: http://localhost:8080

## API 端点

### 会话管理 API
```
GET    /api/sessions           # 获取所有会话
GET    /api/sessions/stats     # 获取会话统计
POST   /api/sessions/cleanup   # 清理空闲会话
```

### 仪表板 API（独立应用）
```
GET    /                       # 仪表板主页
GET    /api/stats             # 统计信息
GET    /api/sessions          # 会话列表
POST   /api/sessions          # 创建会话
DELETE /api/sessions/{id}     # 删除会话
POST   /api/sessions/{id}/default  # 设置默认会话
GET    /api/sessions/{id}/export   # 导出会话数据
POST   /api/sessions/import   # 导入会话
POST   /api/sessions/cleanup  # 清理会话
WS      /ws                   # WebSocket 实时更新
```

## 配置说明

### 会话配置 (session_config.json)
```json
{
  "default_session": "session_id",
  "sessions": [
    {
      "session_id": "uuid",
      "message_id": "uuid",
      "name": "会话名称",
      "mode": "direct_chat|battle",
      "battle_target": "A|B",
      "created_at": "2024-01-01T00:00:00",
      "last_activity": "2024-01-01T00:00:00",
      "status": "active|error|idle|disconnected",
      "request_count": 0,
      "error_count": 0,
      "last_error": null,
      "metadata": {}
    }
  ]
}
```

### 会话模式
- **direct_chat**: 直接对话模式
- **battle**: 战斗模式（需要指定 battle_target: A 或 B）

### 会话状态
- **active**: 活跃状态，最近有成功请求
- **error**: 错误状态，最近请求失败
- **idle**: 空闲状态，长时间无活动
- **disconnected**: 断开状态，WebSocket 连接断开

## 使用场景

### 1. 多模型测试
为不同的 AI 模型创建独立的会话，避免对话历史混淆。

### 2. A/B 测试
使用 Battle 模式创建 A/B 测试会话，比较不同模型的性能。

### 3. 负载均衡
通过多个会话分散请求负载，提高系统稳定性。

### 4. 错误隔离
将错误会话隔离，不影响其他正常会话的运行。

## 高级功能

### 自动会话创建
当 API 请求使用未管理的会话 ID 时，系统会自动创建会话记录：
```python
# 自动创建会话记录
session_info = session_manager.get_session(session_id)
if not session_info:
    session_info = session_manager.create_session(
        name=f"{model_name}_auto",
        mode=SessionMode(mode_override or 'direct_chat'),
        session_id=session_id,
        message_id=message_id,
        metadata={'auto_created': True}
    )
```

### 错误追踪
系统自动记录会话错误：
```python
# 更新会话错误状态
session_manager.update_session_activity(
    session_id, 
    success=False, 
    error_message="Connection timeout"
)
```

### 会话清理
定期清理长时间空闲的会话：
```python
# 清理超过24小时空闲的会话
session_manager.cleanup_idle_sessions(max_idle_hours=24)
```

## 监控和告警

### 实时指标
- 总会话数
- 活跃会话数
- 错误会话数
- 总请求数
- 总错误数
- 错误率

### 告警建议
- 错误率超过 10%
- 活跃会话数为 0
- 单个会话连续错误超过 5 次

## 故障排除

### 常见问题

1. **会话未显示**
   - 检查 `session_config.json` 文件是否存在
   - 运行 `init_sessions.py` 重新初始化

2. **WebSocket 连接失败**
   - 检查防火墙设置
   - 确认端口 8080 未被占用

3. **会话状态不更新**
   - 检查 API 请求是否正常
   - 查看服务器日志

### 日志分析
```bash
# 查看会话管理器日志
grep "session" api_server.log

# 查看错误会话
grep "ERROR.*session" api_server.log
```

## 开发指南

### 扩展会话管理器
```python
from session_manager import SessionManager, SessionInfo, SessionMode

# 创建自定义会话管理器
custom_manager = SessionManager("custom_config.json")

# 添加自定义会话属性
class CustomSessionInfo(SessionInfo):
    custom_field: str = None
```

### 添加新的会话状态
```python
class SessionStatus(Enum):
    ACTIVE = "active"
    ERROR = "error"
    IDLE = "idle"
    DISCONNECTED = "disconnected"
    CUSTOM = "custom"  # 新增状态
```

## 性能优化

### 建议配置
- **会话清理间隔**: 24 小时
- **最大空闲时间**: 48 小时
- **WebSocket 重连间隔**: 1 秒
- **数据刷新间隔**: 5 秒

### 内存优化
- 定期清理过期会话
- 限制最大会话数量
- 压缩会话元数据

## 安全考虑

### 访问控制
- 使用 API Key 保护敏感端点
- 限制 WebSocket 连接数量
- 验证会话 ID 格式

### 数据保护
- 加密敏感会话数据
- 定期备份会话配置
- 审计会话访问日志

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 基础会话管理功能
- Web 仪表板界面
- 实时监控功能

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

本项目采用 MIT 许可证。