# 文档索引

> 主手册（唯一权威）：[`AGENTS.md`](../AGENTS.md) —— 设备全景、坑点、各服务配置、版本历史都在里面。
> 本页只做**导航**：有哪些文档、对应哪块内容、以及记忆（memory）怎么分工。

## 文档

| 文档 | 内容 | 时间 |
|---|---|---|
| [`oect/2026-11-14/INVENTORY.md`](oect/2026-11-14/INVENTORY.md) | **设备全景摸底**：硬件/分区/文件系统地图/端口/DNS 链路/服务/Docker/OpenBox + 改动手册 + 问题清单（含 `raw/` 10 份原始采集） | 2026-11-14 |
| [`homeassistant/PLAN.md`](homeassistant/PLAN.md) | **HA 部署方案**（v3）：方案对比、compose、验证记录、社区案例、风险评估 | 2026-11-15 |
| `homeassistant/examples/` | 仪表盘风格参考截图（Mushroom / Mushroom Strategy / Bubble Card） | 2026-11-15 |
| `openclash-legacy/` | 2026-08 的 OpenClash 优化方案（**历史资料**，OpenClash 已于 2026-09-12 停用） | 2026-08-30 |

## 记忆分工（供其他对话引用）

| 记忆 | 管什么 |
|---|---|
| `oect-index` | 工作区入口：目录约定 + 记忆分工 + 当前状态快照 |
| `oect-device-inventory` | 硬件、存储、网络、工具链、Docker 底座 |
| `oect-services` | 在跑的服务清单（入口 / 位置 / 管理命令） |
| `oect-ha` | Home Assistant 专项（米家 OAuth、时区、IPv6、仪表盘） |
| `oect-extension-rules` | 新增功能硬性规则：一律外置盘 / 少常驻 / 文档整洁 |
| `user-wants-timely-escalation` | 遇到问题先报告求助，不蛮干 |

## 约定

- 新文档按主题建子目录：`docs/<主题>/`；采集类带日期：`docs/oect/<YYYY-MM-DD>/`
- 文件名：大写开头（`INVENTORY.md`）或小写短横线（`how-to-xxx.md`），不混用
- 专项文档**不要重复抄 AGENTS.md**，只写它没有的细节，然后回链过去
- 临时脚本放 `.tmp/` 且用完即删，不要留在根目录
