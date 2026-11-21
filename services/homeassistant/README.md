# Home Assistant（Container）— oect

宿主机：OEC BOX WXY4（RK3566 / 4×A55 / 4G）· iStoreOS 24.10.5 · Docker 27.3.1

| 项 | 值 |
|---|---|
| 访问地址 | `http://192.168.31.2:8123` |
| 数据目录 | `/mnt/data_sda1/services/homeassistant/config` |
| 备份目录 | `/mnt/data_sda1/services/homeassistant/backups`（保留 7 份） |
| 容器名 | `homeassistant` |
| 网络 | host（mDNS/SSDP 发现必需） |
| 内存上限 | 1800 MB（宿主无 swap） |

## 常用命令

```sh
cd /mnt/data_sda1/services/homeassistant
docker compose ps
docker compose logs -f --tail 100
docker compose restart                        # 改 configuration.yaml 后
docker compose pull && docker compose up -d   # 升级
sh backup.sh                                  # 手动备份
```

## 实测数据（2026-11-15 上线）

| 项 | 实测 |
|---|---|
| 首次启动到 healthy | ~80 秒 |
| 常驻内存 | 368 MB（上限 1.758 GB） |
| CPU | 0.2% |
| 镜像体积 | 2.38 GB |
| 局域网访问 | http 302 → onboarding，13 ms |

## 备份策略

- **不备份数据库**：HA 运行时 `home-assistant_v2.db` 处于热状态，直接 tar 会拿到损坏副本。
  `backup.sh` 已排除 `*.db / *.db-wal / *.db-shm / *.db-journal`，只备份核心配置与 `.storage`。
- 定时：每天 **03:30**（cron），保留最近 7 份。
- 恢复：`docker compose down` → 解包覆盖 `config/` → `docker compose up -d`。

## 写入优化

`configuration.yaml` 已加：

```yaml
recorder:
  commit_interval: 30
  purge_keep_days: 7
```

## 插入 USB Zigbee/Z-Wave 棒

⚠️ **不要**用 `volumes` 挂 `/dev/serial/by-id`（那里是相对软链，挂进容器会悬空）。

```sh
ls -l /dev/serial/by-id/       # 拿到真实设备路径
# docker-compose.yml 里加：
#   devices:
#     - /dev/serial/by-id/usb-ITead_...-if00-port0:/dev/ttyUSB0
docker compose up -d
```

## 已知问题：IPv6 组播 EPERM

容器内 `sendto ff02::fb` 报 `Operation not permitted`（宿主机同样受限）：

- 影响：HA 的 **IPv6** mDNS（zeroconf）/ SSDP（UPnP）发现不可用
- **IPv4 组播实测正常**，主流设备发现不受影响
- 本机 IPv6 只有 link-local，ULA 路由 unreachable，本来也没跑 IPv6 业务
- 启动日志里那两条 WARNING/ERROR 就是它，可忽略

## 排错

| 现象 | 排查 |
|---|---|
| 打不开 8123 | `docker compose ps`；`docker compose logs --tail 50` |
| 首次启动很久 | 正常，A55 上约 1~2 分钟（本次实测 80 秒） |
| 设备发现不到 | IPv4 组播正常；若仍异常查 OpenBox DNS 是否把 `.local` 放行 |
| 时间不对 | `docker exec homeassistant date`；不对就把 TZ 改成 `CST-8` |
| 内存告警 | `docker stats homeassistant`；吃紧就减集成或把 mem_limit 降到 1200m |
