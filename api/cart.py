from fastapi import APIRouter, Request, HTTPException, status, Depends
from utils.database import get_db
from utils.session import get_session, SessionManager
from models.cart_item import CartItem
from models.part_details import PartDetails
from models.file import Files
from sqlalchemy.orm import Session
from typing import Optional

router = APIRouter()
# 将数据加入到购物车
@router.post("/add_to_cart")
async def add_to_cart(
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
        
        data = await request.json()
        print('add_to_cart中的data:', data)
        
        for item in data:
            # 查找文件记录
            file_record = db.query(Files).filter(Files.id == item['upload_history_id']).first()
            if not file_record:
                return {"success": False, "msg": "未找到文件记录"}
            
            # 更新文件记录中的访问ID
            if 'productModelAccessId' in item:
                file_record.product_model_accessId = item['productModelAccessId']
            if 'roughnessAccessId' in item:
                file_record.roughnessAccessId = item['roughnessAccessId']
            if 'toleranceAccessId' in item:
                file_record.toleranceAccessId = item['toleranceAccessId']
            
            db.commit()
            db.refresh(file_record)
            
            # 创建零件详情记录
            part_details = PartDetails(
                file_id=item['upload_history_id'],
                record_type='cart',  # 必需字段：标记为购物车相关
                source_id=None,  # 购物车项ID将在创建购物车项后设置
                material_access_id=item.get('materialAccessId'),
                material=item.get('material'),
                quantity=item.get('quantity', 1),
                tolerance=item.get('tolerance'),
                tolerance_access_id=item.get('toleranceAccessId'),
                roughness=item.get('roughness'),
                roughness_access_id=item.get('roughnessAccessId'),
                has_thread=item.get('hasThread', False),
                has_assembly=item.get('hasAssembly', False),
                length=float(item.get('sizeX')) if item.get('sizeX') else None,
                width=float(item.get('sizeY')) if item.get('sizeY') else None,
                height=float(item.get('sizeZ')) if item.get('sizeZ') else None,
                surface_area=float(item.get('modelSurfaceArea')) if item.get('modelSurfaceArea') else None,
                volume=float(item.get('modelVolume')) if item.get('modelVolume') else None,
                surface_treatment=item.get('surfaceTreatment'),
                treatment1_option=item.get('selectedTreatment'),
                treatment1_color=item.get('selectedColor'),
                treatment1_gloss=item.get('glossiness'),
                treatment1_drawing=item.get('uploadedFileName'),
                treatment2_option=item.get('selectedTreatment2'),
                treatment2_color=item.get('selectedColor2'),
                treatment2_gloss=item.get('glossiness2'),
                treatment2_drawing=item.get('uploadedFileName2'),
                craft_access_id1=item.get('craftAccessId1'),
                craft_attribute_color_access_ids1=item.get('craftAttributeColorAccessIds1'),
                craft_attribute_glossiness_access_ids1=item.get('craftAttributeGlossinessAccessIds1'),
                craft_attribute_file_access_ids1=item.get('craftAttributeFileAccessIds1'),
                craft_access_id2=item.get('craftAccessId2'),
                craft_attribute_color_access_ids2=item.get('craftAttributeColorAccessIds2'),
                craft_attribute_glossiness_access_ids2=item.get('craftAttributeGlossinessAccessIds2'),
                craft_attribute_file_access_ids2=item.get('craftAttributeFileAccessIds2'),
                # 价格相关字段
                material_cost=float(item.get('materialCost')) if item.get('materialCost') else None,
                engineering_cost=float(item.get('engineeringCost')) if item.get('engineeringCost') else None,
                clamping_cost=float(item.get('clampingCost')) if item.get('clampingCost') else None,
                processing_cost=float(item.get('processingCost')) if item.get('processingCost') else None,
                expedited_price=float(item.get('expeditedPrice')) if item.get('expeditedPrice') else None,
                surface_cost=float(item.get('surfaceCost')) if item.get('surfaceCost') else None,
                unit_price=float(item.get('pricePerUnit')) if item.get('pricePerUnit') else None,
                total_price=float(item.get('totalPrice')) if item.get('totalPrice') else None,
                tax_fee=float(item.get('taxPrice')) if item.get('taxPrice') else None
            )
            
            try:
                db.add(part_details)
                db.commit()
                db.refresh(part_details)
            except Exception as e:
                db.rollback()
                print("插入零件详情失败，错误信息：", e)
                return {"success": False, "msg": "创建零件详情失败"}
            
            # 处理交付日期 - 直接存储字符串
            expected_delivery_date = item.get('EstimatedDeliveryTime')
            
            # 创建购物车项目
            cart_item = CartItem(
                user_id=user_id,
                part_details_id=part_details.id,
                quantity=item.get('quantity', 1),
                expected_delivery_date=expected_delivery_date
            )
            
            try:
                db.add(cart_item)
                db.commit()
                db.refresh(cart_item)
                
                # 更新零件详情的source_id为购物车项ID
                part_details.source_id = cart_item.id
                db.commit()
                db.refresh(part_details)
                
            except Exception as e:
                db.rollback()
                print("插入购物车项目失败，错误信息：", e)
                return {"success": False, "msg": "添加到购物车失败"}
        
        return {"success": True, "msg": "成功添加到购物车"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 添加到购物车失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

# 获取购物车数据
@router.get("/get_cart")
async def get_cart(request: Request, session: SessionManager = Depends(get_session), db: Session = Depends(get_db)):
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
        
        # 查询购物车项目
        cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
        if not cart_items:
            return {"success": True, "msg": "购物车为空", "result": []}
        
        result = []
        for cart_item in cart_items:
            # 获取零件详情
            part_details = db.query(PartDetails).filter(PartDetails.id == cart_item.part_details_id).first()
            if not part_details:
                continue
            
            # 获取文件信息
            file_info = db.query(Files).filter(Files.id == part_details.file_id).first()
            
            # 构建返回数据
            cart_data = {
                "cart": {
                    "id": cart_item.id,
                    "quantity": cart_item.quantity,
                    "expected_delivery_date": cart_item.expected_delivery_date,
                    "price": float(part_details.total_price) if part_details.total_price else 0
                },
                "part_details": {
                    "id": part_details.id,
                    "material": part_details.material,
                    "material_access_id": part_details.material_access_id,
                    "surface_treatment": part_details.surface_treatment,
                    "treatment1_option": part_details.treatment1_option,
                    "treatment1_color": part_details.treatment1_color,
                    "treatment1_gloss": part_details.treatment1_gloss,
                    "treatment1_drawing": part_details.treatment1_drawing,
                    "treatment2_option": part_details.treatment2_option,
                    "treatment2_color": part_details.treatment2_color,
                    "treatment2_gloss": part_details.treatment2_gloss,
                    "treatment2_drawing": part_details.treatment2_drawing,
                    "quantity": part_details.quantity,
                    "tolerance": part_details.tolerance,
                    "tolerance_access_id": part_details.tolerance_access_id,
                    "roughness": part_details.roughness,
                    "roughness_access_id": part_details.roughness_access_id,
                    "has_thread": part_details.has_thread,
                    "has_assembly": part_details.has_assembly,
                    "length": float(part_details.length) if part_details.length else None,
                    "width": float(part_details.width) if part_details.width else None,
                    "height": float(part_details.height) if part_details.height else None,
                    "volume": float(part_details.volume) if part_details.volume else None,
                    "surface_area": float(part_details.surface_area) if part_details.surface_area else None,
                    "craft_access_id1": part_details.craft_access_id1,
                    "craft_attribute_color_access_ids1": part_details.craft_attribute_color_access_ids1,
                    "craft_attribute_glossiness_access_ids1": part_details.craft_attribute_glossiness_access_ids1,
                    "craft_attribute_file_access_ids1": part_details.craft_attribute_file_access_ids1,
                    "craft_access_id2": part_details.craft_access_id2,
                    "craft_attribute_color_access_ids2": part_details.craft_attribute_color_access_ids2,
                    "craft_attribute_glossiness_access_ids2": part_details.craft_attribute_glossiness_access_ids2,
                    "craft_attribute_file_access_ids2": part_details.craft_attribute_file_access_ids2,
                    "total_price": float(part_details.total_price) if part_details.total_price else 0,
                    "unit_price": float(part_details.unit_price) if part_details.unit_price else 0,
                },
                "file_info": {
                    "id": file_info.id if file_info else None,
                    "file_name": file_info.file_name if file_info else None,
                    "file_url": file_info.file_url if file_info else None,
                    "product_model_accessId": file_info.product_model_accessId if file_info else None,
                    "file_info_accessId": file_info.file_info_accessId if file_info else None
                } if file_info else None
            }
            
            result.append(cart_data)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        print(f"❌ 获取购物车失败: {str(e)}")
        return {"success": False, "msg": "获取购物车失败"}

# 删除购物车项目
@router.delete("/delete_cart_item/{cart_item_id}")
async def delete_cart_item(
    cart_item_id: int,
    request: Request, 
    session: SessionManager = Depends(get_session),
    db: Session = Depends(get_db)
    ):
    """
    删除购物车中的指定项目
    
    Args:
        cart_item_id: 购物车项目ID
        request: FastAPI请求对象
        session: 会话管理器
        db: 数据库会话
    
    Returns:
        dict: 删除结果
    """
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
        
        # 查找购物车项目
        cart_item = db.query(CartItem).filter(
            CartItem.id == cart_item_id,
            CartItem.user_id == user_id
        ).first()
        
        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="购物车项目不存在或无权限访问"
            )
        
        # 获取关联的零件详情ID，用于后续清理
        part_details_id = cart_item.part_details_id
        
        # 删除购物车项目
        db.delete(cart_item)
        
        # 直接删除关联的零件详情（不再检测引用关系）
        if part_details_id:
            part_details = db.query(PartDetails).filter(PartDetails.id == part_details_id).first()
            if part_details:
                db.delete(part_details)
                print(f"✅ 零件详情删除成功: ID={part_details_id}")
        
        db.commit()
        
        print(f"✅ 购物车项目删除成功: ID={cart_item_id}, 用户ID={user_id}")
        
        return {
            "success": True, 
            "msg": "购物车项目删除成功",
            "deleted_item_id": cart_item_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 删除购物车项目失败: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


