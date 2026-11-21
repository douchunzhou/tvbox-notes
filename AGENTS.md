# OECT 项目规则 — iStoreOS (oect) 运维经验手册

> 基于 2026-08-29 完整部署调试过程沉淀，后续每次对话应引用此文件避免重复踩坑。

---

## 📜 文档进化规则（Living Document）

**本文件是活文档，每次对话后都应更新。**

### 更新原则

1. **踩坑即记录**：每次遇到新的报错、配置陷阱、非直觉行为，立刻追加到对应章节
2. **解决即沉淀**：问题解决后，把原因和方案写入，不只是"修好了"而是"为什么修、怎么修"
3. **想法即收录**：任何新的优化思路、工具发现、架构想法，先记到 `§12 待探索与想法`，实施后移到正式章节
4. **变更即同步**：配置发生变更时更新对应章节，标注变更日期
5. **定期回顾**：每次新对话开始时，快速扫一遍最近变更，看是否有可进一步优化的地方

### 版本历史

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-08-29 | 初版：Samba/aria2/yt-dlp 部署、OpenClash BT 放行、网络优化 | Reasonix |
| 2026-08-30 | Samba 共享 media、OpenClash DNS/分组优化尝试、代理分组 v3（引用式）、v4 四象限方案探索失败回滚、血泪教训沉淀 | Reasonix |
| 2026-08-30 | 全面体检：Docker 清理回收 2.1GB、删除 v3 备份残留、记录 ttyd/NFS/BT 规则等安全隐患 | Reasonix |
| 2026-09-12 | 代理从 OpenClash 切换到 OpenBox(sing-box)；nanobot 从 v0.3.0 升级到 main 修复 OpenCode x-opencode-session 问题（PR #5662） | Reasonix |
| 2026-09-12 | 磁盘空间整理：清理 camoufox/cloudflared/tmp_pip/旧 uv 缓存/docker dangling 镜像+build cache，系统盘 65%→52%、数据盘回收约 3G | Reasonix |
| 2026-11-12 | 新增 §14：OpenBox 配置结构摸底（JSON 非 YAML）、分组骨架、导出与校验手法、共享入站安全隐患；新增坑9（跑 OpenClash 的 clash 二进制会触发冲突检测停内核）；OpenBox→Clash/Mihomo YAML 转换 | DSH |
| 2026-11-14 | 新增 §15：oect 全量只读探索（分区/文件系统地图/端口/DNS 链路/工具链/Docker），订正过期信息，登记 7 个待处理问题 | DSH |
| 2026-11-14 | Samba 新增 `downloads` 共享（`/mnt/data_sda1/downloads`，匿名可读写）；记录「命令行测 SMB 会误报 error 5」的验证陷阱 | DSH |
| 2026-11-14 | 新增 §16 tvbox-hub：TVBox 接口中转站（`http://192.168.31.2/tvbox/config.json`，多源合并 + 每日 04:10 同步；配套中文状态页 status.html） | DSH |
| 2026-11-14 | 新增 §0 硬性约束（新增功能一律放外置盘 / 能脚本+cron 就不常驻 / 文档结构规范）；工作区重组：openclash 旧文档移入 docs/openclash-legacy，补 README.md 与 docs/README.md | DSH |
| 2026-11-15 | 新增 §17：Home Assistant Container 上线（:8123，368 MB 常驻，每日 03:30 备份）；记录 IPv6 组播 EPERM 的已知限制；新增 §17 仪表盘（/mushroom、/plan）；禁用云鲸+美的集成 | DSH |
| 2026-11-16 | 记忆整理：新增 `oect-index`/`oect-services`/`oect-ha` 三条项目记忆并互相交叉引用；`docs/README.md` 重写为「文档 + 记忆」双索引 | DSH |
| 2026-11-21 | §16 tvbox-hub 升级：新增 `mirrors.txt` 镜像机制 + `/tvbox/inliang.json`（Inliang 126 站点/10 直播分组）；sync.py 增加 spider 本地化（jar 下到本机并改写为内网地址）；状态页加镜像区块；新增 `!http-only` 补源（合并 38 站点）与每日验活 | DSH |
| 2026-11-21 | 新增 §18：工作区纳入 Git 管理并推送到 GitHub（`douchunzhou/tvbox-notes`，公开）；脱敏 aria2/Clash 密钥与磁盘 UUID，`.gitignore` 排除凭据快照、原始采集、户型图与大文件 | DSH |

---

## 0. 硬性约束（用户要求，优先于其他章节）

### 新增功能一律放外置盘

- 服务/模块/脚本/数据 → `/mnt/data_sda1/services/<名字>/`
- **系统盘 `/` 只有 2G（已用 52%）**，只允许放：UCI 配置、init 脚本、软链
- 需要 HTTP 暴露 → 建 `/www/<名字>` 软链（已实测 uhttpd 跟随软链可行），实体文件留在 USB

### 遇到问题立刻求助，不蛮干

- 命令失败/超时/进度异常/需要取舍时：**先报告现状 + 给 2~3 个可选处置**，等用户点头再动
- 同一条失败命令不反复重试；不因为"看起来没坏"就自动绕路
- 汇报带证据（耗时、速率、占用、日志片段），不要只说"有点慢"

### 能"脚本 + cron"就不要常驻

- 日更/定时类任务：`python3 + /etc/crontabs/root` 即可，不要为此起 Docker 容器
- 可视化需求优先用**静态页面**（sync 时顺手生成），其次才考虑 Web 服务
- 评估取舍时把内存/常驻进程/故障点算进去（设备 4G 内存，现用约 1G）

### 文档结构

本地工作区 `E:\04.OECT` 固定结构，根目录不放临时文件：

| 目录 | 内容 |
|---|---|
| `AGENTS.md` | 主手册（唯一权威） |
| `docs/` | 专项文档，按主题分子目录（见 `docs/README.md`） |
| `backups/<对象>/<日期>/` | 设备配置备份 |
| `services/<名字>/` | 部署到设备的服务源码，与设备 `/mnt/data_sda1/services/<名字>/` 一一对应 |

---

## 1. 设备概况

| 项目 | 值 |
|------|-----|
| 主机名 | `oect` |
| SSH 别名 | `oect`（`~/.ssh/config` 中配置） |
| 系统 | **iStoreOS 24.10.5**（基于 OpenWrt，非标准 Linux） |
| 架构 | aarch64 (ARM64) |
| 内核 | 6.1.141 |
| 包管理器 | **opkg**（不是 apt/yum/pacman） |
| LAN IP | `192.168.31.2` |
| 网关 | `192.168.31.1` |
| 系统盘 | `/dev/mmcblk0p2` 2G（已用 ~52%，可用 ~890MB，空间仍偏紧） |
| USB 硬盘 | `/dev/sda1` → `/mnt/data_sda1` 115.6G（主要数据盘） |
| 内存 | 4GB（可用 ~3GB） |

