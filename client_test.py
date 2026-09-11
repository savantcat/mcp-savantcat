# -*- coding: utf-8 -*-
"""MCP 客户端全链路测试：用官方 SDK 连上 server，跑一遍全部工具。
用法:  python client_test.py [url]      默认 http://127.0.0.1:8765/mcp
"""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url):
    ok = 0
    fail = []
    async with streamable_http_client(url) as streams:
        r, w = streams[0], streams[1]
        async with ClientSession(r, w) as s:
            init = await s.initialize()

            def _g(o, *names):
                for n in names:
                    v = getattr(o, n, None)
                    if v is not None:
                        return v
                return "?"

            print("✅ initialize -> server=%s  proto=%s" % (
                _g(_g(init, "server_info", "serverInfo"), "name"),
                _g(init, "protocol_version", "protocolVersion")))

            tl = await s.list_tools()
            print("✅ tools/list -> %d 个工具" % len(tl.tools))
            for t in tl.tools:
                print("     - %-18s %s" % (t.name, (t.description or "").split("\n")[0][:44]))

            async def call(name, args, check):
                nonlocal ok
                try:
                    res = await s.call_tool(name, args)
                    txt = res.content[0].text if res.content else ""
                    d = json.loads(txt)
                    assert check(d), "断言失败"
                    ok += 1
                    return d
                except Exception as e:
                    fail.append("%s: %r" % (name, e))
                    return None

            d = await call("standard_info", {}, lambda d: d.get("code") == "GB/T 47746-2026")
            if d:
                print("\n✅ standard_info   -> %s | 实施 %s" % (d["code"], d["effective"]))

            d = await call("list_questions", {"cluster": "ai-service-standard"},
                           lambda d: d.get("total") == 6)
            if d:
                print("✅ list_questions  -> %d 条" % d["total"])

            d = await call("search_answers", {"query": "必须自动转人工的场景", "top_k": 3},
                           lambda d: d.get("hits", 0) > 0)
            if d:
                print("✅ search_answers -> %d 命中" % d["hits"])
                for h in d["results"]:
                    print("     *", h["question"])

            d = await call("get_answer", {"slug": "what-is-gbt47746"},
                           lambda d: "body_md" in d)
            if d:
                print("✅ get_answer     -> %s字 / facts %d / faqs %d" % (
                    len(d.get("body_md", "")), len(d.get("facts", [])), len(d.get("faqs", []))))

            d = await call("self_check_list", {}, lambda d: len(d.get("items", [])) > 0)
            if d:
                print("✅ self_check_list-> %d 条自查项" % len(d["items"]))

    print("\n" + "=" * 46)
    print("通过 %d / 失败 %d" % (ok, len(fail)))
    for f in fail:
        print("  ✗", f)
    return 0 if not fail and ok == 5 else 1


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
    print("目标:", url, "\n")
    sys.exit(asyncio.run(main(url)))
