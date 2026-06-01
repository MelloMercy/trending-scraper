# 每日热点聚合（国内 6 平台 + 国际 11 源 + 高信号源）

本地部署的小工具：每天定时抓取 17 个热点源（国内：抖音 / 小红书 / B 站 / 知乎 / 36 氪 / 虎嗅；国际：BBC World / Hacker News / The Verge / TechCrunch / NYT World / Ars Technica / Reuters / AP News / Politico / Axios / Semafor），并额外聚合 AI/product/startup 高信号源。它会做**跨平台共识检测**、**LLM 话题聚类**、**Daily Brief** 和 **public feed 导出**，通过 FastAPI + React 前端展示。借鉴 alltop.com 的「多源汇聚」设计，也吸收了 follow-builders 的中心化 feed / prompt 文件 / skill 入口思路。

前端：React 18 + TypeScript + Tailwind + shadcn/ui，源码在 `webui/`，build 后输出到 `static/`。详见 [webui/README.md](webui/README.md)。

## 功能一览

- **17 个热点源**：国内 6（抖音 / 小红书 / B 站 / 知乎 / 36 氪 / 虎嗅）+ 国际 11（BBC World / Hacker News / The Verge / TechCrunch / NYT World / Ars Technica / Reuters / AP News / Politico / Axios / Semafor）。
- **跨平台共识**：规则法找出出现在最多平台的「今日大故事」，并给标题级共识徽章。
- **LLM 话题聚类 + Daily Brief**：DeepSeek 把标题聚成 5–10 个话题，再做跨地区每日简报（可选，配 key 启用；prompt 抽到 `prompts/*.md`，可对话式修改）。
- **高信号源**：follow-builders 的 X / 播客 / 博客 + 本地 `curated_sources.json` 的 RSS / newsletter。
- **Public Feed**：导出 `feeds/*.json` 静态快照，可发布到 GitHub Pages / raw / R2 / S3，客户端免装 Playwright、免配 cookies。
- **公众号发布链路**：每日精华导出 Markdown / HTML / 纯文本 + 公众号草稿 payload；草稿适配器把它推成公众号「草稿」（人工审核后再发）。
- **前端**：网格 / 时间流视图、历史日期回看、Prompt 在线编辑。
- **自动化**：macOS launchd 每日定时「抓取 → 聚类 → 简报 → 导出」；GitHub Actions 做 CI 门禁与 Pages 发布。
- **隐私边界**：密钥 / cookies / 本地数据全部 gitignore，附 `scripts/audit_public_release.py` 发布前扫描。

## 架构

