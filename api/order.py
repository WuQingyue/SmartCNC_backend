from fastapi import APIRouter, Request, HTTPException, status,Depends
from utils.database import get_db
from utils.session import get_session, SessionManager
from cookie.get_cookie import get_CNC_cookie_from_json, get_CNC_secretKey_from_json,get_YT_cookie_from_json,get_CNC_UserAgent_from_json
from fastapi.encoders import jsonable_encoder
from models.address import Address
from models.order import Order
import requests
import json
from sqlalchemy.orm import Session
import time
import hmac
import base64
import hashlib
from utils.config import settings
from datetime import datetime

router = APIRouter()
@router.post("/price")
async def price(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    """获取价格报价"""
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        url = "https://www.jlc-cnc.com/api/cncOrder/valuation"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,en-GB;q=0.5",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cookie": get_CNC_cookie_from_json(),
            "Loading-Close": "true",
            "Origin": "https://www.jlc-cnc.com",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36 Edg/138.0.0.0",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "secretkey": get_CNC_secretKey_from_json()
        }
        
        print('🔧 请求头配置完成')
        
        # 将请求数据转换为 JSON 格式
        try:
            request_json_data = await request.json()
            print('request.json()', request_json_data)
            
            # 检查数据格式
            if isinstance(request_json_data, list):
                # 如果直接是列表，直接使用
                request_data = request_json_data
            elif isinstance(request_json_data, dict):
                # 如果是字典，尝试获取data字段
                request_data = request_json_data.get('data', request_json_data)
            else:
                raise ValueError("请求数据格式不正确")
                
            print('request_data', request_data)
            request_json = jsonable_encoder(request_data)
            print(f'📤 请求数据: {json.dumps(request_json, indent=2, ensure_ascii=False)}')
        except Exception as e:
            print(f"❌ 数据序列化失败: {str(e)}")
            return {
                "success": False,
                "message": "请求数据格式错误"
            }
        
        # 调用JLC-CNC API
        try:
            response = requests.post(url, json=request_json, headers=headers, timeout=30)
            response.raise_for_status()
            print(f"✅ JLC-CNC API响应状态码: {response.status_code}")
        except requests.Timeout:
            print("⏰ JLC-CNC API请求超时")
            return {
                "success": False,
                "message": "JLC-CNC API请求超时，请稍后重试"
            }
        except requests.ConnectionError:
            print("🌐 JLC-CNC API连接失败")
            return {
                "success": False,
                "message": "无法连接到JLC-CNC服务，请检查网络连接"
            }
        except requests.RequestException as e:
            print(f"❌ JLC-CNC API请求失败: {str(e)}")
            return {
                "success": False,
                "message": f"JLC-CNC API请求失败: {str(e)}"
            }
        
        # 解析响应数据
        try:
            response_data = response.json()
            print(f"📥 JLC-CNC API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            print(f"❌ 响应数据解析失败: {str(e)}")
            return {
                "success": False,
                "message": "JLC-CNC API返回的数据格式错误"
            }
        
        # 提取价格信息
        try:
            quote_infos = response_data.get('data', {}).get('quoteInfos', [])
            if not quote_infos:
                print("⚠️ 未找到价格信息")
                return {
                    "success": False,
                    "message": "未找到价格信息，请检查请求参数"
                }
            
            print(f"💰 成功获取 {len(quote_infos)} 个价格信息")
            return {
                "success": True,
                "message": f"成功获取 {len(quote_infos)} 个价格信息",
                "data": quote_infos
            }
            
        except Exception as e:
            print(f"❌ 提取价格信息失败: {str(e)}")
            return {
                "success": False,
                "message": "提取价格信息失败",
                "data": response_data  # 返回原始响应数据供调试
            }
            
    except Exception as e:
        print(f"❌ 价格查询失败: {str(e)}")
        return {
            "success": False,
            "message": "价格查询失败，请稍后重试"
        }

# 获取国家信息
@router.get("/get_country")
async def get_country(
    request: Request,
    session: SessionManager = Depends(get_session),
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        ProductCode = request.query_params.get("ProductCode")
        print('ProductCode',ProductCode)
        url = f"https://oms2uc.yunexpress.cn/api/Product/GetRecverCountrys?ProductCode={ProductCode}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh_CN",
            "Connection": "keep-alive",
            "Origin": "https://oms2.yunexpress.cn",
            "Referer": "https://oms2.yunexpress.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 Edg/135.0.0.0",
            "X-Client-Channel": "prod",
            "X-Client-Menu": "/oms/singleMail",
            "X-Client-UserName": "CN0341597",
            "X-Client-Version": "2.35.0",
            "Cookie":get_YT_cookie_from_json()
        }

        try:
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print('get_country',response.json())
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="获取国家信息失败，请稍后重试"
            )
    except Exception as e:
        print(f"❌ 获取国家信息失败: {str(e)}")
        return {
            "success": False,
            "message": "获取国家信息失败，请稍后重试",
            "error": str(e)
        }

