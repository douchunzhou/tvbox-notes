# oect 设备全景 · 只读探索快照

> **采集时间**：2026-11-14 22:51 – 23:05 CST（Asia/Shanghai）
> **采集方式**：全程 SSH 只读命令（cat / ls / df / ip / netstat / nft / docker ps / opkg list…），**未修改设备任何文件**
> **原始数据**：同目录 `raw/01-system.txt` … `raw/10-tools.txt`（逐条可复查）
> ⚠️ 本次发现设备**刚在 22:43:57 重启过**（此前连续运行 187 天），uptime 归零

---

## 0. 一分钟速览

| 项目 | 值 |
|---|---|
| 设备 | **OEC BOX WXY4**（board `rockchip,rk3566-oec-box-wxy4`） |
| 系统 | iStoreOS **24.10.5**（rev 2026022100，armsr/armv8，aarch64_generic，busybox taint） |
| 内核 | 6.1.141-rk35xx-ophub（2026-02-10 编译） |
| 根文件系统 | **btrfs**（compress=zstd:6，含 /etc 子卷 + 快照） |
| CPU / 内存 | RK3566（A55，CPU part 0xd05）/ 3.8 GiB，**swap = 0** |
| 系统盘 | `/dev/mmcblk0p2` 2.0G，已用 964.7M（**52%**），可用 902M |
| 数据盘 | `/dev/sda1` 115.6G ext4 → `/mnt/data_sda1`，已用 9.8G（9%） |
| 网络 | `eth0` 192.168.31.2/24，网关 192.168.31.1（旁路由/独立主机，非主网关） |
| 代理 | **OpenBox v0.1.415**（sing-box 1.14.4-openbox-45），TUN 透明代理 + 7080 共享入站 |
| 容器 | 2 个（nanobot-gateway / nanobot-api），Docker 27.3.1，数据在 USB |
| 面板入口 | 主路由 LuCI：`https://192.168.31.2/` ｜ OpenBox：`http://192.168.31.2:2026` |

---

## 1. 硬件与系统

| 项 | 值 |
|---|---|
| 机型 | OEC BOX WXY4 |
| 板卡 | rockchip,rk3566-oec-box-wxy4 |
| CPU | ARMv8 / Cortex-A55（CPU part 0xd05），BogoMIPS 48，features 含 aes/sha2/crc32/atomics |
| 内存 | MemTotal 3990860 kB（3.8 GiB），无 swap |
| 启动时间 | 2026-11-14 22:43:57 |
| 时区 | `/etc/TZ` = CST-8，UCI system.timezone=CST-8，zonename=Asia/Shanghai |
| 主机名 | iStoreOS |
| 日志 | log_size=128KB，logd 写 /tmp（**重启即丢**，所以看不到上次重启原因） |

**sysctl 现状**（/etc/sysctl.d/ 6 个文件：10-default、11-br-netfilter、11-nf-conntrack、12-nf-conntrack-max、30-quic-go-buffer-size、99-download-boost）
- `net.ipv4.tcp_congestion_control = bbr`
- `net.core.rmem_max = 67108864`
- `net.ipv4.tcp_fastopen = 3`

---

## 2. 存储与分区

### 分区表（/proc/partitions / blkid）

| 设备 | 大小 | 卷标 | 文件系统 | 挂载点 | 用量 |
|---|---|---|---|---|---|
| mmcblk0p1 | 462M | BOOT | ext4 | `/boot` | 69.8M / 15% |
| mmcblk0p2 | 2.0G | ROOTFS | **btrfs** | `/` | 964.7M / **52%** |
| mmcblk0p3 | 1023M | MMC_ROOTFS2 | btrfs | `/mnt/mmcblk0p3` | 5.6M / 1%（基本空） |
| mmcblk0p4 | 3.6G | MMC_SHARED | btrfs | `/mnt/mmcblk0p4` | 5.7M / 0%（基本空） |
| sda1 | 115.6G | — | ext4 | `/mnt/data_sda1` | 9.8G / 9% |

- `sda1` UUID `<已脱敏>`，SMART：**PASSED**，通电 184h，温度 28℃，重映射 0
- `/etc/config/fstab` 里 `/boot` 写的是 **vfat**，实际是 **ext4**（配置与实际不符，但靠 label=BOOT 挂得上）；另有 `/rom` 挂载项指向 rootfs UUID
- **btrfs 子卷**：`etc`（ID 256）、`.snapshots/etc-000`（ID 257）→ 系统里存在 /etc 的快照机制

### 系统盘占用（du -xsm /*）

| 目录 | 大小 | 说明 |
|---|---|---|
| /usr | 973M | opkg 安装的软件（大头） |
| /root | 253M | 含 .cache / .deno / .docker 等 |
| /lib | 228M | 库 + 内核模块 |
| /opt | 209M | **open-box** 占大部分 |
| /boot | 70M | 内核 + dtb |
| /etc | 55M | 配置 |

### 关键挂载特性

- `/tmp` 是 **tmpfs 内存盘（1.9G）**，`/var -> /tmp`（符号链接）→ **放 /tmp 的东西重启全丢**
- `/run -> /tmp/run`
- Docker 根目录 `/mnt/data_sda1/docker`（overlay2 在 USB 盘）

---

## 3. 文件系统地图（改配置看这里）

### 系统配置（UCI，改完要 `uci commit <pkg>`）

| 路径 | 内容 | 备注 |
|---|---|---|
| `/etc/config/network` | 接口/IP/网关 | lan = eth0 静态 192.168.31.2 |
| `/etc/config/dhcp` | dnsmasq + odhcpd | 本机 dhcp 关闭，只做 DNS |
| `/etc/config/firewall` | nft 规则（zones/rules） | lan ACCEPT，wan forward REJECT |
| `/etc/config/dockerd` | Docker 数据根、iptables=0 | |
| `/etc/config/fstab` | 挂载表 | |
| `/etc/config/system` | 主机名/时区/NTP/日志 | |
| `/etc/config/dropbear` | SSH 服务 | **允许密码登录** |
| `/etc/config/samba4` | SMB 共享 | media 共享 |
| `/etc/config/aria2` | aria2 + **rpc-secret** | 敏感 |
| `/etc/config/uhttpd` | LuCI 后端 | http 127.0.0.1:8080 / https 443 |
| `/etc/config/nginx` | 前置反代 | 80 → 8080 / newapi → 3000 |
| `/etc/config/ttyd` | Web 终端 | `/bin/login`，端口 7681 |
| `/etc/config/filebrowser` | 文件管理器 | **enable=0**（未启用），admin/admin |
| `/etc/config/openclash` | 已弃用的 OpenClash | 12KB，服务 inactive |

### 自启动/自定义脚本

| 路径 | 作用 |
|---|---|
| `/etc/rc.local` | 启动收尾：`mount -o remount,rw /` + 调 custom_service |
| `/etc/custom_service/start_service.sh` | ophub 通用自定义启动（日志 `/tmp/ophub_start_service.log`） |
| `/etc/crontabs/root` | **只有一条**：`0 3 * * * /usr/bin/update-trackers.sh` |
| `/etc/init.d/*` | procd 服务脚本；`/etc/rc.d/S*` 为开机自启 |
| `/usr/bin/update-trackers.sh` | BT tracker 自动更新 |

### 代理（Open-Box）

| 路径 | 作用 |
|---|---|
| `/opt/open-box/bin/sing-box` | 内核二进制（1.14.4-openbox-45） |
| `/opt/open-box/etc/config.json` | **运行时配置（88K，面板生成，手改会被覆盖）** |
| `/opt/open-box/etc/config.candidate.json` | 候选配置（面板改完待生效） |
| `/opt/open-box/etc/config.meta.json` | 配置元数据（1.2M） |
| `/opt/open-box/data/openbox.sqlite` | 面板数据库（21M，节点/流量/DNS 记录） |
| `/opt/open-box/data/rulesets/*.srs` | 规则集（24 个，可重下） |
| `/opt/open-box/data/flip/` | 故障转移/翻转状态 |
| `/opt/open-box/data/cache.db` | DNS 缓存（fake-ip） |
| `/etc/init.d/openbox` · `openbox-panel` | 两个 procd 服务 |
| `/usr/bin/open-box` | **面板 CLI**（password/port/restart/check/update/uninstall） |
| `/usr/lib/lua/luci/` · `/www/` | LuCI 与 Web 根目录 |

### 数据盘布局（/mnt/data_sda1）