```
trending-scraper/
├── main.py                 # FastAPI 后端 + 前端入口
├── db.py                   # SQLite 存储层
├── aggregator.py           # 跨平台共识聚类（无依赖、规则法）
├── summarizer.py           # DeepSeek 话题聚类（可选，配 key 后启用）
├── briefer.py              # 跨地区 Daily Brief 生成与缓存
├── curated.py              # 高信号源：follow-builders + 本地 RSS/Podcast
├── public_feed.py          # 静态 public feed 构建器（GitHub/R2/S3 友好）
├── publisher.py            # 每日精华发布包（公众号/手动投递友好）
├── wechat_adapter.py       # 公众号草稿适配器（token/封面素材/draft.add）
├── similarity.py           # 字符 bigram + Jaccard 相似度
├── config.py               # 运行时配置加载器（含 schema）
├── config.example.json     # 配置模板（实际配置在 config.json，git 忽略）
├── scrape_daily.py         # 给定时任务调用的抓取入口
├── run_daily.sh            # launchd / cron 包装脚本（带日志）
├── prompts/                # 可对话修改的 LLM prompt markdown 文件
├── feeds/                  # `scripts/export_public_feed.py` 生成的静态 JSON
├── publish/                # `scripts/export_publish_bundle.py` 生成的每日精华稿
├── tests/                  # unittest（feed schema / 上传计划 / 公众号适配器）
├── .github/workflows/      # validate-feed（CI 门禁）+ publish-pages + sync-storage
├── scripts/                # 启动 / 导出 / 发布 / 审计脚本
│   ├── start.sh            # 一键启动 web 服务（:11001）
│   ├── export_public_feed.py     # 导出 feeds/*.json
│   ├── export_publish_bundle.py  # 导出 publish/ 每日精华
│   ├── publish_feed.py     # 发布 feeds → git(Pages/raw) / R2 / S3
│   ├── publish_wechat_draft.py   # 把草稿 payload 推成公众号草稿
│   ├── validate_feed.py    # public feed schema 校验（CI 复用）
│   └── audit_public_release.py   # 公开发布前密钥扫描
├── docs/                   # publishing / 发布清单 / follow-builders 适配说明
├── SKILL.md                # agent/onboarding 操作入口
├── scrapers/
│   ├── base.py             # Playwright 浏览器上下文（反检测配置）
│   ├── douyin.py           # 抖音：API 优先 + Playwright 兜底
│   ├── xiaohongshu.py      # 小红书：双模式（cookies → 热搜榜 / 无 cookies → 发现页热门）
│   ├── bilibili.py         # B 站：公开 API
│   ├── zhihu.py            # 知乎：移动端 API
│   ├── kr36.py             # 36 氪：Playwright 渲染 hot-list/catalog
│   └── huxiu.py            # 虎嗅：api-article.huxiu.com 公开 JSON 接口
├── xhs_login.py            # 交互式登录小红书 → 自动保存 cookies
├── static/index.html       # 单页前端
├── launchd/
│   └── com.local.trending-scraper.plist   # macOS launchd 定时配置
├── data/                   # SQLite 库、cookies、日志、wechat_token.json
├── requirements.txt          # 运行依赖
└── requirements-publish.txt  # 可选：boto3（仅 R2/S3 上传需要）
```

## 快速开始

```bash
cd "trending-scraper"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cd webui
npm install
npm run build
cd ..

uvicorn main:app --reload --port 11001
```

打开 http://localhost:11001 ，点右上角「⟳ 刷新」做一次首抓。

本机已有一键启动脚本：

```bash
bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"
# dev 热重载
RELOAD=1 bash "/Users/mercy/projects/auto scripts/trending-scraper/scripts/start.sh"
```

> 依赖：运行只需 `requirements.txt`。只有要用 `scripts/publish_feed.py` 上传到 R2/S3 时，才额外 `pip install -r requirements-publish.txt`（boto3）。前端构建需要 Node 20+。

## 平台一览

| 平台 | 抓取方式 | 速度 | 数据完整度 |
|------|---------|-----|-----------|
| 抖音 | 公开 API + Playwright 兜底 | <1s | 50 条 + 热度值 |
| 小红书 | 默认抓发现页热门 / 配 cookies 抓真热搜榜 | ~20s | 24 条（无 cookies） |
| B 站 | 公开 API | <1s | 30 条 + 播放量 |
| 知乎 | 移动端 API | <1s | 30 条 + 热度值 |
| 36 氪 | Playwright 渲染 | ~3s | 20 条 |
| 虎嗅 | `api-article.huxiu.com` 公开 JSON | <1s | 22 条 + 发布时间 |

> ⚠️ 小红书的真正「热搜榜」必须登录后才能看到。当前默认抓的是发现页内容，标签会自动显示为「小红书热门笔记」。配置 cookies 后才会切换到「小红书热搜榜」（见下文）。

## 定时任务（macOS launchd）

已配置每天上午 8:00 自动跑。job label: `com.local.trending-scraper`。

```bash
# 查看是否已加载
launchctl list | grep trending-scraper

# 查看下次触发 / 上次退出码
launchctl print "gui/$(id -u)/com.local.trending-scraper"

# 手动触发一次（用来排错）
launchctl kickstart "gui/$(id -u)/com.local.trending-scraper"

# 查看日志
tail -f data/cron.log              # 业务日志
tail -f data/launchd.out.log       # launchd 标准输出
tail -f data/launchd.err.log       # launchd 错误输出

# 卸载（停止定时）
launchctl bootout "gui/$(id -u)/com.local.trending-scraper"

# 重新装载
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.local.trending-scraper.plist
```

