
### 🔐 Secrets 配置说明

| Secret 名称   | 是否必填 | 说明                                                        |
|---------------|----------|-------------------------------------------------------------|
| COOKIE        | ✅ 必填  | Friday 登录 Cookie，格式 `PHPSESSID=xxx; user_id=yyy`       |
| EMAIL         | ❌ 可选  | 通知用备注名，可随意填写                                    |
| GH_TOKEN      | ❌ 可选  | GitHub(classic) token，用于 Cookie 刷新后自动回写，以 `ghp_` 开头 |
| NODE_LINK     | ❌ 可选  | 代理链接（vless/vmess/trojan/hysteria2/tuic/anytls/socks5 等） |
| TG_BOT_TOKEN  | ❌ 可选  | Telegram Bot Token（用于发送通知，含截图）                  |
| TG_CHAT_ID    | ❌ 可选  | Telegram Chat ID（接收通知的用户或群组 ID）                 |

## ⚠️ 免责声明

* 本程序仅供学习了解，非盈利目的。
* 遵守部署服务器所在地、所在国家和用户所在国家的法律法规，作者不对使用者任何不当行为负责。
