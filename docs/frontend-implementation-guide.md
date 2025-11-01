# Frontend实施指南 - 意图上下文与聊天历史

## 项目信息

**前端项目路径**: `/home/msq/gitCode/new/emergency-rescue-brain/`
**主要文件**: `src/components/voice-chat/VoiceChat.jsx`
**Backend API**: `http://localhost:8008`
**参考文档**: `openspec/changes/add-intent-context-chat-history/tasks.md` (Phase 3-5)

---

## Phase 3: Frontend历史加载（Week 2, Days 1-3）

### 3.1 状态管理改造

**文件**: `VoiceChat.jsx`
**位置**: Line 23-29 (在现有useState后添加)

```javascript
// 添加以下状态变量
const [messages, setMessages] = useState([]);  // 消息历史数组
const [currentUserId] = useState('demo_user');  // 固定用户ID（生产环境应从认证系统获取）

// Thread ID持久化（页面刷新后保留会话）
const [currentThreadId] = useState(() => {
  // 尝试从localStorage恢复
  const stored = localStorage.getItem('emergency_thread_id');
  if (stored && /^thread-\d{13}-[a-z0-9]{9}$/.test(stored)) {
    console.log(`恢复会话: ${stored}`);
    return stored;
  }

  // 生成新的thread_id: thread-{timestamp}-{random}
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 11);
  const newId = `thread-${timestamp}-${random}`;

  localStorage.setItem('emergency_thread_id', newId);
  console.log(`新建会话: ${newId}`);
  return newId;
});

const messagesEndRef = useRef(null);  // 自动滚动引用

// 可选：提供"开始新对话"功能
const startNewConversation = () => {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 11);
  const newId = `thread-${timestamp}-${random}`;

  localStorage.setItem('emergency_thread_id', newId);
  setMessages([]);  // 清空UI消息
  console.log(`开始新对话: ${newId}`);

  // 注意：需要将currentThreadId改为可变状态才能动态切换
  // 当前实现中thread_id在组件生命周期内固定
};
```

**说明**:
- `messages`: 存储完整对话历史（包括从服务器加载的）
- `currentUserId`: 多租户隔离标识（生产环境需集成认证系统）
- `currentThreadId`:
  - **持久化策略**: 使用localStorage存储，页面刷新后自动恢复
  - **格式验证**: `thread-{13位时间戳}-{9位随机字符}`
  - **新会话触发**: 如果localStorage无效或不存在，自动生成新ID
- `messagesEndRef`: 用于实现滚动到最新消息
- `startNewConversation`: 可选功能，允许用户主动开始新对话

---

### 3.2 历史加载逻辑

**文件**: `VoiceChat.jsx`
**位置**: 添加新函数（组件内部，在现有函数之前）

```javascript
// 加载历史消息（带重试机制）
const loadHistory = async () => {
  const MAX_RETRIES = 3;
  const RETRY_DELAY = 1000;

  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const response = await fetch(`${apiUrl}/conversations/history`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          user_id: currentUserId,
          thread_id: currentThreadId,
          limit: 20  // 最多加载20条历史
        }),
        signal: AbortSignal.timeout(5000)  // 5秒超时
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setMessages(data.history || []);
      console.log(`✅ 加载历史：${data.total}条`);
      return;

    } catch (error) {
      console.error(`加载历史失败 (尝试 ${i + 1}/${MAX_RETRIES}):`, error);

      if (i < MAX_RETRIES - 1) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * Math.pow(2, i)));
      } else {
        console.warn('历史加载失败，将使用空历史');
        setMessages([]);
      }
    }
  }
};
```

**关键点**:
1. **重试机制**: 3次重试，指数退避（1s, 2s, 4s）
2. **超时保护**: 5秒超时防止长时间等待
3. **降级处理**: 失败后使用空历史，不阻塞用户
4. **错误日志**: 详细记录失败原因便于调试

---

### 3.3 组件挂载时加载历史

