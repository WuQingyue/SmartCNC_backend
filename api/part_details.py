from fastapi import APIRouter, Request, HTTPException, status, Depends
from utils.database import get_db
from utils.session import get_session, SessionManager
from models.part_details import PartDetails
from models.file import Files
from sqlalchemy.orm import Session
from typing import Optional

router = APIRouter()

# 创建零件详情
@router.post("/part-details")
async def create_part_details(
    request: Request,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID
        user_id = session.get("user_id")
        if not user_id:
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                except ValueError:
                    user_id = None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 获取请求数据
        request_data = await request.json()
        
        # 验证必要字段
        required_fields = ['file_id']
        for field in required_fields:
            if not request_data.get(field):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"缺少必要字段: {field}"
                )
        
        # 验证文件是否属于当前用户
        file_id = request_data['file_id']
        file = db.query(Files).filter(
            Files.id == file_id,
            Files.user_id == user_id
        ).first()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权限访问"
            )
        
        # 使用零件详情模型创建记录
        part_details = PartDetails.create_part_details(
            db_session=db,
            file_id=file_id,
            **request_data
        )
        
        return {
            "success": True,
            "message": "零件详情创建成功",
            "data": part_details.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 创建零件详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

# 获取零件详情
@router.get("/part-details/{part_details_id}")
async def get_part_details(
    part_details_id: int,
    request: Request,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID
        user_id = session.get("user_id")
        if not user_id:
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                except ValueError:
                    user_id = None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 查询零件详情，确保只能访问自己的文件
        part_details = db.query(PartDetails).join(Files).filter(
            PartDetails.id == part_details_id,
            Files.user_id == user_id
        ).first()
        
        if not part_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="零件详情不存在或无权限访问"
            )
        
        return {
            "success": True,
            "message": "获取零件详情成功",
            "data": part_details.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取零件详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

# 根据文件ID获取零件详情
@router.get("/part-details/file/{file_id}")
async def get_part_details_by_file(
    file_id: int,
    request: Request,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID
        user_id = session.get("user_id")
        if not user_id:
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                except ValueError:
                    user_id = None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 验证文件是否属于当前用户
        file = db.query(Files).filter(
            Files.id == file_id,
            Files.user_id == user_id
        ).first()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权限访问"
            )
        
        # 使用零件详情模型查询
        part_details = PartDetails.get_part_details_by_file(db, file_id)
        
        if not part_details:
            return {
                "success": False,
                "message": "该文件暂无零件详情",
                "data": None
            }
        
        return {
            "success": True,
            "message": "获取零件详情成功",
            "data": part_details.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取零件详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

# 更新零件详情
@router.put("/part-details/{part_details_id}")
async def update_part_details(
    part_details_id: int,
    request: Request,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID
        user_id = session.get("user_id")
        if not user_id:
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                except ValueError:
                    user_id = None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 查询零件详情，确保只能修改自己的文件
        part_details = db.query(PartDetails).join(Files).filter(
            PartDetails.id == part_details_id,
            Files.user_id == user_id
        ).first()
        
        if not part_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="零件详情不存在或无权限修改"
            )
        
        # 获取请求数据
        request_data = await request.json()
        
        # 更新字段
        for field, value in request_data.items():
            if hasattr(part_details, field):
                setattr(part_details, field, value)
        
        # 如果更新了价格相关字段，重新计算总价
        price_fields = ['material_cost', 'engineering_cost', 'clamping_cost', 
                       'processing_cost', 'expedited_price', 'surface_cost', 'quantity']
        if any(field in request_data for field in price_fields):
            part_details.update_pricing(db)
        else:
            db.commit()
        
        db.refresh(part_details)
        
        return {
            "success": True,
            "message": "零件详情更新成功",
            "data": part_details.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 更新零件详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

# 获取零件详情列表（按材质筛选）
@router.get("/part-details")
async def get_part_details_list(
    material: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 20,
    offset: int = 0,
    request: Request = None,
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，请重新登录"
            )
        
        # 获取用户ID
        user_id = session.get("user_id")
        if not user_id:
            customerid = request.cookies.get("CUSTOMERID")
            if customerid:
                try:
                    user_id = int(customerid)
                except ValueError:
                    user_id = None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效，请重新登录"
            )
        
        # 构建查询条件
        query = db.query(PartDetails).join(Files).filter(Files.user_id == user_id)
        
        if material:
            query = query.filter(PartDetails.material == material)
        
        if min_price is not None and max_price is not None:
            query = query.filter(
                PartDetails.total_price >= min_price,
                PartDetails.total_price <= max_price
            )
        
        # 执行查询
        part_details_list = query.offset(offset).limit(limit).all()
        
        # 转换为字典格式
        result_list = [part_details.to_dict() for part_details in part_details_list]
        
        return {
            "success": True,
            "message": "获取零件详情列表成功",
            "data": result_list,
            "total": len(result_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取零件详情列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )
