#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Friday(dev.fr) 自动续期（单账号 Cookie 版）
# Secrets：
#   COOKIE（必填，格式 "PHPSESSID=xxx; user_id=yyy"）
#   EMAIL（可选，通知用备注名）
#   全局共用：GH_TOKEN / TG_BOT_TOKEN / TG_CHAT_ID / NODE_LINK(代理，可选)

import os, re, sys, time, json, requests, subprocess
from datetime import datetime
from seleniumbase import SB

GH_TOKEN      = os.environ.get("GH_TOKEN") or ""
TG_CHAT_ID    = os.environ.get("TG_CHAT_ID") or ""
TG_BOT_TOKEN  = os.environ.get("TG_BOT_TOKEN") or ""

BASE_URL      = "https://fridaydev.fr"
SERVICES_URL  = f"{BASE_URL}/services/"
DOMAIN        = "fridaydev.fr"

# 真正的登录凭证（写入 Secrets 的只需这两项，其余站点会自动种）
AUTH_COOKIES  = ("PHPSESSID", "user_id")
# Cookie 剩余有效期低于此天数则 TG 预警
EXPIRY_WARN_DAYS = 3


def parse_cookie_str(raw: str):
    """把 "a=b; c=d" 解析成 [(name, value)]，值按第一个 = 切分，值内含 = 也安全。"""
    pairs = []
    for item in (raw or "").split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        name, value = name.strip(), value.strip()
        if name and value:
            pairs.append((name, value))
    return pairs


def get_account():
    """单账号：读 COOKIE + EMAIL，缺 COOKIE 返回 None。"""
    raw = (os.environ.get("COOKIE") or "").strip()
    if not raw:
        return None
    return {"cookie_raw": raw,
            "email": (os.environ.get("EMAIL") or "").strip(),
            "secret_name": "COOKIE"}


def mask_email(email: str) -> str:
    if "@" in email:
        name, domain = email.split("@", 1)
        return f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    return (email[:2] + "****") if email else "（未填）"