**文件**: `VoiceChat.jsx`
**位置**: 添加useEffect（在组件return之前）

```javascript
// 组件挂载时加载历史消息
useEffect(() => {
  loadHistory();
}, []); // 空依赖数组，仅挂载时执行一次
```

**注意**: 必须在组件挂载时立即加载，否则用户看不到历史消息

---

## Phase 4: Frontend UI展示（Week 2, Days 4-5）

### 4.1 消息列表渲染

**文件**: `VoiceChat.jsx`
**位置**: 替换现有的消息展示区域

```jsx
<div className="voice-chat-messages" style={{
  height: '400px',
  overflowY: 'auto',
  padding: '10px',
  backgroundColor: '#f5f5f5',
  borderRadius: '8px'
}}>
  {messages.map((msg) => (
    <div
      key={msg.id}
      className={`message ${msg.role}`}
      style={{
        textAlign: msg.role === 'user' ? 'right' : 'left',
        marginBottom: '10px'
      }}
    >
      <div
        style={{
          display: 'inline-block',
          padding: '8px 12px',
          borderRadius: '12px',
          backgroundColor: msg.role === 'user' ? '#1890ff' : '#fff',
          color: msg.role === 'user' ? '#fff' : '#000',
          maxWidth: '70%',
          wordWrap: 'break-word'
        }}
      >
        <strong>{msg.role === 'user' ? '用户' : 'AI'}:</strong> {msg.content}
        {msg.intent_type && (
          <div style={{fontSize: '12px', marginTop: '4px', opacity: 0.7}}>
            [意图: {msg.intent_type}]
          </div>
        )}
      </div>
    </div>
  ))}
  <div ref={messagesEndRef} />
</div>
```

**样式说明**:
- **用户消息**: 右对齐，蓝色背景
- **AI消息**: 左对齐，白色背景
- **意图标签**: 小字显示，便于调试
- **滚动容器**: 固定高度，自动滚动

---

### 4.2 自动滚动到最新消息

**文件**: `VoiceChat.jsx`
**位置**: 添加useEffect

```javascript
// 消息更新时自动滚动到底部
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages]);
```

**触发时机**: 每次`messages`数组变化（加载历史、新消息到达）

---

### 4.3 发送消息时更新本地状态

**文件**: `VoiceChat.jsx`
**位置**: 修改现有的发送消息逻辑

```javascript
// 在发送消息函数中添加本地状态更新
const sendMessage = async (text) => {
  // 1. 立即添加用户消息到UI（乐观更新）
  const userMessage = {
    id: -Date.now(), // 临时ID（负数）,Backend响应后替换
    role: 'user',
    content: text,
    intent_type: null,
    event_time: new Date().toISOString(),
    metadata: {}
  };
  setMessages(prev => [...prev, userMessage]);

  try {
    // 2. 发送到Backend
    const response = await fetch(`${apiUrl}/intent/process`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        user_id: currentUserId,
        thread_id: currentThreadId,
        message: text
      })
    });

    const data = await response.json();

    // 3. 添加AI回复到UI
    if (data.history && data.history.length > 0) {
      // 使用服务器返回的完整历史（包含AI回复）
      setMessages(data.history);
    } else {
      // 降级：手动添加AI回复（不推荐，应使用history）
      const aiMessage = {
        id: -Date.now() - 1, // 临时ID
        role: 'assistant',
        content: data.result?.response_text || '处理完成',
        intent_type: data.intent?.intent_type,
        event_time: new Date().toISOString(),
        metadata: {}
      };
      setMessages(prev => [...prev, aiMessage]);
    }

  } catch (error) {
    console.error('发送消息失败:', error);
    // 失败时添加错误提示
    setMessages(prev => [...prev, {
      id: -Date.now() - 2, // 临时ID
      role: 'system',
      content: '发送失败，请重试',
      intent_type: null,
      event_time: new Date().toISOString(),
      metadata: {}
    }]);
  }
};
```

