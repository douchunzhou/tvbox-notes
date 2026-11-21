#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TVBox 接口中转：拉取 sources.txt 里的多个接口 -> 合并去重 -> 输出 config.json + status.html

用法:
    python3 sync.py            # 全量拉取并合并，写 config.json 和 status.html
    python3 sync.py --dry-run  # 只跑不写文件

设计原则:
  * 单个源失败不影响其他源（失败只记日志，沿用上一次成功的 config.json）
  * 合并只做"并集去重"，不做跨源改写（spider/parses 保持第一个源的）
"""
import base64
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(BASE, "sources.txt")
MIRRORS = os.path.join(BASE, "mirrors.txt")
OUT = os.path.join(BASE, "config.json")
STATUS = os.path.join(BASE, "status.html")
LOG = os.path.join(BASE, "sync.log")
TIMEOUT = 20
UA = "Mozilla/5.0 (Linux; Android 9) AppleWebKit/537.36 TVBox/1.0"
PUBLIC_URL = "http://192.168.31.2/tvbox/config.json"
PUBLIC_BASE = "http://192.168.31.2/tvbox/"


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    txt = raw.decode("utf-8", "ignore").strip()
    if txt.startswith("{"):
        return json.loads(txt)
    try:
        dec = base64.b64decode(txt).decode("utf-8", "ignore")
        return json.loads(dec)
    except Exception:
        raise ValueError("不是 JSON，也不是 base64 编码的 JSON")


def read_sources():
    """sources.txt: 每行一个 URL，# 注释

    可选前缀 "!http-only "：只合并该源里 api 以 http 开头的站点（即不依赖全局
    spider 的独立接口），用来把别的整套配置"补源"进来而不破坏 spider 一致性。
    """
    if not os.path.exists(SOURCES):
        return []
    out = []
    with open(SOURCES, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            http_only = False
            if s.startswith("!http-only "):
                http_only = True
                s = s[len("!http-only "):].strip()
            out.append({"url": s, "http_only": http_only})
    return out


def read_mirrors():
    """mirrors.txt: 每行 "<输出文件名> <URL>"，# 开头是注释

    镜像与 sources.txt 的区别：镜像**不参与合并**，原样落到独立文件，
    适合外部整套配置（自带 spider 的），避免和主配置的 spider 打架。
    """
    if not os.path.exists(MIRRORS):
        return []
    out = []
    with open(MIRRORS, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 1)
            if len(parts) != 2:
                log("  ! mirrors.txt 行格式不对（应为 <文件名> <URL>），跳过: %s" % s[:60])
                continue
            out.append((parts[0].strip(), parts[1].strip()))
    return out


def localize_spider(cfg, url, dry=False):
    """把相对路径的 spider 抓成本地文件，并把引用改成内网绝对地址

    很多配置的 spider 写的是 "./xxx.png"（相对配置文件），我们镜像后路径就废了；
    这里顺带把 jar 下到本地，客户端从 oect 取，不依赖 GitHub。
    """
    sp = cfg.get("spider") or ""
    if not sp:
        return
    parts = sp.split(";")
    path = parts[0]
    if path.startswith("http://") or path.startswith("https://"):
        return
    base = url.rsplit("/", 1)[0]
    src = base + "/" + path.lstrip("./").lstrip("/")
    fname = os.path.basename(path)
    if dry:
        log("  [dry] spider 将落地为 %s <- %s" % (fname, src.split("//")[-1][:60]))
        return
    req = urllib.request.Request(src, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
    with open(os.path.join(BASE, fname), "wb") as f:
        f.write(data)
    parts[0] = PUBLIC_BASE + fname
    cfg["spider"] = ";".join(parts)
    log("  spider 本地化: %s (%d KB) -> %s" % (fname, len(data) // 1024, parts[0]))


def mirror_all(dry=False):
    """把 mirrors.txt 里的源原样镜像成独立 JSON；失败保留旧文件不动"""
    results = []
    for name, url in read_mirrors():
        if not name.endswith(".json"):
            name += ".json"
        try:
            cfg = fetch(url)
            localize_spider(cfg, url, dry)
            n = len(cfg.get("sites") or [])
            size = len(json.dumps(cfg, ensure_ascii=False).encode("utf-8"))
            if dry:
                log("  [dry] 镜像 %s <- %s (sites=%d)" % (name, url.split("//")[-1][:50], n))
            else:
                tmp = os.path.join(BASE, name + ".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(json.dumps(cfg, ensure_ascii=False, indent=1))
                os.replace(tmp, os.path.join(BASE, name))
                log("  镜像 %s <- %s (sites=%d)" % (name, url.split("//")[-1][:50], n))
            results.append({"name": name, "ok": True, "sites": n, "size": size, "err": ""})
        except Exception as e:
            log("  镜像 FAIL %s -> %s" % (name, e))
            results.append({"name": name, "ok": False, "sites": 0, "size": 0, "err": str(e)})
    return results


def norm_api(api):
    """接口地址归一化，用于跨源判重（忽略协议/大小写/尾斜杠/查询串）"""
    s = str(api or "").strip().lower().split("?")[0].rstrip("/")
    for p in ("https://", "http://"):
        if s.startswith(p):
            s = s[len(p):]
    return s


def is_http_site(site):
    return str(site.get("api") or "").startswith(("http://", "https://"))


def merge(cfgs):
    """合并多份配置。

    cfgs: [(名字, cfg)] 或 [(名字, cfg, http_only)]
    http_only=True 的源只贡献 http 型站点，且统一排在主源站点之后（按名字排序），
    这样既补了源，又不会打乱主配置的顺序。

    返回 (合并结果, 补源起始下标)；没有补源时下标为 None。
    """
    out = {"sites": [], "lives": [], "parses": [], "flags": [], "ads": [], "ijk": []}
    seen = {k: set() for k in ("sites", "lives", "parses", "flags", "ads", "ijk")}
    seen_api = set()
    extra = []
    extra_start = None
    top = {}
    for entry in cfgs:
        name, cfg = entry[0], entry[1]
        http_only = bool(entry[2]) if len(entry) > 2 else False
        if not isinstance(cfg, dict):
            log("  ! %s: 不是对象，跳过" % name)
            continue
        stats = []
        skipped_spider = 0
        for key, ident in (("sites", lambda x: x.get("key") or x.get("name")),
                           ("lives", lambda x: x.get("name") or x.get("url")),
                           ("parses", lambda x: (x.get("name"), x.get("url"))),
                           ("flags", lambda x: str(x)),
                           ("ads", lambda x: x.get("url") or x.get("name")),
                           ("ijk", lambda x: str(x))):
            items = cfg.get(key) or []
            if not isinstance(items, list):
                continue
            added = 0
            for it in items:
                try:
                    ident_val = ident(it) if isinstance(it, dict) else str(it)
                except Exception:
                    continue
                if key == "sites":
                    if http_only:
                        if not is_http_site(it):
                            skipped_spider += 1
                            continue
                        na = norm_api(it.get("api") if isinstance(it, dict) else "")
                        if na in seen_api:
                            continue
                        seen_api.add(na)
                    else:
                        na = norm_api(it.get("api") if isinstance(it, dict) else "")
                        if na:
                            seen_api.add(na)   # 只登记，不过滤：主源保持原样
                if ident_val in seen[key]:
                    continue
                seen[key].add(ident_val)
                if key == "sites" and http_only:
                    extra.append(it)
                else:
                    out[key].append(it)
                added += 1
            if key == "sites" and skipped_spider:
                stats.append("sites+%d(跳过spider源%d)" % (added, skipped_spider))
            else:
                stats.append("%s+%d" % (key, added))
        for k in ("spider", "wallpaper", "logo", "notice", "livesApi", "sitesApi"):
            v = cfg.get(k)
            if v and k not in top:
                top[k] = v
        log("  + %s: %s" % (name, ", ".join(stats)))

    if extra:
        extra_start = len(out["sites"])
        out["sites"].extend(extra)
        log("  补源：新增 %d 个独立站点（保持源文件原有顺序，追加在主源之后）" % len(extra))

    res = dict(out)
    res.update(top)
    for k in ("ads", "ijk"):
        if not res.get(k):
            res.pop(k, None)
    return res, extra_start


def check_sites(sites, timeout=6):
    """补源体检：只剔除"确定性失效"（DNS 失败 / 连接被拒 / 404），
    403、5xx、超时等不确定情况一律保留——宁可留一个坏源，也不误杀好源。
    """
    dead_words = ("Name or service not known", "Temporary failure in name resolution",
                  "Connection refused", "No route to host", "nodename nor servname",
                  "getaddrinfo failed", "Network is unreachable")

    def probe(s):
        api = str(s.get("api") or "")
        try:
            req = urllib.request.Request(api, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code = getattr(r, "status", 200)
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:
            msg = str(e)
            return (s, None if not any(w in msg for w in dead_words) else "连接失败")
        if code in (404, 410):
            return (s, "HTTP %d" % code)
        return (s, None)

    kept, dropped = [], []
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(probe, sites))
    except Exception:
        results = [probe(s) for s in sites]
    for s, why in results:
        if why:
            dropped.append((s, why))
        else:
            kept.append(s)
    return kept, dropped


def human_size(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0
    return "%.1f GB" % n


def write_status(merged, records, out_bytes, mirrors=None):
    """生成中文状态页 status.html（霓虹深色 / 给非技术用户看）"""
    from string import Template

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    sites = len(merged.get("sites") or [])
    lives = len(merged.get("lives") or [])
    parses = len(merged.get("parses") or [])
    ok_n = sum(1 for r in records if r["ok"])
    bad_n = len(records) - ok_n

    if ok_n and not bad_n:
        health_cls, health_txt = "ok", "运行正常"
    elif ok_n:
        health_cls, health_txt = "warn", "部分源异常"
    else:
        health_cls, health_txt = "bad", "同步失败"

    # 上游源列表
    src_rows = []
    for r in records:
        short = html.escape(r["url"].split("//")[-1][:64])
        tag = '<span class="tag">补源</span> ' if r.get("http_only") else ""
        if r["ok"]:
            state, detail = '<span class="st ok">● 成功</span>', "%d 个站点" % r["sites"]
        else:
            state = '<span class="st bad">● 失败</span>'
            detail = '<span class="err">%s</span>' % html.escape(r["err"][:60])
        src_rows.append(
            '<li><div class="src-head">%s%s</div><div class="src-meta">%s · %s</div>'
            '<a class="src-link" href="%s" target="_blank" rel="noopener">查看</a></li>'
            % (state, tag, short, detail, html.escape(r["url"]))
        )

    # 镜像
    mirror_html = ""
    if mirrors:
        rows = []
        for m in mirrors:
            if m["ok"]:
                state = '<span class="st ok">● 成功</span>'
                detail = "%d 个站点 · %.0f KB" % (m["sites"], m["size"] / 1024.0)
            else:
                state = '<span class="st bad">● 失败</span>'
                detail = '<span class="err">%s</span>' % html.escape(m["err"][:60])
            rows.append(
                '<li><div class="src-head">%s</div><div class="src-meta">%s · %s</div>'
                '<a class="src-link" href="%s" target="_blank" rel="noopener">查看</a></li>'
                % (state, html.escape(m["name"]), detail, html.escape(m["name"]))
            )
        mirror_html = (
            '<section class="card">'
            '<h2><span class="num">④</span>备选接口（独立文件，不参与合并）</h2>'
            '<p class="hint">想看电视原版直播分组时用它，站点少但直播分组更全。</p>'
            '<ul class="src-list">%s</ul></section>' % "".join(rows)
        )

    tail = []
    try:
        with open(LOG, encoding="utf-8") as f:
            for line in f.readlines()[-12:]:
                tail.append(html.escape(line.rstrip()))
    except Exception:
        pass

    dsh = merged.get("dsh") or {}
    added = dsh.get("http_only_added") or 0
    dropped = dsh.get("dropped_dead") or []
    note = ""
    if added:
        note = '<p class="hint">本轮从补源新增 <b>%d</b> 个站点' % added
        if dropped:
            note += '，剔除失效 <b>%d</b> 个' % len(dropped)
        note += '。</p>'

    tpl = Template(r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>TVBox 接口中转站 · oect</title>
<style>
:root{
  --bg:#05070c; --panel:rgba(13,18,27,.82); --line:rgba(56,189,248,.16);
  --txt:#e6edf7; --dim:#8b98ad; --cyan:#22d3ee; --violet:#8b5cf6;
  --ok:#34d399; --warn:#fbbf24; --bad:#fb7185;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--txt); min-height:100vh;
  font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  padding:28px 16px 64px; overflow-x:hidden;
}
body::before{
  content:""; position:fixed; inset:0; z-index:-2;
  background-image:linear-gradient(rgba(56,189,248,.055) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(56,189,248,.055) 1px,transparent 1px);
  background-size:44px 44px;
  mask-image:radial-gradient(ellipse 80% 60% at 50% 0%,#000 40%,transparent 100%);
  -webkit-mask-image:radial-gradient(ellipse 80% 60% at 50% 0%,#000 40%,transparent 100%);
}
body::after{
  content:""; position:fixed; inset:0; z-index:-1; pointer-events:none;
  background:
    radial-gradient(600px 320px at 12% -8%,rgba(34,211,238,.16),transparent 70%),
    radial-gradient(720px 420px at 88% 4%,rgba(139,92,246,.16),transparent 72%);
}
.wrap{max-width:920px;margin:0 auto}

/* ---------- 头部 ---------- */
.hero{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;margin-bottom:22px}
.brand{display:flex;gap:14px;align-items:center}
.logo{
  width:46px;height:46px;border-radius:12px;flex:none;
  display:grid;place-items:center;font-weight:800;letter-spacing:.5px;color:#04121a;
  background:linear-gradient(135deg,var(--cyan),var(--violet));
  box-shadow:0 0 22px rgba(34,211,238,.45);
}
h1{font-size:20px;margin:0;letter-spacing:.3px}
.sub{color:var(--dim);font-size:13px;margin:4px 0 0;max-width:560px}
.pill{
  display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:999px;
  font-size:13px;font-weight:600;border:1px solid var(--line);background:var(--panel);
}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;box-shadow:0 0 0 0 currentColor}
.pill.ok{color:var(--ok)} .pill.warn{color:var(--warn)} .pill.bad{color:var(--bad)}
.pill.ok .dot{animation:pulse 2.4s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)}70%{box-shadow:0 0 0 12px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}

/* ---------- 数字卡片 ---------- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:22px}
.stat{
  position:relative;padding:16px 16px 14px;border-radius:14px;background:var(--panel);
  border:1px solid var(--line);overflow:hidden;
}
.stat::after{
  content:"";position:absolute;left:0;top:0;height:2px;width:100%;
  background:linear-gradient(90deg,var(--cyan),var(--violet));opacity:.85;
}
.stat .k{color:var(--dim);font-size:12px;letter-spacing:.4px}
.stat .v{
  font:700 30px/1.15 ui-monospace,Consolas,"Cascadia Mono",monospace;
  font-variant-numeric:tabular-nums;
  background:linear-gradient(180deg,#fff,#9fd8ff);-webkit-background-clip:text;background-clip:text;color:transparent;
}
.stat .u{color:var(--dim);font-size:12px;margin-left:4px}

/* ---------- 卡片 ---------- */
.card{
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:18px 18px 16px;margin-bottom:16px;
  box-shadow:0 18px 40px -28px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.04);
}
.card h2{font-size:15px;margin:0 0 12px;display:flex;align-items:center;gap:8px;letter-spacing:.3px}
.num{
  display:inline-grid;place-items:center;width:22px;height:22px;border-radius:7px;font-size:12px;
  background:linear-gradient(135deg,rgba(34,211,238,.22),rgba(139,92,246,.22));
  border:1px solid var(--line);color:var(--cyan);
}
.hint{color:var(--dim);font-size:13px;margin:10px 0 0}

/* ---------- 地址 ---------- */
.addr-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:6px}
.addr-row + .addr-row{margin-top:14px}
.badge{
  font-size:11px;font-weight:700;letter-spacing:.4px;padding:3px 9px;border-radius:999px;
  color:#04121a;background:linear-gradient(135deg,var(--cyan),#7dd3fc);
}
.badge.alt{background:linear-gradient(135deg,#a78bfa,#c4b5fd)}
code{
  flex:1 1 320px;min-width:0;padding:11px 14px;border-radius:10px;
  background:#070b12;border:1px solid var(--line);
  font:13px/1.5 ui-monospace,Consolas,monospace;color:#a5f3fc;
  word-break:break-all;
}
button{
  padding:10px 16px;border-radius:10px;border:1px solid rgba(34,211,238,.45);cursor:pointer;
  background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(139,92,246,.16));
  color:#c8f4ff;font-size:13px;font-weight:600;transition:.18s;
}
button:hover{border-color:var(--cyan);box-shadow:0 0 18px rgba(34,211,238,.28)}
button:active{transform:translateY(1px)}
.link{color:var(--cyan);font-size:12px;text-decoration:none;opacity:.9}
.link:hover{opacity:1;text-decoration:underline}

/* ---------- 折叠区 ---------- */
details.card{padding:0}
summary{
  cursor:pointer;padding:16px 18px;font-size:14px;font-weight:600;list-style:none;
  display:flex;align-items:center;justify-content:space-between;gap:10px;
}
summary::-webkit-details-marker{display:none}
summary::after{content:"＋";color:var(--cyan);font-size:16px}
details[open] summary::after{content:"－"}
details[open] summary{border-bottom:1px solid var(--line)}
.details-body{padding:16px 18px}

.steps{margin:0;padding-left:0;list-style:none;counter-reset:s}
.steps li{
  counter-increment:s;position:relative;padding:10px 0 10px 40px;
  border-bottom:1px dashed rgba(148,163,184,.16);
}
.steps li:last-child{border-bottom:0}
.steps li::before{
  content:counter(s);position:absolute;left:0;top:10px;
  width:26px;height:26px;border-radius:9px;display:grid;place-items:center;
  font-size:13px;font-weight:700;color:var(--cyan);
  background:rgba(34,211,238,.12);border:1px solid var(--line);
}
.steps b{display:block;font-size:14px}
.steps span{color:var(--dim);font-size:13px}
.faq{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}
.faq p{margin:8px 0;font-size:13px;color:#c3cedd}
.faq b{color:#e8f4ff}

/* ---------- 源列表 ---------- */
.src-list{list-style:none;margin:0;padding:0}
.src-list li{
  display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;
  padding:10px 0;border-bottom:1px dashed rgba(148,163,184,.14);
}
.src-list li:last-child{border-bottom:0}
.src-head{flex:1 1 100%;display:flex;gap:8px;align-items:center;font-size:13px;color:#c3cedd;word-break:break-all}
.src-meta{color:var(--dim);font-size:12px;flex:1 1 auto}
.src-link{color:var(--cyan);font-size:12px;text-decoration:none}
.st{font-weight:700;font-size:12px;flex:none}
.st.ok{color:var(--ok)} .st.bad{color:var(--bad)}
.err{color:var(--bad)}
.tag{
  font-size:10px;padding:1px 6px;border-radius:5px;color:#c4b5fd;
  border:1px solid rgba(167,139,250,.4);background:rgba(139,92,246,.12);
}

pre{
  margin:0;padding:14px;border-radius:10px;background:#070b12;border:1px solid var(--line);
  font:12px/1.7 ui-monospace,Consolas,monospace;color:#93a4bb;overflow:auto;max-height:280px;
}
footer{text-align:center;color:#5d6a7d;font-size:12px;margin-top:26px}
@media (max-width:520px){
  body{padding:20px 12px 48px}
  .stat .v{font-size:26px}
  code{flex:1 1 100%}
}
</style>
</head>
<body>
<main class="wrap">

  <header class="hero">
    <div class="brand">
      <div class="logo">TV</div>
      <div>
        <h1>TVBox 接口中转站</h1>
        <p class="sub">这是一份给电视用的「频道清单」，把它填进电视 App，就能看到最新的片源。</p>
      </div>
    </div>
    <div class="pill $health_cls"><span class="dot"></span>$health_txt</div>
  </header>

  <section class="stats">
    <div class="stat"><div class="k">片源站点</div><div class="v">$sites</div><div class="u">个</div></div>
    <div class="stat"><div class="k">直播分组</div><div class="v">$lives</div><div class="u">组</div></div>
    <div class="stat"><div class="k">解析通道</div><div class="v">$parses</div><div class="u">条</div></div>
    <div class="stat"><div class="k">上游源</div><div class="v">$ok_n<span class="u">/$total_src</span></div><div class="u">成功</div></div>
  </section>

  <section class="card">
    <h2><span class="num">1</span>电视里填这个地址</h2>
    <div class="addr-row">
      <span class="badge">主用</span>
      <code id="u1">$public</code>
      <button data-copy="u1">复制</button>
      <a class="link" href="config.json" target="_blank" rel="noopener">看原始数据</a>
    </div>
    <p class="hint">站点最多（$sites 个），日常用它就行。</p>

    <div class="addr-row">
      <span class="badge alt">备选</span>
      <code id="u2">$public_mirror</code>
      <button data-copy="u2">复制</button>
    </div>
    <p class="hint">想看原版电视直播分组时用这个（$mirror_sites 个站点，直播源带测速排序）。</p>
  </section>

  <details class="card">
    <summary>不知道在哪填？点开看 3 步</summary>
    <div class="details-body">
      <ol class="steps">
        <li><b>打开电视上的 App</b><span>TVBox / 影视仓 / OK影视，装哪个都行</span></li>
        <li><b>找到「配置地址」或「接口」</b><span>通常在「设置」里，有的在首页右上角</span></li>
        <li><b>粘贴上面的地址 → 确定 → 重启 App</b><span>第一次加载要十几秒，属正常</span></li>
      </ol>
      <div class="faq">
        <p><b>打不开 / 一直转圈？</b>先看本页顶部是不是「运行正常」，再确认电视和 oect 连的是同一个 WiFi。</p>
        <p><b>能进但播放失败？</b>多半是那个站点自己挂了，换个站点试。</p>
        <p><b>多久更新？</b>每天 04:10 自动同步一次，这一页每 5 分钟自动刷新。</p>
      </div>
    </div>
  </details>

  <section class="card">
    <h2><span class="num">2</span>今天同步的情况</h2>
    $note
    <ul class="src-list">$src_rows</ul>
  </section>

  $mirror_html

  <details class="card">
    <summary>同步日志（最近 12 行，排错用）</summary>
    <div class="details-body"><pre>$tail</pre></div>
  </details>

  <footer>
    oect · 生成于 $now · 每 5 分钟自动刷新 · 接口大小 $size
  </footer>
</main>
<script>
document.querySelectorAll('button[data-copy]').forEach(function(b){
  b.addEventListener('click',function(){
    var el=document.getElementById(b.dataset.copy);
    var txt=el.textContent.trim();
    var done=function(){var t=b.textContent;b.textContent='已复制 ✓';setTimeout(function(){b.textContent=t},1500);};
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(done,function(){fallback(txt,done)});
    }else{fallback(txt,done)}
    function fallback(v,cb){
      var ta=document.createElement('textarea');ta.value=v;ta.style.position='fixed';ta.style.opacity='0';
      document.body.appendChild(ta);ta.select();try{document.execCommand('copy')}catch(e){}
      document.body.removeChild(ta);cb();
    }
  });
});
</script>
</body>
</html>
''')

    page = tpl.substitute(
        health_cls=health_cls, health_txt=health_txt,
        sites=sites, lives=lives, parses=parses,
        ok_n=ok_n, total_src=len(records),
        public=PUBLIC_URL,
        public_mirror=PUBLIC_BASE + "inliang.json",
        mirror_sites=next((m["sites"] for m in (mirrors or []) if m["ok"]), 0),
        src_rows="".join(src_rows) or '<li><div class="src-meta">（没有配置上游源）</div></li>',
        mirror_html=mirror_html,
        note=note,
        tail="\n".join(tail) or "（暂无日志）",
        now=now, size=human_size(out_bytes),
    )

    tmp = STATUS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, STATUS)
    log("状态页已更新: %s (%d KB)" % (STATUS, len(page.encode("utf-8")) // 1024))


def main():
    dry = "--dry-run" in sys.argv
    no_check = "--no-check" in sys.argv
    srcs = read_sources()
    if not srcs:
        log("sources.txt 里没有有效地址，退出")
        return 2

    log("开始同步，共 %d 个源" % len(srcs))
    ok, records = [], []
    for s in srcs:
        u = s["url"]
        tag = ("[补源] " if s["http_only"] else "") + u.split("//")[-1][:60]
        try:
            cfg = fetch(u)
            n = len(cfg.get("sites") or [])
            log("  ok %s (sites=%d)" % (tag, n))
            ok.append((tag, cfg, s["http_only"]))
            records.append({"url": u, "ok": True, "sites": n, "err": "", "http_only": s["http_only"]})
        except Exception as e:
            log("  FAIL %s -> %s" % (tag, e))
            records.append({"url": u, "ok": False, "sites": 0, "err": str(e), "http_only": s["http_only"]})

    if not ok:
        log("全部源失败，保留旧 config.json 不动")
        return 1

    merged, extra_start = merge(ok)

    dropped = []
    if extra_start is not None and not no_check:
        head = merged["sites"][:extra_start]
        tail = merged["sites"][extra_start:]
        t0 = time.time()
        kept, dropped = check_sites(tail)
        merged["sites"] = head + kept
        log("补源体检：检查 %d 个，保留 %d，剔除 %d（%.0fs）" % (
            len(tail), len(kept), len(dropped), time.time() - t0))
        for s, why in dropped[:8]:
            log("   剔除 %s -> %s" % (str(s.get("name"))[:24], why))
    merged["dsh"] = {
        "by": "oect tvbox-hub",
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": len(ok),
        "failed": [r["url"] for r in records if not r["ok"]],
        "http_only_sources": [r["url"] for r in records if r.get("http_only") and r["ok"]],
        "http_only_added": (len(merged["sites"]) - extra_start) if extra_start is not None else 0,
        "dropped_dead": [str(s.get("name")) for s, _ in dropped],
    }
    txt = json.dumps(merged, ensure_ascii=False, indent=1)
    size = len(txt.encode("utf-8"))
    mirrors = mirror_all(dry)
    if dry:
        log("dry-run: 合并结果 %d 字节，不写文件" % size)
        return 0

    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(txt)
    os.replace(tmp, OUT)
    log("完成: sites=%d lives=%d -> %s (%d 字节)" % (
        len(merged.get("sites") or []), len(merged.get("lives") or []), OUT, size))
    write_status(merged, records, size, mirrors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