要改运行时间：编辑 `launchd/com.local.trending-scraper.plist` 里的 `StartCalendarInterval.Hour/Minute`，重新拷贝到 `~/Library/LaunchAgents/` 后 `launchctl bootout` + `bootstrap`。

## 配置系统

运行时配置存在 `config.json`（gitignore），通过 API 读写。

```bash
# 看当前配置 + schema
curl -s http://localhost:11001/api/config | jq

# 更新某个字段（其他字段保持不变）
curl -X POST -H "Content-Type: application/json" \
  -d '{"schedule_hour": 9}' \
  http://localhost:11001/api/config
```

可配置字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `deepseek_api_key` | string (secret) | "" | DeepSeek 话题聚类 + Daily Brief |
| `xhs_cookies_path` | string | `data/xhs_cookies.json` | 小红书登录态文件路径 |
| `schedule_hour` | int 0-23 | 8 | （未来）UI 设置定时小时 |
| `schedule_minute` | int 0-59 | 0 | （未来）UI 设置定时分钟 |
| `enabled_platforms` | array | 全部 17 个 | （未来）UI 开关单个平台 |
| `wechat_appid` | string | "" | 公众号 AppID（草稿适配器用） |
| `wechat_appsecret` | string (secret) | "" | 公众号 AppSecret（`/api/config` 里遮罩） |

> 当前 `schedule_hour/minute` 只是配置位，**不会**自动改 launchd plist——改时间还是要手动改 plist 文件。把它放在 schema 里是为以后做「web 端改定时」做准备。
>
> `wechat_*` 存在 `config.json`（gitignore），也可被环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET` 覆盖。详见[环境变量](#环境变量)。

## 环境变量

除 `config.json` 外，少量行为可由环境变量控制（CI / 一次性运行友好）：

| 变量 | 用途 | 默认 / 示例 |
|------|------|------------|
| `PORT` | `scripts/start.sh` 监听端口 | `11001` |
| `RELOAD` | `start.sh` 开 uvicorn `--reload` | `0` |
| `DEEPSEEK_MODEL` | 覆盖聚类/简报模型 | `deepseek-v4-flash`（可设 `deepseek-v4-pro`） |
| `WECHAT_APPID` / `WECHAT_APPSECRET` | 公众号凭据（覆盖 `config.json`） | — |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_REGION` / `S3_KEY_PREFIX` | `publish_feed.py` 上传到 R2/S3（`R2_*` / `AWS_*` 别名也认） | R2 region 用 `auto` |
| `PUBLIC_FEED_BASE_URL` | 上传后打印结果 URL 用 | `https://cdn.example.com` |

> secret 类变量（AppSecret、S3 secret key）只从环境/`config.json`/仓库 secret 读取，**绝不写进代码或 commit**；`publish_feed.py` 的 secret key 只走环境变量、不进命令行参数。完整对接见 [docs/publishing.md](docs/publishing.md)。

## 公开发布前检查

这个项目可以公开到 GitHub，但本机运行态不能提交。发布前先跑：

```bash
.venv/bin/python scripts/audit_public_release.py
```

它只报告文件路径和检测规则，不打印疑似密钥值。`NOTE local-only present: config.json/data` 是正常的，表示本机文件存在但已被忽略。
完整清单见 [docs/public-release-checklist.md](docs/public-release-checklist.md)。

## 让小红书抓真热搜榜（一行命令）

```bash
.venv/bin/python xhs_login.py
```

会自动打开一个 Chromium 窗口，你扫码登录后脚本会**自动检测并保存** cookies 到 `data/xhs_cookies.json`，然后退出。下次抓取生效，UI 标签也会自动变成「小红书热搜榜」。

> cookies 一般能用几周到几个月，过期了重新跑一次 `xhs_login.py` 即可。

## 历史日期回看

每个平台卡片右上角的下拉框列出所有可用的日期快照，切换后该卡片就显示那天的数据。今日数据会标注「· 今日」。如果某天的数据是过期的（比如断网那天没抓到），其他天数据照样能看。

## 跨平台聚合（alltop 风格）

抓取完成后，前端会自动拉一次 `/api/aggregate/today`，得到：

