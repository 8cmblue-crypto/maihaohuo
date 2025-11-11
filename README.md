# 麦好火公司 像素相册（MaiHaoHuo）

麦好火，公司以“创意有温度、互动有趣味”为核心理念，专注把真实的品牌故事和用户互动结合到轻量化的网页应用中。我们热爱用像素风与小游戏化交互，打造更亲近、更高效的传播体验。

## 项目简介
- 前端：`Females/` 目录下的静态网页与交互脚本（含页面、样式、素材、小游戏与爆料上传入口）。
- 后端：`backend/app/main.py` 基于 FastAPI 的接口服务，用于爆料上传、审核与删除。
- 数据与素材：`uploads/` 保存用户上传内容；静态素材均在 `Females/` 内。

当前默认密码：`123`
- 上传入口（爆料上传）：输入密码 `123` 后可打开上传弹窗。
- 管理入口（审核/删除）：输入密码 `123` 后可进行管理操作。
- 后端接口通过请求头 `X-Report-Pwd: 123` 进行校验。

## 主要特性
- 轻量前端，无需复杂构建，开箱即用。
- 爆料上传、审核、删除全流程闭环，后端强制密码校验。
- 像素风界面与小游戏式交互，增强趣味与记忆点。
- 简单部署，适合 GitHub Pages + 后端服务的组合方案。

## 快速开始（本地）
1. 启动后端（需要 Python 3.11+）：
   ```bash
   python3 -m pip install fastapi uvicorn[standard] python-multipart
   python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8081 --reload
   ```
2. 启动前端静态服务（任选其一）：
   ```bash
   # 方案 A：使用 Python 内置
   python3 -m http.server 8080

   # 方案 B：使用任意静态服务器（如 http-server）
   npx http-server -p 8080
   ```
3. 访问前端：打开 `http://localhost:8080/Females/index.html`
4. 使用密码 `123` 进入“爆料上传”与“管理”入口；所有与爆料相关的接口均需在请求头携带 `X-Report-Pwd: 123`。

## 接口一览（摘要）
- `POST /api/reports/submit`（上传）
  - 头：`X-Report-Pwd: 123`
  - 功能：提交爆料内容与附件。
- `POST /api/reports/audit`（审核）
  - 头：`X-Report-Pwd: 123`
  - 功能：审核或取消审核某条爆料。
- `POST /api/reports/delete`（删除）
  - 头：`X-Report-Pwd: 123`
  - 功能：删除指定爆料记录。

## 目录结构（简版）
```
├── Females/                 # 前端静态站点（页面、脚本、样式、素材）
│   ├── index.html           # 入口页面
│   ├── reports.js           # 爆料上传/管理交互逻辑
│   ├── reports.css          # 爆料相关样式
│   ├── styles.css           # 全局样式
│   ├── main.js              # 入口脚本（若有）
│   ├── npc-game.js          # 小游戏与交互
│   └── ...                  # 其他页面与素材
├── backend/
│   └── app/
│       └── main.py          # FastAPI 主应用（密码与接口逻辑）
├── uploads/                 # 用户上传内容（生产环境建议不入库）
└── README.md                # 项目说明与使用指引
```



## 致谢
感谢每一位参与和支持麦好火的伙伴。让创意与互动更有温度，是我们一直的追求。
