## Purpose

把对话模型调用限制在一个主模型和一个备用模型上，并在主模型超时或服务端错误时按关闭、打开、半开三种状态切换。

## ADDED Requirements

### Requirement: Primary model is used while the breaker is closed

熔断器处于关闭状态时，系统 MUST 把模型调用发给配置的主模型。默认主模型名为 `qwen3.7-plus`。密钥和基地址 MUST 来自环境变量， MUST NOT 写进仓库。

#### Scenario: Normal request uses the primary model

- **WHEN** 熔断器处于关闭状态且主模型成功返回
- **THEN** 该次调用使用主模型，熔断器保持关闭

### Requirement: Failures open the breaker and send calls to the fallback

建连超时、首个 token 之前超时、连接错误和 HTTP 5xx MUST 计为失败。内容审核类 HTTP 4xx MUST NOT 计为失败。在配置的时间窗口内失败次数达到配置阈值时，熔断器 MUST 变为打开，之后的模型调用 MUST 使用备用模型，直到冷却时间结束。

#### Scenario: Threshold opens the breaker

- **WHEN** 主模型在配置窗口内的失败次数达到阈值
- **THEN** 熔断器变为打开，下一次模型调用使用备用模型

#### Scenario: Content rejection does not open the breaker

- **WHEN** 主模型因内容审核返回 HTTP 4xx
- **THEN** 该次结果不增加失败计数，熔断器状态不变

### Requirement: Half-open allows a single probe

冷却时间结束后，熔断器 MUST 变为半开。半开期间同时只允许一个试探请求发给主模型，其余模型调用 MUST 使用备用模型。试探成功后熔断器 MUST 关闭。试探失败后熔断器 MUST 重新打开。

#### Scenario: One probe and other calls stay on the fallback

- **WHEN** 熔断器处于半开且同时有多个模型调用
- **THEN** 只有一个调用发给主模型，其余调用使用备用模型

#### Scenario: Probe success closes the breaker

- **WHEN** 半开状态下的试探请求成功返回
- **THEN** 熔断器变为关闭

#### Scenario: Probe failure reopens the breaker

- **WHEN** 半开状态下的试探请求失败
- **THEN** 熔断器变为打开

### Requirement: A started reply is not handed to the other model

同一次面向用户的回复在已经输出任何 token 之后，系统 MUST NOT 改用另一个模型续写。若失败发生在任何 token 输出之前，系统 MUST 改用备用模型完成这一次调用。

#### Scenario: Failure before any token retries on the fallback

- **WHEN** 主模型在输出任何 token 之前超时或返回 5xx
- **THEN** 同一次调用改用备用模型，并向用户返回备用模型的结果

#### Scenario: Failure after tokens stops the turn

- **WHEN** 主模型已经向用户输出过 token，随后超时或中断
- **THEN** 系统停止这一轮并返回明确错误，且不会把备用模型的文本接在已输出内容后面
