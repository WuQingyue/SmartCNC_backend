from fastapi import APIRouter, Request, HTTPException, status,Depends
from utils.database import get_db
from utils.session import get_session, SessionManager
from cookie.get_cookie import get_CNC_cookie_from_json, get_CNC_secretKey_from_json,get_YT_cookie_from_json,get_CNC_UserAgent_from_json,get_members_cookie_from_json
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
from models.part_details import PartDetails
from cookie.get_rates import get_cnh_to_usd_rate

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
        except json.JSONDecodeError as e:
            print(f"❌ 响应数据解析失败: {str(e)}")
            return {
                "success": False,
                "message": "JLC-CNC API返回的数据格式错误"
            }
        
        # 提取价格信息
        try:
            quote_infos = response_data.get('data', {}).get('quoteInfos', [])
            print('quote_infos:',quote_infos)
            if not quote_infos:
                print("⚠️ 未找到价格信息")
                return {
                    "success": False,
                    "message": "未找到价格信息，请检查请求参数"
                }
            
            cnh_to_usd_rate = get_cnh_to_usd_rate()
            print('cnh_to_usd_rate:',cnh_to_usd_rate)
            quote_usd_infos = []
            for quote_info in quote_infos:
                # 将价格从CNH转换为USD
                quote_info['price'] = round(quote_info.get('price') / cnh_to_usd_rate, 2)
                quote_info['clampPrice'] = round(quote_info.get('clampPrice') / cnh_to_usd_rate, 2)
                quote_info['craftPrice'] = round(quote_info.get('craftPrice') / cnh_to_usd_rate, 2)
                quote_info['expeditedPrice'] = round(quote_info.get('expeditedPrice') / cnh_to_usd_rate, 2)
                quote_info['materialPrice'] = round(quote_info.get('materialPrice') / cnh_to_usd_rate, 2)
                quote_info['processPrice'] = round(quote_info.get('processPrice') / cnh_to_usd_rate, 2)
                quote_info['programPrice'] = round(quote_info.get('programPrice') / cnh_to_usd_rate, 2)
                quote_info['taxPrice'] = round(quote_info.get('taxPrice') / cnh_to_usd_rate, 2)
                quote_info['remissionAmount'] = round(quote_info.get('remissionAmount') / cnh_to_usd_rate, 2)

                quote_usd_infos.append(quote_info)
            print('quote_usd_infos:',quote_usd_infos)
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
                
                url = "https://member.jlc.com/api/cgi/cncOrder/order/getOrderInfoListByPage"
                headers = {
                    "accept": "application/json, text/plain, */*",
                    "accept-language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
                    "content-type": "application/json",
                    "loading-close": "true",
                    "origin": "https://member.jlc.com",
                    "priority": "u=1, i",
                    "referer": "https://member.jlc.com/center/cnc/",
                    "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "secretkey": get_CNC_secretKey_from_json(),
                    "user-agent": get_CNC_UserAgent_from_json(),
                    "cookie": get_members_cookie_from_json(),
                    }

                endDate = datetime.now().strftime("%Y-%m-%d")
                # 构建请求体
                request_body = {
                    "fileNameOrOrderCode": '',
                    "orderStatus": -1,
                    "startDate":"2025-06-01",
                    "endDate": endDate,
                    "subAccountIds": [],
                    "pageNum": 1,
                    "pageSize": 20
                }
                response = requests.post(
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()  # 检查响应状态
                result_json = response.json()
                select_order_vos = result_json["data"]["selectOrderVOS"]
                for data in select_order_vos:
                    print('data:',data)
                    print('data[orderCode]:',data['orderCode'])
                    if data['orderInfoAccessId'] == order_data['order_number']:
                        print('order_no:',data['orderInfoAccessId'])
                        print('找到订单', data['orderCode'])
                        # 1. 为订单创建独立的零件详情
                        from models.part_details import PartDetails
                        part_details_data = order_data.get('part_details', {})
                        
                        # 从前端获取运费和税费
                        total_shipping_fee = order_data.get('total_shipping_fee')
                        tax_fee = order_data.get('tax_fee')
                        
                        # 从settings获取radio配置
                        jlc_radio = settings.JLC_FREIGHT_RATIO
                        yt_radio = settings.YT_FREIGHT_RATIO

                        # 1. 先创建零件详情记录（不依赖订单ID）
                        part_details = PartDetails(
                            file_id=file_id,
                            record_type='order',  # 设置为订单类型
                            source_id=None,  # 先设为None，后面会更新
                            material_access_id=part_details_data.get('material_access_id'),
                            material=part_details_data.get('material'),
                            quantity=part_details_data.get('quantity', 1),
                            tolerance=part_details_data.get('tolerance'),
                            tolerance_access_id=part_details_data.get('tolerance_access_id'),
                            roughness=part_details_data.get('roughness'),
                            roughness_access_id=part_details_data.get('roughness_access_id'),
                            has_thread=part_details_data.get('has_thread', False),
                            has_assembly=part_details_data.get('has_assembly', False),
                            length=part_details_data.get('length'),
                            width=part_details_data.get('width'),
                            height=part_details_data.get('height'),
                            surface_area=part_details_data.get('surface_area'),
                            volume=part_details_data.get('volume'),
                            surface_treatment=part_details_data.get('surface_treatment'),
                            treatment1_option=part_details_data.get('treatment1_option'),
                            treatment1_color=part_details_data.get('treatment1_color'),
                            treatment1_gloss=part_details_data.get('treatment1_gloss'),
                            treatment1_drawing=part_details_data.get('treatment1_drawing'),
                            treatment2_option=part_details_data.get('treatment2_option'),
                            treatment2_color=part_details_data.get('treatment2_color'),
                            treatment2_gloss=part_details_data.get('treatment2_gloss'),
                            treatment2_drawing=part_details_data.get('treatment2_drawing'),
                            craft_access_id1=part_details_data.get('craft_access_id1'),
                            craft_attribute_color_access_ids1=part_details_data.get('craft_attribute_color_access_ids1'),
                            craft_attribute_glossiness_access_ids1=part_details_data.get('craft_attribute_glossiness_access_ids1'),
                            craft_attribute_file_access_ids1=part_details_data.get('craft_attribute_file_access_ids1'),
                            craft_access_id2=part_details_data.get('craft_access_id2'),
                            craft_attribute_color_access_ids2=part_details_data.get('craft_attribute_color_access_ids2'),
                            craft_attribute_glossiness_access_ids2=part_details_data.get('craft_attribute_glossiness_access_ids2'),
                            craft_attribute_file_access_ids2=part_details_data.get('craft_attribute_file_access_ids2'),
                            material_cost=part_details_data.get('material_cost'),
                            engineering_cost=part_details_data.get('engineering_cost'),
                            clamping_cost=part_details_data.get('clamping_cost'),
                            processing_cost=part_details_data.get('processing_cost'),
                            expedited_price=part_details_data.get('expedited_price'),
                            surface_cost=part_details_data.get('surface_cost'),
                            unit_price=part_details_data.get('unit_price'),
                            total_price=part_details_data.get('total_price'),
                            total_shipping_fee=part_details_data.get('total_shipping_fee'),
                            tax_fee=part_details_data.get('tax_fee'),
                            jlc_radio=part_details_data.get('jlc_radio'),
                            yt_radio=part_details_data.get('yt_radio')
                        )
                        
                        try:
                            db.add(part_details)
                            db.commit()
                            db.refresh(part_details)
                            print(f"✅ 零件详情创建成功: 文件ID {file_id}, 零件详情ID {part_details.id}")
                        except Exception as e:
                            db.rollback()
                            print(f"❌ 插入零件详情失败，错误信息：{e}")
                            continue
                        
                        # 2. 创建订单并关联零件详情ID
                        order = Order(
                            user_id=user_id,
                            order_number=order_data['order_number'],
                            part_details_id=part_details.id,  # 使用已创建的零件详情ID
                            status=data['orderStatusName'],
                            order_code=data['orderCode']
                        )
                        
                        try:
                            db.add(order)
                            db.commit()
                            db.refresh(order)
                            print(f"✅ 订单创建成功: {order.order_number}, 订单ID: {order.id}")
                        except Exception as e:
                            db.rollback()
                            print(f"❌ 创建订单对象失败，错误信息：{e}")
                            continue
                        
                        # 3. 更新零件详情的source_id为订单ID
                        part_details.source_id = order.id
                        db.commit()
                        db.refresh(part_details)
                        print(f"✅ 零件详情source_id更新成功: {part_details.id}")
                        
                        created_part_details.append(part_details.to_dict())
                        created_orders.append(order.to_dict())
                        print(f"✅ 订单创建成功: {order.order_number}")
                
            except Exception as e:
                print(f"❌ 处理订单失败: {str(e)}")
                db.rollback()  # 回滚当前订单的事务
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
        db.rollback()  # 回滚整个事务
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

@router.get("/get_orders_info")  # 返回订单信息的列表
async def get_orders_info( request: Request,
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
    
        orders = db.query(Order).filter(Order.user_id == user_id).all()  # 查询所有订单信息
        if orders == []:
            return {"success": "false", "message": "没有找到订单"}
        filtered_orders = []
        for order in orders:
            # print('order:',order)
            url = "https://member.jlc.com/api/cgi/cncOrder/order/getOrderInfoListByPage"

            # 构建请求头
            headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
            "content-type": "application/json",
            "loading-close": "true",
            "origin": "https://member.jlc.com",
            "priority": "u=1, i",
            "referer": "https://member.jlc.com/center/cnc/",
            "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "secretkey": get_CNC_secretKey_from_json(),
            "user-agent": get_CNC_UserAgent_from_json(),
            "cookie": get_members_cookie_from_json(),
            }
            endDate = datetime.now().strftime("%Y-%m-%d")
            # 构建请求体
            data = {
                "fileNameOrOrderCode":  order.order_code,
                "orderStatus": -1,
                "startDate": "2025-03-01",
                "endDate": endDate,
                "subAccountIds": [],
                "pageNum": 1,
                "pageSize": 100
            }
            try:
                # 使用 httpx 发送异步请求 
                response = requests.post(url, headers=headers, json=data)
                print('response:',response)
                response.raise_for_status()  # 检查响应状态
                result_json = response.json()
                select_order_vos = result_json["data"]["selectOrderVOS"]
                for select_order_vo in select_order_vos:
                    print('select_order_vo:',select_order_vo)
                    if select_order_vo['orderCode'] == order.order_code:
                        filtered_orders.append(order)
                        break
            except Exception as e:
                return {"success": "false", "message": "服务器错误: {str(e)}"}
        if not filtered_orders:
            return {"success": "false", "message": "没有找到订单"}
        return {"success": "true", "message": "获取订单信息成功", "data": filtered_orders}
    except Exception as e:
        return {"success": "false", "message": "服务器错误: {str(e)}"}

# 获取加工费用信息
@router.get("/processing_fees") 
async def get_processing_fee(
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
    except Exception as e:
        return {"success": "false", "message": "服务器错误: {str(e)}"}
    part_details_id = request.query_params.get("part_details_id")
    print('part_details_id:',part_details_id)
    processing_fee = db.query(PartDetails).filter(PartDetails.id == part_details_id).first()  # 查询加工费用信息
    print('processing_fee:',processing_fee)
    if not processing_fee:
        return {"success": "false", "message": "未找到加工费用信息"}
    processing_fee_dict = processing_fee.to_dict()
    print('processing_fee_dict:',processing_fee_dict['total_price'])
    return {
        "success": "true",
        "message": "获取加工费用信息成功",
        "total_price": processing_fee_dict['total_price']
    }

# 处理支付成功
@router.post("/success")
async def payment_success(
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

        payment_data = await request.json()
        print('payment_data', payment_data)

        try:
            # 获取订单详情
            pay_id = payment_data["paypalOrder"]["id"]
            order_no = payment_data["order_no"]
            # 获取访问令牌
            access_token = get_paypal_access_token()
            
            # 验证订单
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept-Language": "zh-CN"
            }
            
            order_url = f"https://api.sandbox.paypal.com/v2/checkout/orders/{pay_id}"
            order_response = requests.get(order_url, headers=headers)
            print('order_response:',order_response.json())
            if not order_response.ok:
                logger.error(f"获取订单详情失败: {order_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="订单验证失败"
                )

            order_data = order_response.json()
            
            # 验证订单状态
            if order_data["status"] != "COMPLETED":
                logger.error(f"订单状态不正确: {order_data['status']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="订单未完成支付"
                )

            # 更新订单状态
            order = order_model.Order(
                user_id=user_id,
                file_id=1,
                quantity=1,
                amount=float(payment_data["paypalOrder"]["purchase_units"][0]["amount"]["value"]),
                order_no=order_no,
                status="pending_processing",
                payment_id=pay_id
            )
            db.add(order)
            
            db.commit()
            # jlc支付
            url = "https://trade.jlc.com/api/cgi/pms/unifyOrderPay/unifyOrderPay"
            data = {
                "payUuid": "a7a2c392bb894bf098eb630493be7331",
                "paymentCode": "walletpay",
                "hasChequePay": False,
                "paySource": "PC"
            }
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
                "content-type": "application/json",
                "origin": "https://trade.jlc.com",
                "priority": "u=1, i",
                "referer": f"https://trade.jlc.com/pay/unifyPayInit/?payUuid={data['payUuid']}",
                "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "secretkey": get_CNC_secretKey_from_json(),
                "user-agent": get_CNC_UserAgent_from_json()
            }
            cookies = {
                "acw_tc": "0ae5a7e317485884917267726e004f265f9763974cb269776034568f08c179",
                "JLC_CUSTOMER_CODE": "9246228A",
                "JLC_PAY_SESSION_ID": "92cdf960-f4d2-455a-82a9-1910e6d4325a"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, cookies=cookies, json=data)
                print('jlc支付结果response:', response.json())
            logger.info("订单创建成功")
            return {"status": 200, "message": "支付成功"}
        except Exception as e:
            logger.error(f"订单处理失败: {str(e)}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="订单处理失败"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"处理支付失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理支付失败，请联系客服"
        )

# jlc下单
@router.post("/jlc_order")
async def jlc_order(request: Request):
    request_data = await request.json()
    print('payUrl:', request_data)
    # 获取 payUrl 字段
    pay_url = request_data.get("payUrl", "")
    match = re.search(r'payUuid=([a-f0-9]+)', pay_url)
    value = None
    if match:
        value = match.group(1)
        print('value:',value)
    url = "https://trade.jlc.com/api/cgi/pms/unifyOrderPay/unifyOrderPay"
    print('referer:',"https://trade.jlc.com/pay/unifyPayInit/?payUuid=" + value)
    headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "content-type": "application/json",
    "origin": "https://trade.jlc.com",
    "priority": "u=1, i",
    "referer": "https://trade.jlc.com/pay/unifyPayInit/?payUuid=" + value,
    "sec-ch-ua": "\"Google Chrome\";v=\"137\", \"Chromium\";v=\"137\", \"Not/A)Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "secretkey": get_CNC_secretKey_from_json(),
    "user-agent": get_CNC_UserAgent_from_json(),
    "cookie": get_pay_cookie_from_json(),
    } 
    data = {
        "payUuid": value,
        "paymentCode": "walletpay",
        "hasChequePay": False,
        "paySource": "PC"
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 获取payUuid
@router.get("/get_payUuid")
async def get_payUuid(orderAccessId:str):
    url = "https://member.jlc.com/api/cgi/cncOrder/walletWeb/pay"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-GB;q=0.7,en;q=0.6,en-US;q=0.5",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://member.jlc.com",
        "Referer": "https://member.jlc.com/center/cnc/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": get_CNC_UserAgent_from_json(),
        "Cookie": get_members_cookie_from_json(),
        "sec-ch-ua": "\"Microsoft Edge\";v=\"137\", \"Chromium\";v=\"137\", \"Not/A)Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "\"Android\"",
        "secretkey": get_CNC_secretKey_from_json(),
        }
    data = {
        "paySource": "PC",
        "payFinishUrl": "https://member.jlc.com/center/cnc/#/mainPage/orderListCNC",
        "orderAccessIdList": [orderAccessId]
        }

    response = requests.post(url, headers=headers, json=data)
    print('response:',response.json())
    print("Status Code:", response.status_code)
    return response.json()