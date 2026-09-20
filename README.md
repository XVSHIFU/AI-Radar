# AI 革新雷达

AI 资讯聚合网站，自动收录来源并展示原文标题、简介和链接。当前版本为 v0.1.0。

## 目录

- [功能](#功能)
- [快速开始](#快速开始)
- [本机数据库备份](#本机数据库备份)
- [项目目录](#项目目录)
- [致谢](#致谢)

## 功能

- 自动收录 RSS/Atom，清洗和去重。
- 按时间浏览文章，支持搜索、分类、日期过滤和统计；提供多套主题与手机布局。
- 在后台管理来源、采集故障和文章展示状态。

可选的 pi 研究助手可根据已收录内容回答问题并列出来源。

## 快速开始

需要 Docker（Linux 容器）和 Python 3；以下命令在 Linux 终端执行，Windows 可用 WSL。

### 环境检查

```bash
docker --version
docker compose version
python3 --version
```

### 镜像部署

下载的是启动配置和脚本；应用直接使用已构建的镜像，无需克隆源码。

公开镜像仓库：`crpi-z2yvaep8ppb79obm.cn-hangzhou.personal.cr.aliyuncs.com/ai_radar_spec/ai_radar_docker`。

```bash
curl -fL https://github.com/XVSHIFU/AI-Radar/releases/download/v0.1.0/ai-radar-deploy.zip -o ai-radar-deploy.zip
unzip ai-radar-deploy.zip
cd ai-radar
python3 scripts/pull-release.py
python3 scripts/release.py init --data-root "$PWD/.local-data"
python3 scripts/release.py up --data-root "$PWD/.local-data"
```

访问 `http://127.0.0.1:8080`，后台入口为 `/ingest`。首次初始化生成的管理员口令位于 `.local-data/secrets/admin_token`；`init` 只在新建数据目录时运行。

## 本机数据库备份

```bash
python3 scripts/backup-database.py --data-root "$PWD/.local-data" --output "$PWD/backup/database.dump"
```

## 项目目录

```text
frontend/   网站界面
backend/    API、采集与数据库
agent/      可选研究助手
scripts/    启动与备份脚本
deploy/     容器构建文件
```


## 致谢

本项目复刻于一位朋友的「AI革新雷达」项目，感谢 [@zc-18](https://github.com/zc-18)；可查看[原型](http://101.200.184.201:8000/)。界面设计使用了 [Impeccable](https://impeccable.style/)。

项目原创代码采用 [Apache License 2.0](LICENSE)；第三方字体、图标和依赖见[第三方说明](THIRD_PARTY_NOTICES.md)。
