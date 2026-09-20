## 🚀 Friday 自动续期（GitHub Actions，单账号 Cookie 版）

定时登录 [Friday](https://fridaydev.fr/services/) 自动续期免费服务（5 天手动续一次，脚本每天巡检）。

### 🔐 Secrets 配置说明

| Secret 名称   | 是否必填 | 说明                                                        |
|---------------|----------|-------------------------------------------------------------|
| COOKIE        | ✅ 必填  | Friday 登录 Cookie，格式 `PHPSESSID=xxx; user_id=yyy`       |
| EMAIL         | ❌ 可选  | 通知用备注名，可随意填写                                    |
| GH_TOKEN      | ❌ 可选  | GitHub(classic) token，用于 Cookie 刷新后自动回写，以 `ghp_` 开头 |
| NODE_LINK     | ❌ 可选  | 代理链接（vless/vmess/trojan/hysteria2/tuic/anytls/socks5 等） |
| TG_BOT_TOKEN  | ❌ 可选  | Telegram Bot Token（用于发送通知，含截图）                  |
| TG_CHAT_ID    | ❌ 可选  | Telegram Chat ID（接收通知的用户或群组 ID）                 |

> * Cookie 有效期约 30 天：脚本每次跑通会自动回写最新串；`user_id` 剩余不足 3 天会 TG 预警；彻底失效时 TG 会告警"Cookie 已失效"，需手动重拷。
> * 账密备用登录为二期扩展位，MVP 仅 Cookie 登录。

━━━━━━━━━━━━━━━━━━━━━━

## 部署步骤

1. 新建仓库（建议名 `Friday-Renew`），把 `app.py`、`.github/workflows/renew.yml`、`README.md` 推上去，在 Actions 菜单允许工作流。
2. 在 `Settings` ➡ `Secrets and variables` ➡ `Actions` 里添加上方 Secrets。
3. 去 Actions 手动试运行一次；cron 为每天 UTC 7 点（北京时间 15 点），可按需调整。

### COOKIE 获取

1. 浏览器登录 https://fridaydev.fr/ 。
2. 按 F12 ➡ 应用程序（Application）➡ 左侧 Cookie ➡ `https://fridaydev.fr`。
3. 复制 `PHPSESSID` 和 `user_id` 的值（`user_id` 保持原样，别解码），拼成一行：
   `PHPSESSID=xxx; user_id=yyy`，填入 `COOKIE`。

### 获取 `GH_TOKEN`

参考 Bothosting-Renew：GitHub 头像 ➡ Settings ➡ Developer settings ➡ Personal access tokens(classic) ➡ Generate new token(classic)，权限勾 repo 相关即可。

## 注意事项

* Friday 免费档每 5 天需点一次 `Renouveler gratuitement` 并确认弹窗，脚本已覆盖：可续则点，未到时间（`Renouvelable dans X jours`）则只通知。
* cron 运行时间不一定准时，以 Actions 实际触发为准。

## ⚠️ 免责声明

* 本程序仅供学习了解，非盈利目的。
* 遵守部署服务器所在地、所在国家和用户所在国家的法律法规，作者不对使用者任何不当行为负责。
