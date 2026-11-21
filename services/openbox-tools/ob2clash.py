
# -*- coding: utf-8 -*-
"""OpenBox(sing-box) config.json -> Clash/Mihomo YAML converter"""
import json, re, io, os, sys
import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG  = os.path.join(BASE, "etc", "config.json")
OUT  = os.path.join(BASE, "clash")
LIST = os.path.join(OUT, "ruleset", "overseas-ai.list")

cfg = json.load(open(CFG, encoding="utf-8"))
obs = cfg["outbounds"]
NODE_TYPES = ("shadowsocks", "vmess", "anytls")
GROUP_TYPES = ("selector", "urltest")

def dur_sec(s):
    if not s: return None
    m = re.fullmatch(r"(\d+)(s|m|h|d)?", s.strip())
    if not m: return None
    n = int(m.group(1)); u = m.group(2) or "s"
    return n * {"s":1, "m":60, "h":3600, "d":86400}[u]

def conv(o):
    t = o["type"]
    p = {"name": o["tag"]}
    if t == "shadowsocks":
        p.update({"type": "ss", "server": o["server"], "port": o["server_port"],
                  "cipher": o["method"], "password": o["password"], "udp": True})
    elif t == "vmess":
        p.update({"type": "vmess", "server": o["server"], "port": o["server_port"],
                  "uuid": o["uuid"], "alterId": o.get("alter_id", 0),
                  "cipher": o.get("security") or "auto", "udp": True})
        tls = o.get("tls") or {}
        if tls.get("enabled"):
            p["tls"] = True
            p["skip-cert-verify"] = bool(tls.get("insecure", False))
            if tls.get("server_name"): p["servername"] = tls["server_name"]
        tr = o.get("transport") or {}
        if tr.get("type") == "ws":
            p["network"] = "ws"
            wo = {"path": tr.get("path", "/")}
            if tr.get("headers"): wo["headers"] = tr["headers"]
            p["ws-opts"] = wo
        elif tr.get("type") == "grpc":
            p["network"] = "grpc"
            p["grpc-opts"] = {"grpc-service-name": tr.get("service_name", "")}
    elif t == "anytls":
        tls = o.get("tls") or {}
        p.update({"type": "anytls", "server": o["server"], "port": o["server_port"],
                  "password": o["password"], "client-fingerprint": "chrome", "udp": True})
        if tls.get("server_name"): p["sni"] = tls["server_name"]
        if tls.get("insecure"): p["skip-cert-verify"] = True
    return p

SPECIAL = {"直连": "DIRECT", "拒绝": "REJECT"}

def member(m):
    return SPECIAL.get(m, m)

proxies, groups = [], []
for o in obs:
    if o["type"] in NODE_TYPES:
        proxies.append(conv(o))
    elif o["type"] in GROUP_TYPES:
        g = {"name": o["tag"]}
        if o["type"] == "urltest":
            g.update({"type": "url-test", "url": o.get("url", "http://www.gstatic.com/generate_204"),
                      "interval": dur_sec(o.get("interval")) or 300,
                      "tolerance": o.get("tolerance", 50),
                      "proxies": [member(x) for x in o["outbounds"]]})
        else:
            g.update({"type": "select", "proxies": [member(x) for x in o["outbounds"]]})
        groups.append(g)

# ---------- rules ----------
C = []  # (comment_or_none, rule_or_none)
def sec(t): C.append(("sec", t))
def rule(r): C.append(("rule", r))

sec("私有网段 / 保留地址 → 直连")
for c in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
          "169.254.0.0/16", "100.64.0.0/10"]:
    rule("IP-CIDR,%s,DIRECT,no-resolve" % c)
for c in ["::1/128", "fc00::/7", "fe80::/10"]:
    rule("IP-CIDR6,%s,DIRECT,no-resolve" % c)
rule("DST-PORT,123,DIRECT")

