# admin-observability Specification

## Purpose

记录每一轮对话的完整调用过程和 token 用量，并只允许管理员查看这些记录。普通用户仍然只能访问自己的对话和偏好。

## Requirements

### Requirement: Users sign in with a role

系统 MUST 要求调用对话、偏好、trace 和用量接口的请求先完成登录。用户角色只能是普通用户或管理员。未登录请求 MUST 被拒绝。

#### Scenario: Anonymous request is rejected

- **WHEN** 未登录客户端请求对话或管理接口
- **THEN** 系统拒绝该请求

#### Scenario: First startup creates an administrator

- **WHEN** 系统首次启动且还没有任何用户
- **THEN** 系统使用环境变量中的管理员用户名和密码创建一名管理员

### Requirement: Each turn has one trace

系统 MUST 为每一轮用户消息分配一个 `trace_id`，并在响应中返回它。该 trace MUST 包含这一轮的记忆读取、模型调用和工具调用。若发生上下文压缩，trace 也 MUST 包含这次压缩。模型调用记录 MUST 含有模型名、耗时、当时的熔断器状态和 token 数。工具调用记录 MUST 含有工具名、耗时和成功或失败。

#### Scenario: A planned trip trace shows model and tool steps

- **WHEN** 一轮消息生成了行程并调用了天气和网页搜索
- **THEN** 对应的 trace 同时包含这些模型调用和工具调用，且它们共享同一个 `trace_id`

#### Scenario: Client receives the trace id

- **WHEN** 一轮消息处理结束
- **THEN** 客户端能够从该次响应中得到 `trace_id`

### Requirement: Token usage is recorded from provider usage

系统 MUST 按供应商返回的用量记录 prompt token 和 completion token。上下文压缩和偏好抽取如果另一次调用了模型，也 MUST 各记一条用量。

#### Scenario: Side model calls are included

- **WHEN** 一轮对话除了主回复之外还执行了上下文压缩或偏好抽取
- **THEN** 用量记录里能分别看到这些调用，而不是只有主回复

### Requirement: Only administrators can read traces and usage

系统 MUST 拒绝普通用户查看 trace 详情和 token 统计。管理员 MUST 能够按对话查看 trace，并按用户和时间范围查看用量汇总。界面只向管理员展示这些入口；服务端仍 MUST 自行校验角色。

#### Scenario: Regular user calls the trace API

- **WHEN** 普通用户请求 trace 或用量接口
- **THEN** 系统拒绝该请求

#### Scenario: Administrator reads a trace

- **WHEN** 管理员按某一轮的 `trace_id` 查询
- **THEN** 系统返回该 trace 的全部步骤

#### Scenario: Administrator summarizes usage

- **WHEN** 管理员按用户和时间范围查询用量
- **THEN** 系统返回该范围内的 token 汇总