```
/mnt/data_sda1/
├── Configs/        (空? 配置备份预留)
├── apps/           temp_vision_images
├── cache/          camoufox / node-compile-cache / uv
├── docker/         ← Docker 数据根（overlay2）
├── downloads/      ← aria2 默认下载（属主 aria2）
├── lost+found/
├── media/          ← Samba 共享（media）
├── nanobot/        ← docker-compose.yml + repo/ + config/ + backup-*
├── new-api/        ← 只有 data/（New API 未运行）
├── nodejs/         ← Node 运行时（glibc+musl 双版本）
└── tmp_pip/
```

### 用户目录

| 路径 | 内容 |
|---|---|
| `/root/.ssh` | known_hosts（空），**没有 authorized_keys** |
| `/etc/dropbear/authorized_keys` | **真正的 SSH 公钥**（1 条，ed25519，SHA256:i/bY69E0…） |
| `/root/AGENTS.md` | 设备上的一份旧副本（2026-08-30，17KB）← 与本地工作区不同步 |
| `/root/openclash-backup-20260830-2014.yaml` | 旧 OpenClash 配置备份 |
| `/root/.deno/bin/deno` | deno 二进制（85M，**不在 PATH**） |
| `/root/.config/yt-dlp/config` | yt-dlp 全局配置（见问题清单） |

---

## 4. 网络

### 接口

| 接口 | 状态 | 地址 | 说明 |
|---|---|---|---|
| lo | — | 127.0.0.1/8 | |
| eth0 | UP | 192.168.31.2/24 | 主网口 |
| dheth0@if17 | UP | 无 IPv4 | 桥 br-lan 的成员之一（UCI 里 br-lan = eth0 + dheth0，但 lan 实际绑 eth0） |
| openbox-tun | UP | 172.19.0.1/30 | sing-box TUN（透明代理） |
| docker0 | **DOWN** | 172.17.0.1/16 | 未使用 |
| br-7cb20008cea0 | UP | 172.18.0.1/16 | nanobot_default 网桥 |

### 路由 / 策略路由

- 默认路由：`default via 192.168.31.1 dev eth0`
- `ip rule` 有 6 条 mark 规则（8998–9002，0x2024/0x2023 等）→ **sing-box 的 fwmark 分流**，改网络前务必先看
- **nft 表**：`inet fw4`（防火墙）、`inet openbox`（TUN 入口放行）、`inet sing-box`（内核自己的规则），ruleset 共 **2623 行**

### DNS（链条要记牢）

```
局域网设备 → dnsmasq :53  →（noresolv，唯一上游）→ 127.0.0.1#7853 (sing-box dns-in) → 上游/代理
```

- dnsmasq 监听 53：127.0.0.1 / 192.168.31.2 / 172.17.0.1 / 172.18.0.1 / 172.19.0.1 / ::1
- `/etc/config/dhcp` 里 **`noresolv '1'` + `list server '127.0.0.1#7853'`** → DNS 全交给 Open-Box，改 DNS 策略得动 OpenBox 面板
- `filter_aaaa '1'`（过滤 AAAA 应答）、`ednspacket_max 1232`
- 静态域名：`time.android.com → 203.107.6.88`
- `/etc/resolv.conf` → `nameserver 192.168.31.1`（系统自身解析走网关）
- 代理侧 fake-ip 段 198.19.0.0/16（cache.db.fakeip-…）

### DHCP

- `config dhcp 'lan'` → **dhcpv4 disabled + ignore=1**；`config odhcpd` → `maindhcp '0'`
- 结论：**这台机器不派 IP**（主路由 192.168.31.1 才派），它只是"旁挂 DNS + 代理 + 存储 + 容器"节点

### 端口清单（谁在听）

| 端口 | 进程 | 绑定 | 用途 |
|---|---|---|---|
| 22 | dropbear | 0.0.0.0/:: | SSH（**允许密码**） |
| 80 | nginx | 0.0.0.0 | 反代：/ → 8080，/newapi/ → 3000 |
| 443 | uhttpd | 0.0.0.0/:: | LuCI HTTPS |
| 8080 | uhttpd | 127.0.0.1 | LuCI HTTP（仅本机） |
| 139/445 | smbd | 192.168.31.2 | Samba |
| 111/2049/32777-32780 | rpcbind/nfsd | 0.0.0.0 | NFS（**当前无 export，空跑**） |
| 6800 | aria2c | 0.0.0.0 | aria2 RPC |
| 7681 | ttyd | 0.0.0.0 | **Web 终端（root shell）** |
| 2026 | node(panel) | ::: | **Open-Box 面板 UI** |
| 7854 | node(panel) | 127.0.0.1 | 面板 API |
| 7891 | sing-box | 127.0.0.1 | **mixed 代理（HTTP+SOCKS）** |
| 7853 | sing-box | 0.0.0.0 | dns-in |
| 9095 | sing-box | 127.0.0.1 | Clash API |
| 7080 | sing-box | ::: | **共享入站（无认证）** |
| 8765/18790 | docker-proxy | 0.0.0.0 | nanobot-gateway |
| 8900 | docker-proxy | 127.0.0.1 | nanobot-api |
| 3200 | FastNet | ::: | iStoreOS 内置 |
| 5355/3702 | wsdd2 | 0.0.0.0 | Windows 发现 |