**关键点**:
1. **乐观更新**: 用户消息立即显示，不等服务器响应
2. **服务器同步**: 使用Backend返回的完整历史
3. **错误处理**: 失败时显示错误消息

---

## Phase 5: 端到端测试（Week 3, Days 1-2）

### 5.1 手动测试检查清单

**前置条件**:
- ✅ Backend服务运行在 `http://localhost:8008`
- ✅ Frontend开发服务器已启动
- ✅ 浏览器开发者工具打开（查看Network和Console）

**测试步骤**:

#### 测试1: 历史加载
1. 打开VoiceChat组件
2. 检查Network标签，应看到 `POST /conversations/history` 请求
3. 检查Console，应看到 "✅ 加载历史：X条" 日志
4. 验证UI显示历史消息

**预期结果**:
- 历史消息正确显示
- 用户/AI消息样式区分明显
- 自动滚动到最新消息

#### 测试2: 多轮对话持久化
1. 发送第一条消息："四川汶川发生地震"
2. 等待AI回复
3. 刷新页面
4. 验证历史消息仍然存在

**预期结果**:
- 刷新后历史不丢失
- 消息顺序正确
- 意图标签正确显示

#### 测试3: 上下文连续性
1. 发送："四川汶川发生地震"
2. 发送："坐标是103.85,31.68"（不提地震）
3. 验证AI能理解第二条消息的上下文

**预期结果**:
- AI正确关联两条消息
- Backend mem0上下文检索生效
- 对话流畅自然

#### 测试4: 错误降级
1. 停止Backend服务
2. 打开VoiceChat组件
3. 验证不会白屏或崩溃

**预期结果**:
- 显示空历史（降级处理）
- Console有错误日志但不崩溃
- 用户仍可尝试发送消息

---

### 5.2 自动化测试（可选）

**文件**: `VoiceChat.test.jsx` (新建)

```javascript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VoiceChat from './VoiceChat';

describe('VoiceChat历史功能', () => {
  beforeEach(() => {
    // Mock fetch API
    global.fetch = jest.fn();
  });

  test('组件挂载时加载历史', async () => {
    // Mock历史API响应
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        history: [
          { role: 'user', content: '测试消息1' },
          { role: 'assistant', content: '测试回复1' }
        ],
        total: 2
      })
    });

    render(<VoiceChat />);

    // 验证API调用
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/conversations/history'),
        expect.any(Object)
      );
    });

    // 验证UI显示
    expect(screen.getByText('测试消息1')).toBeInTheDocument();
    expect(screen.getByText('测试回复1')).toBeInTheDocument();
  });

  test('发送消息后更新历史', async () => {
    // Mock intent/process响应
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        history: [
          { role: 'user', content: '新消息' },
          { role: 'assistant', content: 'AI回复' }
        ]
      })
    });

    render(<VoiceChat />);

    // 模拟用户输入
    const input = screen.getByRole('textbox');
    await userEvent.type(input, '新消息');
    await userEvent.click(screen.getByText('发送'));

    // 验证消息显示
    await waitFor(() => {
      expect(screen.getByText('新消息')).toBeInTheDocument();
      expect(screen.getByText('AI回复')).toBeInTheDocument();
    });
  });
});
```

---

## 常见问题排查

### Q1: 历史加载失败，返回404
**原因**: Backend API路径错误
**解决**: 检查`apiUrl`配置，确保指向 `http://localhost:8008`

### Q2: 历史加载成功但UI不显示
**原因**: `messages`状态更新失败
**解决**: 检查`setMessages(data.history)`是否正确调用，`data.history`格式是否正确

### Q3: 消息发送后不显示
**原因**: 本地状态未更新
**解决**: 确保`sendMessage`函数中有 `setMessages(prev => [...prev, newMessage])`

### Q4: 刷新后历史丢失
**原因**: `currentThreadId`每次刷新都生成新值
**解决**: ✅ 已在3.1节实现localStorage持久化，页面刷新后自动恢复session