### 磁盘分区

| 挂载点 | 设备 | 大小 | 用途 |
|--------|------|------|------|
| `/` | mmcblk0p2 | 2G | 系统（⚠️ 空间紧张） |
| `/boot` | mmcblk0p1 | 462M | 启动 |
| `/mnt/mmcblk0p3` | mmcblk0p3 | 1G | 空 |
| `/mnt/mmcblk0p4` | mmcblk0p4 | 3.6G | 空 |
| `/mnt/data_sda1` | sda1 | 115.6G | **USB 硬盘，主要存储** |

---

## 2. ⚠️ 关键坑点（必须记住）

### 坑1：OpenWrt 的 opkg ≠ apt

- 不是标准 Linux 发行版，**没有 apt、yum、systemd**
- 用 `opkg install <package>` 安装软件
- 配置文件在 `/etc/config/` 下，使用 **UCI 格式**（不是普通的 ini/yaml）
- 服务管理用 `/etc/init.d/<service> start|stop|restart|enable|status`

### 坑2：代理拦截一切（⚠️ 2026-09-12 起已从 OpenClash 切换到 OpenBox）

> ⚠️ **重大变更（2026-09-12）**：已弃用 OpenClash，改用 **OpenBox（基于 sing-box）**。下方 OpenClash 描述仅作历史参考，端口/机制已变。
>
> **当前 OpenBox 代理环境**：
> - 程序：`/opt/open-box/bin/sing-box run -c /opt/open-box/etc/config.json -D /opt/open-box/data`
> - 面板：`/opt/open-box/panel/server/index.mjs`（node）
> - 代理端口：**`127.0.0.1:7891`（mixed，HTTP + SOCKS5 都可用）** ← 替代旧 OpenClash 的 7890
> - 透明代理：TUN 入站（`tun-in`），无需再手动给工具配 `--proxy`
> - DNS：dnsmasq 监听 53（多接口：127.0.0.1 / 192.168.31.2 / 172.17~19.0.1），sing-box 另开 `dns-in`
> - 面板/API 端口：`7853`（0.0.0.0）、`9095`（127.0.0.1）
> - 服务状态：`/etc/init.d/openclash status` → `inactive`（已停用），不要再依赖 OpenClash 相关命令/端口
> - 验证代理连通：`curl -x http://127.0.0.1:7891 http://www.gstatic.com/generate_204` 应返回 204

**旧 OpenClash 描述（历史参考，勿再套用）**：

oect 上曾运行 **OpenClash**（基于 Clash/Mihomo 的透明代理），会导致：

- **所有 TCP/UDP 流量**都被 tproxy 拦截转发到代理端口
- 端口：HTTP=`7890`，SOCKS=`7891`，API=`9090`（密钥：默认弱口令，**公开仓库不收录**）
- DNS 被劫持到 `127.0.0.1:53`，实际走 Clash fake-ip `198.19.x.x`
- **影响**：aria2/yt-dlp 等工具必须显式配置 `--proxy http://127.0.0.1:7890` 才能正常工作
- **BT 灾难**：DHT/UDP 流量也被拦截，导致磁力链接找不到 peer → 没速度
- 解决方案：固定 BT 端口 + nftables 规则放行（见第 6 节）

### 坑3：Samba4 UCI 段类型必须是 `sambashare`

```
# ❌ 错误 — 不会被 init 脚本识别
config share
    option name 'media'

# ✅ 正确
config sambashare
    option name 'media'
```

init 脚本 `/etc/init.d/samba4` 第 174 行：
```sh
config_foreach smb_add_share sambashare  # 只识别 sambashare 类型
```

### 坑4：aria2 jail（沙箱）机制导致崩溃

OpenWrt 的 procd jail 会限制 aria2 的文件系统访问，导致：
```
jail: jail (xxxx) exited with exit: 7    ← 权限不足
Please make sure user 'aria2' has write access
```

**解决方案**：注释掉 `/etc/init.d/aria2` 中的 jail 相关行：
```sh
#procd_add_jail "$NAME.$section" log
#procd_add_jail_mount "/usr/lib/ossl-modules"
#procd_add_jail_mount "$ca_certificate" ...
#procd_add_jail_mount_rw "$dir" "$config_dir" "$log"
```
并将 aria2 运行用户设为 root：`uci set aria2.main.user='root'`

### 坑5：aria2 RPC 认证方式

aria2 的 RPC 认证**不是** HTTP Bearer Token，而是：
```json
{"jsonrpc":"2.0","id":"1","method":"aria2.getVersion","params":["token:<SECRET>"]}
```
即 token 放在 JSON-RPC 的 `params` 数组第一个位置。

### 坑6：base64 命令不存在

OpenWrt 精简版没有 `base64` 命令，生成随机密钥用：
```sh
cat /proc/sys/kernel/random/uuid | tr -d '-'
```

### 坑7：yt-dlp 需要 JavaScript 运行时

新版 yt-dlp (2026.x) 渲染 YouTube 页面需要 deno：
```sh
curl -fsSL https://deno.land/install.sh | sh
# 安装到 /root/.deno/bin/deno
```
配置中加：`--js-runtimes deno:/root/.deno/bin/deno`

### 坑8：系统盘空间紧张

系统盘只有 2G 且已用 53%，**所有大数据操作必须指向 USB 硬盘** `/mnt/data_sda1/`。
安装 opkg 包可以装在系统盘（包很小），但下载文件、Docker 数据等必须在外置存储。

### 坑9：跑 OpenClash 的 `clash` 二进制会把 Open-Box 内核打停（⚠️ 2026-11-12 实测）

Open-Box 面板带**冲突检测**：只要检测到 `clash` 进程在跑，就判定「OpenClash 与 Open-Box 同时运行」，**直接停掉自己的 sing-box 内核**（实测停了 5 分 40 秒，全屋代理中断，之后面板自行拉起）。

```log
21:16:05 daemon.err node[11925]: [conflict] 检测到 OpenClash 和 Open-Box 同时在运行,
两个代理工具会互相冲突,已自动停止 Open-Box 内核。要用 Open-Box,请先停用 OpenClash...
```

**触发示例（别做）**：`/etc/openclash/clash -t -d /tmp/x -f /tmp/x/config.yaml` —— 只是想做个语法检查，内核就被停了。

**正确做法**：

- Clash/Mihomo 配置校验去**别的机器**做（本地 mihomo / 容器）；oect 上只做静态结构校验
- 真要在本机跑：先 `/etc/init.d/openbox stop`，跑完再 `start`（风险高，不建议）
- 想根治：`mv /etc/openclash/core/clash_meta /etc/openclash/core/clash_meta.disabled`（OpenClash 已弃用）

---

## 3. 已安装软件清单

### 核心工具

