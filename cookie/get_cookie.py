import os
import json
import requests
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import time
import re
import logging
from utils.config import settings
from selenium.common.exceptions import TimeoutException,NoSuchElementException
from selenium.webdriver import ActionChains
# Linux系统下ChromeDriver路径配置
CHROMEDRIVER_PATH = '/usr/local/bin/chromedriver' 
# CHROMEDRIVER_PATH = 'E:\chromedriver-win64\chromedriver.exe' 
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_request_headers(driver):
    cookies = driver.get_cookies()
    cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    return cookie_header

def get_CNC_cookie_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_Cookie", "")
def get_CNC_code_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("code", "")

def get_CNC_secretKey_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_Secretkey", "")

def get_members_cookie_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_Member_Cookie", "")


def get_pay_cookie_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_Pay_Cookie", "")

def get_CNC_UserAgent_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_User_Agent", "")

def get_YT_cookie_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("YT_Cookie", "")

def get_YC_cookie_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("YC_Cookie", "")

def get_YT_UserAgent_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("YT_User_Agent", "")
def get_JLC_user_agent_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("JLC_User_Agent", "")
def get_YT_user_agent_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("YT_User_Agent", "")

def get_YC_user_agent_from_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
    data_json_path = os.path.normpath(data_json_path)
    with open(data_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("YC_User_Agent", "")

def init_chrome_driver():
    """初始化Chrome WebDriver（Linux适配版）"""
    seleniumwire_options = {
        'scopes': [
            # 只拦截这一个URL的请求，其他所有请求（如css, js, 图片等）都会被忽略
            # 这可以极大地减少内存消耗
            r'.*member\.jlc\.com/api/cgi/cncOrder/cas-auth/get-current-user.*'
        ]
    }
    chrome_options = webdriver.ChromeOptions()
    
    # Linux系统特有配置
    chrome_options.add_argument('--no-sandbox')  # 必须参数
    chrome_options.add_argument('--disable-dev-shm-usage')  # 必须参数
    chrome_options.add_argument('--headless')  # 无头模式，适合服务器环境
    chrome_options.add_argument('--incognito')  # 无痕模式
    chrome_options.add_argument('--disable-gpu')
    
    # 通用配置
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 添加一个真实的User-Agent
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')
 
    # 初始化Service
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options,seleniumwire_options=seleniumwire_options)

    # 应用 selenium-stealth
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
            
    return driver
