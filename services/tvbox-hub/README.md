# tvbox-hub — TVBox 接口中转站

把 TVBox 接口放 oect 上，电视里填**内网固定地址**，换源只改 oect，不用碰电视。

## 三个地址

| 用途 | 地址 | 内容 |
|---|---|---|
| **主配置**（站点多） | `http://192.168.31.2/tvbox/config.json` | **592 站点 / 30 直播 / 85 解析**（主源 + http 补源，含体检） |
| **镜像配置**（直播强） | `http://192.168.31.2/tvbox/inliang.json` | 126 站点 / 10 直播分组（Inliang 原版，含其测速排序） |
| **状态页** | `http://192.168.31.2/tvbox/status.html` | 中文，5 分钟自刷新，含镜像区块 |

> 电视里填哪个都行：想要片源多用第一个，想要直播/换台舒服用第二个。

## sources 与 mirrors 的区别

| 文件 | 语义 | 适合什么 |
|---|---|---|
| `sources.txt` | **合并**：多源并集去重，spider 取第一个 | 多个"单仓"想合成一份 |
| `mirrors.txt` | **镜像**：原样落到独立文件，不合并 | 整套自带 spider 的配置（避免 spider 打架） |

`mirrors.txt` 格式：`<输出文件名> <URL>`，一行一个。

现在配置的镜像：

```
inliang.json https://raw.githubusercontent.com/Inliang/tvbox/main/zijian.json
```

### 补源：`!http-only` 前缀

主配置（spider = eisite 的 jar）和 Inliang（spider = 另一个 jar）**不能整份合并**——spider 全局只能有一个，
混进去的 `csp_` 站点会全废。所以 `sources.txt` 支持给一个源加前缀：

```
!http-only https://raw.githubusercontent.com/Inliang/tvbox/main/zijian.json
```

语义：**只取该源里 api 以 http 开头的独立站点**（自带接口、不依赖全局 spider），
`csp_` / `./lib` 这类依赖 spider 的站点自动跳过（日志会写 `跳过spider源N`）。

结果：Inliang 的 126 站点里 46 个被跳过，其余 80 个 http 站点按 key/名字/api 三重判重后**新增 38 个**，
保持源文件原有顺序追加在主源之后——主配置顺序不变，spider 也不动。

### 补源体检（自动剔除死源）

新增的补源站点每天会做一次轻量探测（8 线程并发，约 10s）：

- **剔除**：DNS 解析失败 / 连接被拒绝 / HTTP 404、410
- **保留**：403、5xx、超时（不确定的一律留，宁留勿杀）

跳过体检：`python3 sync.py --no-check`。

> 来自 [Inliang/tvbox](https://github.com/Inliang/tvbox)：126 站点 + 10 个直播分组（直播源每 6 小时自动测速排序）。
> 扩展版 `zijian-full.json`（509 站点）在 `mirrors.txt` 里注释着，需要时放开。

### spider 会自动本地化

很多配置的 spider 写的是相对路径（`./xxx.png`），镜像后路径就废了。
`sync.py` 会**把 jar 下载到本机**并把 `spider` 改写成内网绝对地址：

```
spider = http://192.168.31.2/tvbox/9c8e4-b797010b-....png;md5;...
```

这样电视端不依赖 GitHub，断外网也能起站点。

## 目录说明

| 文件 | 作用 |
|---|---|
| `sources.txt` | 合并源列表（一行一个 URL，`#` 注释） |
| `mirrors.txt` | 镜像源列表（`<文件名> <URL>`） |
| `sync.py` | 拉取 → 合并/镜像 → 输出 config.json、镜像文件、status.html |
| `config.json` | 合并后的主接口（自动生成，别手改） |
| `inliang.json` | 镜像接口（自动生成） |
| `*.png` | 镜像下载的 spider jar（自动生成） |
| `status.html` | 中文状态页（自动生成） |
| `sync.log` | 每次同步的日志 |

## 日常操作

```sh
cd /mnt/data_sda1/services/tvbox

python3 sync.py            # 手动同步（合并 + 镜像 + 状态页）
python3 sync.py --dry-run  # 只拉不写
tail -30 sync.log
```

定时任务：每天 **04:10** 自动同步（`/etc/crontabs/root`）。

## 排错

- 电视打不开接口 → 浏览器开 `status.html` 看源状态
- 全失败 → 保留上一份文件，电视照样能看；查 `sync.log` 的 FAIL 行
- 站点能进但播放失败 → 多半是 spider 没加载：确认 `status.html` 里 spider 是**内网地址**且能打开
- 想换源 → 改 `sources.txt` 或 `mirrors.txt`，再跑一次 `python3 sync.py`