| 软件 | 版本 | 用途 | 备注 |
|------|------|------|------|
| samba4 | 4.18.11 | SMB 文件共享 | LuCI 管理界面可用 |
| aria2 | 1.37.0 | 多协议下载器 | 已配置 BT/HTTP/磁力 |
| yt-dlp | 2026.08.19 | 视频下载 | pip 安装，已配 aria2 加速 |
| ffmpeg | 6.1.3 | 音视频处理 | yt-dlp 合并格式必需 |
| deno | latest | JS 运行时 | yt-dlp 渲染 YouTube 页面用 |
| OpenBox | sing-box | 代理（当前） | 2026-09-12 起替代 OpenClash，mixed 端口 `127.0.0.1:7891`，TUN 透明代理 |
| OpenClash | 0.47.075 | 代理（已停用） | 2026-09-12 起弃用，`/etc/init.d/openclash status` = inactive |

### LuCI Web 界面

| 地址 | 功能 |
|------|------|
| `http://192.168.31.2/` | iStoreOS 管理主页 |
| `http://192.168.31.2/ariang` | AriaNg 下载管理 |
| `http://192.168.31.2/cgi-bin/luci/admin/services/aria2` | aria2 设置 |
| `http://192.168.31.2/cgi-bin/luci/admin/services/samba4` | Samba 设置 |

---

## 4. 关键配置文件路径

| 文件 | 用途 |
|------|------|
| `/etc/config/samba4` | Samba UCI 配置 |
| `/etc/config/aria2` | aria2 UCI 配置 |
| `/etc/init.d/aria2` | aria2 启动脚本（**已修改：禁用 jail**） |
| `/etc/init.d/samba4` | Samba 启动脚本 |
| `/var/etc/aria2/aria2.conf.main` | aria2 运行时配置（自动生成） |
| `/root/.config/yt-dlp/config` | yt-dlp 全局配置 |
| `/root/.deno/bin/deno` | deno 运行时 |
| `/tmp/aria2_rpc_secret` | aria2 RPC 密钥备份 |
| `/etc/sysctl.d/99-download-boost.conf` | 网络优化（BBR 等） |
| `/usr/bin/update-trackers.sh` | BT Tracker 自动更新脚本 |
| `/etc/openclash/config/*.yaml` | OpenClash 配置 |

---

## 5. 存储目录规范

```
/mnt/data_sda1/                    ← USB 硬盘根目录
├── media/                         ← Samba 共享目录
│   └── video/                     ← yt-dlp 默认下载目录
├── downloads/                     ← aria2 默认下载目录
├── docker/                        ← Docker 数据
├── Configs/                       ← 配置备份
├── nanobot/                       ← nanobot 项目
├── nodejs/                        ← Node.js 相关
└── ...
```

**规则**：
- 所有用户数据下载到 `/mnt/data_sda1/`
- Samba 对外共享 `/mnt/data_sda1/media`
- yt-dlp 默认输出到 `/mnt/data_sda1/media/video/`
- aria2 默认下载到 `/mnt/data_sda1/downloads/`

---

## 6. 网络与防火墙

### OpenClash 代理端口

| 端口 | 协议 | 用途 |
|------|------|------|
| 7890 | HTTP | HTTP 代理 |
| 7891 | SOCKS5 | SOCKS 代理 |
| 7892 | TCP | redir（重定向） |
| 7893 | Mixed | 混合代理 |
| 7895 | TPROXY | 透明代理 |
| 9090 | HTTP | Clash API（密钥：默认弱口令，**公开仓库不收录**） |

### BT 放行规则（nftables）

为了 BT/磁力正常工作，在 OpenClash 的 mangle 链中放行了 aria2 的 BT 端口：

```nftables
# /etc/nftables.d/ 或运行时添加
# openclash_mangle 链顶部：
udp dport 51414 return    # DHT 放行
tcp dport 51413 return    # BT 数据放行

# openclash_output 链：
udp dport 51414 return
tcp dport 51413 return
```

> ⚠️ **注意**：OpenClash 更新或防火墙重启后这些规则可能丢失，需要重新添加。
> 持久化方法：写入 `/etc/nftables.d/` 下的 `.nft` 文件。

### sysctl 网络优化

已写入 `/etc/sysctl.d/99-download-boost.conf`：
- BBR 拥塞控制
- TCP 缓冲区 64MB
- TCP FastOpen
- MTU 探测

---

## 7. 服务管理速查

```sh
# Samba
/etc/init.d/samba4 start|stop|restart|enable|status

# aria2
/etc/init.d/aria2 start|stop|restart|enable|status

# 防火墙（修改规则后需要）
/etc/init.d/firewall restart

# OpenClash
/etc/init.d/openclash start|stop|restart

# 查看日志
logread | grep -i samba
logread | grep -i aria2
logread | grep -i openclash
```

---

## 8. aria2 使用备忘

### RPC 接口

```sh
# 基础 URL
http://192.168.31.2:6800/jsonrpc

# 认证方式：token 放在 params[0]
"params":["token:<RPC 密钥，见设备 /tmp/aria2_rpc_secret>", ...]
```

### 常用 RPC 方法

```sh
# 添加 HTTP 下载
curl -d '{"jsonrpc":"2.0","id":"1","method":"aria2.addUri","params":["token:xxx",["URL"],{"dir":"/mnt/data_sda1/media"}]}' http://127.0.0.1:6800/jsonrpc

# 添加磁力链接
curl -d '{"jsonrpc":"2.0","id":"1","method":"aria2.addUri","params":["token:xxx",["magnet:?xt=urn:btih:..."],{"dir":"/mnt/data_sda1/media/video"}]}' http://127.0.0.1:6800/jsonrpc

# 查看全局状态
curl -d '{"jsonrpc":"2.0","id":"1","method":"aria2.getGlobalStat","params":["token:xxx"]}' http://127.0.0.1:6800/jsonrpc

# 查看活跃下载
curl -d '{"jsonrpc":"2.0","id":"1","method":"aria2.tellActive","params":["token:xxx"]}' http://127.0.0.1:6800/jsonrpc
```

### yt-dlp 使用

```sh
# SSH 下载视频（自动走代理 + aria2 16线程）
ssh oect "yt-dlp 'https://www.youtube.com/watch?v=xxxxx'"

# 指定格式
ssh oect "yt-dlp -f 'bestvideo[height<=1080]+bestaudio' 'URL'"
```

---

## 9. 排障流程图

