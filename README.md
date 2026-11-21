# 04.OECT — oect 运维工作区

这台设备是 **OEC BOX WXY4 / iStoreOS 24.10.5**（192.168.31.2），本目录是它的运维与文档工作区。

## 目录约定

| 目录 | 放什么 | 规则 |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | **主手册**（设备全景、坑点、服务配置、变更记录） | 唯一权威文档，改动后必须更新版本历史 |
| `docs/` | 专项文档 | 按主题分子目录，见 [`docs/README.md`](docs/README.md) |
| `backups/` | 设备配置备份 | `backups/<对象>/<日期>/`，全量跑完要校验 |
| `services/` | 部署到设备的服务源码 | `services/<名字>/`，与设备上 `/mnt/data_sda1/services/<名字>/` 对应 |

**不要在根目录放临时文件、散落产物。**

## 关于公开仓库

本仓库只收录**手册、脚本、文档**，刻意**不收录**以下内容（见 [`.gitignore`](.gitignore)）：

| 排除项 | 原因 |
|---|---|
| `backups/` | OpenBox 配置快照里有 67 个节点的 server / port / password / uuid **明文凭据** |
| `services/homeassistant/floorplan/` | 自家户型图，属私人平面布局 |
| `docs/oect/*/raw/` | 原始采集数据含 MAC、磁盘 UUID、完整包清单 |
| `downloads/` | 安装包等大文件 |

同时文档里已做脱敏：aria2 RPC 密钥、Clash API 密钥、磁盘 UUID 均替换为占位说明。

> 说明：文中保留 `192.168.31.x` 这类**私有网段地址**——不可路由、不构成密钥，保留是为了让命令可直接照抄。
> 若你想更彻底，把全文的 `192.168.31.2` 换成 `<oect-ip>` 即可，不影响阅读。

## 许可

| 范围 | 许可 |
|---|---|
| 代码（`services/` 下的脚本、配置模板） | [MIT](LICENSE) |
| 文档（`AGENTS.md`、`README.md`、`docs/`） | [CC BY-NC-SA 4.0](LICENSE-docs) |

简单说：**代码随便用**（保留版权声明即可），**文档可转载可改但需署名、非商用、同协议共享**。

## 设备侧约定（硬性）

1. **功能/模块/数据一律放外置盘** `/mnt/data_sda1/services/<名字>/`
   - 系统盘 `/` 只有 2G（已用 52%），只放配置、软链、init 脚本
   - 需要 HTTP 暴露就用 `/www/<名字>` 软链（已验证 uhttpd 跟随软链）
2. **能 cron 就不常驻**：批处理任务用「脚本 + cron」，不要为一个日更任务起容器
3. 改动后同步更新 `AGENTS.md` 对应章节 + 版本历史

## 当前服务

| 服务 | 地址 | 位置 |
|---|---|---|
| Samba 共享 | `\\\\192.168.31.2\\media`、`\\downloads` | 系统配置 + USB |
| Open-Box 面板 | `http://192.168.31.2:2026` | `/opt/open-box` |
| TVBox 接口 | `http://192.168.31.2/tvbox/config.json` | `/mnt/data_sda1/services/tvbox` |
| TVBox 状态页 | `http://192.168.31.2/tvbox/status.html` | 同上 |
| LuCI | `https://192.168.31.2/` | 系统 |
| AriaNg | `http://192.168.31.2/ariang` | 系统 |
