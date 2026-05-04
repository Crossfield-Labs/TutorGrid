# TutorGrid Web Console Deployment

目标：

- 保留现有静态站 `https://tutorgrid.indolyn.com`
- 新增控制台站点 `https://console.tutorgrid.indolyn.com`
- 后端入口使用 `https://api-tutorgrid.microindole.me`

## Frontend

前端项目目录：

- `TutorGridFront/`

Cloudflare Pages 建议配置：

- Project name: `tutorgrid-console`
- Production branch: 你的主分支
- Root directory: `TutorGridFront`
- Build command: `yarn build`
- Build output directory: `dist`
- Environment variable `YARN_VERSION`: `1.22.22`
- Environment variable `VITE_API_BASE_URL`: `https://api-tutorgrid.microindole.me`
- Environment variable `VITE_WS_URL`: `wss://api-tutorgrid.microindole.me/ws/orchestrator`
- Environment variable `VITE_DEFAULT_HOME_ROUTE`: `/board`

说明：

- 不给现有 `tutorgrid.indolyn.com` 项目配置 `VITE_DEFAULT_HOME_ROUTE=/board`
- 现有静态站继续保持默认 `/landing` 入口
- 控制台站点单独使用自己的 Pages 项目和自定义域名 `console.tutorgrid.indolyn.com`

## Backend

后端公网域名：

- `api-tutorgrid.microindole.me`

前端将使用：

- REST/SSE: `https://api-tutorgrid.microindole.me`
- WebSocket: `wss://api-tutorgrid.microindole.me/ws/orchestrator`

阿里云服务器上建议用 Nginx 反代到本机服务：

- HTTP API: `127.0.0.1:8000`
- WebSocket orchestrator: `127.0.0.1:3210`

示例 Nginx 配置：

```nginx
server {
    listen 80;
    server_name api-tutorgrid.microindole.me;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api-tutorgrid.microindole.me;

    ssl_certificate /etc/letsencrypt/live/api-tutorgrid.microindole.me/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-tutorgrid.microindole.me/privkey.pem;

    client_max_body_size 50m;

    location /ws/orchestrator {
        proxy_pass http://127.0.0.1:3210/ws/orchestrator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backend CORS

后端至少允许以下 Origin：

- `https://console.tutorgrid.indolyn.com`

如果保留本地调试，也可以同时允许：

- `http://localhost:4399`
- `http://127.0.0.1:4399`

## DNS

需要配置的记录：

- `console.tutorgrid.indolyn.com` 指向 Cloudflare Pages
- `api-tutorgrid.microindole.me` 指向阿里云服务器公网 IP

## Verification

完成部署后至少验证：

1. 打开 `https://console.tutorgrid.indolyn.com` 后默认进入 `/board`
2. 浏览器 Network 中 `/api/workspaces` 请求命中 `https://api-tutorgrid.microindole.me`
3. 浏览器中 WebSocket 连接目标为 `wss://api-tutorgrid.microindole.me/ws/orchestrator`
4. 刷新 `board`、`tasks/:taskId`、`hyperdoc/:id` 页面不出现 404
5. 现有 `https://tutorgrid.indolyn.com` 仍保持原来的 `/landing` 站点行为
