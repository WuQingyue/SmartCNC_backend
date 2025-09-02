from fastapi import APIRouter, Request, HTTPException, status,Depends
from utils.database import get_db
from utils.session import get_session, SessionManager
from cookie.get_cookie import get_CNC_cookie_from_json, get_CNC_secretKey_from_json,get_YT_cookie_from_json
from fastapi.encoders import jsonable_encoder
from models.address import Address
import requests
import json
from sqlalchemy.orm import Session

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

# @router.post("/save_selected_datas")
# async def save_selected_datas(
#     request:Request,
#     session: SessionManager = Depends(get_session)
#     ):
#     try:
#         # 验证会话ID
#         session_id = request.cookies.get("SESSIONID")
#         print('验证session_id', session_id)
        
#         # 检查SESSIONID是否存在
#         if session_id is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="未登录"
#             )
        
#         # 检查SESSIONID是否在Redis中存在（会话是否过期）
#         if session.is_session_expired(session_id):
#             print(f"🔴 Session已过期: {session_id}")
#             # 清除过期的Cookie
#             session.clear_expired_cookies()
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="会话已过期，请重新登录"
#             )
        
#         print(f"✅ Session验证通过: {session_id}")
        
#         # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
#         user_id = session.get("user_id")
#         if not user_id:
#             # 从CUSTOMERID Cookie获取用户ID
#             customerid = request.cookies.get("CUSTOMERID")
#             if customerid:
#                 try:
#                     user_id = int(customerid)
#                     print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
#                 except ValueError:
#                     print(f"CUSTOMERID格式错误: {customerid}")
#                     user_id = None
        
#         print('user_id', user_id)
        
#         if not user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="用户信息无效，请重新登录"
#             )
        
#         # 获取CUSTOMER_CODE
#         customer_code = request.cookies.get("CUSTOMER_CODE")
#         if not customer_code:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="用户信息无效，请重新登录"
#             )
        
#         print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
#         data = await request.json()
#         session.set("selected_datas", [item.dict() for item in data])
#         # 确保session被保存
#         await session.save_session()
#         print("保存成功")
#     except Exception as e:
#         print(f"❌ 保存价格查询失败: {str(e)}")
#         return {
#             "success": False,
#             "error": str(e)
#         }

# @router.get("/get_selected_datas")
# async def get_selected_datas(
#     request: Request,
#     session: SessionManager = Depends(get_session)
#     ):
#     try:
#         # 验证会话ID
#         session_id = request.cookies.get("SESSIONID")
#         print('验证session_id', session_id)
        
#         # 检查SESSIONID是否存在
#         if session_id is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="未登录"
#             )
        
#         # 检查SESSIONID是否在Redis中存在（会话是否过期）
#         if session.is_session_expired(session_id):
#             print(f"🔴 Session已过期: {session_id}")
#             # 清除过期的Cookie
#             session.clear_expired_cookies()
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="会话已过期，请重新登录"
#             )
        
#         print(f"✅ Session验证通过: {session_id}")
        
#         # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
#         user_id = session.get("user_id")
#         if not user_id:
#             # 从CUSTOMERID Cookie获取用户ID
#             customerid = request.cookies.get("CUSTOMERID")
#             if customerid:
#                 try:
#                     user_id = int(customerid)
#                     print(f"从CUSTOMERID Cookie获取用户ID: {user_id}")
#                 except ValueError:
#                     print(f"CUSTOMERID格式错误: {customerid}")
#                     user_id = None
        
#         print('user_id', user_id)
        
#         if not user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="用户信息无效，请重新登录"
#             )
        
#         # 获取CUSTOMER_CODE
#         customer_code = request.cookies.get("CUSTOMER_CODE")
#         if not customer_code:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="用户信息无效，请重新登录"
#             )
        
#         print(f"📁 用户ID: {user_id}, CUSTOMER_CODE: {customer_code}")
#         # 从 session 取出数据
#         selected_datas = session.get("selected_datas", [])
#         if selected_datas is []:
#             return []
#         return [selected_datas(**item) for item in selected_datas]
#     except Exception as e:
#         print(f"❌ 获取价格查询失败: {str(e)}")
#         return {
#             "success": False,
#             "message": "获取价格查询失败，请稍后重试",
#             "error": str(e)
#         }
 
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
        except requests.RequestError as e:
            return {"error": f"请求出错: {str(e)}"}
        except ValueError as e:
            return {"error": f"解析响应出错: {str(e)}"}
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

