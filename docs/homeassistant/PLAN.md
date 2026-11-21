# 方案：在 oect 上部署 Home Assistant（v2 · 已检查）

> 状态：**待批准**，未执行
> v1 2026-11-15 00:05 → **v2 00:12**（验证阶段发现 2 处会失败的设计，已修正，见 §9）
> 设备：OEC BOX WXY4（RK3566 / 4×A55 / 4G）· iStoreOS 24.10.5 · Docker 27.3.1

---

## 1. 目标

在 oect 上跑一个可用的 Home Assistant，局域网可访问，能接 USB Zigbee/Z-Wave 棒与局域网设备。

**不做**：替代 HA OS 的全家桶；不追求加载项生态；不改变 OpenBox / Samba / nanobot 现有行为。

---

## 2. 方案对比

| 方案 | 可行性 | 结论 |
|---|---|---|
| **A. HA Container（Docker）** | ✅ 全部前置条件已验证（见 §9） | **推荐** |
| B. HA Supervised | ❌ 需 Debian+systemd+AppArmor，OpenWrt 不具备 | 排除 |
| C. HA OS | ❌ 整机镜像，会覆盖 iStoreOS | 排除 |
| D. 跑在 Windows 主机 | ⚠️ 可行但要求主机常开 | 备选 |

---

## 3. 架构

```
局域网 ──► oect:8123 ──► [homeassistant 容器]  network_mode: host
                              ├─ ./config        → /mnt/data_sda1/services/homeassistant/config
                              ├─ /run/dbus (ro)  → 蓝牙（插 USB dongle 时）
                              └─ /dev/tty*       → Zigbee/Z-Wave 棒（按需，见 §6 注）
```

- **host 网络**：mDNS/SSDP 发现必需（宿主 avahi 已在跑）
- **privileged**：访问 USB 设备
- 数据全部在 USB 盘，系统盘零占用（符合 §0）

---

## 4. 文件结构

```
/mnt/data_sda1/services/homeassistant/
├── docker-compose.yml
├── config/          # HA 配置 + 数据库
├── backups/         # 每日备份 tar.gz（保留 7 份）
├── backup.sh
└── README.md
```
工作区镜像：`E:\04.OECT\services\homeassistant\`

---

## 5. docker-compose.yml（v2 修正版）

```yaml
services:
  homeassistant:
    container_name: homeassistant
    image: ghcr.io/home-assistant/home-assistant:stable
    restart: unless-stopped
    network_mode: host
    privileged: true
    stop_grace_period: 60s        # 官方模板同款：HA 关库慢，给足时间防损坏
    environment:
      - TZ=Asia/Shanghai          # 宿主无 zoneinfo，靠这个；异常则改 TZ=CST-8
    volumes:
      - ./config:/config
      - /run/dbus:/run/dbus:ro
      # USB 棒插上后再放开下面这行（届时 /dev/serial/by-id 才会存在）
      # - /dev/serial/by-id:/dev/serial/by-id:ro
    mem_limit: 1500m
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8123/manifest.json',timeout=5)"]
      interval: 60s
      timeout: 10s
      retries: 5
      start_period: 600s