# 获取州的信息
@router.get("/get_region1")
async def get_region1(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        country_code = request.query_params.get("country_code")
        print('country_code',country_code)
        url = f"https://ucv2.yunexpress.cn/api/ars/GetRegion?country={country_code}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh_CN",
            "Connection": "keep-alive",
            "Origin": "https://oms2.yunexpress.cn",
            "Referer": "https://oms2.yunexpress.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 Edg/135.0.0.0",
            "X-Client-Channel": "prod",
            "X-Client-IP": "45.76.70.158",
            "X-Client-Menu": "/oms/singleMail",
            "X-Client-UserName": "CN0341597",
            "X-Client-Version": "2.35.0",
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": "Android",
            "Cookie":get_YT_cookie_from_json()
        }

        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print('get_region1',response.json())
            return response.json()
        except requests.HTTPStatusError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except Exception as err:
            return {"error": f"Other error occurred: {err}"}
    except Exception as e:
        print(f"❌ 获取州的信息失败: {str(e)}")
        return {
            "success": False,
            "message": "获取州的信息失败，请稍后重试",
            "error": str(e)
        }

# 获取城市的信息
@router.get("/get_region2")
async def get_region2(
    request: Request,
    session: SessionManager = Depends(get_session),
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        country = request.query_params.get("country")
        region1 = request.query_params.get("region1")
        print('get_region2',country,region1)
        url = f"https://ucv2.yunexpress.cn/api/ars/GetRegion?country={country}&region1={region1}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh_CN",
            "Connection": "keep-alive",
            "Origin": "https://oms2.yunexpress.cn",
            "Referer": "https://oms2.yunexpress.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 Edg/135.0.0.0",
            "X-Client-Channel": "prod",
            "X-Client-IP": "45.76.70.158",
            "X-Client-Menu": "/oms/singleMail",
            "X-Client-UserName": "CN0341597",
            "X-Client-Version": "2.35.0",
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Cookie":get_YT_cookie_from_json()
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print('get_region2',response.json())
            return response.json()
        except requests.HTTPStatusError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except Exception as err:
            return {"error": f"Other error occurred: {err}"}
    except Exception as e:
        print(f"❌ 获取城市的信息失败: {str(e)}")
        return {
            "success": False,
            "message": "获取城市的信息失败，请稍后重试",
            "error": str(e)
        }

# 获取邮政编码
@router.get("/get_postcode")
async def get_postcode(
    request: Request,
    session: SessionManager = Depends(get_session),
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        country = request.query_params.get("country")
        region1 = request.query_params.get("region1")
        region2 = request.query_params.get("region2")
        region2: str
        print('country:',country)
        print('region1:',region1)
        print('region2:',region2)
        url =f"https://ucv2.yunexpress.cn/api/ars/GetPostcode?country={country}&region1={region1}&region2={region2}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh_CN",
            "Connection": "keep-alive",
            "Origin": "https://oms2.yunexpress.cn",
            "Referer": "https://oms2.yunexpress.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 Edg/135.0.0.0",
            "X-Client-Channel": "prod",
            "X-Client-IP": "45.76.70.158",
            "X-Client-Menu": "/oms/singleMail",
            "X-Client-UserName": "CN0341597",
            "X-Client-Version": "2.35.0",
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Cookie":get_YT_cookie_from_json()
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print("postcode:",response.json())
            return response.json()
        except requests.HTTPStatusError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except Exception as err:
            return {"error": f"Other error occurred: {err}"}
    except Exception as e:
        print(f"❌ 获取邮政编码失败: {str(e)}")
        return {
            "success": False,
            "message": "获取邮政编码失败，请稍后重试",
            "error": str(e)
        }

# 增加收货地址
@router.post("/add_address")
async def add_address(
    request:Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        # 获取请求数据
        request_json_data = await request.json()
        address_data = jsonable_encoder(request_json_data)
        print('address_data', address_data)
        
        # 创建地址对象，使用模型的字段名
        address = Address(
            user_id=user_id,
            contact_name=address_data.get("contact_name"),
            contact_phone=address_data.get("contact_phone"),
            address_detail=address_data.get("address_detail"),  # 对应模型的address_detail字段
            shipping_method=address_data.get("shipping_method"),
            country_code=address_data.get("country_code"),      # 对应模型的country_code字段
            province=address_data.get("province"),
            city=address_data.get("city"),
            post_name=address_data.get("post_name"),
            postal_code=address_data.get("postal_code"),
            is_default=address_data.get("is_default", False)   # 默认为False
        )
        # 如果设置为默认地址，需要更新其他地址的默认状态
        if address.is_default:
            address.update_default_status(db)
        
        db.add(address)
        db.commit()
        db.refresh(address)
        
        return {"success": True, "detail": "添加地址成功", "data": address.to_dict()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="添加地址失败，请稍后重试"
        )
# 删除地址
@router.delete("/delete_address/{address_id}")
async def delete_address(
    request:Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        
        # 从路径参数获取地址ID
        address_id = request.path_params.get("address_id")
        print('address_id', address_id)
        if not address_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="地址ID不能为空"
            )
        
        # 查询地址，确保只能删除自己的地址
        address = db.query(Address).filter(
            Address.id == address_id, 
            Address.user_id == user_id
        ).first()
        
        if not address:
            return {"success": False, "detail": "地址不存在或无权限删除"}
        
        # 删除地址
        db.delete(address)
        db.commit()
        
        return {"success": True, "detail": "删除地址成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="删除地址失败，请稍后重试"
        )

# 获取地址列表
@router.get("/get_user_addresses")
async def get_user_addresses(
    request:Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
       
        # 查询用户的所有地址，按创建时间排序
        addresses = db.query(Address).filter(
            Address.user_id == user_id
        ).order_by(Address.created_at.desc()).all()
        
        if not addresses:
            return {"success": False, "detail": "地址列表为空", "data": []}
        
        # 使用模型的to_dict方法转换数据
        address_list = [address.to_dict() for address in addresses]
        return {"success": True, "detail": "获取地址列表成功", "data": address_list}
    except Exception as e:
        print(f"❌ 获取地址列表失败: {str(e)}")
        return {
            "success": False,
            "message": "获取地址列表失败，请稍后重试",
            "error": str(e)
        }
# 设置默认地址
@router.post("/set_default_address")
async def set_default_address(
    request:Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        
        # 获取请求数据
        data = await request.json()
        print('data', data)
        
        # 查询该地址，确保只能操作自己的地址
        address = db.query(Address).filter(
            Address.id == data.get("address_id"), 
            Address.user_id == user_id
        ).first()
        
        if not address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="地址不存在或无权限操作"
            )

        # 使用模型的update_default_status方法更新默认状态
        address.is_default = True
        address.update_default_status(db)
        
        db.commit()
        db.refresh(address)
        
        return {"success": True, "detail": "默认地址设置成功", "data": address.to_dict()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设置默认地址失败，请稍后重试"
        )

# 获取默认地址
@router.get("/get_default_addresses")
async def get_default_addresses(
    request:Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        
        # 查询用户的默认地址
        address = db.query(Address).filter(
            Address.user_id == user_id,
            Address.is_default == True
        ).first()
        
        if not address:
            return {"success": False, "detail": "请添加默认地址", "data": None}
        
        print('address', address)
        return {"success": True, "detail": "获取默认地址成功", "data": address.to_dict()}
    except Exception as e:
        print(f"❌ 获取默认地址失败: {str(e)}")
        return {
            "success": False,
            "message": "获取默认地址失败，请稍后重试",
            "error": str(e)
        }

# 获取订单访问ID
@router.post("/get_orderAccessIds")
async def get_orderAccessIds(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        url = "https://www.jlc-cnc.com/api/cncOrder/settlement/immediatelyCncOrder"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://www.jlc-cnc.com",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": get_CNC_UserAgent_from_json(),
            "sec-ch-ua": '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "secretkey": get_CNC_secretKey_from_json(),
            "cookie": get_CNC_cookie_from_json()
            }
        # 1. 以原始 JSON 格式读取前端数据
        request_data = await request.json()
        print('get_orderAccessIds接受的数据', request_data)

        # 2. 直接转发
        response = requests.post(url, json=request_data, headers=headers)
        if response.status_code == 200:
            print('get_orderAccessIds返回的数据', response.json())
            return response.json()
        else:
            return {"error": response.status_code, "message": response.text}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取订单访问ID失败，请稍后重试"
        )

# 获取估重
@router.post("/get_weight")
async def get_weight(
    request:Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        """查询JLC CNC业务订单信息"""
        url = "https://www.jlc-cnc.com/api/cncSettlement/obtain/queryObtainBizOrder"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://www.jlc-cnc.com",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
            "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "secretkey": get_CNC_secretKey_from_json(),
            "cookie": get_CNC_cookie_from_json()
        }
        try:
            request_data = await request.json()
            print('get_weight接受的数据',request_data)
            print('bizOrderAccessId',request_data['bizOrderAccessId'])
            data = {
            "businessLine": "cnc",
            "bizOrderAccessIds": [request_data['bizOrderAccessId']]
        }
            response = requests.post(url, headers=headers, json=data)
            print('get_weight的response',response.json())
            if(response.status_code != 200):
                return {"status_code":500, "detail":"获取估重失败"}
            else:
                response.raise_for_status()
                print('get_weight的response',response.json())
                return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取估重失败，请稍后重试"
        )
    
# 运费试算
@router.get("/price-trial")
async def price_trial(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        country_code = request.query_params.get("country_code")
        weight = request.query_params.get("weight")
        print('country_code:',country_code)
        print('weight:',weight)
        token_url = "https://openapi.yunexpress.cn/openapi/oauth2/token"
        headers = {"Content-Type": "application/json"}
        data = {
            "appId": "7ddf7d20ed8d",
            "appSecret": "70207db73472464cbf3733fa1e198347",
            "grantType": "client_credentials",
            "sourceKey": "lcb1nvgi"
        }
        response = requests.post(token_url, data=json.dumps(data), headers=headers)  
        print('response',response.json())
        accessToken = response.json()["accessToken"]
        print('accessToken',accessToken)

        timestamp = int(time.time() * 1000)
        print('timestamp',timestamp)
        # 生成签名
        client_secret =  "70207db73472464cbf3733fa1e198347"
        content = f"date={timestamp}&method=GET&uri=/v1/price-trial/get"  # 请确认实际需要签名的内容
        signature = hmac.new(
            client_secret.encode('utf-8'),
            content.encode('utf-8'),
            hashlib.sha256
        ).digest()  
        signature = base64.b64encode(signature).decode()  # Base64 编码并转为字符串
        print('signature',signature)
        url = "https://openapi.yunexpress.cn/v1/price-trial/get"
        headers = {
            "token": accessToken,
            "date": str(timestamp),
            "sign": signature,
            "Content-Type": "application/json",
            "Accept-Language": "zh-CN"
        }
        data = {
            "country_code": country_code,
            "weight": weight,
            "package_type": "C"
        }
        response = requests.get(
            url,
            headers=headers,
            params=data
        )
        print('response',response.json())
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取运费失败，请稍后重试"
        )

# 下单计算优惠券费用
@router.post("/place_calculate_coupon_fee")
async def place_calculate_coupon_fee(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        url = "https://www.jlc-cnc.com/api/cncOrder/walletWeb/placeCalculateCouponFee"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Loading-Close": "true",
            "Origin": "https://www.jlc-cnc.com",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": get_CNC_UserAgent_from_json(),
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Cookie": get_CNC_cookie_from_json()
        }
        request_data = await request.json()
        print('place_calculate_coupon_fee接受的数据', request_data)
        print("[request_data['bizOrderAccessId']]",[request_data['bizOrderAccessId']])
        data = {
            "bizOrderType": "cnc",
            "bindingDelivery": True,
            "expressCode": "JDTH",
            "receiptType": "PAPER",
            "invoiceFlag": 1,
            "invoiceType": "VAT_DIGITAL_SPECIAL_INVOICE",
            "receiptTitle": "",
            "confirmOrderType": "CUSTOMER_CONFIRM",
            "remark": "",
            "invoiceOrganization": 1,
            "vatCompanyName": "厦门修蓁慧进技术有限公司",
            "vatTaxCode": "91350200MAE7YW2W60",
            "invoiceEmail": None,
            "customerInvoiceInfoAccessId": "09716b28b76a4f9d975343bd3fa9b369",
            "salesmanCode": "",
            "couponFlag": True,
            "packingType": 0,
            "expressName": "京东特惠快递",
            "invoiceCategory": 1,
            "invoiceMethod": 1,
            "vatCompanyNameEncode": None,
            "vatTaxCodeEncode": None,
            "businessLine": "cnc",
            "bizOrderAccessIds": [request_data['bizOrderAccessId']],
            "receiverInfoAccessId": "8c7abea1cb4642309e9ae95e24dbd06c",
            "customerLinkInfoAccessId": "9823674928a74b128c3340a2864cf002",
            "expressType": "JDTH",
            "riskConfirmFlag": False,
            "ignoreAddressErrorFlag": False,
            "modelFrom": "",
            "couponOrderAccessId": None
        }

        
        try:
            response = requests.post(url, headers=headers, json=data)
            if(response.status_code != 200):
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取运费失败")
            else:
                response.raise_for_status()
                print('JLC-CNC运费计算:', response.json())
                return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取运费失败，请稍后重试"
        )

# 获取运费比例
@router.get("/getFreightRate")
def getFreightRate(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        # 查询is_active=1并且email为tongtron@admin.com的记录
        jlc_ratio = settings.JLC_FREIGHT_RATIO
        yt_ratio = settings.YT_FREIGHT_RATIO
        if not jlc_ratio or not yt_ratio:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Freight ratio not found")
        return {
            "success": "true",
            "message": "获取运费比例成功",
            "jlc_ratio": float(jlc_ratio),
            "yt_ratio": float(yt_ratio)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取运费比例失败，请稍后重试"
        )

# 下单
@router.get("/submit_cnc_order")
async def submit_cnc_order(
    request: Request,
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        bizOrderAccessId = request.query_params.get("bizOrderAccessId")
        print('submit_cnc_order',bizOrderAccessId)
        url = "https://www.jlc-cnc.com/api/cncSettlement/order/submitOrder"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Loading-Close": "true",
            "Origin": "https://www.jlc-cnc.com",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": get_CNC_UserAgent_from_json(),
            "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Bran"d";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "secretkey": get_CNC_secretKey_from_json(),
            "Cookie": get_CNC_cookie_from_json()
        }

        data = {
            "bizOrderType": "cnc",
            "bindingDelivery": True,
            "expressCode": "JDTH",
            "receiptType": "PAPER",
            "invoiceFlag": 1,
            "invoiceType": "VAT_DIGITAL_SPECIAL_INVOICE",
            "receiptTitle": "",
            "confirmOrderType": "CUSTOMER_CONFIRM",
            "remark": "",
            "invoiceOrganization": 1,
            "vatCompanyName": "厦门修蓁慧进技术有限公司",
            "vatTaxCode": "91350200MAE7YW2W60",
            "invoiceEmail": None,
            "customerInvoiceInfoAccessId": "09716b28b76a4f9d975343bd3fa9b369",
            "salesmanCode": "",
            "couponFlag": True,
            "packingType": 0,
            "expressName": "京东特惠快递",
            "invoiceCategory": 1,
            "invoiceMethod": 1,
            "vatCompanyNameEncode": None,
            "vatTaxCodeEncode": None,
            "businessLine": "cnc",
            "bizOrderAccessIds":  [bizOrderAccessId],
            "receiverInfoAccessId": "8c7abea1cb4642309e9ae95e24dbd06c",
            "customerLinkInfoAccessId": "9823674928a74b128c3340a2864cf002",
            "expressType": "JDTH",
            "riskConfirmFlag": False,
            "ignoreAddressErrorFlag": False,
            "modelFrom": "",
            "couponOrderAccessId": None
        }
        try:
            response = requests.post(url, headers=headers, json=data)
            print('submitOrder接受的数据response',response)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提交询价订单失败，请稍后重试"
        )

# 将订单信息存入数据库
@router.post("/orders")
async def orders(
    request: Request,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print('验证session_id', session_id)
        
        # 检查SESSIONID是否存在
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id = session.get("user_id")
        if not user_id:
            # 从CUSTOMERID Cookie获取用户ID
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                    print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
                except ValueError:
                    print(f"CUSTOMERID格式错误: {customerid}")
                    user_id = None
        
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取CUSTOMER_CODE
        customer_code = request.cookies.get("CUSTOMER_CODE")
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息无效，请重新登录"
            )
        
        print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
        
        # 获取请求数据
        request_data = await request.json()
        print('创建订单接受的数据', request_data)
        
        created_orders = []
        created_part_details = []
        
        # 处理每个订单数据
        for order_data in request_data:
            try:
                # 验证必要字段
                required_fields = ['order_number', 'file_id']
                for field in required_fields:
                    if not order_data.get(field):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"缺少必要字段: {field}"
                        )
                
                # 验证文件是否属于当前用户
                file_id = order_data['file_id']
                from models.file import Files
                file = db.query(Files).filter(
                    Files.id == file_id,
                    Files.user_id == user_id
                ).first()
                
                if not file:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"文件ID {file_id} 不存在或无权限访问"
                    )
                
                # 1. 创建或更新零件详情
                from models.part_details import PartDetails
                part_details_data = order_data.get('part_details', {})
                
                # 检查是否已存在零件详情
                existing_part_details = PartDetails.get_part_details_by_file(db, file_id)
                
                if existing_part_details:
                    # 更新现有零件详情
                    for field, value in part_details_data.items():
                        if hasattr(existing_part_details, field):
                            setattr(existing_part_details, field, value)
                    
                    # 如果更新了价格相关字段，重新计算总价
                    price_fields = ['material_cost', 'engineering_cost', 'clamping_cost', 
                                   'processing_cost', 'expedited_price', 'surface_cost', 'quantity']
                    if any(field in part_details_data for field in price_fields):
                        existing_part_details.update_pricing(db)
                    else:
                        db.commit()
                    
                    part_details = existing_part_details
                    print(f"✅ 零件详情更新成功: 文件ID {file_id}")
                else:
                    # 创建新的零件详情
                    part_details = PartDetails.create_part_details(
                        db_session=db,
                        file_id=file_id,
                        **part_details_data
                    )
                    print(f"✅ 零件详情创建成功: 文件ID {file_id}")
                
                created_part_details.append(part_details.to_dict())
                
                # 2. 创建订单
                order = Order.create_order(
                    db_session=db,
                    user_id=user_id,
                    order_number=order_data['order_number'],
                    part_details_id=part_details.id,  # 使用刚创建/更新的零件详情ID
                    status=order_data.get('status', '待审核'),
                    order_code=order_data.get('order_code'),
                    logistics_info_id=order_data.get('logistics_info_id')
                )
                
                created_orders.append(order.to_dict())
                print(f"✅ 订单创建成功: {order.order_number}")
                
            except Exception as e:
                print(f"❌ 处理订单失败: {str(e)}")
                # 继续处理其他订单，不中断整个流程
                continue
        
        if not created_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="所有订单创建失败"
            )
        
        return {
            "success": True,
            "message": f"成功创建 {len(created_orders)} 个订单和 {len(created_part_details)} 个零件详情",
            "data": {
                "orders": created_orders,
                "part_details": created_part_details
            }
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        print(f"❌ 创建订单失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )
