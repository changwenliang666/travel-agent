# chat-ui Specification

## Purpose

规定对话页如何呈现查询进度和逐步到达的回复，以及输入快捷键和顶栏在滚动时的位置。

## Requirements

### Requirement: Query progress appears inside the assistant bubble

用户发出一条消息后，在面向用户的回复正文开始出现之前，系统发出的进度说明 MUST 显示在这一轮的助手气泡内部。进度说明 MUST NOT 只出现在气泡之外，而让该气泡保持空白。同一轮内新的进度说明 MUST 替换气泡里上一条进度说明。

#### Scenario: Search status fills the assistant bubble

- **WHEN** 用户发送一条消息，系统给出进度说明，且面向用户的回复正文尚未开始
- **THEN** 该进度说明显示在这一轮助手气泡内部

#### Scenario: A later status replaces the previous one

- **WHEN** 同一轮里系统先给出一条进度说明，随后又给出另一条，且回复正文仍未开始
- **THEN** 助手气泡内显示最新的进度说明

#### Scenario: Visible reply text replaces the status

- **WHEN** 助手气泡已经开始显示面向用户的回复正文
- **THEN** 气泡展示这段正文，而不再只显示进度说明

### Requirement: Assistant reply text appears incrementally

系统 MUST 按生成顺序把面向用户的回复文本分段送到客户端。客户端 MUST 在每一段到达时把它追加到当前助手气泡，而不是等全部正文到齐后一次渲染。行程卡片 MUST 在这一轮的行程数据就绪后显示。用来生成行程的结构化数据 MUST NOT 作为气泡正文显示。

#### Scenario: Early text is visible before the reply finishes

- **WHEN** 回复仍在生成，且客户端已经收到第一段面向用户的文本
- **THEN** 助手气泡立刻显示这段文本，并在后续段落到达时继续追加

#### Scenario: Plan structure stays out of the bubble

- **WHEN** 系统正在生成带有行程结构的回复
- **THEN** 助手气泡中出现的是面向用户的说明文本，而不是未解析的结构化数据

#### Scenario: The finished reply remains in the bubble

- **WHEN** 这一轮回复结束
- **THEN** 助手气泡保留完整的面向用户的回复；若这一轮带有行程数据，行程卡片与该回复一起显示

### Requirement: Enter sends and Shift+Enter inserts a newline

输入框含有非空白内容时，按下 Enter MUST 发送当前内容并清空输入框。按下 Shift+Enter MUST 在输入框中插入换行，且 MUST NOT 发送。输入框只有空白时，按下 Enter MUST NOT 发送。

#### Scenario: Enter sends the draft

- **WHEN** 输入框含有非空白内容，且用户按下 Enter
- **THEN** 该内容作为一条用户消息发送，输入框被清空

#### Scenario: Shift+Enter inserts a newline

- **WHEN** 用户在输入框中按下 Shift+Enter
- **THEN** 输入框插入一行换行，且不发送消息

#### Scenario: Enter on blank input does not send

- **WHEN** 输入框只有空白，且用户按下 Enter
- **THEN** 不发送消息

### Requirement: Header stays fixed while content scrolls

顶栏 MUST 固定在视口顶部，不随页面内容滚动。对话页的消息列表 MUST 在顶栏与输入区之间独立滚动。输入区 MUST 保持在消息列表下方的可见位置。

#### Scenario: Scrolling the conversation leaves the header and composer in place

- **WHEN** 对话消息超出可视区域，且用户滚动消息列表
- **THEN** 顶栏仍停留在视口顶部，输入区仍留在消息列表下方

#### Scenario: Other pages keep the header fixed

- **WHEN** 用户在偏好页或记录页滚动页面内容
- **THEN** 顶栏仍停留在视口顶部
