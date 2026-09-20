# 脚本目录

日常使用只需要少数入口：

| 用途 | 入口 |
| --- | --- |
| 从镜像安装或更新 | `pull-release.py`、`release.py` |
| 在本机备份数据库 | `backup-database.py` |
| 本地抓取后同步到服务器 | `collect-sync.py`，配置样例为 `collect-sync.example.json`；`import-collected.py` 由同步程序在服务器端调用 |
| 开发验证 | `verify-linux.sh`（CI 同样调用）、`verify.ps1`；`freeze-openapi.py` 和 `check-*.py` 提供专项检查 |

其余脚本服务于已有部署的定时任务、数据恢复、隔离运行环境、来源探测或研究质量验证。它们不会因放在此目录中就自动运行；需要时查看文件开头说明及调用方。`install-*.sh` 会修改运行环境，只应由部署维护者执行。