### 🥇 今日大故事（Big Story）
顶部 hero 卡片，自动挑出**出现在最多平台**的话题，列出每个平台的原标题和原链接。如果今天没有跨平台话题，这块就空着。

### 📑 今日话题（Threads）— 需要 DeepSeek
让 DeepSeek 把所有标题语义聚成 5-10 个话题，每个话题有名称 + 总结 + 关联标题。**没配 key 时这块显示「配置 DeepSeek 后启用」的提示**。

启用方式：
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"deepseek_api_key": "sk-..."}' \
  http://localhost:11001/api/config
```

刷新页面即可看到话题。结果按 `snapshot_date` 缓存在 `summary_cache` 表里，同一天不会重复调用。
想强制重跑：`GET /api/aggregate/today?force_llm=true`。

> 💡 模型默认 `deepseek-v4-flash`（V4 代，每天成本 < $0.001）。想用更强的 `deepseek-v4-pro` 时，设 `DEEPSEEK_MODEL` 环境变量覆盖即可。

### 🔥 共识徽章
每个平台卡片里，如果某条标题与其他平台的标题语义重合（字符 bigram Jaccard ≥ 0.40），会在标题后显示 `🔥 N 平台` 徽章。

### 📊 视图切换
顶部右侧「网格 / 时间流」按钮：
- **网格**（默认）：当前区域的平台并排，每列一个平台的榜单
- **时间流**：所有平台合并，按「共识 + 排名」综合得分排序，单列展示。每条显示在哪些平台、各自排名

视图偏好存在 localStorage，下次打开自动恢复。

### 🛰 高信号源（follow-builders 模式）

`高信号` 视图借鉴 `follow-builders`：把“刷 AI builders / 官方博客 / 播客”的信息流单独做成一条高信号通道。

数据来源：

- `follow-builders` 中心化生成的 X / podcast / blog JSON
- 本地 `curated_sources.json` 维护的 RSS、newsletter、podcast 源

接口：

```bash
curl -s http://localhost:11001/api/curated/latest | jq
```

如果上游某个 feed 失败，接口会返回 `status: "partial"` 并带 `errors`，页面会显示 warning，但可用内容仍继续展示。

## Public Feed（中心化 feed 改造）

如果要让别人的客户端“不装 Playwright / 不配 cookies / 不跑 scraper”，可以由一台发布机每天跑完整抓取，然后导出静态 JSON：

```bash
.venv/bin/python scripts/export_public_feed.py
```

输出：

- `feeds/latest.json`
- `feeds/YYYY-MM-DD.json`

不传 `--date` 时会使用最新有数据的快照，避免跨日但新抓取还没跑时生成空 feed。
运行 `scrape_daily.py` 时会在成功抓取后自动导出 public feed。客户端也可以直接读：

```bash
curl -s http://localhost:11001/api/feed/latest | jq
curl -s "http://localhost:11001/api/feed/latest?region=intl" | jq
```

发布方式可以是 GitHub Pages（推荐，干净的 CDN URL）、GitHub raw、R2/S3，或继续由本地 FastAPI 提供 `/api/feed/latest`。一键发布脚本：

```bash
# 提交并推送 feeds/（先跑 audit，只暂存 feeds/，再 commit + push）
.venv/bin/python scripts/publish_feed.py --target git
# 上传到 R2/S3（先 dry-run 看计划，凭据走环境变量，secret 不进 argv）
.venv/bin/python scripts/publish_feed.py --target r2 --dry-run
```

推到 GitHub 后，`.github/workflows/publish-pages.yml` 会校验并把 `feeds/` 发布到
GitHub Pages（`https://<owner>.github.io/<repo>/latest.json`）；`validate-feed.yml`
对每次 push/PR 跑 audit + feed schema 校验 + 单元测试 + 前端构建。完整操作见
[docs/publishing.md](docs/publishing.md)。

## Publish Bundle（公众号素材准备）

如果要把每日精华后续做到公众号，先把 cached Daily Brief 转成可审阅、可复制、可对接 API 的发布包：

