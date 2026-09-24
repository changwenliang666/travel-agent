# local-mysql Specification

## Purpose

让本机上的数据库客户端能够连接 Compose 中的 MySQL，并查看应用写入的库表。

## Requirements

### Requirement: MySQL is published on the host loopback

Compose 中的 MySQL MUST 把容器内的 3306 端口发布到本机回环地址上的一个端口。默认发布端口为 3306。该映射 MUST 可以通过环境变量改成其他本机端口。该端口 MUST NOT 绑定到非回环地址。应用服务 MUST 继续通过 Compose 网络内的数据库服务名访问 MySQL，而不是改走本机映射端口。

#### Scenario: A local client connects with the configured account

- **WHEN** 使用环境变量中的数据库名、用户名和密码，从本机连接 127.0.0.1 上的已发布端口
- **THEN** 连接成功，并且能列出该库中的表

#### Scenario: The host port can avoid a local conflict

- **WHEN** 本机 3306 已被占用，并且发布端口被配置成另一个端口
- **THEN** 从 127.0.0.1 的该端口可以连接 MySQL，应用服务仍能通过数据库服务名访问同一库

#### Scenario: The database is not published beyond the host

- **WHEN** 查看 MySQL 的端口发布配置
- **THEN** 发布地址是本机回环地址，而不是所有网络接口