### 防火墙要点（UCI firewall）

- zones：lan（ACCEPT/ACCEPT/ACCEPT，masq）、wan（input ACCEPT，forward REJECT，masq，mtu_fix）
- defaults：input REJECT、output ACCEPT、forward REJECT、`fullcone 2`、synflood 保护开

---

## 5. 服务与自启

### 开机自启（rc.d S*，节选关键）

`dnsmasq, dropbear, firewall, network, dockerd, openbox, openbox-panel, samba4, aria2, nginx, uhttpd, ttyd, nfsd, rpcbind, avahi-daemon, smartd, cron, wsdd2, miniupnpd, odhcpd, sysntpd, fastnet, istore, quickstart, ddnsto, filebrowser, unishare, webdav2, openclash`

> ⚠️ `openclash` **在 rc.d 里是启用的**，但 UCI enable 状态下服务为 inactive（不占资源，但二进制在 → 见坑9）。

### 当前运行状态

| 服务 | 状态 |
|---|---|
| samba4 | running |
| aria2 | running（root 身份） |
| openbox + openbox-panel | running |
| dockerd | running |
| nginx / uhttpd / dnsmasq / dropbear | running |
| nfsd / rpcbind | 在跑但无共享 |
| ttyd | running（7681） |
| filebrowser | **未启用**（enable=0） |
| openclash | inactive |

---

## 6. 软件与工具链

- opkg 包：**977 个**
- 关键版本：

| 工具 | 版本 | 备注 |
|---|---|---|
| python3 | 3.11.14（pip 23.3.1） | |
| node | v24.14.0 / npm 11.9.0 | |
| ffmpeg | 6.1.3 | **ffprobe 缺失** |
| yt-dlp | 2026.08.19 | 配置有坑，见问题清单 |
| aria2c | 1.37.0 | |
| deno | 85M 二进制在 `/root/.deno/bin/deno` | **不在 PATH**（用绝对路径才生效） |
| jq / curl / git | 1.8.1 / 8.12.1 / 2.50.1 | |
| docker / compose | 27.3.1 / 2.39.1 | |
| sqlite3 / uv / ffprobe | **均无** | 写脚本别依赖 |

---

## 7. Docker

| 项 | 值 |
|---|---|
| 版本 | 27.3.1（cgroup v2 / cgroupfs） |
| 数据根 | `/mnt/data_sda1/docker`（overlay2） |
| 配置 | `/etc/config/dockerd`（**iptables=0**），`/etc/docker/daemon.json` 不存在 |
| 网络 | bridge 172.17（未用）、nanobot_default 172.18.0.0/16 |

| 容器 | 镜像 | 端口 | 状态 |
|---|---|---|---|
| nanobot-gateway | nanobot-nanobot-gateway | 0.0.0.0:8765、0.0.0.0:18790 | Up |
| nanobot-api | nanobot-nanobot-api | 127.0.0.1:8900 | Up |

- 编排文件：`/mnt/data_sda1/nanobot/docker-compose.yml`（`build.context: ./repo`，源码构建）
- 卷：命名卷 0 个；配置走 bind mount `./config:/home/nanobot/.nanobot`

---

## 8. Open-Box 详解

| 项 | 值 |
|---|---|
| 版本 | OpenBox **v0.1.415** / sing-box **1.14.4-openbox-45** / commit `cda098a`（2026-11-07 构建） |
| 内核进程 | `/opt/open-box/bin/sing-box run -c /opt/open-box/etc/config.json -D /opt/open-box/data` |
| 面板进程 | `/opt/open-box/node/bin/node --max-old-space-size=160 .../panel/server/index.mjs` |
| 面板 UI | `http://192.168.31.2:2026`（监听 `::`） |
| 面板 API | `127.0.0.1:7854` |
| CLI | `open-box password|port|restart|start|check|update|uninstall` |