```bash
.venv/bin/python scripts/export_publish_bundle.py
# 可选：把公开 feed URL 写进稿件末尾
.venv/bin/python scripts/export_publish_bundle.py --feed-url "https://example.com/feeds/latest.json"
```

输出：

- `publish/YYYY-MM-DD/digest.md`：Markdown 稿，最适合人工审稿和改标题。
- `publish/YYYY-MM-DD/digest.html`：HTML 正文，适合富文本/公众号编辑器工作流。
- `publish/YYYY-MM-DD/digest.txt`：纯文本兜底。
- `publish/YYYY-MM-DD/wechat-draft.json`：后续接公众号草稿 API 的基础 payload。
- `publish/latest.*`：最新一次发布包的快捷副本。

运行 `scrape_daily.py` 时，在 public feed 导出后会自动尝试生成发布包；如果当天还没有可用 Daily Brief，会跳过而不影响抓取。
不传 `--date` 时会使用最新有 cached Daily Brief 的快照。
接口也可以预览当前发布内容：

```bash
curl -s http://localhost:11001/api/publish/latest | jq
```

### 接公众号草稿（draft only）

`publish/latest-wechat-draft.json` 可直接喂给公众号草稿适配器。它只建**草稿**，不群发、不发布——你在公众号后台「草稿箱」里审核后再发：

```bash
# dry-run（默认）：加载草稿、打印计划、列出还差什么
.venv/bin/python scripts/publish_wechat_draft.py
# 真正提交：token → 上传封面为永久素材（thumb_media_id）→ draft/add
.venv/bin/python scripts/publish_wechat_draft.py --cover cover.jpg --submit
```

