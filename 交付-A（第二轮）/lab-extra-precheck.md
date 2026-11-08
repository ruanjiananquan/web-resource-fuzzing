# lab-extra 预检与部署记录

## 一、环境信息
- 操作系统：Windows（本机 Docker Desktop）
- Docker 版本：Docker version 29.9.2, build a82e528
- 容器基础镜像：`php:8.2-apache`（Apache + PHP 8.2 单镜像）
- 容器内 PHP 版本：PHP 8.2.35 (cli) (built: Nov  5 2026 07:29:05) (NTS)
- 靶场镜像 ID（lab-extra）：IMAGE_ID: d65aad973987
- 镜像源：daocloud（`registry-mirrors: ["https://docker.m.daocloud.io"]`，用于拉取 `php:8.2-apache`）

## 二、部署命令
（在 `02-工作过程/lab-extra` 目录执行）
```bash
docker build -t lab-extra .
docker run -d --name lab-extra -p 127.0.0.1:18081:80 lab-extra
```

## 三、访问与端口
- 端口映射：本机 `127.0.0.1:18081` → 容器 `80`
- 靶场入口：`http://127.0.0.1:18081/lab-extra/`
- 停止/恢复：`docker stop lab-extra` / `docker start lab-extra`

## 四、预检结果（2026-11-08）
== 首页 ==
home: HTTP 200
== 8 个目标文件 ==
materials.txt: HTTP 200
course.html: HTTP 200
downloads.txt: HTTP 200
notice.html: HTTP 200
help.txt: HTTP 200
contact.html: HTTP 200
legacy-console.html: HTTP 200
maintenance-2024.txt: HTTP 200
== 3 个不存在路径（应为 404） ==
nope1: HTTP 404
nope2: HTTP 404
nope3: HTTP 404
