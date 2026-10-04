# Git 与版本管理约定

> 面向在本仓库工作的协作者与 Agent。
> 这些是**约定**不是枷锁——目标是让版本历史对使用者可读、可查、可追溯。
> 全文只有一条硬性红线：**敏感信息不进 Git**（见最后一节）。

---

## 一、提交信息的格式

建议格式：`type(scope): 描述`

常用 type（够用就行，不必为此纠结）：

| type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(crawlers): 新增 58 同城 Adapter` |
| `fix` | 修复缺陷 | `fix(ui): 缺失价格不再显示为 ￥0` |
| `docs` | 文档 | `docs: 更新数据源状态表` |
| `test` | 测试 | `test(dedup): 补充跨平台重复用例` |
| `refactor` | 重构（不改变行为） | `refactor(search): 拆分筛选条件构造逻辑` |
| `chore` | 杂务 / 依赖 / 发布 | `chore(release): v0.2.0` |
| `ci` | CI 配置 | `ci: 后端测试增加依赖缓存` |

要点：

- 描述**可以用中文**，写清楚"改了什么、为什么"比格式正确更重要
- 一次提交做一件事；小步提交好过一个巨型 commit
- `scope` 可选，用着顺手的别名即可（如 `crawlers` / `ui` / `api` / `search`）
- 提交正文（`-m` 第二段）用来写原因、影响范围、已知副作用

## 二、分支

- 主线是 `main`，个人开发**可以直接提交到 main**
- 有风险的改造（大重构、实验性功能）建议开分支：`feat/xxx`、`fix/xxx`，完成并过 CI 后合回
- 分支名不需要严格规范，能看懂就行

## 三、版本号与标签（重点）

版本号用语义化版本：`v主版本.次版本.补丁`

**当前处于 0.x 阶段**，规则简化如下：

- 新增功能 → 次版本 +1：`v0.1.0 → v0.2.0`
- 修 bug / 小调整 → 补丁 +1：`v0.2.0 → v0.2.1`
- 破坏性变更在 0.x 阶段直接进次版本，并在 CHANGELOG 里明确标注

到 1.0 之后再按标准 semver 严格区分。

**打标签一律用 annotated tag**，说明里写清这个版本包含什么：

```bash
git tag -a v0.2.0 -m "v0.2.0 - 一句话概括这个版本

- 新增: xxx
- 修复: xxx
- 数据源状态: 豆瓣 ✅ / 贝壳 ✅ / 闲鱼 🔐 / 小红书 🔐"
git push origin v0.2.0
```

**数据源状态是本项目的核心事实**。只要任一平台的状态
（✅ 可用 / ⚠️ 部分可用 / 🔐 需登录 / ❌ 不可用）发生变化，
就要如实更新到 tag 说明与 CHANGELOG——不要沿用旧状态。

## 四、CHANGELOG 的维护

`CHANGELOG.md` 采用 Keep a Changelog 风格：

- **平时开发**：新改动追加到顶部 `[Unreleased]` 段落，随提交一起进仓库
- **发布版本**：把 `[Unreleased]` 的内容移到新版本号下，附上日期
- **写法以"使用者能感知的变化"为准**：
  - 好：`修复：豆瓣时间列解析错误导致发布时间恒为当前时间`
  - 差：`修改 douban.py 第 42 行`（内部细节，多个小修合并成一条即可）
- 数据源实测状态变化属于必记内容
- 不要为了好看编造条目；没发生的事不写

## 五、发布一个新版本的流程

1. 确认测试全过、CI 绿灯（见下一节自检清单）
2. 更新 CHANGELOG：`[Unreleased]` → `[vX.Y.Z] - YYYY-MM-DD`
3. 提交：`git commit -m "chore(release): vX.Y.Z"`
4. 打标签并推送：`git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`
5. 建 GitHub Release（与 tag 说明保持一致即可）：
   ```bash
   gh release create vX.Y.Z --verify-tag --notes-from-tag
   # 需要更详细时用 --notes-file 引用 CHANGELOG 对应段落
   ```
6. 顺手看一眼仓库 Releases 页面显示正常

## 六、推送前后自检（成本很低，建议每次都做）

```bash
# 1) 离线测试（快，不联网、不触发平台风控）
python tests/test_parsers.py && python tests/test_dedup_risk.py

# 2) 敏感信息扫描（唯一的硬性检查，见下一节）
git status --short
git grep -iE "(cookie|token|api[_-]?key|secret|password)\s*[:=]\s*['\"][A-Za-z0-9_%-]{16,}" -- ":!*.example"
git log --all --oneline -- .env | head -3        # 应为空

# 3) 推送后确认 CI
gh run list --limit 2
```

CI 红了就修——不要留红灯过夜。不建议用 force push 掩盖问题
（当前是单人项目影响小，但保持好习惯；确需 force push 时先想清楚有没有人会受影响）。

## 七、红线（全文唯一不可灵活的部分）

- **Cookie / Token / API Key / 密码 / `.env` / `data/*.db` —— 永远不进 Git，包括历史**
- 万一误提交了密钥：改 `.gitignore` 只是第一步。已推送的密钥视为已泄漏 →
  先去对应平台重置/吊销该凭据，再处理历史清理
- 不要在代码、文档、截图、日志里粘贴真实 Cookie 或 Token（文档写变量名，如 `DOUBAN_COOKIE`）
- 采集行为本身：不绕过验证码、不做签名逆向、不访问需要未授权权限的内容——
  这是本项目的产品边界，版本说明里也要保持如实描述

---

## 附：给接手仓库的 Agent 的一段话

你在管理的是一个人的本地租房工具（正在逐步打磨）。
版本历史的第一读者是**未来的使用者本人**——他半年后回来看 `git log` 和 CHANGELOG，
要能快速明白"哪个版本能干什么、数据源状态如何、为什么当时那样改"。

所以：格式是为了可读性服务的，不要为了格式而格式；
拿不准的时候，选择"对未来的自己更有信息量"的那种写法。

常用命令速查：

```bash
git log --oneline -10                    # 最近提交
git tag -l --sort=-v:refname             # 版本列表（新→旧）
gh run list --limit 3                    # CI 状态
gh release list                          # 已发布版本
git status --short                       # 工作区状态
```
