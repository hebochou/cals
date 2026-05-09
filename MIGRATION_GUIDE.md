# CALS 应用架构迁移说明文档

## 1. 新文件结构与模块职责
由于早期单文件与大模块职责过于集中，为遵循“单一职责原则 (SRP)”，已对代码进行了进一步模块化重构。当前结构将职责按层次拆分在 `cals_app` 包内：

```text
cals/
│
├── cals_app/                          # 核心应用包
│   ├── __init__.py                    # 应用工厂 (create_app)，注册所有 Blueprint
│   ├── __main__.py                    # 支持 `python -m cals_app` 启动
│   ├── core/                          # 核心依赖
│   │   ├── db.py                      # 数据库连接与配置加载
│   │   └── security.py                # 鉴权装饰器、当前用户、角色判断
│   ├── utils/                         # 工具层
│   │   └── helpers.py                 # 类型转换、时间处理、HTML过滤、打乱算法等纯函数
│   ├── services/                      # 业务逻辑服务层
│   │   ├── logic.py                   # 兼容层，对外保留原服务导入入口
│   │   └── student/                   # 学生端相关业务能力
│   │       ├── accounts.py            # 用户查询、密码校验、默认用户初始化
│   │       ├── favorites.py           # 收藏数据访问
│   │       ├── questions.py           # 题目加载、标签与答案处理
│   │       ├── attempts.py            # 作答记录读写
│   │       ├── mistakes.py            # 错题记录读写
│   │       ├── recommendations.py     # 智能推荐元数据与选题逻辑
│   │       ├── evaluation.py          # 编程题判题/编译运行辅助
│   │       └── analytics.py           # 统计分析与辅助聚合
│   └── routes/                        # 路由控制层 (Controllers)
│       ├── auth.py                    # 认证相关的路由 (登录/登出)
│       ├── admin.py                   # 管理端路由
│       └── student/                   # 学生端路由包
│           ├── blueprint.py           # student_bp 与共享缓存
│           ├── common.py              # 分页、筛选、状态集公共辅助
│           ├── home.py                # 首页与统计接口
│           ├── question_bank.py       # 题库列表与详情
│           ├── favorites.py           # 收藏页与收藏切换
│           ├── mistakes.py            # 错题本列表与移除
│           ├── practice.py            # 练习页与样例运行
│           ├── practice_api.py        # 练习相关 AJAX/JSON 接口
│           └── health.py              # 数据库健康检查接口
│
├── run.py                             # 项目启动入口点
├── README_split.md                    # 本次拆分结构补充说明
├── test_utils.py                      # 现有工具函数测试文件
└── app.py                             # 旧单体入口，现已由包结构替代
```

## 2. 主要变更点
- **引入应用工厂 (App Factory)**：采用 `create_app()` 创建应用，避免直接在全局实例化 `app` 带来的耦合和循环依赖问题。
- **使用 Blueprints (蓝图)**：路由使用 `auth_bp`、`student_bp`、`admin_bp` 注册，保持模块边界清晰。
- **学生端路由细分**：原学生端大路由已拆为 `routes/student/` 包，按首页、题库、收藏、错题本、练习、练习接口、健康检查等职责拆分。
- **学生端服务细分**：原集中在 `services/logic.py` 的学生端逻辑已拆到 `services/student/` 包，按账户、题目、收藏、作答、错题、推荐、评测、统计等职责划分。
- **兼容旧导入路径**：`cals_app.services.logic` 目前保留为兼容层，对外继续导出原有公有 API，降低调用方改动成本。
- **环境变量**：`load_dotenv()` 仍在 `create_app` 启动阶段加载，原始 `CALS_DB_*` 等逻辑保持不变。

## 3. 启动方式
以前的启动方式可能是 `flask run` 或 `python app.py`。
由于入口迁移，现在请使用以下命令启动：
```bash
python run.py
```
*(如果是生产环境，请配置 WSGI 服务器指向 `run:app`)*

## 4. 兼容与回滚说明
- 当前 `create_app()` 中仍通过 `from cals_app.routes.student import student_bp` 导入学生端蓝图，因此 Flask 注册路径未发生变化。
- 当前 `cals_app.services.logic` 仍可继续被 `auth.py`、`admin.py` 及其它旧调用方导入。
- 如果后续需要回滚，可优先从 Git 历史或本地备份中恢复拆分前的 `routes/student.py` 与 `services/logic.py` 实现；数据库结构、模板 `templates/` 与静态资源 `static/` 未因本次拆分发生结构性变化。

---
*当前迁移文档已同步到最新 student 路由包与 student 服务包结构，旧有学生端 URL 与蓝图名称保持不变。*
