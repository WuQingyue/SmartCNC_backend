from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File,Form,Request
from sqlalchemy.orm import Session
from utils.database import get_db
from models.file import Files
from utils.session import get_session, SessionManager
import os
import requests
import io
import json
from cookie.get_cookie import get_CNC_UserAgent_from_json,get_CNC_cookie_from_json,get_CNC_secretKey_from_json
from typing import List
from datetime import datetime
router = APIRouter()

@router.get("/history")
async def history(
    request: Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """获取上传历史"""
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
        user_id = request.cookies.get("CUSTOMERID")
        print('user_id', user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 查询历史记录
        records = db.query(Files).filter(
            Files.user_id == user_id,
        ).order_by(
            Files.uploaded_at.desc()
        ).all()
        
        print("查询历史记录", records)
        
        return {
            "success": True,
            "data": [
                {
                    "id": record.id,
                    "file_name": record.file_name,
                    "file_url": record.file_url,
                    "file_size": record.file_size,
                    "file_info_accessId": record.file_info_accessId,
                    "uploaded_at": record.uploaded_at.isoformat()
                }
                for record in records
            ]
        }
        
    except HTTPException:
        # 重新抛出HTTP异常，不进行额外处理
        raise
    except Exception as e:
        print(f"获取历史记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取历史记录失败，请稍后重试"
        )

@router.post("/uploadDrawFile")
async def uploadDrawFile(
    request: Request,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """上传图纸文件列表"""
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
        print(f"📋 接收到的文件数量: {len(files)}")
        
        # 创建文件存储目录
        base_dir = "uploads"
        customer_dir = os.path.join(base_dir, customer_code)
        
        # 检查目录是否已存在
        if not os.path.exists(customer_dir):
            os.makedirs(customer_dir)
            print(f"📂 创建新目录: {customer_dir}")
        else:
            print(f"📂 目录已存在: {customer_dir}")
        
        files_data = []
        for file in files:
            try:
                print(f"🔄 处理文件: {file.filename}")
                
                # 保存文件到本地
                file_path = os.path.join(customer_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    file_content = await file.read()
                    buffer.write(file_content)

                # 重新读取文件用于API上传
                file_obj2 = io.BytesIO(file_content)
                files_data.append(
                    ('files', (file.filename, file_obj2, 'application/octet-stream'))
                )
            except Exception as e:
                print(f"❌ 处理文件 {file.filename} 失败: {str(e)}")
                # 继续处理下一个文件，不中断整个流程
                continue
        url = "https://www.jlc-cnc.com/api/cncOrder/file/uploadDrawFile"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Connection": "keep-alive",
            "Referer": "https://www.jlc-cnc.com/cncOrder/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "origin": "https://www.jlc-cnc.com",
            "Cookie": get_CNC_cookie_from_json(),
            "Sec-Fetch-Site": "same-origin"
        }

        # 调用JLC-CNC API
        response = requests.post(url, files=files_data, headers=headers)
        response.raise_for_status()
        jlc_response = response.json()
        
        print(f'JLC-CNC上传响应: {jlc_response}')
        return {
            "success": True,
            "message": f"文件上传完成，成功处理 {len(files)} 个文件",
            "data": jlc_response.get("data",[]),
            "total_files": len(files),
            "successful_files": len(files)
        }
        
    except HTTPException:
        raise
    except requests.RequestException as e:
        print(f"❌ JLC-CNC API请求失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"JLC-CNC API请求失败: {str(e)}"
        )
    except Exception as e:
        print(f"❌ 文件上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )

@router.post("/upload")
async def upload(
    request: Request, 
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """上传文件到3D预览服务"""
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")  # 注意：这里应该是SESSIONID而不是SESSION_ID
        print('验证session_id', session_id)
        
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID - 优先从session获取，备选从CUSTOMERID Cookie获取
        user_id =  request.cookies.get("CUSTOMERID")
        print('user_id:', user_id)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )   

        #获取用户邮箱
        userEmail = request.cookies.get("CUSTOMER_CODE")
        print('userEmail:', userEmail)
        
        if not userEmail:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 解析前端发送的数据
        form_data = await request.form()
        print(f"接收到的表单数据: {form_data}")
        
        # 存储上传结果
        upload_results = []
        
        # 处理上传的文件列表
        # 前端发送的格式是: uploadList[0][files], uploadList[1][files], ...
        upload_list = []
        index = 0
        
        while f"uploadList[{index}][files]" in form_data:
            file = form_data[f"uploadList[{index}][files]"]
            file_info_access_id = form_data.get(f"uploadList[{index}][fileInfoAccessId]", "")
            
            if hasattr(file, 'filename') and file.filename:
                upload_list.append({
                    'file': file,
                    'file_info_access_id': file_info_access_id
                })
            index += 1
        
        print(f"解析到 {len(upload_list)} 个文件需要上传")
        
        # 为每个文件调用3D预览服务
        for upload_item in upload_list:
            file = upload_item['file']
            file_info_access_id = upload_item['file_info_access_id']
            
            try:
                print(f"🔄 处理文件: {file.filename}")
                
                # 调用3D预览服务
                url = "https://api.forface3d.com/forface/viewer/example/uploadModel"
                headers = {
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                    "Connection": "keep-alive",
                    "Origin": "https://viewer.forface3d.com",
                    "Referer": "https://viewer.forface3d.com/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-site",
                    "User-Agent": get_CNC_UserAgent_from_json(),
                    "X-Requested-With": "XMLHttpRequest",
                    "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                    "sec-ch-ua-mobile": "?1",
                    "sec-ch-ua-platform": '"Android"',
                }
                
                # 构建文件数据
                files = {
                    'file': (file.filename, file.file, 'application/octet-stream')
                }
                
                response = requests.post(url, files=files, headers=headers)
                response.raise_for_status()
                
                if response.status_code == 200:
                    response_data = response.json()
                    print(f'3D模型预览响应 ({file.filename}):', response_data)
                    
                    if response_data.get("data") and response_data["data"].get("tokenKey"):
                        tokenKey = response_data["data"]["tokenKey"]
                        preview_url = f'https://viewer.forface3d.com/modelPreview?fileSize={file.size}&fileType=STEP&tokenKey={tokenKey}'
                        
                        # 保存记录到数据库
                        upload_record = Files(
                            user_id=user_id,
                            file_size=file.size // 1024,  # 转换为KB
                            file_name=file.filename,
                            file_path="uploads/"+userEmail+"/"+file.filename,
                            file_info_accessId=file_info_access_id,
                            file_url=preview_url,
                            uploaded_at=datetime.utcnow()
                        )
                        
                        db.add(upload_record)
                        db.commit()
                        db.refresh(upload_record)
                        
                        print(f"✅ 文件记录已保存到数据库，ID: {upload_record.id}")
                        
                        # 添加到结果列表
                        upload_results.append({
                            "id": upload_record.id,
                            "file_name": upload_record.file_name,
                            "file_url": upload_record.file_url,
                            "file_info_accessId": file_info_access_id,
                        })
                    else:
                        print(f"❌ 3D预览服务返回数据格式异常: {response_data}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="3D预览服务返回数据格式异常"
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="获取预览图失败"
                    )
                    
            except Exception as e:
                print(f"❌ 处理文件 {file.filename} 失败: {str(e)}")
                # 继续处理下一个文件，不中断整个流程
                continue
        
        print(f" 文件处理完成，成功处理 {len(upload_results)} 个文件")
        
        return {
            "success": True,
            "message": f"文件上传完成，成功处理 {len(upload_results)} 个文件",
            "data": upload_results,
            "total_files": len(upload_list),
            "successful_files": len(upload_results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 文件上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )


@router.post("/analyze_model")
async def analyze_model(request: Request):
    url = "https://www.jlc-cnc.com/api/cncOrder/model/analyze"
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
    }
    cookies = {
        "acw_tc": "0a0011ba17456384523225986e6f934336f3ea0d76c36c93b75dcc52880e21",
        "SANWEIHOU_SESSION_ID": "1c6e33ec-3d41-4ad2-85df-023ea8c816c8",
        "Hm_lvt_3cfaf02525759f54ef51c0a5b03760a2": "1745638459",
        "HMACCOUNT": "1762F8FBB9913B1F",
        "JLCGROUP_SESSIONID": "c723fa95-62f8-435b-b09b-239f8781d351",
        "JLC_CUSTOMER_CODE": "9246228A",
        "JLC_CNC_SESSION_ID": "f178ab21-4ca4-4402-9873-22b265b56e27",
        "HWWAFSESID": "122d973a87e342b25b",
        "HWWAFSESTIME": "1745638544328",
        "Hm_lpvt_3cfaf02525759f54ef51c0a5b03760a2": "1745639094"
    }
    request_data = await request.json()
    print(f'request_data: {request_data}')
    fileInfoAccessIds = request_data.get("fileInfoAccessIds")
    print(f'fileInfoAccessIds: {fileInfoAccessIds}')
    data = {
        "clientId": request_data.get("clientId"),
        "from": None,
        "fileInfoAccessIds": request_data.get("fileInfoAccessIds")
    }
    print(f'data: {data}')

    try:
        response = requests.post(url, headers=headers, cookies=cookies, json=data)
        response.raise_for_status()
        print(f'JLC-CNC分析模型响应: {response.json()}')
        return response.json()
    except requests.RequestException as e:
        return {"error": f"请求失败: {str(e)}", "status_code": getattr(e.response, 'status_code', 500)}

# 删除上传记录
@router.delete("/history/{file_id}")
async def delete_upload_history(
    request: Request,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """删除上传记录"""
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
        file_id = request.path_params.get("file_id")
        print(f'file_id: {file_id}')
        # 查找记录
        record = db.query(Files).filter(
            Files.id == file_id,
            Files.user_id == user_id
        ).first()
        
        if not record:
            return {"success": "false", "message": "记录不存在"}  
        # 删除数据库记录
        db.delete(record)
        db.commit()
        
        return {"success": "true", "message": "删除成功"}
        
    except Exception as e:
        print(f"删除记录失败: {str(e)}")
        return {"success": "false", "message": "删除失败，请稍后重试"}
 
# 获取文件信息
@router.get("/get_file_info") 
async def get_file_info(
    request: Request,
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
        # 获取文件ID参数 - 使用 query_params 获取 GET 请求的查询参数
        file_id = request.query_params.get("id")
        print(f'file_id: {file_id}')
        # 根据文件id查询订单信息
        fileInfo = db.query(Files).filter(
                Files.id == file_id,
                Files.user_id == user_id
            ).first()
        if not fileInfo:
            return {"success": False, "message": "没有找到文件"}
        
        print('fileInfoAccessId', fileInfo.file_info_accessId)
        return {
            "success": True,
            "message": "获取文件信息成功",
            "data": {
                "file_info_accessId": fileInfo.file_info_accessId,
                "file_name": fileInfo.file_name,
            }
        }
    except Exception as e:
        print(f"获取文件信息失败: {str(e)}")
        return {"success": "false", "message": "获取文件信息失败，请稍后重试"}
    
# 获取分析结果
@router.post("/get_analysis_result")
async def get_analysis_result(
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
        url = "https://www.jlc-cnc.com/api/cncOrder/model/getAnalysisResult"
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
        try:
            # 获取POST请求体中的数据
            request_data = await request.json()
            print(f'request_data: {request_data}')
            
            file_info_accessId = request_data.get("file_info_accessId")
            print(f'file_info_accessId: {file_info_accessId}')
            
            if not file_info_accessId:
                return {"success": False, "message": "缺少文件访问ID参数"}
            
            response = requests.post(url, headers=headers, json=[file_info_accessId])
            response.raise_for_status()
            response_data = response.json()
            print('response', response_data)

            return {
                "success": True,
                "message": "获取分析结果成功",
                "data": response_data
            }
        except requests.RequestException as e:
            print(f"JLC-CNC API请求失败: {str(e)}")
            return {
                "success": False,
                "message": f"JLC-CNC API请求失败: {str(e)}"
            }
        
    except Exception as e:
        print(f"获取分析结果失败: {str(e)}")
        return {"success": False, "message": "获取分析结果失败，请稍后重试"}

# 更新文件信息
@router.post("/update_product_model")
async def update_product_model(
    request: Request,
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
        try:
            # 获取POST请求体中的数据
            request_data = await request.json()
            print(f'request_data: {request_data}')
            
            product_model_accessId = request_data.get("product_model_accessId")
            print(f'product_model_accessId: {product_model_accessId}')
            
            if not product_model_accessId:
                return {"success": False, "message": "缺少产品模型访问编号参数"}
            
            id = request_data.get("id")
            print(f'id: {id}')
            
            if not id:
                return {"success": False, "message": "缺少文件编号参数"}
            
            db.query(Files).filter(Files.id == id).update({"product_model_accessId": product_model_accessId})
            db.commit()
            
            return {"success": True, "message": "更新文件信息成功"}
            
        except requests.RequestException as e:
            print(f"JLC-CNC API请求失败: {str(e)}")
            return {
                "success": False,
                "message": f"JLC-CNC API请求失败: {str(e)}"
            }
        

    except Exception as e:
        print(f"更新文件信息失败: {str(e)}")
        return {"success": False, "message": "更新文件信息失败，请稍后重试"}