### Q5: 自动滚动不生效
**原因**: `messagesEndRef`未正确绑定
**解决**: 确保在消息列表最后有 `<div ref={messagesEndRef} />`

---

## Backend API参考

### 1. 加载历史记录

**接口**: `POST /conversations/history`

**请求体**:
```json
{
  "user_id": "demo_user",
  "thread_id": "thread-1234567890",
  "limit": 20
}
```

**响应示例**:
```json
{
  "history": [
    {
      "id": 1,
      "role": "user",
      "content": "四川汶川发生地震",
      "intent_type": null,
      "event_time": "2025-10-28T12:00:00Z",
      "metadata": {}
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "收到地震报告，正在分析...",
      "intent_type": "rescue-task-generate",
      "event_time": "2025-10-28T12:00:01Z",
      "metadata": {}
    }
  ],
  "total": 2,
  "user_id": "demo_user",
  "thread_id": "thread-1735370000000-abc123"
}
```

### 2. 发送意图消息

**接口**: `POST /intent/process`

**请求体**:
```json
{
  "user_id": "demo_user",
  "thread_id": "thread-1234567890",
  "message": "坐标是103.85,31.68"
}
```

**响应示例**:
```json
{
  "conversation_id": "conv-uuid",
  "history": [...],  // 完整对话历史
  "status": "success",
  "intent": {
    "intent_type": "rescue-task-generate",
    "slots": {...}
  },
  "result": {
    "response_text": "已记录坐标信息"
  }
}
```

---

## 性能优化建议

### 1. 减少不必要的re-render
```javascript
// 使用React.memo包装消息组件
const MessageItem = React.memo(({ message }) => (
  <div className={`message ${message.role}`}>
    {message.content}
  </div>
));
```

### 2. 虚拟滚动（大量历史时）
```javascript
// 使用react-window或react-virtualized
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={400}
  itemCount={messages.length}
  itemSize={60}
>
  {({ index, style }) => (
    <div style={style}>
      <MessageItem message={messages[index]} />
    </div>
  )}
</FixedSizeList>
```

### 3. 防抖发送
```javascript
import { debounce } from 'lodash';

const debouncedSend = debounce(sendMessage, 300);
```

---

## 完成标准

### Phase 3 完成标准
- ✅ 组件挂载时自动加载历史
- ✅ 加载失败有降级处理
- ✅ Console有清晰日志

### Phase 4 完成标准
- ✅ 消息列表正确渲染
- ✅ 用户/AI消息样式区分
- ✅ 自动滚动到最新消息
- ✅ 发送消息后立即显示

### Phase 5 完成标准
- ✅ 手动测试4个场景全部通过
- ✅ 多轮对话上下文连贯
- ✅ 刷新后历史不丢失

---

## 相关文件

**Backend文档**:
- `openspec/changes/add-intent-context-chat-history/tasks.md` - 完整任务定义
- `src/emergency_agents/api/main.py` - Backend实现参考

**前端项目**:
- `/home/msq/gitCode/new/emergency-rescue-brain/` - 前端代码库
- `src/components/voice-chat/VoiceChat.jsx` - 主要修改文件

**测试文档**:
- 本文档 Phase 5 - 手动测试清单

---

## 估算工作量

| Phase | 任务 | 预估时间 | 难度 |
|-------|------|---------|------|
| Phase 3.1 | 状态管理改造 | 30分钟 | 简单 |
| Phase 3.2 | 历史加载逻辑 | 1小时 | 中等 |
| Phase 3.3 | useEffect集成 | 15分钟 | 简单 |
| Phase 4.1 | 消息列表渲染 | 1.5小时 | 中等 |
| Phase 4.2 | 自动滚动 | 30分钟 | 简单 |
| Phase 4.3 | 发送消息更新 | 1小时 | 中等 |
| Phase 5 | 端到端测试 | 2小时 | 中等 |
| **总计** | - | **6.5小时** | - |

---

**文档版本**: v1.0
**最后更新**: 2025-10-28
**作者**: AI Assistant
**审核**: 待人工审核