**配置骨架**（详细结构见 `backups/openbox/2026-11-12/`）
- inbounds：`tun-in`（TUN）、`panel-in`（7891）、`dns-in`（7853）、`share-smvmgmodqgira`（**7080，无认证**）
- outbounds 99：ss 39 / anytls 14 / vmess 14 + selector 22 + urltest 7
- 分组：地区「自动/手动」双轨（所有 67、日本 20、香港 17、新加坡 6、台湾 3、美国 3、韩国 1）+ 15 个应用组

**面板数据库表**（openbox.sqlite，只读查询）

| 表 | 行数 |
|---|---|
| traffic_daily | 89,351 |
| dns_filter_records | 19,998 |
| node_quality_hours | 1,512 |
| dns_filter_domains | 426 |
| app_storage | 121 |
| bandwidth_samples / bandwidth_history_bindings | 56 / 56 |
| dns_filter_hours | 25 |

---

## 9. 用户 · 认证 · 共享

| 项 | 状态 |
|---|---|
| 登录用户 | `root`（/bin/bash）；另有 nanobot(1000)、aria2(6800)、openclawmgr(999，锁定) 等 |
| SSH | dropbear :22，**PasswordAuth=on、RootPasswordAuth=on**；公钥 1 条在 `/etc/dropbear/authorized_keys` |
| OpenWrt 界面 | LuCI `https://192.168.31.2/` → uhttpd:8080；nginx:80 做前置 |
| Samba | `media` → `/mnt/data_sda1/media`，**guest_ok=yes、read_only=no、force root** |
| aria2 | root 运行，RPC 6800 带 `rpc-secret`（在 /etc/config/aria2） |
| ttyd | `/bin/login`，**0.0.0.0:7681** |
| filebrowser | 未启用；假如启用是 admin/admin |
| Open-Box 面板 | 密码可用 `open-box password` 查 |

---

## 10. ⚠️ 危险区 / 改之前必读

1. **别在设备上跑 `/etc/openclash/clash`**（哪怕 `-t`）→ Open-Box 冲突检测会**停掉自己的内核**（2026-11-12 已踩，见 AGENTS.md 坑9）
2. **系统盘只有 2G（已用 52%）**，任何下载/解压/构建都指向 `/mnt/data_sda1`
3. **`/tmp` 是内存盘，`/var` 指向 `/tmp`** → 重启全丢；日志也只活到重启
4. **根是 btrfs + /etc 子卷 + 快照**（`.snapshots/etc-000`）：改 `/etc` 大量文件前建议先做快照
5. **Open-Box 的 config.json 由面板生成**，手改会被面板覆盖 → 要改配置走面板或改面板数据
6. **改网络/UCI**：`uci set/batch` → `uci commit <pkg>` → 重启对应服务；动 firewall/network 前先准备好串口/物理接触方案
7. **动 TUN / ip rule 前**先记录 `ip rule` 与 `nft list ruleset`，否则很难回滚
8. **Docker 数据在 USB 盘**，别在跑容器时拔盘
9. 面板 2026、ttyd 7681、共享入站 7080 都**对局域网开放**，改这些端口前想清楚

---

## 11. 常见改动：改哪里 / 怎么生效 / 怎么回滚

| 想做的事 | 改这里 | 生效方式 | 回滚 |
|---|---|---|---|
| 改 IP / 网关 | `/etc/config/network` | `/etc/init.d/network restart` | 改回 + restart（建议先 `cp` 备份） |
| 开/关端口转发、防火墙 | `/etc/config/firewall` | `/etc/init.d/firewall restart` | 同上 |
| 加 SMB 共享 | `/etc/config/samba4`（段类型必须 `sambashare`） | `/etc/init.d/samba4 restart` | 删段 + restart |
| 改 aria2 参数 | `/etc/config/aria2` → 提交后生成 `/var/etc/aria2/aria2.conf.main` | `/etc/init.d/aria2 restart` | 同上 |
| 改 SSH 端口/密码登录 | `/etc/config/dropbear` | `/etc/init.d/dropbear restart` | 小心把自己关外面，先留一个会话 |
| 改代理节点/分组 | **面板 UI :2026**（不要手改 config.json） | 面板「应用」 | 面板回滚/或恢复备份的 config.json |
| 查/改面板密码、端口 | `open-box password` / `open-box port <端口>` | 自动重启面板 | `open-box port <旧端口>` |
| 升级 Open-Box | `open-box check` → `open-box update` | 自动 | 旧版安装包/回滚见 update.sh |
| 改时区/NTP | `/etc/config/system` | `/etc/init.d/system restart`（或 reboot） | 同上 |
| 加开机自启脚本 | `/etc/custom_service/start_service.sh` 或新增 init.d | reboot | 注释掉 |
| 跑定期任务 | `/etc/crontabs/root` | `/etc/init.d/cron restart` | 删行 + restart |