sec("AI（geosite category-ai-!cn + OverseasAI 列表内联）")
rule("GEOSITE,category-ai-!cn,AI")
rule("DOMAIN-KEYWORD,opencode,AI")
ai_count = 0
if os.path.exists(LIST):
    for ln in io.open(LIST, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#"): continue
        parts = s.split(",")
        k = parts[0].upper()
        if k in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and len(parts) >= 2:
            rule("%s,%s,AI" % (k, parts[1])); ai_count += 1
        elif k in ("IP-CIDR", "IP-CIDR6") and len(parts) >= 2:
            rule("%s,%s,AI,no-resolve" % (k, parts[1])); ai_count += 1

sec("Telegram")
for d in ["telegram.org", "t.me", "telegram.me", "tdesktop.com", "telegra.ph", "telesco.pe"]:
    rule("DOMAIN-SUFFIX,%s,Telegram" % d)
for c in ["91.105.192.0/23","91.108.4.0/22","91.108.8.0/21","91.108.16.0/21","91.108.56.0/22",
          "95.161.64.0/20","149.154.160.0/20","185.76.151.0/24",
          "2001:67c:4e8::/48","2001:b28:f23c::/47","2001:b28:f23f::/48","2a0a:f280::/32"]:
    rule(("IP-CIDR6,%s,Telegram,no-resolve" if ":" in c else "IP-CIDR,%s,Telegram,no-resolve") % c)

sec("X / Twitter")
for d in ["x.com", "twitter.com", "t.co", "twimg.com", "tweetdeck.com", "twtrdns.net", "twttr.com"]:
    rule("DOMAIN-SUFFIX,%s,X" % d)

sec("YouTube / TikTok / Netflix / GitHub / Google / Microsoft / Apple / Games")
rule("GEOSITE,youtube,Youtube")
rule("GEOSITE,tiktok,TikTok")
rule("GEOSITE,netflix,Netflix")
rule("GEOSITE,github,Github")
rule("GEOSITE,google,Google")
rule("GEOSITE,microsoft,Microsoft")
rule("GEOSITE,apple,Apple")
rule("GEOSITE,steam,Games")
rule("GEOSITE,sony,Games")

sec("国外（GFW 域名 + 自定义）")
rule("GEOSITE,gfw,国外")
for d in ["crosspointreader.com", "reasonix.io", "edcbook.com"]:
    rule("DOMAIN,%s,国外" % d)

sec("国内（CN 域名 + CN IP + 自定义）")
rule("GEOSITE,cn,国内")
for d in ["ikanbot.com", "crossmux.com", "cloudzao.com"]:
    rule("DOMAIN-SUFFIX,%s,国内" % d)
rule("GEOIP,CN,国内")

sec("自定义")
rule("DOMAIN-SUFFIX,codebuddy.ai,自定义")

sec("兜底")
rule("MATCH,其他")

# ---------- emit ----------
def q(s):
    return yaml.safe_dump(s, default_flow_style=True, allow_unicode=True, width=100000).strip().rstrip("...").strip()

def build(with_rules=True):
    out = []
    out.append("# OpenBox (sing-box) -> Mihomo(Clash.Meta) 转换结果")
    out.append("# 源：oect:/opt/open-box/etc/config.json  (OpenBox v0.1.415 / sing-box 1.14.4-openbox-45)")
    out.append("# 生成：2026-11-12  by DSH  |  说明：详见同目录 README-conversion.md")
    out.append("# ⚠️ 含明文节点凭据，勿外发")
    out.append("")
    out.append("mixed-port: 7890")
    out.append("allow-lan: false")
    out.append("mode: rule")
    out.append("log-level: info")
    out.append("ipv6: true")
    out.append("external-controller: 127.0.0.1:9090")
    out.append("unified-delay: true")
    out.append("tcp-concurrent: true")
    out.append("")
    out.append("# ---------- 节点 %d 个 ----------" % len(proxies))
    out.append(yaml.safe_dump({"proxies": proxies}, allow_unicode=True, sort_keys=False,
                              default_flow_style=False, width=100000).rstrip())
    out.append("")
    out.append("# ---------- 策略组 %d 个 ----------" % len(groups))
    out.append(yaml.safe_dump({"proxy-groups": groups}, allow_unicode=True, sort_keys=False,
                              default_flow_style=False, width=100000).rstrip())
    out.append("")
    if with_rules:
        out.append("rules:")
        for kind, v in C:
            if kind == "sec":
                out.append("  # === %s ===" % v)
            else:
                out.append("  - " + q(v))
    else:
        out.append("rules:")
        out.append("  - " + q("MATCH,所有-手动"))
    out.append("")
    return "\n".join(out)

full = build(True)
lite = build(False)
io.open(os.path.join(OUT, "openbox-mihomo.yaml"), "w", encoding="utf-8", newline="\n").write(full)
io.open(os.path.join(OUT, "openbox-proxies-only.yaml"), "w", encoding="utf-8", newline="\n").write(lite)

# ---------- self checks ----------
d = yaml.safe_load(full)
names = [p["name"] for p in d["proxies"]]
assert len(names) == len(set(names)), "duplicate proxy names"
pool = set(names) | {"DIRECT", "REJECT"} | {g["name"] for g in d["proxy-groups"]}
bad = [(g["name"], m) for g in d["proxy-groups"] for m in g["proxies"] if m not in pool]
print("proxies:", len(d["proxies"]), "groups:", len(d["proxy-groups"]), "rules:", len(d["rules"]))
print("dangling group members:", bad[:5] if bad else "none")
from collections import Counter
print("proxy types:", dict(Counter(p["type"] for p in d["proxies"])))
print("rules total:", len(d["rules"]), "| AI inlined:", ai_count)
print("full yaml lines:", full.count("\n") + 1, "bytes:", len(full.encode("utf-8")))
print("lite yaml lines:", lite.count("\n") + 1)
print("OK")

