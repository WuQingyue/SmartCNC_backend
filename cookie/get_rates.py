import requests
from utils.config import settings
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_cnh_to_usd_rate():
    cnh_to_usd_url="https://openexchangerates.org/api/latest.json"
    cnh_to_usd_params = {
        "app_id": settings.APP_ID,
        "base": settings.BASE,
        "symbols": settings.SYMBOLS
    }
    # 配置重试策略
    session = requests.Session()
    retry_strategy = Retry(
        total=10,  # 总重试次数
        backoff_factor=1,  # 重试间隔
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        response = session.get(cnh_to_usd_url, params=cnh_to_usd_params, timeout=10)
        response.raise_for_status()
        return response.json().get('rates', {}).get(settings.SYMBOLS, 0)
    except Exception as e:
        print(f"汇率获取失败，使用默认汇率: {e}")
        return 7.2  # 返回一个默认汇率作为备选