---

## 12. 本次发现的问题清单（只读观察，未修）

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | `/root/.config/yt-dlp/config` 里 `--proxy http://127.0.0.1:7890` **已失效**（OpenBox 用 7891，7890 无人监听） | yt-dlp 走该代理必失败 | 改成 7891（或删掉该行走 TUN） |
| 2 | `/etc/localtime` → `/mnt/data_sda1/hermes_data/localtime_shanghai`，**目标已不存在** | 悬空链接；时间实际靠 `/etc/TZ` | 重新指向 `/usr/share/zoneinfo/...` 或删链接 |
| 3 | nginx 80 配了 `/newapi/ → 127.0.0.1:3000`，但 **3000 没在监听**（new-api 容器未运行；数据库 `/mnt/data_sda1/new-api/data/one-api.db` 1.6M 还在） | 访问 `/newapi/` 502 | 要么起服务，要么删这段 |
| 4 | Open-Box 共享入站 7080 监听 `::`、`users: null` | 同网段任何人可当代理用 | 改绑 127.0.0.1 或加认证 |
| 5 | ttyd 7681 = root shell，对全网开放 | 高（等于免密登录入口） | 不用就停用/绑本机 |
| 6 | dropbear 允许 root 密码登录 | 中（公网未暴露，但 LAN 内可爆破） | 只留公钥登录 |
| 7 | NFS/rpcbind 在跑但 `/etc/exports` 为空 | 多开 4 个端口无收益 | 不用就停 |
| 8 | `/boot` 在 fstab 里写成 vfat，实际 ext4；`/rom` 挂载项指向 rootfs UUID | 配置漂移，重刷可能挂错 | 顺手校正 |
| 9 | `/root/AGENTS.md` 是 8-30 的旧副本 | 与本地工作区文档不一致，容易看错 | 同步或删除 |
| 10 | `deno` 不在 PATH、`ffprobe` 缺失、无 `sqlite3` 命令行 | 脚本若按 PATH 找会失败 | 用绝对路径 / 补包 |
| 11 | 设备 **2026-11-14 22:43:57 重启**，此前 187 天未重启；日志在 /tmp 已丢 | 原因不明（断电/看门狗/手动） | 若再发生，建议配持久日志到 USB |

---

## 13. 原始数据索引

| 文件 | 内容 |
|---|---|
| `raw/01-system.txt` | 内核/发行版/board/CPU/内存/时区/sysctl/dmesg |
| `raw/02-storage.txt` | df/分区/blkid/btrfs/挂载/du/fstab//mnt |
| `raw/03-network.txt` | 接口/路由/ip rule/UCI network+dhcp/resolv/端口/nft/防火墙 |
| `raw/04-services.txt` | init.d/rc.d/进程/crontab/inittab/system/NTP |
| `raw/04b-packages.txt` | **977 条 opkg 包全量清单** |
| `raw/05-docker.txt` | docker info/容器/镜像/网络/compose/磁盘 |
| `raw/06-openbox.txt` | Open-Box 目录/init 脚本/面板端口/sqlite 表 |
| `raw/07-security.txt` | passwd/shadow 权限/dropbear/uhttpd/nginx/luci/samba/aria2 |
| `raw/08-openbox-tree.txt` | 目录树/日志尾部/重启线索 |
| `raw/09-misc.txt` | **uci export 全量配置**（含密钥，注意保密） |
| `raw/10-tools.txt` | rc.local/root 目录/opt/工具版本/top |

> 🔐 `raw/09-misc.txt` 与 `raw/07-security.txt` 含明文密钥（aria2 token、samba secrets 路径等），**不要外发/上云**。

---

*采集者：DSH（DeepSeek Harness）· 全程只读，命令见 raw/ · 下次改配置前先看 §10 与 §11*