def get_CNC_cookie():
    driver = init_chrome_driver()
    driver.get("https://passport.jlc.com/login?appId=CNC_BIZ_GATEWAY&redirectUrl=https%3A%2F%2Fwww.jlc-cnc.com%2F&backCode=1")
    print("get_CNC_cookie访问了jlc-passport.com")
    try:
        # Use WebDriverWait to ensure the element is present and clickable
        # We locate the button by its visible text "账号登录"
        wait = WebDriverWait(driver, 20)  # Wait for up to 20 seconds
        account_login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '账号登录')]"))
        )
        
        # Click the button
        account_login_button.click()
        print("成功点击'账号登录'按钮。")
        
        # Keep the browser open for a few seconds to observe the result
        time.sleep(5) 

    except Exception as e:
        print(f"点击'账号登录'按钮时出错: {e}")
    try:
        username = settings.JLC_CNC_USERNAME
        password = settings.JLC_CNC_PASSWORD
        username_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='请输入手机号码/客户编号/邮箱']"))
        )
        # 输入用户名
        username_input.clear()
        for char in username:
            username_input.send_keys(char)
            time.sleep(0.1)  # 模拟人类输入速度

        print("已输入账号。")

        # Find the password input field using its placeholder and enter the password
        password_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='请输入登录密码']"))
        )
        # 输入密码
        password_input.clear()
        for char in password:
            password_input.send_keys(char)
            time.sleep(0.1)  # 模拟人类输入速度
        print("已输入密码。")

    except Exception as e:
        print(f"输入账号和密码时出错: {e}")
    
    print("正在尝试滑动验证码...")
    slider = wait.until(
        EC.presence_of_element_located((By.ID, "nc_1_n1z")) # Locate the slider handle
    )
    
    action = ActionChains(driver)
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.ID, "nc_1_n1z"))
    )
    action.click_and_hold(slider).perform()
    action.move_by_offset(350, 0).perform()
    action.release().perform()
    try:
        # 等待滑块验证通过
        wait.until(
            EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'验证通过')]"))
        )
        print("滑块验证成功！")
        
    except Exception as e:
        print(f"滑块验证失败或超时: {e}")
    
   # 等待登录按钮可点击
    login_submit = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'el-button base-button w-full el-button--primary')]"))
    )
    login_submit.click()
    print("get_CNC_cookie点击登录按钮")
    time.sleep(5)
    try:
        print("等待登录后页面加载...")
        customer_id_element = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "span.code"))
        )
        
        # Get the text from the element
        customer_id = customer_id_element.text
        print(f"成功获取客编: {customer_id}")
    except Exception as e:
        print(f"获取客编失败: {e}")
    try:
        online_quote_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "在线报价"))
        )
        # 点击按钮
        online_quote_button.click()
        print("成功点击 '在线报价' 按钮。")
    except Exception as e:
        print(f"无法点击按钮: {e}")
    time.sleep(5)
    try:
        # 等待“跳过”按钮出现并且变为可点击状态，最长等待10秒
        # XPath释义: 寻找一个文本内容正好是'跳过'的button元素
        skip_button_xpath = "//button[text()='跳过']"
        
        skip_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, skip_button_xpath))
        )

        # 点击按钮
        skip_button.click()
        
        print("成功点击 '跳过' 按钮。")

    except Exception as e:
        print(f"无法找到或点击'跳过'按钮: {e}")
    time.sleep(5)
    button_locator = (By.XPATH, "//table[contains(@class, 'history-table')]/tbody/tr[1]//button/span[text()='立即下单']/parent::button")
    # 或者使用 CSS 选择器，它更简洁且通常也有效
    # button_locator = (By.CSS_SELECTOR, "table.history-table tbody tr:first-child td:last-child button.el-button--primary")

    button_locator = (By.CSS_SELECTOR, "table.history-table tbody tr:first-child button.el-button--primary")

    try:
        print("正在等待第一条历史记录的 '立即下单' 按钮可点击...")
        # 使用 EC.element_to_be_clickable 等待元素可见且可点击
        # 将等待时间设置为 20 秒，以便页面有足够时间加载
        place_order_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(button_locator)
        )
        print("'立即下单' 按钮已找到且可点击。")

        # 确保元素滚动到视图中，防止因不在可视区域导致点击问题
        print("尝试将按钮滚动到视图中...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", place_order_button)
        print("已将按钮滚动到视图中。")

        # 使用 JavaScript 点击找到的元素（绕过 Selenium 标准点击可能遇到的问题）
        print("尝试使用 JavaScript 点击按钮...")
        driver.execute_script("arguments[0].click();", place_order_button)
        print("使用 JavaScript 成功点击了第一条历史记录的 '立即下单' 按钮。")
        time.sleep(5)

    except TimeoutException:
        print("错误：在指定时间内（20秒）未能找到或等待 '立即下单' 按钮变为可点击。")
        print("请检查：1. 页面是否完全加载；2. 历史记录表格是否已显示；3. CSS 选择器是否仍然有效。")
    except WebDriverException as e:
        print(f"发生 WebDriver 错误：{e}")
        print("请检查您的浏览器驱动版本与浏览器版本是否匹配。")
    except Exception as e:
        print(f"发生未知错误：{e}")
        # 可以在这里添加截图以便调试
    # 获取并保存Cookie
    cookies_3 = driver.get_cookies()
    cookie_dict_3 = {c['name']: c['value'] for c in cookies_3}
    cookies_str_3 = "; ".join([f"{k}={v}" for k, v in cookie_dict_3.items()])
    
    # 保存到文件
    save_cookie_to_json("JLC_Cookie", cookies_str_3)
    print(cookies_str_3)
    print('get_CNC_cookie已保存JLC_Cookie')
    driver.get("https://member.jlc.com/center/cnc/#/mainPage/orderListCNC")
    print("https://member.jlc.com/center/cnc/#/mainPage/orderListCNC")
    time.sleep(10)
    # 获取并保存Cookie
    cookies_1 = driver.get_cookies()
    cookie_dict_1 = {c['name']: c['value'] for c in cookies_1}
    cookies_str_1 = "; ".join([f"{k}={v}" for k, v in cookie_dict_1.items()])
    print(cookies_str_1)
    # 保存到文件
    save_cookie_to_json("JLC_Member_Cookie", cookies_str_1)
    print('get_CNC_cookie已保存JLC_Member_Cookie')

    driver.get("https://trade.jlc.com/pay/")
    time.sleep(10)
    # 获取并保存Cookie
    cookies_2 = driver.get_cookies()
    cookie_dict_2 = {c['name']: c['value'] for c in cookies_2}
    cookies_str_2 = "; ".join([f"{k}={v}" for k, v in cookie_dict_2.items()])
    # 保存到文件
    save_cookie_to_json("JLC_Pay_Cookie", cookies_str_2)
    print(cookies_str_2)
    print('get_CNC_cookie已保存JLC_Pay_Cookie')
    time.sleep(10)
    print("等待 'https://member.jlc.com/api/cgi/cncOrder/cas-auth/get-current-user' API 请求...")
    try:
        # (关键修改2) 使用 try...except 包裹，并增加超时时间
        request = driver.wait_for_request(
            'https://member.jlc.com/api/cgi/cncOrder/cas-auth/get-current-user', 
            timeout=120
        ) 
        
        # (关键修改3) 增加详细的调试打印信息
        print(f"成功捕获到请求! 请求方法: {request.method}")
        print("捕获到的请求的全部 Headers:", request.headers)

        
        secret_key = request.headers.get('SecretKey')
        User_Agent = request.headers.get('User-Agent')
        if secret_key:
            print("\n🎉 成功获取到 SecretKey!")
            save_cookie_to_json("JLC_Secretkey", secret_key)
            print('get_CNC_cookie已保存JLC_Secretkey')
        else:
            print("\n❌ 错误：在捕获到的请求头中未找到 SecretKey。请检查上面的 '全部 Headers' 打印信息。")
        if User_Agent:
            print("\n🎉 成功获取到 User-Agent!")
            save_cookie_to_json("JLC_User_Agent", User_Agent)
            print('get_CNC_cookie已保存JLC_User_Agent')
        else:
            print("\n❌ 错误：在捕获到的请求头中未找到 User-Agent。请检查上面的 '全部 Headers' 打印信息。")

    except TimeoutException:
        print("\n❌ 错误：在指定时间内没有捕获到 'secret/update' 的请求。")
        print("可能原因：1. 登录后未触发此API；2. 网络延迟；3. 网站逻辑已变更。")
    driver.quit()
