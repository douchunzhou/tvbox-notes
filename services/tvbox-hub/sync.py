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
    """生成中文状态页 status.html"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    sites = len(merged.get("sites") or [])
    lives = len(merged.get("lives") or [])
    parses = len(merged.get("parses") or [])
    ok_n = sum(1 for r in records if r["ok"])
    bad_n = len(records) - ok_n

    rows = []
    for r in records:
        url = html.escape(r["url"])
        short = html.escape(r["url"].split("//")[-1][:70])
        if r["ok"]:
            badge = '<span class="ok">成功</span>'
            detail = "%d 站点" % r["sites"]
        else:
            badge = '<span class="bad">失败</span>'
            detail = html.escape(r["err"][:80])
        if r.get("http_only"):
            short = "补源 · " + short
        rows.append(
            '<tr><td>%s</td><td class="mono">%s</td><td>%s</td><td>%s</td></tr>'
            % (badge, short, detail, '<a href="%s" target="_blank">打开</a>' % url)
        )

    tail = []
    try:
        with open(LOG, encoding="utf-8") as f:
            for line in f.readlines()[-12:]:
                tail.append(html.escape(line.rstrip()))
    except Exception:
        pass

    mirror_rows = []
    for m in (mirrors or []):
        if m["ok"]:
            badge = '<span class="ok">成功</span>'
            detail = "%d 站点 · %.0f KB" % (m["sites"], m["size"] / 1024.0)
        else:
            badge = '<span class="bad">失败</span>'
            detail = html.escape(m["err"][:80])
        mirror_rows.append(
            '<tr><td>%s</td><td class="mono">%s</td><td>%s</td><td>%s</td></tr>'
            % (badge, html.escape(m["name"]), detail,
               '<a href="%s" target="_blank">打开</a>' % html.escape(m["name"]))
        )

    spider = (merged.get("spider") or "").split(";")[0]

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>TVBox 接口中转站 · 状态</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:24px 16px 48px; font:15px/1.6 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
         background:#0f1115; color:#e6e8ec; }}
  .wrap {{ max-width: 980px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .sub {{ color:#8b94a3; font-size:13px; margin-bottom:20px; }}
  .card {{ background:#171a21; border:1px solid #232833; border-radius:10px; padding:16px 18px; margin-bottom:16px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }}
  .k {{ color:#8b94a3; font-size:12px; }}
  .v {{ font-size:22px; font-weight:600; margin-top:2px; }}
  .url {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  code {{ background:#0b0d11; border:1px solid #232833; border-radius:6px; padding:6px 10px; font-size:13px; word-break:break-all; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 6px; border-bottom:1px solid #232833; vertical-align:top; }}
  th {{ color:#8b94a3; font-weight:500; font-size:12px; }}
  .mono {{ font-family:ui-monospace,Consolas,monospace; font-size:12px; color:#a8b1c0; word-break:break-all; }}
  .ok {{ color:#39d353; }} .bad {{ color:#f85149; }}
  pre {{ background:#0b0d11; border:1px solid #232833; border-radius:8px; padding:12px; overflow:auto;
         font-size:12px; color:#a8b1c0; margin:0; }}
  a {{ color:#58a6ff; text-decoration:none; }}
  button {{ background:#238636; color:#fff; border:0; border-radius:6px; padding:6px 12px; font-size:13px; cursor:pointer; }}
  .tip {{ color:#8b94a3; font-size:12px; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>TVBox 接口中转站</h1>
  <div class="sub">oect · 本页每 5 分钟自动刷新 · 生成于 {now}</div>

  <div class="card">
    <div class="k">电视里填这个地址（配置地址 / 接口）</div>
    <div class="url" style="margin-top:8px">
      <code id="u">{public}</code>
      <button onclick="navigator.clipboard.writeText('{public}');this.textContent='已复制';setTimeout(()=>this.textContent='复制',1500)">复制</button>
      <a href="config.json" target="_blank">直接查看 JSON</a>
    </div>
  </div>

  <div class="card grid">
    <div><div class="k">上次同步</div><div class="v" style="font-size:16px">{now}</div></div>
    <div><div class="k">成功 / 失败源</div><div class="v"><span class="ok">{ok_n}</span> / <span class="bad">{bad_n}</span></div></div>
    <div><div class="k">站点</div><div class="v">{sites}</div></div>
    <div><div class="k">直播源</div><div class="v">{lives}</div></div>
    <div><div class="k">解析</div><div class="v">{parses}</div></div>
    <div><div class="k">接口大小</div><div class="v" style="font-size:16px">{size}</div></div>
  </div>

  <div class="card">
    <div class="k" style="margin-bottom:8px">上游源</div>
    <table>
      <tr><th>状态</th><th>地址</th><th>结果</th><th></th></tr>
      {rows}
    </table>
    <div class="tip">spider：<span class="mono">{spider}</span></div>
  </div>

  <div class="card">
    <div class="k" style="margin-bottom:8px">镜像接口（独立文件，不参与上面合并）</div>
    <table>
      <tr><th>状态</th><th>文件</th><th>结果</th><th></th></tr>
      {mirror_rows}
    </table>
    <div class="tip">来源见 mirrors.txt；镜像失败时保留上一份文件，电视端不会白屏。</div>
  </div>

  <div class="card">
    <div class="k" style="margin-bottom:8px">最近同步日志</div>
    <pre>{tail}</pre>
    <div class="tip">每天 04:10 自动同步。手动同步：<code>cd /mnt/data_sda1/services/tvbox &amp;&amp; python3 sync.py</code></div>
  </div>
</div>
</body>
</html>
""".format(now=now, public=PUBLIC_URL, ok_n=ok_n, bad_n=bad_n, sites=sites, lives=lives,
           parses=parses, size=human_size(out_bytes), rows="\n      ".join(rows) or "<tr><td colspan=4>（无）</td></tr>",
           spider=html.escape(spider or "（未设置）"), tail="\n".join(tail) or "（暂无日志）",
           mirror_rows="\n      ".join(mirror_rows) or "<tr><td colspan=4>（未配置镜像，见 mirrors.txt）</td></tr>")

    tmp = STATUS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, STATUS)
    log("状态页已更新: %s" % STATUS)


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
