# Galgame百宝盒（NoneBot 版）

参考 [PyuraMazo/astrbot_plugin_galgame_box](https://github.com/PyuraMazo/astrbot_plugin_galgame_box)
重新实现的 NoneBot2 + OneBot v11 插件，独立于 xqq-forwarder，命令统一挂在
**`/shou gal`** 下，与 xqq-forwarder 的 `/shou` 管理命令共存。

## 功能

结合 VNDB、TouchGal、AnimeTrace 三个数据源：

| 功能 | 命令 | 说明 |
| --- | --- | --- |
| 作品查询 | `/shou gal vn <名称>` | 搜索指定作品 |
| 角色查询 | `/shou gal character <名称>` | 搜索指定角色 |
| 厂商查询 | `/shou gal producer <名称>` | 搜索指定厂商及其代表作 |
| ID 查询 | `/shou gal id <VNDB ID>` | 通过 `v`/`c`/`p` 开头的 VNDB ID 直接查询 |
| 今日简讯 | `/shou gal event [月-日]` | 历史上的今天发售的作品与生日角色 |
| 随机作品 | `/shou gal random` | TouchGal 随机获取一部作品 |
| 标签推荐 | `/shou gal recommend <标签...>` | 按一个或多个标签推荐作品 |
| 资源下载 | `/shou gal download <ID/关键词>` | 获取 TouchGal 资源下载链接 |
| 出处识别 | `/shou gal find [图片链接]` | AnimeTrace 角色识别，并尝试在 VNDB 匹配 |
| 每日老婆 | `/shou gal waifu` | 每位用户每天一次，随机抽取 VNDB 女性角色；管理员可 `waifu reroll` 更换或 `waifu set <角色名>` 指定 |
| 每日推送 | 定时任务 | 每天定时向配置的群推送今日简讯 |

搜索类命令（`vn`/`character`/`producer`/`event`/`recommend`/`download`）
可在末尾追加 `limits <N>` 覆盖本次返回条数（上限 50），例如：

```
/shou gal character ムラサメ limits 1
/shou gal vn 千恋万花 limits 3
```

### 每日老婆

- `/shou gal waifu`：所有用户可用，每位用户每天只能抽取一次；当天再次调用会重复展示今日结果；
- `/shou gal waifu reroll`：仅管理员，重新随机抽取并覆盖今日结果；
- `/shou gal waifu set <角色名或c开头的VNDB ID>`：仅管理员，直接指定今日老婆；
- 只接受 VNDB 性别为女性的角色，随机抽取与管理员指定都会校验；
- 管理员只读取 `admin_ids.json`（不读环境变量），与 x_admin 完全共用；
- 文件格式：`{"version": 2, "admins": [123456789]}`，可由 `/shou admin add/remove`
  维护，或直接编辑文件。
- 每日老婆状态保存在 `GALGAME_DATA_DIR`（默认 `LOCALSTORE_DATA_DIR`，再回退 `data/`）。

与参考项目的差异（适配 NoneBot 文本消息）：

- 结果以文本 + 图片形式返回，不依赖 AstrBot 的 HTML 渲染服务；
- `recommend` 一次返回一批结果，不做“换一个”会话；
- `download` 关键词搜索到多个结果时直接列出候选，使用
  `/shou gal download <TouchGal ID>` 获取资源，不做交互式选择；
- `find` 支持指令参数图片链接、同消息图片或回复图片，不做等待下一张图片的会话。

## 安装

```bash
cd /opt/galgame-box
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

在 NoneBot 入口（如 `bot.py`）中加载插件：

```python
nonebot.load_plugin("galgame_box")
```

需要把项目目录加入 Python 路径（例如软链到 site-packages，或 `pip install -e .`）。

可选：安装 `curl_cffi` 以便 TouchGal 遇到 Cloudflare 反爬时自动降级：

```bash
.venv/bin/pip install curl_cffi
```

## 配置（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `GALGAME_NSFW` | `sfw` | `sfw` 仅全年龄；`all` 允许 NSFW（需要 token） |
| `GALGAME_TOUCHGAL_TOKEN` | 空 | TouchGal 登录 Token（`kun-galgame-patch-moe-token`） |
| `GALGAME_CF_CLEARANCE` | 空 | Cloudflare `cf_clearance` Cookie（可选） |
| `GALGAME_PROXY` | 空 | 仅作用于本插件的代理，如 `http://127.0.0.1:7897` |
| `GALGAME_TLS` | `chrome136` | curl_cffi 的 TLS 指纹 |
| `GALGAME_REQUEST_TIMEOUT` | `30` | 单次请求超时（秒） |
| `GALGAME_REQUEST_RETRIES` | `3` | 请求重试次数 |
| `GALGAME_SEARCH_LIMIT` | `5` | 作品/角色搜索展示条数 |
| `GALGAME_PRODUCER_VNS` | `5` | 厂商查询时每个厂商展示的作品数 |
| `GALGAME_EVENT_RATING` | `75` | 简讯过滤的最低 VNDB 评分 |
| `GALGAME_EVENT_LIMIT` | `10` | 简讯最多展示条数 |
| `GALGAME_CHARACTER_OPTIONS` | `abc` | 角色额外信息：`a`血型 `b`身高体重 `c`性别 `d`真实性别 `e`三围 `f`罩杯 |
| `GALGAME_RECOMMEND_COUNT` | `5` | 推荐一次返回数量 |
| `GALGAME_FIND_RESULTS` | `3` | 每个识别框最多展示的候选角色数 |
| `GALGAME_PUSH_GROUPS` | 空 | 每日推送的群号，逗号或 JSON 数组，如 `111,222` |
| `GALGAME_PUSH_TIME` | `07:00` | 每日推送时间 `HH:MM` |
| `GALGAME_DATA_DIR` | `data/` | 插件状态数据目录（每日老婆等） |

## 与 xqq-forwarder 的共存方式

- 本插件注册 `on_command("shou", rule=<仅 /shou gal 开头>, priority=1, block=True)`，
  只在消息以 `gal` 子命令开头时进入，其他 `/shou` 消息不会被这个匹配器拦截；
- 非 gal 的 `/shou` 子命令会原样放行给 xqq-forwarder 的 `x_admin`（priority=5）；
- 因此两者可以同时加载，互不冲突。

## 测试

```bash
make test
```

测试覆盖配置解析、数据模型、格式化、三个 API 客户端与命令入口。