```
下载没速度？
├── HTTP 下载（yt-dlp/aria2 HTTP）
│   ├── 检查代理配置 → 是否配了 --proxy http://127.0.0.1:7890
│   ├── 检查 Clash 代理是否正常 → curl -x http://127.0.0.1:7890 URL
│   └── 检查 DNS → nslookup 域名
│
├── BT/磁力下载
│   ├── 检查 DHT 端口是否被 OpenClash 拦截
│   │   → nft list chain inet fw4 openclash_mangle | head -5
│   ├── 检查是否有放行规则
│   │   → 应有: udp dport 51414 return / tcp dport 51413 return
│   ├── 检查 aria2 BT 端口配置
│   │   → listen-port=51413 / dht-listen-port=51414
│   └── 检查 tracker 数量
│       → grep bt-tracker /var/etc/aria2/aria2.conf.main | tr ',' '\n' | wc -l
│
├── aria2 报错
│   ├── "exited with exit: 7" → jail 权限问题 → 检查 /etc/init.d/aria2 jail 注释
│   ├── "SSL/TLS handshake failure" → check-certificate=false
│   ├── "Unauthorized" → RPC 密钥不匹配 → 检查 token 参数格式
│   └── "Write access" → 目录权限 → chown aria2:aria2 DIR
│
└── Samba 访问不了
    ├── 检查 samba4 配置段类型是 sambashare（不是 share）
    ├── 检查共享路径权限 → chmod 777
    └── Windows 用 \\192.168.31.2\共享名 访问
```

---

## 10. 安全注意事项

1. **aria2 RPC 密钥**：见设备 `/tmp/aria2_rpc_secret`（仅内网可用，勿外泄到公网）
2. **Clash API 密钥**：默认弱密码，**建议改为强密码**（具体值不入库）
3. **Samba 匿名共享**：`media` 目录对局域网所有人可读写（guest_ok=yes）
4. **aria2 以 root 运行**：因 jail 问题改为 root，安全等级降低，仅限内网使用
5. **nftables BT 规则**：OpenClash 重启后可能丢失，需检查持久化

---

## 11. 更新维护备忘

| 操作 | 命令 |
|------|------|
| 更新 yt-dlp | `pip3 install -U yt-dlp` |
| 更新 Tracker 列表 | `/usr/bin/update-trackers.sh`（每天 03:00 自动） |
| 更新 OpenClash 规则 | LuCI 界面操作，或等 cron 自动（每天 04:00） |
| 更新系统包 | `opkg update && opkg upgrade`（⚠️ 慎用，可能覆盖配置） |
| 重启后检查 | BBR 是否生效、BT 防火墙规则是否丢失、aria2 是否运行 |

---

---

## 12. 待探索与想法（TODO & Ideas）

> 💡 想法先放这里，讨论确认后实施，实施后迁移到正式章节。

### 🔴 待解决（已知问题）

- [ ] **OpenClash 优化（DNS + 旁路由兼容 + 分组）**：已出完整方案文档，见 `docs/openclash-legacy/openclash-optimization.html` 和 `docs/openclash-legacy/openclash-groups-optimization.html`（OpenClash 已停用，仅留档）
  - DNS 缺 fallback 导致国外域名解析异常（最可能的 YouTube 问题根因）
  - `bypass_gateway_compatible` 需开启（旁路由模式关键选项）
  - 分组需从 select 改为 url-test 自动选优
  - ⚠️ **Mihomo 坑**：health-check URL 只测试 `proxies` 字段节点，不测试 `use`/proxy-providers 节点 → 必须用 `include-all: true` 替代 `use`
- [ ] **ttyd Web 终端暴露**：端口 7681 绑定 0.0.0.0，任何人可访问 root shell → 如不需要应禁用
- [ ] **NFS/rpcbind 空跑**：端口 111/2049/32777-32780 监听但无共享配置 → 如不需要应禁用
- [ ] **BT 防火墙规则可能无效**：nftables forward 链中 BT 放行规则 counter=0，可能被 OpenClash mangle 链先拦截
- [ ] **OpenClash 重启后 BT 防火墙规则丢失**：nftables 规则是运行时添加的，需要持久化到 `/etc/nftables.d/` 或写成 OpenClash 自定义规则
- [ ] **aria2 以 root 运行安全性低**：等 procd jail 问题修复后（或找到正确的 jail 目录挂载方式），应改回 aria2 用户
- [ ] **Clash API 密钥是默认弱密码**：应改为强密码
- [ ] **nftables BT 规则需要持久化脚本**：写一个 `/etc/init.d/aria2-bt-bypass` 在 aria2 启动后自动注入

### 🟡 优化方向