凭据走 `config.json` 的 `wechat_appid` / `wechat_appsecret`（后者在 `/api/config` 里遮罩），或环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET`。注意 access_token 需要公众号 IP 白名单。完整步骤与坑见 [docs/publishing.md](docs/publishing.md)。

## 测试

纯 stdlib + httpx 的单元测试（无网络、不导入 scraper / Playwright），覆盖 feed schema 校验、上传计划与配置解析、公众号适配器（token 缓存、草稿组装、API 错误处理）：

```bash
.venv/bin/python -m unittest discover -s tests
```

公众号网络调用用 `httpx.MockTransport` 打桩；37 个用例。CI 里也会跑（见下）。

## 持续集成与 GitHub Actions

仓库带三个工作流（`.github/workflows/`）：

- **`validate-feed`** — 每次 push / PR 的门禁，无需 secret：`audit_public_release.py` 扫密钥 → `compileall` → `validate_feed.py` 校验 feed schema → `unittest` → `webui` 的 `npm ci && lint && build`。
- **`publish-pages`** — 当 `feeds/**` 变动（`feeds/README.md` 除外）时，把 `feeds/` 部署到 GitHub Pages，得到 `https://mellomercy.github.io/trending-scraper/latest.json`。`configure-pages` 设了 `enablement: true`，首次运行会自动开启 Pages（若 token 权限不足，到仓库 Settings → Pages 手动开一次即可）。
- **`sync-storage`** — 可选：`feeds/**` 变动时把 feeds 同步到 R2/S3，凭据走仓库 secret（`S3_*`）；未设 `S3_BUCKET` 时自动空跑，可安全保留。

本地对应的发布命令见上方 Public Feed 一节与 [docs/publishing.md](docs/publishing.md)。

## Prompt 文件（对话式调风格）

LLM prompt 已从 Python 里抽到 markdown 文件：

- `prompts/cluster-cn.md`
- `prompts/cluster-intl.md`
- `prompts/daily-brief.md`

修改后重新请求：

```bash
curl -s "http://localhost:11001/api/aggregate/today?force_llm=true" | jq
curl -s "http://localhost:11001/api/brief/today?force=true" | jq
```

前端「Prompt」视图也可以直接编辑这三个文件，保存时会校验必需占位符，页面内可触发 CN / INTL 聚类或 Daily Brief 重跑。
这让“摘要更短一点”“语气更像投研简报”“国际内容保留英文标题”这类变化可以通过 UI 或改 prompt 文件完成，并且能被 `git diff` 追踪。

## API 一览

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/platforms` | 平台列表（带当前显示名称） |
| GET | `/api/trending/{platform}` | 最新一天的榜单 |
| GET | `/api/trending/{platform}/history` | 有数据的日期列表 |
| GET | `/api/trending/{platform}/{YYYY-MM-DD}` | 某天的快照 |
| POST | `/api/refresh/{platform}` | 手动抓单平台 |
| POST | `/api/refresh` | 手动并行抓全部 |
| GET | `/api/runs` | 最近抓取的运行日志 |
| GET | `/api/config` | 当前配置 + schema（secrets 已遮罩） |
| POST | `/api/config` | 更新一个或多个配置字段 |
| GET | `/api/aggregate/today` | 跨平台共识 + LLM 话题聚类 |
| GET | `/api/aggregate/today?date=YYYY-MM-DD&force_llm=true` | 指定日期 / 强制重新调用 LLM |
| GET | `/api/brief/today` | 跨地区 Daily Brief |
| GET | `/api/curated/latest` | 高信号源（follow-builders + 本地 RSS/Podcast） |
| GET | `/api/feed/latest` | 可发布的静态 public feed payload |
| GET | `/api/publish/latest` | 公众号/投递友好的每日精华预览 |
| GET | `/api/prompts` | Prompt 文件列表 + 内容 + 占位符校验 |
| GET | `/api/prompts/{prompt_id}` | 单个 prompt 文件 |
| POST | `/api/prompts/{prompt_id}` | 保存 prompt 文件（allowlist + placeholder 校验） |

## 已知问题

- 抖音 API 偶尔加签名/限流 → 已自动回退到 Playwright
- 知乎 web API 现在要登录 → 已改用 `api.zhihu.com` 移动端接口
- 小红书所有热点入口强制登录 → 用「双模式」处理
- Playwright headless 模式遇到滑块验证就废 → 改 `scrapers/base.py` 里 `headless=True` → `False` 调试

## 想加的东西

- [x] ~~DeepSeek 智能摘要~~ → 已实现「今日话题」LLM 聚类
- [x] ~~跨平台共识检测~~ → 已实现 Big Story + 共识徽章
- [x] ~~视图切换~~ → 已实现网格 / 时间流
- [x] ~~高信号源~~ → 已实现 follow-builders + 本地 curated_sources
- [x] ~~Prompt 单文件可改~~ → 已抽到 `prompts/*.md`
- [x] ~~Prompt UI 编辑器~~ → 已实现 `/api/prompts` + 前端 Prompt 视图
- [x] ~~中心化 public feed 导出~~ → 已实现 `/api/feed/latest` + `feeds/*.json`
- [x] ~~每日精华发布包~~ → 已实现 `publish/*.md/html/json` + `/api/publish/latest`
- [x] ~~Skill 形态入口~~ → 已补 `SKILL.md`
- [x] ~~feeds 公开发布（GitHub Pages/raw + R2/S3）~~ → `scripts/publish_feed.py` + GitHub Actions（validate-feed / publish-pages / sync-storage）
- [x] ~~公众号草稿适配器~~ → `wechat_adapter.py` + `scripts/publish_wechat_draft.py`（只建草稿，人工审核后发）
- [ ] 历史折线趋势图（哪些话题连续多天上榜）
- [x] ~~在 launchd 抓取后自动预生成话题聚类~~ → `scrape_daily.py` 抓取后会跑 clustering + brief
- [ ] 加更多平台（微博 / 头条 / 雪球）

## 声明与合理使用

- 本项目是**个人自用**的学习 / 信息聚合工具，抓的是各平台**公开**的热点榜单与页面。
- 请控制频率、尊重各平台 robots 与服务条款；默认每天一次，不要拿它做高频或商业化抓取。
- 抓取内容版权归原平台 / 作者；二次发布（public feed、公众号）请保留来源链接并自行承担合规责任。
- 不抓取、不存储任何登录用户的私人数据；小红书 cookies 仅用于读取你自己账号可见的热搜榜，存于本机 `data/`（已 gitignore）。
- 暂无开源 LICENSE：在他人复用前，请先决定并补一个许可证文件。