def send_telegram_message(message: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram 未配置，跳过通知")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT_ID, "text": message}, timeout=10)
        print("✅ Telegram 文字通知已发送")
    except Exception as e:
        print(f"❌ Telegram 发送失败: {e}")


def send_telegram_photo(message: str, image_path: str):
    """TG 附截图通知（Xserver 方案），截图不存在或未配置则退化为纯文字。"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram 未配置，跳过通知")
        return
    try:
        if image_path and os.path.isfile(image_path):
            with open(image_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TG_CHAT_ID, "caption": message[:1000]},
                    files={"photo": (os.path.basename(image_path), f, "image/png")},
                    timeout=20)
            if r.status_code == 200:
                print("✅ Telegram 截图通知已发送")
                return
            print(f"⚠️ sendPhoto 失败({r.status_code})，降级为文字通知")
    except Exception as e:
        print(f"⚠️ 截图通知异常，降级为文字通知: {e}")
    send_telegram_message(message)


def update_github_secret(secret_name, new_value):
    if not new_value:
        print(f"⚠️ 跳过更新 {secret_name}：新值为空")
        return False
    print(f"🔄 更新 Secret: {secret_name}（长度 {len(new_value)}）")
    try:
        env = os.environ.copy()
        if GH_TOKEN:
            env["GH_TOKEN"] = GH_TOKEN
        proc = subprocess.run(["gh", "secret", "set", secret_name, "--body", new_value],
                              capture_output=True, text=True, timeout=30, check=False, env=env)
        if proc.returncode == 0:
            return True
        print(f"❌ 更新失败: {proc.stderr.strip()}")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def format_notification(status: str, email: str = "", extra: str = "",
                        error: str = "", old_due: str = "", new_due: str = "") -> str:
    """Hiden 风格：续期成功时双行展示续期前/后到期，其余状态单行展示到期时间。"""
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 8 * 3600))
    lines = ["🇫🇷 Friday 续期通知", "", f"{status}", f"👤 账户: {mask_email(email) or '账号'}"]
    if new_due:
        lines.append(f"📅 续期前到期：{old_due or '（未获取到）'}")
        lines.append(f"📅 续期后到期：{new_due}")
    elif old_due:
        lines.append(f"📅 到期时间: {old_due}")
    if extra:
        lines.append(extra)
    if error:
        lines.append(f"⚠️ 错误信息: {error}")
    lines.append(f"⏱️ 执行时间: {now}(北京时间)")
    return "\n".join(lines)


def get_current_ip(proxy_server: str = "") -> str:
    proxies = {"http": proxy_server, "https": proxy_server} if proxy_server else None
    r = requests.get("https://api.ip.sb/ip", proxies=proxies, timeout=15)
    r.raise_for_status()
    return r.text.strip()


def extract_dates(page_text: str):
    """提取页面内 DD/MM/YYYY 日期（法语站格式），返回 datetime 列表。"""
    out = []
    for m in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", page_text or ""):
        try:
            out.append(datetime(int(m[2]), int(m[1]), int(m[0])))
        except ValueError:
            pass
    return out


def cookie_expiry_warning(sb) -> str:
    """检查 user_id Cookie 剩余有效期，不足阈值返回预警文案，否则返回空串。"""
    try:
        for c in sb.get_cookies():
            if c.get("name") == "user_id" and c.get("expiry"):
                remain_days = (datetime.fromtimestamp(c["expiry"]) - datetime.now()).total_seconds() / 86400
                exp_str = datetime.fromtimestamp(c["expiry"]).strftime("%Y-%m-%d")
                if remain_days < EXPIRY_WARN_DAYS:
                    return (f"🔔 Cookie 告警：user_id 仅剩 {remain_days:.1f} 天"
                            f"（约 {exp_str} 过期），请尽快从浏览器重拷 COOKIE 更新 Secrets")
                print(f"🔑 user_id 剩余有效期约 {remain_days:.1f} 天（{exp_str} 过期）")
                return ""
    except Exception as e:
        print(f"⚠️ Cookie 有效期检查异常: {e}")
    return ""


def rebuild_cookie_str(sb, old_raw: str) -> str:
    """从浏览器最新 Cookie 重建 Secrets 串：优先取浏览器里的 AUTH_COOKIES，缺失用旧值补。"""
    try:
        browser = {c.get("name"): c.get("value") for c in sb.get_cookies() if c.get("value")}
    except Exception:
        browser = {}
    old = dict(parse_cookie_str(old_raw))
    merged = dict(old)
    changed = False
    for name in AUTH_COOKIES:
        if browser.get(name) and browser[name] != old.get(name):
            merged[name] = browser[name]
            changed = True
    if not changed:
        return ""
    return "; ".join(f"{k}={v}" for k, v in merged.items() if v)


def dismiss_cookie_banner(sb):
    """关闭 Cookie 同意横幅（Accepter），找不到就跳过。"""
    for sel in ['button:contains("Accepter")', 'button:contains("Accept")',
                'button:contains("Tout accepter")', '[id*="cookie"] button']:
        try:
            if sb.is_element_visible(sel):
                sb.click(sel)
                print("🍪 已关闭 Cookie 横幅")
                sb.sleep(1)
                return
        except Exception:
            pass


# ---------- 登录（HidenCloud 双通道结构，MVP 只实现 Cookie 通道） ----------

def login_with_cookie(sb, cookie_raw) -> bool:
    pairs = parse_cookie_str(cookie_raw)
    if not pairs:
        print("❌ COOKIE 为空或格式错误（应为 a=b; c=d）")
        return False
    sb.open(BASE_URL + "/")
    sb.wait_for_ready_state_complete()
    sb.sleep(2)
    try:
        sb.delete_all_cookies()
    except Exception:
        pass
    for name, value in pairs:
        try:
            sb.add_cookie({"name": name, "value": value, "domain": DOMAIN})
        except Exception as e:
            print(f"⚠️ 注入 Cookie {name} 失败: {e}")
    sb.open(SERVICES_URL)
    sb.wait_for_ready_state_complete()
    sb.sleep(5)
    dismiss_cookie_banner(sb)
    try:
        text = sb.get_text("body")
    except Exception:
        text = ""
    url = sb.get_current_url()
    # 通用判定：到达服务页且含 "Mes services"（不用硬编码用户名）
    if "Mes services" in text and "/services" in url:
        print("✅ Cookie 登录成功，已到达服务页")
        return True
    print(f"❌ Cookie 登录失败，URL={url}")
    return False


def login_with_password(sb) -> bool:
    """账密备用通道（二期扩展位，MVP 未实现）。"""
    print("ℹ️ 账密备用通道尚未实现（MVP 仅 Cookie 登录）")
    return False


def login(sb, cookie_raw) -> bool:
    if login_with_cookie(sb, cookie_raw):
        return True
    print("🔄 Cookie 登录失败，尝试账密备用通道...")
    return login_with_password(sb)


# ---------- 续期（wabiss 三态判定移植） ----------

def find_renew_button(sb):
    """找可点的续期按钮；返回 (element, text)。排除 'Renouvelable dans' 未到时间态。"""
    try:
        btns = sb.find_elements("button, a")
    except Exception:
        return None, ""
    for el in btns:
        try:
            if not el.is_displayed():
                continue
            t = (el.text or "").strip()
            if not t or "renouvelable dans" in t.lower():
                continue
            if re.search(r"Renouveler(\s+gratuitement)?\s*$", t):
                return el, t
        except Exception:
            continue
    return None, ""


def find_not_yet_text(page_text: str) -> str:
    m = re.search(r"Renouvelable dans\s*(\d+)\s*jours?", page_text or "", re.IGNORECASE)
    return f"{m.group(1)} 天" if m else ""


def click_modal_confirm(sb) -> bool:
    sels = [".modal.show button.btn-primary", ".modal.show button",
            ".swal2-confirm", 'button:contains("Confirmer")',
            'button:contains("Valider")', 'button:contains("Confirm")']
    for sel in sels:
        try:
            if sb.is_element_visible(sel):
                sb.click(sel, timeout=3)
                print(f"✅ 已点击确认弹窗 ({sel})")
                return True
        except Exception:
            pass
    print("⚠️ 未找到确认弹窗按钮（可能无需确认，直接检查结果）")
    return False


def renew(sb, cookie_raw, email) -> dict:
    result = {"ok": False, "summary": "未知"}
    shot = "result.png"

    if not login(sb, cookie_raw):
        msg = format_notification("❌ 登录失败", email=email,
                                  error="Cookie 已失效，请从浏览器重拷 COOKIE 更新 Secrets")
        send_telegram_message(msg)
        result["summary"] = "❌ 登录失败（Cookie 失效）"
        return result

    try:
        page_text = sb.get_text("body")
    except Exception:
        page_text = ""
    old_dates = extract_dates(page_text)
    old_max = max(old_dates) if old_dates else None
    print(f"📅 当前页面日期: "
          f"{[d.strftime('%d/%m/%Y') for d in old_dates] or '（未提取到）'}")

    # 未到时间态
    not_yet = find_not_yet_text(page_text)
    btn, btn_text = find_renew_button(sb)

    if btn is None and not_yet:
        print(f"⏳ 未到续期时间：{not_yet} 后可续")
        send_telegram_message(format_notification(
            "⏳ 未到续期时间", email=email,
            extra=f"⏱️ {not_yet}后可续",
            old_due=old_max.strftime("%d/%m/%Y") if old_max else "（未获取到）"))
        result.update(ok=True, summary=f"⏳ 未到时间（{not_yet}后）")

    elif btn is not None:
        print(f"✅ 发现续期按钮: '{btn_text}'，点击...")
        try:
            btn.click()
        except Exception:
            try:
                sb.execute_script("arguments[0].click();", btn)
            except Exception as e:
                err = f"点击续期按钮失败: {e}"
                print(f"❌ {err}")
                send_telegram_message(format_notification("❌ 续期失败", email=email, error=err))
                result["summary"] = "❌ 续期失败（点击按钮出错）"
                return result
        sb.sleep(4)
        click_modal_confirm(sb)
        print("⏳ 等待结果并刷新...")
        sb.sleep(5)
        try:
            sb.execute_script("location.reload();")
        except Exception:
            sb.open(SERVICES_URL)
        sb.wait_for_ready_state_complete()
        sb.sleep(5)
        try:
            new_text = sb.get_text("body")
        except Exception:
            new_text = ""
        new_dates = extract_dates(new_text)
        new_max = max(new_dates) if new_dates else None
        ok = False
        if old_max and new_max and new_max > old_max:
            ok = True
        elif "Actif" in new_text and "Suspendu" not in new_text and not find_not_yet_text(new_text):
            ok = True  # 日期未变但状态活跃（可能续期即时生效无日期变化）
        try:
            sb.save_screenshot(shot)
        except Exception:
            shot = ""
        if ok:
            print(f"✅ 续期成功，新日期: "
                  f"{[d.strftime('%d/%m/%Y') for d in new_dates] or '（状态活跃）'}")
            send_telegram_photo(format_notification(
                "✅ 续期成功", email=email,
                old_due=old_max.strftime("%d/%m/%Y") if old_max else "",
                new_due=new_max.strftime("%d/%m/%Y") if new_max else "（状态活跃）"), shot)
            result.update(ok=True,
                          summary=f"✅ 续期成功（到期 {new_max.strftime('%d/%m/%Y') if new_max else '活跃'}）")
        else:
            print("⚠️ 续期结果未知，请手动检查")
            send_telegram_photo(format_notification(
                "⚠️ 续期可能未成功", email=email, extra="请登录后台检查",
                old_due=old_max.strftime("%d/%m/%Y") if old_max else "（未获取到）"), shot)
            result["summary"] = "⚠️ 结果未知（请手动检查）"
    else:
        print("ℹ️ 未找到续期按钮/倒计时，状态未知")
        send_telegram_message(format_notification(
            "ℹ️ 状态未知", email=email, extra="未找到续期按钮，请手动检查",
            old_due=old_max.strftime("%d/%m/%Y") if old_max else "（未获取到）"))
        result["summary"] = "ℹ️ 状态未知"

    # Cookie 有效期预警 + 自动回写
    warn = cookie_expiry_warning(sb)
    if warn:
        print(warn)
        send_telegram_message(format_notification("🔔 Cookie 有效期预警", email=email, extra=warn))
    new_raw = rebuild_cookie_str(sb, cookie_raw)
    if new_raw:
        print("🔄 浏览器 Cookie 有更新，回写 Secrets...")
        if GH_TOKEN:
            print('✅ 回写成功' if update_github_secret("COOKIE", new_raw) else '⚠️ 回写失败，请检查 GH_TOKEN')
        else:
            print("⚠️ 未设置 GH_TOKEN，无法自动回写")
    else:
        print("✅ Cookie 无需更新")
    return result


def main():
    print("#" * 25)
    print("   Friday 自动续期（单账号）")
    print("#" * 25)

    acct = get_account()
    if not acct:
        print("ℹ️ 未配置 COOKIE，脚本终止。Secrets 里填 COOKIE（格式 a=b; c=d）。")
        sys.exit(1)

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    PROXY_SERVER = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1080"
    HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"  # Friday 无盾，默认 headless
    sb_kwargs = {"uc": True, "headless": HEADLESS}
    print(f"🔗 {'挂载代理: ' + PROXY_SERVER if IS_PROXY else '🍭 未使用代理，直连访问'}")
    if IS_PROXY:
        sb_kwargs["proxy"] = PROXY_SERVER

    with SB(**sb_kwargs) as sb:
        try:
            print(f"📍 当前出口IP: {get_current_ip(PROXY_SERVER if IS_PROXY else '')}")
        except Exception as e:
            print(f"⚠️ 获取出口 IP 失败: {e}")
        try:
            result = renew(sb, acct["cookie_raw"], acct["email"])
        except Exception as e:
            print(f"❌ 执行异常: {e}")
            import traceback
            traceback.print_exc()
            result = {"ok": False, "summary": f"❌ 执行异常：{e}"}
            try:
                send_telegram_message(format_notification(
                    "❌ 续期失败", email=acct["email"], error=f"执行异常：{e}"))
            except Exception:
                pass

    print(f"\n🏁 执行完毕：{result['summary']}")


if __name__ == "__main__":
    main()
