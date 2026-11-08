# 任务 A 交付说明（A 视角）

> 截止：2026-11-08 12:00。本说明随交付物一并分发给组员。

## 一、已生成的交付物（位置）
- 靶场源码：`02-工作过程/lab-extra/`（index.php + 8 个目标文件 + Dockerfile）
- 冻结压缩包：`02-工作过程/lab-extra-frozen.tar.gz`
- 冻结哈希：`02-工作过程/lab-extra-frozen.sha256`
  - SHA-256：`8cec2794298c52d8b37e75409ea1f0e4055924ed015394b52e438153068394b6`
- 完整目标清单（A/E 双保管）：`02-工作过程/lab-extra-targets.txt`
- 预检脚本：`02-工作过程/lab-extra-precheck.sh`
- 首页 HTML（交 B）：`02-工作过程/交付-A/lab-extra-home.html`
- 环境版本与部署截图：见 `02-工作过程/lab-extra-precheck.md`（A 跑完容器后补充）

## 二、给 B（页面线索采集）
- 仅提供 `lab-extra-home.html`（首页）+ 其中的公开材料（六个业务词）。
- **严禁**向 B 提供 8 个目标路径、目标清单、资源设计表。

## 三、给 D（排序实现与对照扫描）
- 提供 `lab-extra-frozen.tar.gz` + `lab-extra-frozen.sha256` + `Dockerfile`（均在 `lab-extra/` 内）。
- D 在本机解包后部署同一环境：
  ```bash
  tar -xzf lab-extra-frozen.tar.gz
  cd lab-extra
  docker build -t lab-extra .
  docker run -d --name lab-extra -p 127.0.0.1:18081:80 lab-extra
  ```
- 扫描目标固定：`http://127.0.0.1:18081/lab-extra/FUZZ`（参数见主清单）。

## 四、给 E（扩展对照与核验）
- 提供 `lab-extra-targets.txt`（目标清单）+ 冻结包（同 D）。
- E 在本机部署同样容器，独立 GET 核验 8 个目标均为 200 且正文含对应标记。

## 五、关于"同一台电脑"的处理
各自在本机部署**同一冻结包**即可保证环境、文件、路径完全一致，扫描结果跨机器可比，无需物理同机。详见《任务A补充实验-操作清单.md》"关于同一台电脑"一节。