```

---

## 6. 实施步骤（预计 15 分钟）

| # | 步骤 | 验证点 |
|---|---|---|
| 1 | 建目录、写 compose / README / backup.sh | `docker compose config -q` 通过 |
| 2 | `docker compose pull`（~1.2 GB） | `docker images` 有镜像 |
| 3 | `docker compose up -d` | state=running |
| 4 | 轮询 8123 最多 10 分钟 | 返回 200 |
| 5 | 校验时区：`docker exec homeassistant date` | 显示 CST |
| 6 | 查日志无 CRITICAL | — |
| 7 | 每日 03:30 备份 cron | backups/ 有产物 |
| 8 | 更新 AGENTS.md §17 + 工作区副本 | 文档一致 |

> **注**：Zigbee/Z-Wave 棒现在没插，`/dev/serial/by-id` 不存在；等插上后再加那行挂载并重启容器。

---

## 7. 回滚

```sh
cd /mnt/data_sda1/services/homeassistant && docker compose down
# config/ 保留；确认不要了再删目录（回收 ~1.2 GB 镜像）
```
互不影响：OpenBox / Samba / nanobot 各自独立。

---

## 8. 资源预算

| 项 | 预算 | 依据（实测） |
|---|---|---|
| USB 磁盘 | 镜像 1.2 GB + 配置 100~300 MB | 空闲 107 GB |
| 内存 | 常驻 400~700 MB（上限 1.5 G） | 可用 3.13 GB |
| CPU | 稳态 ~5~15% | 负载 0.83 / 4 核 |
| 系统盘 | **0** | 全部落 USB |

---

## 9. 检查记录（v1 → v2：发现 2 处会失败的设计）

| # | 检查项 | 结果 | 对方案的影响 |
|---|---|---|---|
| 1 | `docker compose` 可用 | ✅ v2.39.1 | 无 |
| 2 | dbus + `/run/dbus/system_bus_socket` | ✅ 存在 | 蓝牙挂载可行 |
| 3 | HA `stable` 是否有 arm64 | ✅ manifest 含 `linux/arm64` | 无 |
| 4 | 端口 8123 | ✅ 空闲 | 无 |
| 5 | 内存 / 负载 | ✅ 可用 3.13 GB，load 0.83 | 无 |
| 6 | **宿主 zoneinfo 是否存在** | ❌ **`/usr/share/zoneinfo/Asia/Shanghai` 不存在**（OpenWrt 无 tzdata） | **v1 的挂载会失败 → 改为只用 `TZ` 环境变量** |
| 7 | **`/dev/serial/by-id` 是否存在** | ❌ **不存在**（没插棒） | **v1 的 bind mount 会建出空目录 → 改为注释掉、插棒后再开** |
| 8 | 镜像内是否有 curl（healthcheck） | ⚠️ 未确认，HA 镜像基于 Alpine，不保证有 curl | **healthcheck 改用 `python3`（HA 必有）** |
| 9 | 磁盘可写 | ✅ | 无 |
| 10 | 现有容器内存上限写法 | `1073741824`（1 GiB） | `mem_limit` 语法确认可用 |

**结论**：v1 有 3 处会在启动阶段直接报错/失效（#6 #7 #8），v2 已全部修正。

---

## 10. 评估

### 10.1 可行性评分（1~5）

| 维度 | 分 | 说明 |
|---|---|---|
| 硬件够不够 | 4 | A55×4 + 4G 能跑，代价是首次启动慢、UI 略卡 |
| 软件兼容 | 4 | Docker 容器自带运行时，不受 OpenWrt musl 影响；非官方支持平台扣 1 分 |
| 运维复杂度 | 3 | 无 Supervisor → 加载项要自己起容器、升级要手动 |
| 可回滚性 | 5 | 独立容器，down 即撤销 |
| 对现有服务影响 | 5 | 独立端口、独立目录、独立资源上限 |

### 10.2 收益 vs 成本

- **收益**：本地隐私的家庭自动化中枢；不依赖云端；能接 USB 棒；和现有 OpenBox（广告过滤）、Samba（媒体）天然互补
- **成本**：1.2 GB 磁盘 + 400~700 MB 常驻内存 + 每天维护注意力

### 10.3 三个真实风险（按概率排序）

1. **内存压力**（中）：这台机器有过 OOM 记录（nanobot 的 python3 被杀过）。对策：`mem_limit 1500m` + 上线后观察 `docker stats`
2. **TUN 干扰发现**（低）：HA 走 host 网络会经过 OpenBox TUN；内网已配直连规则，仍异常就把 HA 流量加白
3. **HA 升级破坏配置**（低）：用 `stable` 但手动升级，升级前自动备份

### 10.4 结论

**建议做，但按"最小可用"做**：先只跑 HA 本体，验证 8123 可访问、内存稳定；**Zigbee/ESPHome 等按需再加容器**，不要一次上一堆。
如果你是"只想手机控制几个插座/灯"，HA 有点重，但既然你要的就是它，容器形态是这台机器上唯一正确的形态。

---

## 11. 案例参考（GitHub / 官方文档，2026-11-15 查证）

| 案例 | 链接 | 我们吸收了什么 |
|---|---|---|
| **Home Assistant 官方容器 compose 模板** | `home-assistant/home-assistant.io` → `source/_includes/installation/container/compose.md` | 与我们的 v2 逐项对齐：`network_mode: host`、`privileged: true`、`/run/dbus`、`restart: unless-stopped`、`TZ`。**唯一差异**：官方挂 `/etc/localtime`，我们这台是悬空软链 → 改用 `TZ`。另补了官方的 `stop_grace_period: 60s`（关库慢，默认 10s 易损 DB） |
| **Seeed Studio 官方教程：OpenWrt 软路由跑 HA** | `seeed-studio/wiki-documents` → `sites/zh-CN/docs/Network/RK_Devices/LinkStar/Application/cn_h68k-ha-esphome.md`（LinkStar H68K，RK3568） | **同类型硬件 + OpenWrt + Docker 的完整成功案例**。两个经验：① 他们要先扩 Docker 空间（默认仅 ~250MB）——我们 Docker 根目录已在 107GB USB 盘上，无此问题；② 原文明确说"由于软路由的系统限制"，加载项要另想办法装（如 ESPHome 单独部署）→ **印证我们"无 add-ons"的判断** |
| **真实项目 compose** | `RastaChaum/Intelligent-Heating-Pilot` → `docker-compose.yml`（v0.5.0-rc2） | 与我们 v2 几乎一致：`ghcr.io/home-assistant/home-assistant:stable` + host 网络 + privileged + `/run/dbus` + `TZ`。说明这是社区主流写法，不是偏方 |
| **硬件同款背书：HA Green** | Nabu Casa 官方硬件 | **HA Green 用的就是 Rockchip RK3566 + 4GB 内存 + 四核 A55 @1.8GHz** —— 与 oect 同 SoC 同内存。相当于我们要跑的负载，就是官方硬件跑得动的负载（我们只少了 eMMC，用 USB 盘替代） |
| 社区实测 | HASSbian 论坛（电视盒子复刻 HA Green 帖） | 原话："RK3566 跑 HA 那是轻松加愉快，内存够还可以同时跑其他服务" |

### 案例对我们方案的影响

1. **硬件焦虑解除**：RK3566 是官方 HA Green 平台，性能不是问题；瓶颈只会在加载项和视频转码上。
2. **配置写法被三方印证**：官方模板 + 真实项目 + 厂商教程，三种来源的 compose 都是 host 网络 + privileged + dbus，v2 的方案没有自创风险。
3. **唯一需要偏离官方的地方**：不挂 `/etc/localtime`（本机悬空），改 `TZ`；这是环境差异，不是方案缺陷。
4. **新增一条**：`stop_grace_period: 60s`（官方模板有，v2 漏了，已补）。

> 所有引用内容均为公开文档/仓库，抓取于 2026-11-15；链接可能随上游变动。

---

## 12. 待你确认

1. 批准执行（我按 §6 逐条做，任何一步不过就停）
2. 或者：先只拉镜像验证架构兼容，不启动
3. 或者：改成跑在你的 Windows 主机上（方案 D）
