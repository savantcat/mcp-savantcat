# savantcat-answers-mcp

> **把中国 AI 客服国标 GB/T 47746—2026 变成 Agent 能直接调用的工具。**
> An MCP server for China's **GB/T 47746—2026** AI customer-service compliance standard.

[![MCP](https://img.shields.io/badge/MCP-2025--06--18-blue)](https://modelcontextprotocol.io)
[![Protocol](https://img.shields.io/badge/transport-streamable--http-green)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Endpoint](https://img.shields.io/badge/endpoint-live-brightgreen)](https://savantcat.cn/mcp)
[![API Key](https://img.shields.io/badge/API%20Key-不需要-success)](https://savantcat.cn/mcp)
[![Tools](https://img.shields.io/badge/tools-5-orange)](https://savantcat.cn/mcp)

### 为什么值得接

**2026-09-01 已经实施了。** 只要你在用 AI 客服，这份标准的合规问题就绕不过去 ——
而标准原文 40 多页、条款密度极高，「AI 客服怎么算达标」散落在 4~9 章里，人工翻效率极低。

这个 MCP 把**条款级问答**做成工具：答案全部标注条款出处，Agent 一问即得，**不用装、不用 Key、公开只读**。

---

## 这是什么

`GB/T 47746—2026`《顾客联络服务 人工与智能客户服务协同要求》是中国**第一个**聚焦「人工客服与智能客服协同机制」的国家标准，**2026-05-25 发布、2026-09-01 实施**。

这个 MCP Server 把该标准的合规问答做成了 **Agent 可以直接调用的工具**。任何支持 MCP 的客户端（Claude Desktop、Cursor、Cline、自研 Agent）连上就能问：

- 「AI 客服怎么过国标？」
- 「哪 5 类场景必须自动转人工？」
- 「53 条强制自查项从哪来？」
- 「上线要走备案还是登记？」

**所有答案都标注标准条款依据。**

## 直接用（无需安装）

已部署在公网，公开只读、不需要 API Key：

```
https://savantcat.cn/mcp
```

传输方式 `streamable-http`，无状态。接入文档：**https://savantcat.cn/mcp/**

## 可用工具

| 工具 | 作用 |
|---|---|
| `list_questions` | 列出全部合规问答（可按集群过滤） |
| `search_answers` | 按关键词检索问答，返回最相关的 N 条 |
| `get_answer` | 取单条完整答案（正文 + 要点 + 条款依据 + 常见追问） |
| `self_check_list` | 取国标自查清单，企业对照自查 |
| `standard_info` | 标准元信息（发布/实施日期、归口、篇幅、核心要求） |

## 接入

### Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "savantcat-answers": {
      "url": "https://savantcat.cn/mcp"
    }
  }
}
```

### Cursor

编辑 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "savantcat-answers": {
      "url": "https://savantcat.cn/mcp"
    }
  }
}
```

### Hermes Agent

```yaml
mcp_servers:
  savantcat-answers:
    connect_timeout: 20
    enabled: true
    url: https://savantcat.cn/mcp
```

### 任意 MCP 客户端 / 自研 Agent

标准 MCP `streamable-http` 握手即可：

```bash
curl -X POST https://savantcat.cn/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2025-06-18","capabilities":{},
                 "clientInfo":{"name":"my-agent","version":"1.0"}}}'
```

## 自托管

想换成你自己的内容？把 `data/` 里的 JSON 替换掉即可。

```bash
pip install -r requirements.txt

# 本地 stdio 通道（给桌面客户端用）
python server.py

# 远程 HTTP 通道
python server.py --transport http --host 0.0.0.0 --port 8765 --stateless

# 自检：不走协议，直接打全部工具
python server.py --selftest
```

### Docker

```bash
docker build -t savantcat-answers-mcp .
docker run -p 8765:8765 savantcat-answers-mcp --transport http --host 0.0.0.0 --port 8765 --stateless
```

> **公网部署提示**：MCP SDK 默认开启 DNS-rebinding 防护，只放行 `localhost`，用真实域名访问会得到 `421 Invalid Host header`。本项目通过 `TransportSecuritySettings` 把你的域名加入白名单（**保留防护**，而不是关掉），见 `server.py` 的 `DEFAULT_ALLOWED_HOSTS`——部署前记得改成你自己的域名。

## 数据

`data/` 下三个文件：

```
data/answers.json   12 条原子问答全文（含 facts / sources / faqs / body_md）
data/index.json     轻量索引（列表与检索用）
data/meta.json      集群元信息
```

每个原子问答都带 `sources` 字段，标注条款出处。

## 项目结构

```
server.py             MCP Server 主体（双通道 stdio / streamable-http）
client_test.py        用官方 SDK 做的全链路测试
data/                 知识库数据
examples/             各客户端配置示例
server.json           MCP Registry 发布清单
Dockerfile
```

## 关于标准

| 项 | 值 |
|---|---|
| 标准号 | `GB/T 47746—2026` |
| 名称 | 顾客联络服务 人工与智能客户服务协同要求 |
| 类型 | 推荐性国家标准（GB/T） |
| 发布 | 2026-05-25 |
| 实施 | 2026-09-01 |
| 发布机构 | 国家市场监督管理总局 / 国家标准化管理委员会 |
| 归口 | SAC/TC 264 |
| 核验渠道 | 国家标准全文公开系统 `openstd.samr.gov.cn` |

**核心要求**：AI 客服不能只看「答得对不对」，还要看「答不了的时候会不会转人工」——有 5 类场景被明确要求自动转人工。

## License

MIT — 见 [LICENSE](LICENSE)。

---

## English

**`savantcat-answers-mcp`** exposes China's national standard **GB/T 47746—2026** (*Customer contact service — Requirements for the collaboration between human and intelligent customer service*, issued 2026-05-25, effective 2026-09-01) as callable MCP tools.

Live endpoint (public, read-only, no API key): `https://savantcat.cn/mcp` · transport: `streamable-http`

Tools: `list_questions` · `search_answers` · `get_answer` · `self_check_list` · `standard_info`

Works with any MCP client. Self-host by replacing the JSON files under `data/`.
