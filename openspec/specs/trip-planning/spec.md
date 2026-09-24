# trip-planning Specification

## Purpose

让已登录用户在对话里得到一份可修改的多日行程；目的地或天数不足时，系统先追问，这一轮不调用外部工具。

## Requirements

### Requirement: Authenticated user can start a conversation

系统 MUST 只允许已登录用户创建和查看对话。每条对话只属于创建它的用户。

#### Scenario: Create an empty conversation

- **WHEN** 已登录用户新建对话
- **THEN** 系统返回一个没有历史消息、也没有行程的对话

#### Scenario: User cannot read another user's conversation

- **WHEN** 已登录用户请求不属于自己的对话
- **THEN** 系统拒绝该请求

### Requirement: Missing key facts produce a clarifying question

当目的地为空，或天数不是 1 到 14 的整数时，系统 MUST 只返回一句澄清问题。这一轮 MUST NOT 查询天气、网页、地点或路径。

#### Scenario: Destination is missing

- **WHEN** 用户要求规划行程但没有给出目的地
- **THEN** 系统追问目的地，并且不产生行程

#### Scenario: Days are missing or out of range

- **WHEN** 用户给出了目的地但没有给出天数，或天数大于 14
- **THEN** 系统追问一个 1 到 14 天的行程长度，并且不产生行程

#### Scenario: Dates may be omitted

- **WHEN** 用户给出了目的地和合法天数，但没有给出日期
- **THEN** 系统仍然生成行程

### Requirement: Sufficient facts produce a day-by-day itinerary

目的地和合法天数都具备时，系统 MUST 返回 Markdown 说明，以及按天排列的行程。每一天包含标题、当天安排；能拿到天气时，当天包含天气摘要。回复 MUST 带上来源标题和链接（如果使用了网页搜索结果）。

#### Scenario: Build a multi-day plan

- **WHEN** 用户给出目的地和 1 到 14 的天数
- **THEN** 系统返回 Markdown 说明和一份覆盖这些天的行程，且每一天都有安排

#### Scenario: Progress is visible before the reply finishes

- **WHEN** 系统正在查询外部信息或撰写行程
- **THEN** 客户端先收到对应的进度说明，再收到回复正文

### Requirement: Existing itinerary can be revised as a whole

已有行程时，用户的修改请求 MUST 得到一份完整的新行程，而不是只返回被点名的那一天。目的地和出发日期都没有变化时，系统 MUST NOT 再次查询天气或网页。

#### Scenario: Revise one day

- **WHEN** 用户要求修改已有行程中的某一天，且目的地和出发日期不变
- **THEN** 系统返回更新后的完整行程，并且这一轮没有新的天气或网页查询

#### Scenario: Change destination

- **WHEN** 用户把已有行程的目的地改成另一个城市
- **THEN** 系统按新目的地返回一份新的完整行程

### Requirement: User can ask about the current itinerary

针对已有行程的提问，系统 MUST 基于该行程作答。这一轮最多发起一次外部查询。

#### Scenario: Ask how to travel between two stops

- **WHEN** 用户询问行程中两个地点之间怎么走
- **THEN** 系统返回路径说明，且这一轮的外部查询不超过一次

#### Scenario: Ask a question that needs no lookup

- **WHEN** 用户询问的内容已经包含在当前行程说明里
- **THEN** 系统直接回答，且这一轮没有外部查询