- [ ] **WebUI 下载管理**：AriaNg 功能基础，考虑部署 [Motrix](https://motrix.app/) 或 [FileBrowser](https://filebrowser.org/) 的 Web 界面做统一下载面板
- [ ] **自动追剧/追番脚本**：用 yt-dlp + cron 实现定期检查 RSS 订阅源，自动下载新剧集到 media 目录
- [ ] **Plex/Jellyfin 媒体服务器**：在 Docker 中部署，配合 Samba 共享的 media 目录做家庭影院
- [ ] **下载完成后自动通知**：aria2 hook 脚本 + Telegram Bot 推送（oect 上已有 python-telegram-bot）
- [ ] **磁盘健康监控**：USB 硬盘 SMART 监控 + 告警，防止数据丢失
- [ ] **UPS 供电**：如果断电频繁，考虑给 oect 配 UPS，防止 USB 硬盘损坏

### 🟢 新技术探索

- [ ] **aria2 + webui-aria2**：更现代的 aria2 Web 前端
- [ ] **qBittorrent/Transmission Docker**：如果 BT 需求大，专用 BT 客户端可能比 aria2 更稳定
- [ ] **WireGuard VPN**：比 OpenClash 更轻量的远程访问方案
- [ ] **Wireguard + aria2 远程下载**：在外面也能控制 oect 下载
- [ ] **NAS 功能扩展**：利用 iStoreOS 的 Docker 能力，把 oect 变成轻量 NAS

### 🔵 经验反思（下次做得更好的）

- [ ] **先查代理环境再配工具**：以后在 oect 上装任何网络工具，第一步应该检查 OpenClash 代理配置
- [ ] **opkg 包优先于 pip**：OpenWrt 上优先用 opkg 安装（体积小、依赖少），pip 作为备选
- [ ] **先 read 再 write**：修改 `/etc/init.d/` 脚本前，先备份原文件（这次做了 `.bak`，好习惯）
- [ ] **UCI 段类型要查 init 脚本**：不确定 UCI section type 时，先 `grep config_foreach /etc/init.d/<service>` 看它期望什么类型

### 🔴 OpenClash YAML 修改血泪教训（2026-08-30）

- [ ] **绝对不要多次 Python 脚本叠加修改同一个 YAML**：每次修改都会残留旧内容，导致重复锚点（mapping key already defined）→ Mihomo 拒绝启动。正确做法：**备份 → 一次性替换整个目标段 → 验证**
- [ ] **RULE-SET 的格式是 `RULE-SET,rule_provider_name,group_name`**：第一个参数必须匹配 `rule-providers` 段中定义的 key，第二个才是代理分组名。改分组名时**只改第二个参数**，不要动第一个
- [ ] **rule-providers 段绝对不能丢**：YAML 替换时如果用了 `content[:pos] + new + content[pos2:]`，必须确认 pos2 正确指向 rule-providers 段开头。丢了 rule-providers → 所有 RULE-SET 报 "rule set not found"
- [ ] **OpenClash 重启有 watchdog 机制**：直接 `killall clash` 后，`openclash_version.sh` 等后台脚本还在跑，会干扰重启。正确方式：`/etc/init.d/openclash restart`，如果卡住就 `killall clash` + 等 5 秒 + 再 `/etc/init.d/openclash start`
- [ ] **Mihomo health-check URL 只测试 `proxies` 字段中的节点**：通过 `use`（proxy-providers）引入的节点不会被健康检查。用 `include-all: true` 替代 `use` 可以解决，但会让界面显示所有节点（126+个），很凌乱
- [ ] **`include-all: true` vs `use: [provider]` 的取舍**：`include-all` 界面凌乱但健康检查全覆盖；`use` 界面简洁但 provider 节点不被检查。对于路由器场景，**`use` + 地区自动组引用**是更好的折中
- [ ] **修改 OpenClash YAML 前必须用 `clash -t` 测试**：`/etc/openclash/clash -d /etc/openclash -f /etc/openclash/config/xxx.yaml -t`，通过了才能重启。不要盲改盲重启

---

## 13. nanobot 运维（AI Agent Bot）

### 部署信息

| 项目 | 值 |
|------|-----|
| 项目目录 | `/mnt/data_sda1/nanobot/`（`repo/`=源码，`config/`=数据，`docker-compose.yml`） |
| 部署方式 | Docker Compose（`build.context: ./repo`，源码构建，非镜像仓库） |
| 服务 | `nanobot-gateway`（Telegram/WebSocket 网关，端口 18790/8765）、`nanobot-api`（OpenAI 兼容 API，127.0.0.1:8900） |
| 配置 | `/mnt/data_sda1/nanobot/config/config.json`（挂载到容器 `/home/nanobot/.nanobot`） |
| 运行用户 | 容器内 `nanobot`（uid 1000），entrypoint 先 root 后 setpriv 降权 |
| 默认模型 | `deepseek-v4-flash` |
| 关键配置 | `providers.openai.apiBase = https://opencode.ai/zen/go/v1`（走 OpenCode Zen/Go 中继） |
| Telegram | `@Chunzhouclawbot`，polling 模式 |

### 升级流程（源码构建）

```sh
# 1. 备份 config 与旧镜像（可回滚）
TS=$(date +%Y%m%d%H%M%S)
cp /mnt/data_sda1/nanobot/config/config.json /mnt/data_sda1/nanobot/config/config.json.bak.$TS
docker inspect nanobot-gateway --format '{{.Image}}'   # 记录旧镜像 id

# 2. 升级源码（detached at tag → 切到 main）
cd /mnt/data_sda1/nanobot/repo
git fetch --tags origin
git checkout main && git reset --hard origin/main

# 3. 重建镜像（ARM64 小设备约 5~10 分钟，后台跑）
cd /mnt/data_sda1/nanobot
docker compose -f docker-compose.yml build --progress=plain

# 4. 用新镜像校验 config（不重启现有服务）
docker run --rm -v /mnt/data_sda1/nanobot/config:/home/nanobot/.nanobot nanobot-nanobot-gateway status

# 5. 重启
docker compose -f docker-compose.yml up -d

# 6. 验证
docker ps --filter name=nanobot
docker logs --tail 30 nanobot-gateway
```

### 2026-09-12 修复：OpenCode 缺 x-opencode-session header（PR #5662）

- **症状**：OpenCode 官方 2026-09-06 起强制要求请求带 `x-opencode-session` header，缺失会报 `MissingSessionID`（尤其后台 session compaction/consolidation 路径），导致 bot 调 LLM 失败/漏消息。
- **根因**：oect 上 nanobot 停在 v0.3.0（2026-07-25），比修复早约一个半月；且用 `providers.openai.apiBase` 指向 `opencode.ai` 自定义 endpoint，正好命中问题。
- **修复**：升级 repo 到 main 最新（本次到 `7cede64f`，含 merge commit `20f115bf`）。官方补丁逻辑：检测 opencode/opencode_zen/opencode_go provider 或 hostname 为 `opencode.ai`（含子域）的 endpoint → 自动加 `x-opencode-session`（有会话上下文用 sha256(session_id)，无上下文用实例 uuid fallback）。
- **验证方法**（代码级）：
  ```sh
  docker exec nanobot-gateway python -c "
  from nanobot.providers.openai_compat_provider import OpenAICompatProvider
  p = OpenAICompatProvider(api_key='t', default_model='o3', api_base='https://opencode.ai/zen/go/v1')
  print('x-opencode-session' in p._default_headers)  # True
  "
  ```
- **教训**：v0.3.0 的 `chat()/chat_stream()` 无 `provider_context`/session 上下文，官方补丁**无法 cherry-pick**（相隔 725 commit，结构差异大），只能整体升级 main。升级前务必备份 config + 记录旧镜像 id 以便回滚。

### 经验：Docker build 网络超时

- **现象**：`docker compose build` 时 `uv pip install` 从 `files.pythonhosted.org` 下载超时（`operation timed out`）。
- **排查**：先测宿主机直连 `curl https://files.pythonhosted.org/...`（成功则网络本身通），再测容器内 `docker exec nanobot-gateway python -c "urllib.request.urlopen(...)"`。
- **常见根因**：代理（OpenBox/OpenClash）切换期间短暂抖动；等代理稳定后重试 build 即可，Docker layer 缓存会保留已完成的步骤。
- **注意**：build 期间不要 `kill` 掉已有容器；build 失败不影响运行中的旧容器。

### 经验：磁盘空间整理（2026-09-12）

- **背景**：系统盘 `/`（2G）65% 偏紧，做了一次全面分析 + 清理。
- **关键认知**：
  - 系统盘大头排序：`/usr`（opkg 软件 973M）> `/root`（`~/.cache/camoufox` 343M、`~/.local/share/uv` 124M、`~/.deno` 81M）> `/opt`（open-box 245M）> `/lib` 228M。
  - `/tmp` 是 **tmpfs 内存盘**（`mount` 可见，不在系统盘磁盘内），清它只省内存不省磁盘。
  - 统计各目录用 `du -xsm /*`（`-x` 避免跨文件系统，否则会把 `/mnt/data_sda1` 等挂载点一起算进 `/`）。
- **本次清理**：camoufox 343M、cloudflared 镜像 72M、`tmp_pip` 736M、旧 uv 缓存 789M（`UV_CACHE_DIR` 已改回默认 `/root/.cache/uv`，数据盘 `cache/uv` 是历史遗留）、docker dangling 镜像 480.9M + build cache 495M、`/tmp` 下 open-box 安装包残留 77M。
- **结果**：系统盘 65%→52%（可用 646M→892M），数据盘回收约 3G。
- **经验**：
  - docker dangling 镜像在 `docker system df -v` 里 `SHARED SIZE` 大但 `UNIQUE SIZE` 小 → 实际 `docker image prune` 回收量远小于镜像显示大小（本次显示 676M×2，实际只回收 480.9M）。
  - "无容器但可能想再用"的镜像（如 cloudflared）删前需确认，本次用户拍板删。
  - 待精简（未拍板）：`/mnt/data_sda1/nodejs/` 有 glibc+musl 双版本 + tar.xz（~1.1G），OpenWrt 是 musl，glibc 版可删；`current` 指向 musl 版，系统实际用 `/usr/bin/node`。

## 14. OpenBox 配置结构（2026-11-12 摸底）

### 🚨 配置是 JSON，不是 YAML

- OpenBox 是 **sing-box 套壳**（不是 Clash/Mihomo），配置只有 JSON。`/opt/open-box` 全目录搜 `*.yaml / *.yml` = **0 个文件**
- 主目录 `/opt/open-box/etc/`：

| 文件 | 大小 | 用途 |
|------|------|------|
| `config.json` | 88K | **运行时真身**，sing-box 实际加载的唯一配置 |
| `config.candidate.json` | 52K | 候选配置（面板改写后待生效） |
| `config.latency.json` | 28K | 延迟测速专用 |
| `config.meta.json` | 1.2M | 配置元数据（节点/分组原始信息） |
| `entry-bypass.nft` | 1K | nftables 入站绕过规则 |

- 面板数据库：`/opt/open-box/data/openbox.sqlite`（21MB，节点库/订阅源/设置）；UI 签名密钥 `data/.ui-links-key`
- 安装元信息：`/opt/open-box/meta.json` → 当前 **OpenBox v0.1.415** / sing-box `1.14.4-openbox-45` / commit `cda098a`
- 运行时缓存（无备份价值）：`data/cache.db`、`data/flip/*`；规则集 `.srs` 可联网重下

### 配置骨架（2026-11-12 快照）

- **inbounds**：`tun-in`（TUN 透明代理）、`panel-in`（mixed `127.0.0.1:7891`）、`dns-in`（direct `0.0.0.0:7853`）、`share-smvmgmodqgira`（mixed `::`:7080 ⚠️ 局域网无认证共享入站）
- **outbounds 共 99**：shadowsocks ×39、anytls ×14、vmess ×14；selector ×22、urltest ×7、direct ×2、block ×1
- **分组双轨制**：地区「自动(urltest) / 手动(selector)」各一套 —— 所有(67)、香港(17)、日本(20)、新加坡(6)、台湾(3)、美国(3)、韩国(1)
- **应用组（各 16 成员）**：AI、Telegram、X、Youtube、TikTok、Netflix、Github、Google、Microsoft、Apple、Games、国外、国内、自定义、其他

### 导出 / 备份手法

- 逐文件 `scp` 拉回本地 `backups/openbox/<日期>/`，两端 `sha256sum` 对齐（勿用 `scp -r` 图省事，容易漏 `.` 开头文件）
- 需要人眼读时用 pyyaml 无损转 YAML（**必须做 round-trip 校验**），但 `sing-box` 只读 JSON，YAML 不能拿去启动
- 改完必须先 `/opt/open-box/bin/sing-box check -c <file>` 再重启，否则直接起不来

### ⚠️ 安全

- `config*.json` / `meta.json` 里是**明文节点凭据**（地址/端口/UUID/密码）→ 不进 Git、不上网盘、不外发
- `share-*` 共享入站监听 `::` 且 `users: null` → 同网段任何人可当代理用，建议改绑 `127.0.0.1` 或加 users 认证

---

## 15. 文件系统与配置地图（2026-11-14 全量只读探索）

> 完整版见 `docs/oect/2026-11-14/INVENTORY.md`（含 10 份 raw 原始数据、端口表、改动手册、问题清单）
> 采集方式：全程只读（cat/ls/df/ip/netstat/nft/docker ps/opkg list），未改设备任何文件

### 硬件/系统订正

| 项 | 值 |
|---|---|
| 机型 | **OEC BOX WXY4**，board `rockchip,rk3566-oec-box-wxy4`（RK3566 / Cortex-A55） |
| 根文件系统 | **btrfs**（compress=zstd:6），有 `/etc` 子卷 + `.snapshots/etc-000` 快照 |
| 重启 | **2026-11-14 22:43:57 重启过**（此前连续 187 天），日志在 /tmp 已丢，原因未记录 |
| swap | 无（0） |

### 存储（2026-11-14 实测）

| 分区 | 大小 | 类型 | 挂载 | 用量 |
|---|---|---|---|---|
| mmcblk0p1 BOOT | 462M | ext4 | /boot | 15% |
| mmcblk0p2 ROOTFS | 2.0G | btrfs | / | **52%** |
| mmcblk0p3 MMC_ROOTFS2 | 1023M | btrfs | /mnt/mmcblk0p3 | 1%（空） |
| mmcblk0p4 MMC_SHARED | 3.6G | btrfs | /mnt/mmcblk0p4 | 0%（空） |
| sda1 | 115.6G | ext4 | /mnt/data_sda1 | 9%（SMART PASSED，通电 184h） |

- 系统盘大头：`/usr` 973M、`/root` 253M、`/lib` 228M、`/opt` 209M
- **`/tmp` 是内存盘，`/var` 指向 `/tmp`** → 重启全丢（日志也只活到重启）

### 网络口径（与旧文档不同处）

- `eth0` 静态 192.168.31.2，默认网关 192.168.31.1；**本机不派 DHCP**（dhcpv4 disabled、odhcpd maindhcp=0）
- **DNS 链路**：局域网 → dnsmasq:53（`noresolv '1'`，唯一上游）→ **127.0.0.1#7853**（sing-box dns-in）→ 代理；改 DNS 等于改 OpenBox
- TUN：`openbox-tun` 172.19.0.1/30；`ip rule` 6 条 fwmark 规则（0x2024/0x2023）
- nft 表三张：`inet fw4` / `inet openbox` / `inet sing-box`（合计 2623 行）
- 开放端口（重点）：22 dropbear、**80 nginx（→8080）**、443 uhttpd、139/445 samba、6800 aria2、**7681 ttyd**、**2026 OpenBox 面板**、7854 面板 API、**7891 代理**、7853 dns-in、9095 clash-api、**7080 共享入站**、111/2049 NFS、8765/18790/8900 docker、3200 FastNet

### 自启动与任务

- `/etc/rc.local` → `mount -o remount,rw /` + `/etc/custom_service/start_service.sh`（ophub 通用脚本，日志 /tmp/ophub_start_service.log）
- cron **只剩一条**：`0 3 * * * /usr/bin/update-trackers.sh`
- **OpenClash 在 rc.d 里是 enabled**，但服务 inactive —— 二进制还在，见坑9

### 工具链现状（订正 §3）

| 工具 | 实际 | 备注 |
|---|---|---|
| python3 | 3.11.14 + pip 23.3.1 | |
| node | v24.14.0 / npm 11.9.0 | |
| deno | `/root/.deno/bin/deno`（85M）**存在但不在 PATH** | 只能绝对路径调用 |
| yt-dlp | 2026.08.19 | ⚠️ 配置里 `--proxy 127.0.0.1:7890` **已失效**（OpenBox 用 7891） |
| ffmpeg | 6.1.3 | **ffprobe 缺失** |
| 缺 | sqlite3 CLI、uv | 写脚本别依赖 |

### Docker（2026-11-14）

- 27.3.1，数据根 `/mnt/data_sda1/docker`，overlay2，`iptables '0'`，无 daemon.json
- 容器：`nanobot-gateway`（8765/18790）、`nanobot-api`（127.0.0.1:8900），网络 `nanobot_default` 172.18.0.0/16
- 编排文件：`/mnt/data_sda1/nanobot/docker-compose.yml`
- `/mnt/data_sda1/new-api/` 只剩 `data/one-api.db`（1.6M），**容器未运行** → nginx 的 `/newapi/` 反代会 502

### Open-Box 补充

- 面板 UI `http://192.168.31.2:2026`（监听 `::`，局域网可访问），API `127.0.0.1:7854`
- CLI `open-box password|port|restart|start|check|update|uninstall`（`/usr/bin/open-box`）
- 数据库表：traffic_daily 89351、dns_filter_records 19998、node_quality_hours 1512、dns_filter_domains 426…

### Samba 局域网共享（2026-11-14 调整）

| 共享名 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `media` | `/mnt/data_sda1/media` | 匿名可读写 | 原有 |
| `downloads` | `/mnt/data_sda1/downloads` | 匿名可读写 | **2026-11-14 新增** |

- 两个共享都是 `guest_ok=yes`、`read_only=no`、`create_mask/dir_mask=0777`、`force_root=1`（→ `force user/group = root`）
- 配置：`/etc/config/samba4`；改完必须 `uci commit samba4` + `/etc/init.d/samba4 restart`
- 改前备份：`/etc/config/samba4.bak.20261114-230340`
- 访问方式：资源管理器输入 `\\192.168.31.2\downloads` 或 `\\192.168.31.2\media`（Windows 可直接打开，免密码）
- ⚠️ **验证陷阱**：在 DSH 的命令行环境（PowerShell `net use` / `Get-ChildItem \\...`）里测 SMB 会报 `Access is denied (错误5)`，**但资源管理器实际能正常访问** —— 命令行进程的令牌/会话与交互式桌面不同，guest 被拒。判断共享好坏请看资源管理器或手机`smb://192.168.31.2/media`，不要信命令行结果

### 🔴 本次发现的问题（只读观察，均未修）

1. yt-dlp 代理端口写死 7890（应 7891）→ 走代理必失败
2. `/etc/localtime` 指向已不存在的 `/mnt/data_sda1/hermes_data/...`（悬空；时间靠 /etc/TZ）
3. nginx 的 `/newapi/` 反代目标 3000 无服务
4. 共享入站 7080 无认证；ttyd 7681 = root shell 对全网开放；dropbear 允许 root 密码登录
5. NFS/rpcbind 空跑（`/etc/exports` 为空）
6. `/boot` 在 fstab 里写 vfat、实际 ext4；`/rom` 挂载项指向 rootfs UUID
7. 设备上 `/root/AGENTS.md` 是 8-30 的旧副本，与本文件不同步

---

## 16. TVBox 接口中转站（tvbox-hub，2026-11-14）

把 TVBox 接口放本机，电视端填固定内网地址，换源只改本机。

| 项 | 值 |
|---|---|
| 对外地址（主，合并） | `http://192.168.31.2/tvbox/config.json` |
| 对外地址（镜像，直播强） | `http://192.168.31.2/tvbox/inliang.json`（**2026-11-21 新增**） |
| 状态页 | `http://192.168.31.2/tvbox/status.html`（中文，5 分钟自刷新；每次 sync 自动重新生成；含镜像区块） |
| 实际目录 | `/mnt/data_sda1/services/tvbox/`（`/www/tvbox` 是软链，uhttpd 跟随软链正常） |
| 上游列表 | `sources.txt`（一行一个 URL，支持 `#` 注释）；当前主源 = `Lightconer/tvbox-ysc-config` 的 `output/单仓聚合.json`（GitHub Actions 每日更新的聚合仓，内部已合 10 家常见单仓） |
| 当前产出 | 主：**592 站点 / 30 直播 / 85 解析**（2026-11-21：主源 554 + Inliang 补源 38）；spider 仍指向 `ss1.eisite.cn` 的 jar（伪装 .png），实测 200 |
| 补源机制 | `sources.txt` 里给源加前缀 **`!http-only`**：只取该源 `api` 以 http 开头的独立站点，`csp_`/`./lib` 等依赖 spider 的自动跳过——**spider 全局唯一，整份合并会废掉一半站点** |
| 补源体检 | 新增站点每天探测一次（8 线程，约 10s）：DNS 失败/拒绝连接/404·410 剔除；403、5xx、超时保留。`--no-check` 可跳过 |
| 镜像来源 | `mirrors.txt`（`<文件名> <URL>`）：当前 = [Inliang/tvbox](https://github.com/Inliang/tvbox) 的 `zijian.json`，**126 站点 / 10 直播分组**，直播源每 6h 自测速 |
| spider 本地化 | 镜像时把网址里相对路径的 spider jar **下载到本机**并改写成内网绝对地址（`http://192.168.31.2/tvbox/<name>.png;md5;...`），断外网也能起站点 |
| 同步脚本 | `python3 sync.py`（`--dry-run` 只测不写） |
| 定时任务 | `10 4 * * * cd /mnt/data_sda1/services/tvbox && python3 sync.py >> sync.cron.log 2>&1` |
| 本地副本 | `E:\04.OECT\services\tvbox-hub\`（sync.py / sources.txt / README.md） |

**行为**

- 支持普通 JSON 与 base64 编码接口
- 多源合并去重：sites 按 `key`、lives 按 `name`、parses 按 `(name,url)`、flags 按值
- `spider`/`parses` 取第一个有值的源（不同源 spider 版本混用会崩）
- 单源失败只记日志；**全失败则保留上一份 config.json 不动**
- 输出里带 `dsh` 字段记录本次同步时间/成功源数/失败源

**已验证**：自测两源合并（含 1 个 404 源）→ sites 去重成功、失败源不中断；`curl http://192.168.31.2/tvbox/config.json` → 200。

**注意**

- `/www` 在系统盘（2G），实体文件放 USB 盘，靠软链暴露
- `config.json` **已填充实时接口**（517 站点，2026-11-14 23:37 同步）；改 sources.txt 后记得跑一次 `python3 sync.py`，否则要等到次日 04:10

---

## 17. Home Assistant（Container，2026-11-15 上线）

| 项 | 值 |
|---|---|
| 访问地址 | **`http://192.168.31.2:8123`**（局域网实测 302 → onboarding，13ms） |
| 部署目录 | `/mnt/data_sda1/services/homeassistant/`（compose + config + backups + backup.sh） |
| 镜像 | `ghcr.io/home-assistant/home-assistant:stable`，**2.38 GB**，arm64 |
| 容器 | `homeassistant` · `network_mode: host` · `privileged` · `mem_limit 1800m` · `stop_grace_period 60s` |
| 实测资源 | 常驻 **368 MB**（上限 1.758 GB）、CPU 0.2%、首次启动 **~80 秒**到 healthy |
| 时区 | `TZ=Asia/Shanghai`（宿主无 zoneinfo 且 `/etc/localtime` 悬空，只能靠 TZ；容器内 `date` 已验 = CST） |
| 备份 | 每日 **03:30** `sh backup.sh`，保留 7 份；**排除 *.db / *.db-wal / *.db-shm**（防热拷贝损坏） |
| 写入优化 | `configuration.yaml` 已加 `recorder: commit_interval: 30 / purge_keep_days: 7`，降低 USB 盘擦写 |

### 常用操作

```sh
cd /mnt/data_sda1/services/homeassistant
docker compose ps / logs -f --tail 100 / restart
docker compose pull && docker compose up -d     # 升级
sh backup.sh                                     # 手动备份
```

### 已知问题

- **IPv6 组播不可用**：容器内 `sendto ff02::fb` 报 `EPERM`（宿主机同样受限，非容器权限问题）。
  影响：HA 的 **IPv6** mDNS(zeroconf) / SSDP(UPnP) 发现不可用；**IPv4 组播实测正常**，主流设备发现不受影响。
  旁证：本机 IPv6 只有 link-local（ULA 路由 unreachable），本来也没跑 IPv6 业务。
- 启动日志里 zeroconf / async_upnp_client 各一条 WARNING/ERROR 即上述原因，可忽略。

- **米家集成 OAuth 回调（重要）**：`xiaomi_home/miot/const.py` 的 `OAUTH_REDIRECT_URL` 硬编码 `http://homeassistant.local:8123`，
  且小米 OAuth **白名单只认这个地址**（改成 IP 会报 `invalid redirect uri`，已试过并回退）。
  正确解法：让 `homeassistant.local` 能解析 → 已新增 procd 服务 **`/etc/init.d/ha-mdns-alias`**（avahi-publish 发布 `homeassistant.local → 192.168.31.2`，respawn 守护）。
  Windows 侧实测 `Test-NetConnection homeassistant.local -Port 8123 = True`。
  ⚠️ 若以后 `homeassistant.local` 又解析不了，先查 `pgrep -af avahi-publish` 与服务是否在跑。
- **仪表盘（2026-11-15）**：新增侧边栏「我的家」(`/mushroom`)，用 Mushroom Dashboard Strategy 自动生成；
  前端卡片装在 `config/www/community/{mushroom,mini-graph-card,mushroom-strategy}/`，
  资源已注册到 `.storage/lovelace_resources`，仪表盘配置在 `.storage/lovelace.mushroom`（策略模式，改 options 即可调整）。
  卡片来源：piitaya/lovelace-mushroom v5.3.0、kalkih/mini-graph-card v0.13.0、AalianKhan/mushroom-strategy dist。
  ⚠️ 这些是手动装的，不走 Marketplace；升级需手动替换 JS 并强刷浏览器缓存。
- **平面图仪表盘（2026-11-15）**：新增侧边栏「平面图」(`/plan`)，`panel` 视图 + `picture-elements`；
  底图 `config/www/floorplan/plan.png`（本地生成的示意图，1400x900，可替换成真实户型图），
  14 个 mushroom 设备图标按房间坐标摆放；配置在 `.storage/lovelace.plan`。换底图后图标坐标要跟着调。
- **云鲸（narwal）诊断结论**：MQTT 能连（TLS 8883 到华为云）、订阅成功，但所有命令无响应，
  集成日志明写 `Vacuum unreachable for 5 consecutive polls` → **机器人离线，不是网络问题**，开机器/放回基站即恢复。
- **美的（midea_smart_home）**：电饭煲 `192.168.31.141` 不在线（ARP FAILED），集成每 30s 重连一次；设备通电后自动恢复。
- **2026-11-15 21:20 用户决定「暂时折腾到这里」**：HA 保持现状运行（healthy），三个仪表盘（地图/我的家/平面图）在线。
- **2026-11-15 21:23 已禁用 `narwal` 与 `midea_smart_home`**（`.storage/core.config_entries` 里 `disabled_by: user`），实测重启后 0 条重试日志。
  恢复方法：HA「设置 → 设备与服务 → 已禁用」点该集成→启用；或把 `disabled_by` 改回 `null` 后重启容器。

### 回滚

```sh
cd /mnt/data_sda1/services/homeassistant && docker compose down   # config/ 保留
```

---

## 18. 版本管理 / GitHub 备份（2026-11-21 起）

| 项 | 值 |
|---|---|
| 仓库 | <https://github.com/douchunzhou/tvbox-notes>（**公开**） |
| 本地 | `E:\04.OECT`（git 已初始化，分支 `main`） |
| 收录范围 | **只收手册 / 脚本 / 文档**：`AGENTS.md`、`docs/`、`services/` |
| 明确排除 | `backups/`（含节点明文凭据）、`docs/oect/*/raw/`（MAC/UUID/包清单）、`services/homeassistant/floorplan/`（自家户型图）、`downloads/`（安装包） |
| 脱敏 | aria2 RPC 密钥、Clash API 密钥、磁盘 UUID 均已替换为占位说明 |

### 更新流程

```bash
cd /e/04.OECT
git add -A
git commit -m "说明这次改了什么"
git push
```

凭据走 Windows 凭据管理器里已存的 GitHub 账号（`douchunzhou`），无需重复登录。

### 注意

- **历史是永久的**：一旦推上去，即使之后删除文件，commit 历史里仍可翻到。
  所以`backups/` 这类含凭据的内容**永远不要**加进来；要备份请另建私有仓库。
- 仓库名虽然是 `tvbox-notes`，但内容是整台 oect 的运维手册。


---

*最后更新：2026-11-15 by DSH — 新增 §17 Home Assistant（Container，8123）；2026-11-14 §15 文件系统与配置地图（全量只读探索，见 docs/oect/2026-11-14/INVENTORY.md），订正存储/网络/工具链，记录 7 个待处理问题；2026-11-12 §14 OpenBox 结构 + 坑9；2026-09-12 Reasonix 磁盘整理/nanobot 修复/OpenBox 切换*
