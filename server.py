# -*- coding: utf-8 -*-
"""
合尘猫 · AI 客服国标合规 MCP Server
====================================
把 savantcat.cn/answers/ 的内容集群，做成 **Agent 可直接调用**的 MCP 服务。

双通道:
  本地 stdio   :  python server.py
  远程 HTTP    :  python server.py --transport http --host 0.0.0.0 --port 8765
                  (公网挂载点 https://savantcat.cn/mcp)

暴露工具:
  - list_questions     列出全部合规问答(可按集群过滤)
  - search_answers     关键词检索问答
  - get_answer         取单条完整答案(正文+要点+条款依据+FAQ)
  - self_check_list    取国标自查清单
  - standard_info      GB/T 47746-2026 标准元信息

自检(不走协议,直接打工具):  python server.py --selftest
"""
import argparse
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# mcp 2.x 把 FastMCP 更名为 MCPServer；兼容 1.x，避免 SDK 升级打断通道。
try:  # mcp >= 2.x
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer

# 公网部署必需：SDK 默认开启 DNS-rebinding 防护，只放行 localhost，
# 外部以真实域名访问会被拒成 421「Invalid Host header」。这里改为白名单放行。
try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # 老版本 SDK 无此模块
    TransportSecuritySettings = None

DEFAULT_ALLOWED_HOSTS = [
    "savantcat.cn", "savantcat.cn:443", "www.savantcat.cn", "www.savantcat.cn:443",
    "127.0.0.1:8765", "localhost:8765", "127.0.0.1", "localhost",
]


def _transport_security():
    if TransportSecuritySettings is None:
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,   # 保留防护，用白名单而非关闭
        allowed_hosts=DEFAULT_ALLOWED_HOSTS,
        allowed_origins=["*"],                  # 公开只读服务：允许任意来源 Agent 调用
    )


