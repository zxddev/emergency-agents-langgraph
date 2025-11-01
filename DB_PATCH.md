---数据库补充SQL---
-- 请添加到 sql/operational.sql 末尾：
-- 会话与消息表
CREATE TABLE operational.conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT {}::jsonb
);
COMMENT ON TABLE operational.conversations IS AI 对话会话表，记录多租户多线程会话信息。;
COMMENT ON COLUMN operational.conversations.user_id IS 租户或操作用户标识。;
COMMENT ON COLUMN operational.conversations.thread_id IS 会话线程标识，用于挂载上下文。;
COMMENT ON COLUMN operational.conversations.started_at IS 首次消息时间。;
COMMENT ON COLUMN operational.conversations.last_message_at IS 最近一条消息时间。;
COMMENT ON COLUMN operational.conversations.metadata IS 会话附加信息，例如前端会话ID。;
CREATE INDEX idx_conversations_user_id ON operational.conversations (user_id);
CREATE INDEX idx_conversations_last_message_at ON operational.conversations (last_message_at DESC);

CREATE TABLE operational.messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES operational.conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    intent_type VARCHAR(100),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT {}::jsonb
);
COMMENT ON TABLE operational.messages IS AI 对话消息表，记录每一轮人机对话。;
COMMENT ON COLUMN operational.messages.conversation_id IS 所属会话ID，引用operational.conversations。;
COMMENT ON COLUMN operational.messages.role IS 消息角色：user / assistant / system。;
COMMENT ON COLUMN operational.messages.intent_type IS 解析出的意图类型。;
COMMENT ON COLUMN operational.messages.event_time IS 消息发生时间。;
COMMENT ON COLUMN operational.messages.metadata IS 消息扩展字段，例如日志ID。;
CREATE INDEX idx_messages_conversation_time ON operational.messages (conversation_id, event_time DESC);
CREATE INDEX idx_messages_intent ON operational.messages (intent_type);

