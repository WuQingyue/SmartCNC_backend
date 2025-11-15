# app/utils/ga4_client.py
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest, RunRealtimeReportRequest
from google.oauth2 import service_account
import os
from datetime import datetime, timedelta
from typing import Optional

# 配置你的 GA4 property_id 和密钥路径
PROPERTY_ID = "490508682"
KEY_PATH = os.path.join(os.path.dirname(__file__), "../utils/service-account.json")

def get_ga4_client():
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    client = BetaAnalyticsDataClient(credentials=credentials)
    return client

def get_today_stats(start_date_str: Optional[str] = None, end_date_str: Optional[str] = None):
    """
    获取指定日期范围的统计数据。
    如果未提供日期，则默认为今天。
    """
    client = get_ga4_client()

    # 如果没有提供 date_str，则默认查询今天的数据
    if not start_date_str and not end_date_str:
        start_date = "today"
        end_date = "today"
    elif start_date_str and end_date_str:
        start_date = start_date_str
        end_date = end_date_str
    else:
        # 如果只提供了一个日期，使用同一个日期
        date_str = start_date_str or end_date_str
        start_date = date_str
        end_date = date_str

    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[],
        metrics=[
            Metric(name="totalUsers"),
            Metric(name="transactions"),
            Metric(name="purchaseRevenue")
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)]
    )
    response = client.run_report(request)
    print('获取统计response', response)

    # 如果查询的日期没有数据，GA会返回空的 rows
    if not response.rows:
        return {
            "visitors": 0,
            "orders": 0,
            "revenue": 0.0
        }

    row = response.rows[0]
    return {
        "visitors": int(row.metric_values[0].value),
        "orders": int(row.metric_values[1].value),
        "revenue": float(row.metric_values[2].value)
    }

def get_amount_data(start_date: str, end_date: str):
    """
    获取指定日期范围的每小时实付金额。
    """
    client = get_ga4_client()
    
    # 检查是否为日期范围
    is_date_range = start_date != end_date
    
    if is_date_range:
        # 日期范围模式：按日期分组
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="purchaseRevenue")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)]
        )
        response = client.run_report(request)
        print('获取金额response', response)

        # 将结果处理成前端易于使用的格式 [{date: "20240101", amount: 123.45}, ...]
        amounts_by_date = []
        for row in response.rows:
            date = row.dimension_values[0].value
            amount = float(row.metric_values[0].value)
            amounts_by_date.append({"date": date, "amount": amount})
            
        return { "amountsByDate": amounts_by_date }
    else:
        # 单日模式：按小时分组
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="hour")],
            metrics=[Metric(name="purchaseRevenue")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)]
        )
        response = client.run_report(request)
        print('获取金额response', response)

        # 将结果处理成前端易于使用的格式 [{hour: 0, amount: 123.45}, ...]
        amounts_by_hour = []
        for row in response.rows:
            hour = int(row.dimension_values[0].value)
            amount = float(row.metric_values[0].value)
            amounts_by_hour.append({"hour": hour, "amount": amount})
            
        return { "amountsByHour": amounts_by_hour }

def get_active_users_last_30_minutes():
    client = get_ga4_client()
    from google.analytics.data_v1beta.types import RunRealtimeReportRequest, Metric, Dimension

    request = RunRealtimeReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="minutesAgo")],
        metrics=[Metric(name="activeUsers")]
    )
    response = client.run_realtime_report(request)
    active_users_arr = [0] * 30

    for row in response.rows:
        minutes_ago = int(row.dimension_values[0].value)
        if 0 <= minutes_ago < 30:
            active_users_arr[minutes_ago] = int(row.metric_values[0].value)

    return {"activeUsersLast30Minutes": active_users_arr}

def get_active_users_last_30_minutes_by_country():
    client = get_ga4_client()
    from google.analytics.data_v1beta.types import RunRealtimeReportRequest, Metric, Dimension

    request = RunRealtimeReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="country"), Dimension(name="minutesAgo")],
        metrics=[Metric(name="activeUsers")]
    )
    response = client.run_realtime_report(request)

    # 统计过去30分钟每个国家的活跃用户数
    country_data = {}
    for row in response.rows:
        country = row.dimension_values[0].value
        minutes_ago = int(row.dimension_values[1].value)
        active_users = int(row.metric_values[0].value)
        if 0 <= minutes_ago < 30:
            country_data.setdefault(country, 0)
            country_data[country] += active_users

    # 返回格式：[{country: "China", activeUsers: 5}, ...]
    result = [{"country": k, "activeUsers": v} for k, v in country_data.items()]
    # 可选：按活跃用户数降序排序
    result.sort(key=lambda x: x["activeUsers"], reverse=True)
    return {"activeUsersLast30MinutesByCountry": result}

def get_active_users_by_platform_and_country():
    """
    获取过去30分钟内，按平台和国家/地区细分的活跃用户数据。
    """
    client = get_ga4_client()
    request = RunRealtimeReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[
            Dimension(name="customUser:source_platform"),
            Dimension(name="country"),
            Dimension(name="minutesAgo")
        ],
        metrics=[Metric(name="activeUsers")]
    )
    response = client.run_realtime_report(request)

    # 使用字典来聚合数据
    # 结构: { "platform_name": { "totalUsers": X, "countries": { "country_name": Y, ... } } }
    platform_data = {}

    for row in response.rows:
        platform = row.dimension_values[0].value or "unknown" # 如果平台为空，则标记为 "unknown"
        country = row.dimension_values[1].value
        minutes_ago = int(row.dimension_values[2].value)
        active_users = int(row.metric_values[0].value)

        if 0 <= minutes_ago < 30:
            # 初始化平台数据
            if platform not in platform_data:
                platform_data[platform] = {"totalUsers": 0, "countries": {}}
            
            # 累加总用户数
            platform_data[platform]["totalUsers"] += active_users
            
            # 累加国家用户数
            country_data = platform_data[platform]["countries"]
            country_data[country] = country_data.get(country, 0) + active_users

    # 将聚合后的数据转换为前端期望的数组格式
    # 结构: { "platform_name": { "totalUsers": X, "countries": [ { "country": "Y", "activeUsers": Z } ] } }
    result = {}
    for platform, data in platform_data.items():
        countries_list = [{"country": c, "activeUsers": u} for c, u in data["countries"].items()]
        # 按用户数对国家列表进行降序排序
        countries_list.sort(key=lambda x: x["activeUsers"], reverse=True)
        result[platform] = {
            "totalUsers": data["totalUsers"],
            "countries": countries_list
        }
        
    return {"activeUsersByPlatform": result}

def get_visitor_data(start_date: str, end_date: str):
    """
    获取指定日期范围的每小时访客数据，按平台分组。
    这对应于GA4探索中的 日期+时点(YYYYMMDDhh)维度 和 用户总数指标。
    """
    client = get_ga4_client()

    # 检查是否为日期范围
    is_date_range = start_date != end_date
    
    if is_date_range:
        # 日期范围模式：按日期和平台分组
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[
                Dimension(name="date"),  # 使用 'date' 维度获取每日数据
                Dimension(name="customUser:source_platform")  # 添加平台维度
            ],
            metrics=[Metric(name="totalUsers")], # 'totalUsers' 对应"用户总数"
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)] # 限制在所选日期范围
        )
        response = client.run_report(request)
        print('获取日期访客量数据response', response)

        # 将结果处理成前端易于使用的格式，按平台分组
        platform_data = {}
        for row in response.rows:
            # dimension_values[0] 对应 'date'
            date = row.dimension_values[0].value
            # dimension_values[1] 对应 'platform'
            platform = row.dimension_values[1].value or "unknown"
            # metric_values[0] 对应 'totalUsers'
            count = int(row.metric_values[0].value)
            
            if platform not in platform_data:
                platform_data[platform] = []
            platform_data[platform].append({"date": date, "count": count})

        # 转换为前端期望的格式
        visitors_by_platform = []
        for platform, data in platform_data.items():
            visitors_by_platform.append({
                "platform": platform,
                "data": data
            })

        return { "visitorsByPlatform": visitors_by_platform }
    else:
        # 单日模式：按小时和平台分组
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[
                Dimension(name="hour"),  # 使用 'hour' 维度获取每小时数据
                Dimension(name="customUser:source_platform")  # 添加平台维度
            ],
            metrics=[Metric(name="activeUsers")], # 'activeUsers' 对应"用户总数"
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)] # 限制在所选日期
        )
        response = client.run_report(request)
        print('获取时段访客量数据response', response)

        # 将结果处理成前端易于使用的格式，按平台分组
        platform_data = {}
        for row in response.rows:
            # dimension_values[0] 对应 'hour'
            hour = int(row.dimension_values[0].value)
            # dimension_values[1] 对应 'platform'
            platform = row.dimension_values[1].value or "unknown"
            # metric_values[0] 对应 'activeUsers'
            count = int(row.metric_values[0].value)
            
            if platform not in platform_data:
                platform_data[platform] = []
            platform_data[platform].append({"hour": hour, "count": count})

        # 转换为前端期望的格式
        visitors_by_platform = []
        for platform, data in platform_data.items():
            visitors_by_platform.append({
                "platform": platform,
                "data": data
            })

        return { "visitorsByPlatform": visitors_by_platform }

def get_user_source_platform_data(start_date, end_date):
    client = get_ga4_client()
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="customUser:source_platform")],  # 注意用 customUser: 前缀
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)]
    )
    response = client.run_report(request)
    # 统计每个平台的访客数
    result = []
    for row in response.rows:
        platform = row.dimension_values[0].value
        users = int(row.metric_values[0].value)
        result.append({"source_platform": platform, "activeUsers": users})
    return {"userSourcePlatformData": result}