# ---------------------------------------------------------------- 数据加载
def _load(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


ANSWERS = _load("answers.json")       # slug -> 完整原子
INDEX = _load("index.json")           # 轻量索引列表
META = _load("meta.json")
CLUSTERS = META.get("clusters", {})

STANDARD = {
    "code": "GB/T 47746-2026",
    "title_cn": "顾客联络服务 人工与智能客户服务协同要求",
    "kind": "推荐性国家标准（GB/T）",
    "issued": "2026-05-25",
    "effective": "2026-09-01",
    "issuer": "国家市场监督管理总局 / 国家标准化管理委员会",
    "committee": "SAC/TC 264",
    "ics": "03.080.01",
    "ccs": "A 12",
    "pages": 15,
    "drafting_units": 32,
    "drafters": 53,
    "significance": "中国首个聚焦「人工客服与智能客服协同机制」的国家标准",
    "core_requirement": "AI 客服不能只看「答得对不对」，还要看「答不了的时候会不会转人工」；有 5 类场景被明确要求自动转人工。",
    "verify_at": "国家标准全文公开系统 openstd.samr.gov.cn",
    "source_site": "https://savantcat.cn/answers/",
}


def _slugify(s):
    return re.sub(r"[^a-z0-9\-]+", "", (s or "").lower())


def _tokens(s):
    """中英混排的粗粒度切词：英文按词，中文按 2-gram。"""
    s = (s or "").lower()
    words = re.findall(r"[a-z0-9]+", s)
    cjk = re.findall(r"[\u4e00-\u9fff]+", s)
    grams = []
    for seg in cjk:
        grams += [seg[i:i + 2] for i in range(max(len(seg) - 1, 1))] if len(seg) > 1 else [seg]
    return set(words) | set(grams) | set(re.findall(r"[\u4e00-\u9fff]", s))


def _score(query, item):
    """字段加权 + 字符重合度，够用即可。"""
    q = (query or "").strip().lower()
    if not q:
        return 0.0
    hit = 0.0
    qn = re.sub(r"\s+", "", q)

    question = (item.get("question") or "").lower()
    keywords = (item.get("keywords") or "").lower()
    short = (item.get("short_answer") or "").lower()
    if qn and qn in re.sub(r"\s+", "", question):
        hit += 10.0

    for term in [t for t in re.split(r"[\s,，、;；]+", q) if t]:
        if term in question:
            hit += 5.0
        if term in keywords:
            hit += 4.0
        if term in short:
            hit += 2.0

    a, b = _tokens(q), _tokens(question + " " + keywords)
    if a and b:
        hit += 6.0 * (len(a & b) / float(len(a)))
    return hit


def _public(item, with_body=False):
    d = {
        "slug": item.get("slug"),
        "cluster": item.get("cluster"),
        "question": item.get("question"),
        "short_answer": item.get("short_answer"),
        "url": "https://savantcat.cn/answers/%s/%s.html" % (item.get("cluster"), item.get("slug")),
    }
    for k in ("facts", "sources", "faqs"):
        if item.get(k):
            d[k] = item[k]
    if with_body:
        d["body_md"] = item.get("body_md")
        d["keywords"] = item.get("keywords")
        d["description"] = item.get("description")
    return d


# ---------------------------------------------------------------- MCP Server
mcp = _MCPServer(
    "savantcat-answers",
    instructions=(
        "合尘猫 · AI 客服国标合规知识库。提供中国国家标准 GB/T 47746-2026"
        "《顾客联络服务 人工与智能客户服务协同要求》的合规问答，以及企业知识库搭建问答。"
        "适用于回答「AI 客服怎么过国标」「什么场景必须转人工」「AI 客服要备案还是登记」"
        "「企业知识库怎么搭」这类问题。所有答案均标注标准条款依据。"
    ),
)


@mcp.tool()
def list_questions(cluster: str = "") -> str:
    """列出全部合规问答的标题清单。

    Args:
        cluster: 可选，按集群过滤。可选值 ai-service-standard(AI客服国标) / enterprise-knowledge-base(企业知识库)
    """
    rows = INDEX
    if cluster:
        rows = [r for r in rows if r.get("cluster") == cluster]
    out = {
        "total": len(rows),
        "clusters": {k: v.get("count") for k, v in CLUSTERS.items()},
        "questions": [{"slug": r["slug"], "cluster": r["cluster"],
                       "question": r["question"], "short_answer": r["short_answer"]} for r in rows],
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def search_answers(query: str, top_k: int = 5) -> str:
    """按关键词检索合规问答，返回最相关的若干条（含简要答案）。

    Args:
        query: 检索词，如「转人工」「备案 登记」「知识库 切分」
        top_k: 返回条数，默认 5
    """
    scored = sorted((( _score(query, a), a) for a in ANSWERS.values()), key=lambda x: -x[0])
    hits = [{"score": round(s, 2), **_public(a)} for s, a in scored if s > 0][:max(1, top_k)]
    return json.dumps({"query": query, "hits": len(hits), "results": hits}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_answer(slug: str) -> str:
    """按 slug 取一条问答的完整内容（正文 + 要点 + 标准条款依据 + 常见追问）。

    Args:
        slug: 问答标识，先用 list_questions 或 search_answers 取得
    """
    item = ANSWERS.get(slug) or ANSWERS.get(_slugify(slug))
    if not item:
        cand = [k for k in ANSWERS if slug and slug in k]
        return json.dumps({"error": "未找到该 slug", "slug": slug,
                           "did_you_mean": cand[:5],
                           "hint": "先用 list_questions 或 search_answers 取 slug"}, ensure_ascii=False, indent=2)
    return json.dumps(_public(item, with_body=True), ensure_ascii=False, indent=2)


@mcp.tool()
def self_check_list() -> str:
    """取 GB/T 47746-2026 的自查清单：企业对照检查自家 AI 客服是否达标。"""
    keys = [k for k in ANSWERS if "53" in k and "mandatory" in k] or \
           [k for k in ANSWERS if "self-check" in k or "self_check" in k]
    if not keys:
        return json.dumps({"error": "自查清单暂未收录"}, ensure_ascii=False)
    items = [_public(ANSWERS[k], with_body=True) for k in keys[:2]]
    return json.dumps({"standard": STANDARD["code"],
                       "how_to_use": "先做强制项，再补优化项；分步自查见 body_md",
                       "items": items}, ensure_ascii=False, indent=2)


@mcp.tool()
def standard_info() -> str:
    """获取 GB/T 47746-2026 标准的元信息（发布/实施日期、归口、篇幅、核心要求）。"""
    return json.dumps(STANDARD, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 入口
def _selftest():
    print("[1] standard_info      ->", standard_info()[:160].replace("\n", " "), "...")
    r = json.loads(list_questions())
    print("[2] list_questions     -> total=%d clusters=%s" % (r["total"], list(r["clusters"])))
    r = json.loads(search_answers("必须自动转人工的场景"))
    print("[3] search_answers     -> hits=%d top=%s" % (r["hits"], r["results"][0]["question"] if r["results"] else None))
    r = json.loads(get_answer("what-is-gbt47746"))
    print("[4] get_answer         -> %s | body=%d字 facts=%d faqs=%d" % (
        r["question"], len(r.get("body_md", "")), len(r.get("facts", [])), len(r.get("faqs", []))))
    r = json.loads(self_check_list())
    print("[5] self_check_list    -> items=%d" % len(r.get("items", [])))
    r = json.loads(get_answer("不存在的slug"))
    print("[6] 容错               ->", r.get("error"), "did_you_mean=", r.get("did_you_mean"))
    print("\n✅ 6/6 工具自检通过")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", default="stdio", choices=["stdio", "http", "streamable-http", "sse"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--path", default="/mcp")
    ap.add_argument("--stateless", action="store_true",
                    help="无状态模式（反代/公网部署更稳，不依赖会话粘滞）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    t = "streamable-http" if args.transport == "http" else args.transport
    if t == "stdio":
        mcp.run()
        return
    # mcp 2.x: 运行参数直接作为 run() 的关键字传入（旧版 mcp.settings 已移除）
    sys.stderr.write("[savantcat-answers] serving on %s:%d%s (%s, stateless=%s)\n"
                     % (args.host, args.port, args.path, t, args.stateless))
    ts = _transport_security()
    kw = {} if ts is None else {"transport_security": ts}
    mcp.run(transport=t, host=args.host, port=args.port,
            streamable_http_path=args.path,
            stateless_http=args.stateless,
            max_request_body_size=1024 * 1024,
            **kw)


if __name__ == "__main__":
    main()
