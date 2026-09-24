## Purpose

为行程生成和行程问答提供天气、地点、路径和网页摘要。任一外部查询失败时，系统仍用已经拿到的材料继续回答。

## ADDED Requirements

### Requirement: Map service supplies weather, places, geocoding, and routes

生成行程时，系统 MUST 能够按目的地查询天气和地点。用户询问两个地点之间怎么走时，系统 MUST 能够返回路径摘要。地点查询前，系统 MUST 能够把目的地解析为地理位置。

#### Scenario: Weather and places are collected for a new plan

- **WHEN** 系统为新的目的地和日期生成行程
- **THEN** 行程撰写所使用的材料包含该目的地的天气和地点结果（这些查询成功时）

#### Scenario: Route question uses the map service

- **WHEN** 用户询问行程里两个地点之间怎么走，且路径查询成功
- **THEN** 回答中包含这段路径的摘要

### Requirement: Web search returns a short list of sources

网页搜索 MUST 最多返回 5 条结果，且每条只包含标题、链接和短摘要。系统 MUST NOT 把网页全文放进模型上下文。

#### Scenario: Search results are capped

- **WHEN** 系统为行程检索网页资料
- **THEN** 交给模型的网页材料不超过 5 条，且每条含有标题和链接

### Requirement: Tool failure does not stop the turn

天气、地点、路径或网页查询失败时，系统 MUST 记录这次失败，并用已经拿到的材料继续生成回复。回复 MUST 说明哪一项没能查到。

#### Scenario: Web search times out

- **WHEN** 网页搜索超时或返回错误，且天气或地点查询已经成功
- **THEN** 系统仍然返回行程或回答，并说明网页资料没能取到

#### Scenario: All external lookups fail

- **WHEN** 生成行程所需的外部查询全部失败
- **THEN** 系统仍然返回基于用户要求和已有偏好的行程说明，并说明外部资料不可用
