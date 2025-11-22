import os
import time
import requests
from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv
    load_dotenv() 
    print("✅ 本地调试模式：已加载 .env 文件")
except ImportError:
    print("⚠️ 未安装 python-dotenv，或运行在云端，跳过加载 .env")

# ----------------------------------------------------------------
# 通用通知函数
# ----------------------------------------------------------------
def send_notification(title, content):
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token: return
    try:
        requests.post("http://www.pushplus.plus/send", json={
            "token": token, "title": title, "content": content, "template": "html"
        })
    except: pass

class JuejinBrowser:
    def __init__(self):
        self.cookie_str = os.getenv("JUEJIN_COOKIE", "")
        if not self.cookie_str:
            print("❌ 错误：未找到 JUEJIN_COOKIE")
            exit(1)

    def parse_cookie(self):
        """把 Cookie 字符串转换为 Playwright 需要的字典列表格式"""
        cookies = []
        # 简单的解析逻辑：按分号分割
        for item in self.cookie_str.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.juejin.cn', # 关键：指定域名
                    'path': '/'
                })
        return cookies

    def run(self):
        print("🚀 启动 Playwright 浏览器模式...")
        
        with sync_playwright() as p:
            # 启动 Chrome (headless=True 表示无头模式，不显示界面，适合服务器跑)
            is_github = os.getenv("GITHUB_ACTIONS") == "true"
            
            print(f"⚙️ 当前运行环境: {'GitHub Actions (云端)' if is_github else 'Local (本地)'}")
            
            # 如果是云端，必须 True (无头模式)；如果是本地，可以是 False (看界面)
            # 这里的逻辑是：如果是云端 -> True；本地 -> False
            browser = p.chromium.launch(headless=is_github, slow_mo=1000)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            # 1. 注入 Cookie (这就相当于如果你登录了)
            cookies_list = self.parse_cookie()
            context.add_cookies(cookies_list)
            
            page = context.new_page()
            msg_log = []

            # -------------------------------------------------------
            # 任务一：去签到
            # -------------------------------------------------------
            try:
                print("🌍 正在打开签到页面...")
                page.goto("https://juejin.cn/user/center/signin", timeout=30000)
                
                # 等待网页加载，寻找签到按钮
                # 掘金签到按钮通常有 "立即签到" 或 "今日已签到" 的文字
                # 我们等待这个按钮出现
                signin_btn = page.locator("button.signin").first
                
                if signin_btn.is_visible():
                    btn_text = signin_btn.inner_text()
                    if "已签到" in btn_text:
                        print("✅ 检测到今日已签到")
                        msg_log.append("✅ 签到: 今日已完成")
                    else:
                        print("👆 点击签到按钮...")
                        signin_btn.click()
                        # 等待一会儿，确保请求发送成功
                        time.sleep(3)
                        print("✅ 点击完成")
                        msg_log.append("✅ 签到: 点击成功")
                else:
                    # 有时候页面结构不同，尝试另一种定位方式（按文字找）
                    check_btn = page.get_by_text("立即签到")
                    if check_btn.count() > 0:
                        check_btn.first.click()
                        time.sleep(3)
                        msg_log.append("✅ 签到: 点击成功 (文字定位)")
                    elif page.get_by_text("已签到").count() > 0:
                        msg_log.append("✅ 签到: 今日已完成")
                    else:
                        print("❌ 未找到签到按钮，截图保存")
                        # 截图方便调试 (仅本地可见)
                        # page.screenshot(path="debug_signin.png")
                        msg_log.append("❌ 签到: 未找到按钮 (Cookie可能失效)")
            
            except Exception as e:
                print(f"❌ 签到出错: {e}")
                msg_log.append(f"❌ 签到异常: {e}")

            # -------------------------------------------------------
            # 任务二：去抽奖
            # -------------------------------------------------------
            try:
                print("🌍 正在打开抽奖页面...")
                page.goto("https://juejin.cn/user/center/lottery", timeout=30000)
                time.sleep(3) # 等页面渲染
                
                # 1. 尝试寻找“免费抽奖”按钮
                # 使用 exact=True 精确匹配，防止匹配到规则文字
                free_draw_btn = page.get_by_text("免费抽奖", exact=True)
                
                if free_draw_btn.is_visible():
                    print("👆 发现免费次数，点击抽奖...")
                    free_draw_btn.click()
                    
                    # 点击后可能需要再点一次“收下奖励”或者只需点击一次
                    # 这里简单处理，只要不报错就行
                    time.sleep(3)
                    msg_log.append("🎉 抽奖: 点击成功")
                
                else:
                    # 2. 如果没找到免费按钮，检查是不是变成了“单抽”
                    # 掘金抽完后，按钮会变成 "单抽" 或显示 "200" (矿石)
                    if page.get_by_text("单抽").is_visible() or page.get_by_text("200").is_visible():
                        print("✅ 检测到今日已抽奖 (按钮已变更为单抽)")
                        msg_log.append("✅ 抽奖: 今日已完成")
                    else:
                        # 既没免费，也没单抽，可能是页面改版或加载失败
                        print("⚠️ 未找到抽奖按钮，可能是页面加载不全")
                        msg_log.append("⚠️ 抽奖: 按钮未找到 (可能已完成)")
                        
            except Exception as e:
                print(f"❌ 抽奖出错: {e}")
                # 只有当不是超时错误时，才记录为异常，避免超时报错吓人
                if "Timeout" not in str(e):
                    msg_log.append(f"❌ 抽奖异常: {e}")
                else:
                     msg_log.append("⚠️ 抽奖: 操作超时 (可能已完成)")

            browser.close()
            print("🏁 浏览器关闭")
            
            # 汇总结果
            final_msg = "<br>".join(msg_log)
            print(f"📊 最终报告: {final_msg}")
            
            if "❌" in final_msg or "🎉" in final_msg:
                send_notification("掘金浏览器打卡", final_msg)

if __name__ == "__main__":

    JuejinBrowser().run()