def get_YT_cookie():
    driver = None
    try:
        driver = init_chrome_driver()
        driver.get("https://oms2.yunexpress.cn/home")
        # 等待用户名输入框出现
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'el-input--prefix') and contains(@class, 'el-input--suffix')]/input[@type='text']"))
        )
        username = settings.YT_USERNAME
        password = settings.YT_PASSWORD
        # 输入用户名
        username_input = driver.find_element(By.XPATH, "//div[contains(@class, 'el-input--prefix') and contains(@class, 'el-input--suffix')]/input[@type='text']")
        username_input.clear()
        for ch in username:
            username_input.send_keys(ch)
            time.sleep(0.1)

        # 等待密码输入框出现
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'el-input--prefix') and contains(@class, 'el-input--suffix')]/input[@type='password']"))
        )

        # 输入密码
        password_input = driver.find_element(By.XPATH, "//div[contains(@class, 'el-input--prefix') and contains(@class, 'el-input--suffix')]/input[@type='password']")
        password_input.clear()
        for ch in password:
            password_input.send_keys(ch)
            time.sleep(0.1)

        # 等待登录按钮出现
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'el-form-item__content')]/button"))
        )

        # 点击登录按钮
        login_btn = driver.find_element(By.XPATH, "//div[contains(@class, 'el-form-item__content')]/button")
        login_btn.click()

        # 等待登录完成，检查用户名元素
        try:
            # 等待用户名元素出现
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-name"))
            )
            
            # 获取用户名
            username_element = driver.find_element(By.CLASS_NAME, "user-name")
            username_text = username_element.text.strip()
            # print(driver.page_source)
            print("get_YT_cookie登录成功！")
            time.sleep(10)
            print(f"get_YT_cookie用户名: {username_text}")
            print(f"get_YT_cookie当前页面URL: {driver.current_url}")
        except Exception as e:
            print("get_YT_cookieyt登录失败:", e)
            print(f"get_YT_cookie当前页面URL: {driver.current_url}")
            driver.quit() 
        # 获取User-Agent
        YT_user_agent = driver.execute_script("return navigator.userAgent;")
        
        # 获取并保存Cookie
        cookies = driver.get_cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        cookies_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存到文件
        save_cookie_to_json("YT_Cookie", cookies_str)
        save_cookie_to_json("YT_User_Agent", YT_user_agent)  # 新增：保存User-Agent
        save_cookie_to_json("timestamp", timestamp)
        print('已保存YT_Cookie和YT_User_Agent')
        # app_div = driver.find_element(By.ID, 'app')
        # 你可以对 app_div 做进一步操作，比如打印其 HTML
        # print(app_div.get_attribute('outerHTML'))
        # main_container = driver.find_element("xpath", '//*[@id="app"]//div[contains(@class, "main-container")]')
        # 假设页面已打开
        element = driver.find_element(
            By.CSS_SELECTOR,
            "#app .main-container .content-container.big-screen-collose .middle-width-big-collose .no-crumbs .index-view .dialog-notice-message .el-dialog .el-dialog__header .el-dialog__headerbtn"
        )

        # 如果你想看下这个元素
        # print(element.get_attribute('outerHTML'))
        try:
            element.click()
            print("get_YT_cookie点击弹窗取消按钮")
        except Exception as e:
            print("get_YT_cookie点击弹窗取消按钮失败:", e)
        # 等待弹窗消失
        time.sleep(10)
        # cancel = driver.find_element(
        #     By.CSS_SELECTOR,
        #     "#app .main-container .content-container.big-screen-collose .middle-width-big-collose .no-crumbs .index-view .dialog-notice-message"
        # )
        # print('get_YT_cookie点击弹窗取消按钮后',cancel.get_attribute('outerHTML'))
        time.sleep(10)
        try:
            driver.execute_script("document.querySelector('.yuncang-box').click();")
            # yc_btn.click()
            print("get_YT_cookie点击云仓按钮")
        except Exception as e:
            print("get_YT_cookie点击云仓按钮失败:", e)
        time.sleep(10)
        handles = driver.window_handles
        driver.switch_to.window(handles[-1])
        # 抓取新网页内容
        print(driver.current_url)
        # print(driver.page_source)
        print('get_YT_cookie成功打开云仓界面')
        # 点击提交审核按钮
        time.sleep(2)
        driver.switch_to.frame("iframe-container-79")
        submit_wait = WebDriverWait(driver, 10)
        submit_btn = submit_wait.until(EC.presence_of_element_located((By.ID, "orderSubmitCheckBtn")))
        try:
            submit_btn.click()
            print("get_YC_cookie点击提交审核按钮")
        except Exception as e:
            print("get_YC_cookie点击提交审核按钮失败:", e)

        # 获取User-Agent
        YC_user_agent = driver.execute_script("return navigator.userAgent;")
        
        # 获取并保存Cookie
        YC_cookies = driver.get_cookies()
        YC_cookie_dict = {c['name']: c['value'] for c in YC_cookies}
        YC_cookies_str = "; ".join([f"{k}={v}" for k, v in YC_cookie_dict.items()])

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存到文件
        save_cookie_to_json("YC_Cookie", YC_cookies_str)
        save_cookie_to_json("YC_User_Agent", YC_user_agent)
        print('已保存YC_Cookie和YC_User_Agent')
    except Exception as e:
        print("get_YC_cookie点击提交审核按钮失败:", e)
    finally:
        # 3. 无论成功还是失败，都必须在 finally 块中关闭浏览器
        if driver:
            driver.quit()
            logger.info("YT 浏览器实例已关闭。")
       
def save_cookie_to_json(key, value):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_json_path = os.path.join(current_dir, '../Agent_data/login_status.json')
        
        if os.path.exists(data_json_path):
            with open(data_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        data[key] = value
        with open(data_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"保存{key}失败: {str(e)}")