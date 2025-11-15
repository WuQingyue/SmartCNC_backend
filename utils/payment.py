from utils.config import settings
import requests
import base64
import json
from fastapi import APIRouter

def get_paypal_access_token():
    """获取 PayPal 访问令牌"""
    try:
        # 构建认证凭据
        credentials = base64.b64encode(
            f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # 获取访问令牌 
        token_url = "https://api.paypal.com/v1/oauth2/token"
        response = requests.post(
            token_url,
            headers=headers,
            data="grant_type=client_credentials"
        )
        if not response.ok:
            print(f"获取PayPal访问令牌失败: {response.text}")
            raise Exception("PayPal认证失败")

        return response.json()["access_token"]
    except Exception as e:
        print(f"获取PayPal访问令牌出错: {str(e)}")
        raise
