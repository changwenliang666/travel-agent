# memory Specification

## Purpose

在当前对话中保留近期上下文，在跨对话中保留用户偏好，并在上下文过长时把较早的内容压成摘要。

## Requirements

### Requirement: Current conversation keeps recent turns

系统 MUST 把当前对话的近期消息纳入后续模型调用的上下文。用户只能影响自己的对话记忆。

#### Scenario: Follow-up uses earlier turns in the same conversation

- **WHEN** 用户在同一对话中基于前几轮内容继续提问
- **THEN** 模型收到的上下文包含这些近期消息

#### Scenario: A new conversation does not include another conversation's recent turns

- **WHEN** 用户新建对话并发送第一条消息
- **THEN** 模型收到的短期上下文不包含其他对话的原文消息

### Requirement: User can view and edit long-term preferences

系统 MUST 为每个用户保存一份长期偏好，至少包括常住城市、行程节奏、预算、饮食限制，以及是否偏好早起。用户 MUST 能够查看和修改自己的偏好。其他用户 MUST NOT 读取或修改这份偏好。

#### Scenario: Preferences survive a new conversation

- **WHEN** 用户保存了偏好后新建另一条对话并请求行程
- **THEN** 新行程会使用这些已保存的偏好

#### Scenario: User edits a preference

- **WHEN** 用户在偏好页修改预算并保存
- **THEN** 之后的行程使用修改后的预算

### Requirement: Preference extraction does not delay the reply

系统 MUST 在回复已经交给用户之后，才可以从该轮对话更新长期偏好。这项更新失败 MUST NOT 改变已经返回的回复。

#### Scenario: Reply is returned before preference extraction finishes

- **WHEN** 用户的一轮对话会触发偏好更新
- **THEN** 用户先收到回复，偏好更新在回复之后进行

### Requirement: Long context is compressed into a rolling summary

当当前对话的上下文估算超过配置阈值时，系统 MUST 把较早的消息收成一份滚动摘要，并保留最近若干轮原文。网页搜索和工具结果 MUST 计入这个预算。摘要更新后，后续调用 MUST 使用摘要加上最近原文，而不是把被摘要替换的原文再次全部送入模型。

#### Scenario: Older turns become a summary

- **WHEN** 一条对话的上下文估算超过阈值
- **THEN** 下一次模型调用包含滚动摘要和最近原文，且不包含已被摘要替换的全部早期原文
