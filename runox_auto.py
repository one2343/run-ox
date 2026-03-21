"""
runox.io 自动续期 + 开机脚本

流程:
  1. 打开首页 https://runox.io/en/
  2. 点击 Cookie 弹窗 "Accept all"
  3. 点击顶部 Log In
  4. 输入账号密码
  5. 过 Cloudflare 验证
  6. 点击登录按钮
  7. 点击 Manage
  8. 点击 Start / Restore 续期（没有则跳过）
  9. 点击 Start 开机

Secrets:
  RUNOX_ACCOUNTS = email:password（多账号逗号分隔）
  TG_TOKEN / TG_CHAT_ID（可选，Telegram 推送）
"""

import time
import os
import random
import requests

if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"
if "XAUTHORITY" not in os.environ:
    if os.path.exists("/home/headless/.Xauthority"):
        os.environ["XAUTHORITY"] = "/home/headless/.Xauthority"

print(f"[DEBUG] DISPLAY:    {os.environ.get('DISPLAY')}")
print(f"[DEBUG] XAUTHORITY: {os.environ.get('XAUTHORITY')}")

from seleniumbase import SB

PROXY_URL  = os.getenv("PROXY", "")
TG_TOKEN   = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
HOME_URL   = "https://runox.io/en/"


class RunoxRenewal:
    def __init__(self, acc):
        parts = acc.strip().split(":")
        if len(parts) < 2:
            raise ValueError(f"账号格式错误，应为 email:password，收到: {acc}")
        self.email    = parts[0]
        self.password = parts[1]
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def hw(self, a=4, b=8):
        time.sleep(random.uniform(a, b))

    def shot(self, sb, name):
        p = f"{self.screenshot_dir}/{name}"
        sb.save_screenshot(p)
        self.log(f"📸 {name}")
        return p

    def try_click(self, sb, selectors, timeout=6):
        for sel in selectors:
            try:
                sb.wait_for_element_visible(sel, timeout=timeout)
                sb.click(sel)
                return True
            except Exception:
                continue
        return False

    def send_tg(self, message, photo_path=None):
        if not TG_TOKEN or not TG_CHAT_ID:
            return
        try:
            if photo_path and os.path.exists(photo_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(photo_path, 'rb') as f:
                    requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': message},
                                  files={'photo': f}, timeout=15)
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': message}, timeout=15)
            self.log("✅ TG 推送成功")
        except Exception as e:
            self.log(f"⚠️ TG 推送失败: {e}")

    def run(self):
        self.log("=" * 50)
        self.log(f"🚀 开始处理: {self.email}")
        self.log("=" * 50)

        with SB(
            uc=True,
            test=True,
            headed=True,
            headless=False,
            xvfb=False,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-position=0,0,--start-maximized",
            proxy=PROXY_URL if PROXY_URL else None
        ) as sb:
            try:
                self.log("✅ 浏览器已启动")

                # ── 1. 打开首页 ───────────────────────────────────────────
                self.log(f"📂 打开首页: {HOME_URL}")
                sb.delete_all_cookies()
                sb.uc_open_with_reconnect(HOME_URL, reconnect_time=5)
                self.hw(3, 5)
                self.shot(sb, "01_homepage.png")

                # ── 2. 点击 Cookie 弹窗 "Accept all" ─────────────────────
                self.log("🍪 处理 Cookie 弹窗...")
                cookie_clicked = self.try_click(sb, [
                    "//button[contains(text(),'Accept all')]",
                    "//button[contains(text(),'Accept All')]",
                    "//button[contains(text(),'accept')]",
                    "button.accept-all",
                    "[data-testid='accept-all']",
                ], timeout=8)
                if cookie_clicked:
                    self.log("✅ Cookie 弹窗已接受")
                else:
                    self.log("⚠️ 未找到 Cookie 弹窗（可能已接受过），继续...")
                self.hw(2, 3)
                self.shot(sb, "02_after_cookie.png")

                # ── 3. 点击顶部 Log In ────────────────────────────────────
                self.log("🖱️ 点击 Log In...")
                login_clicked = self.try_click(sb, [
                    "//a[normalize-space()='Log In']",
                    "//button[normalize-space()='Log In']",
                    "a[href*='login']",
                    "//a[contains(text(),'Log In')]",
                    "//a[contains(text(),'Login')]",
                ], timeout=10)
                if not login_clicked:
                    self.shot(sb, "error_no_login_btn.png")
                    raise Exception("未找到 Log In 按钮")
                self.log("✅ Log In 已点击")
                self.hw(3, 5)
                self.shot(sb, "03_loginpage.png")
                self.log(f"📍 当前URL: {sb.get_current_url()}")

                # ── 4. 填写账号密码 ───────────────────────────────────────
                self.log("✏️ 等待登录表单...")
                email_sel = None
                for sel in ["#email", "input[name='email']", "input[type='email']",
                            "input[placeholder*='mail']", "input[type='text']"]:
                    try:
                        sb.wait_for_element_visible(sel, timeout=8)
                        email_sel = sel
                        self.log(f"✅ 邮箱框: {sel}")
                        break
                    except Exception:
                        continue

                if not email_sel:
                    self.shot(sb, "error_no_form.png")
                    raise Exception("未找到登录表单，查看截图确认页面状态")

                sb.type(email_sel, self.email)

                for sel in ["#password", "input[name='password']", "input[type='password']"]:
                    try:
                        sb.wait_for_element_visible(sel, timeout=8)
                        sb.type(sel, self.password)
                        self.log(f"✅ 密码框: {sel}")
                        break
                    except Exception:
                        continue

                self.shot(sb, "04_after_input.png")

                # ── 5. 过 Cloudflare 验证 ─────────────────────────────────
                self.log("🔄 处理 Cloudflare 验证...")
                try:
                    sb.uc_gui_click_captcha()
                    self.hw(6, 10)
                    sb.uc_gui_handle_captcha()
                    self.hw(6, 10)
                    self.log("✅ CF 验证完成")
                except Exception as e:
                    self.log(f"⚠️ CF 验证跳过: {e}")
                self.shot(sb, "05_after_captcha.png")

                # ── 6. 点击登录按钮 ───────────────────────────────────────
                self.log("🖱️ 点击登录按钮...")
                login_submit = self.try_click(sb, [
                    "button.submit-btn",
                    "button[type='submit']",
                    "//button[contains(text(),'Log In')]",
                    "//button[contains(text(),'Login')]",
                    "//button[contains(text(),'Sign In')]",
                ], timeout=10)
                if not login_submit:
                    self.shot(sb, "error_no_submit.png")
                    raise Exception("未找到登录提交按钮")

                self.log("⏳ 等待登录跳转（30s）...")
                time.sleep(30)
                self.shot(sb, "06_after_login.png")
                self.log(f"📍 当前URL: {sb.get_current_url()}")

                # ── 7. 点击 Manage ────────────────────────────────────────
                self.log("🔍 寻找 Manage 按钮...")
                manage_ok = self.try_click(sb, [
                    "//button[contains(text(),'Manage')]",
                    "//a[contains(text(),'Manage')]",
                    "a[href*='manage']",
                    ".manage-btn",
                ], timeout=15)
                if not manage_ok:
                    self.shot(sb, "error_no_manage.png")
                    raise Exception("未找到 Manage 按钮，登录可能失败")
                self.log("✅ Manage 点击成功")
                self.hw(3, 5)
                self.shot(sb, "07_after_manage.png")

              # ── 7.5. 处理续期/开机前的 Cloudflare Turnstile 验证 ──────
                self.log("🔄 检测并处理操作前的 Cloudflare 验证...")
                try:
                    # 使用 wait_for_element_present 等待元素出现，支持 timeout
                    sb.wait_for_element_present(".turnstile-container", timeout=45)
                    self.log("👀 发现 Turnstile 验证容器，尝试自动处理...")
                    self.hw(3, 5) # 给它一点时间彻底加载 iframe
                    
                    # 调用 UC 模式的方法点击验证
                    sb.uc_gui_click_captcha() 
                    self.hw(4, 7) # 等待验证通过（变成绿勾）
                    self.log("✅ Turnstile 验证点击指令已发送")
                except Exception as e:
                    # 如果 8 秒内没找到容器，说明当前不需要验证，正常跳过
                    self.log(f"⏭️ 未检测到 Turnstile 验证或已跳过: {e}")

                self.shot(sb, "07_5_after_cf_check.png")

                # ── 8. 点击 Start / Restore 续期 ─────────────────────────
                self.log("🔍 寻找 Start / Restore 按钮...")
                
                restore_ok = self.try_click(sb, [
                    "//button[contains(text(),'Start / Restore')]",
                    "//button[contains(text(),'Restore')]",
                    "//button[contains(normalize-space(),'Start / Restore')]",
                ], timeout=12)
                
                if restore_ok:
                    self.log("✅ 续期完成！")
                else:
                    self.log("⏰ 无 Start/Restore 按钮 —— 未到续期时间")
                    self.shot(sb, "08_no_restore.png")
                self.hw(3, 5)

                # ── 9. 点击 Start 开机 ────────────────────────────────────
                self.log("🔍 寻找 Start 按钮（开机）...")
                start_ok = self.try_click(sb, [
                    "//button[normalize-space()='Start']",
                    "//a[normalize-space()='Start']",
                    "//button[contains(text(),'Start') and not(contains(text(),'Restore'))]",
                ], timeout=8)
                if start_ok:
                    self.log("✅ 开机指令已发送！")
                else:
                    self.log("⚠️ 未找到 Start 按钮（可能已在运行中）")

                time.sleep(3)
                final = self.shot(sb, "09_final.png")
                msg = f"✅ {self.email} 保活完成"
                self.log(msg)
                self.send_tg(msg, final)

            except Exception as e:
                self.log(f"❌ 运行异常: {e}")
                import traceback
                traceback.print_exc()
                err_shot = self.shot(sb, "error.png")
                self.send_tg(f"❌ {self.email} 保活失败: {e}", err_shot)
                raise


if __name__ == "__main__":
    accounts = os.getenv("RUNOX_ACCOUNTS", "")
    if not accounts:
        print("❌ 请设置 RUNOX_ACCOUNTS 环境变量（格式: email:password）")
        exit(1)
    for acc in accounts.split(','):
        acc = acc.strip()
        if acc:
            try:
                RunoxRenewal(acc).run()
            except Exception:
                print(f"⚠️ {acc.split(':')[0]} 处理失败，继续下一个...")
