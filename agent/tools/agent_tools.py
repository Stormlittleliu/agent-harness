import csv
import json
import os
import random

from langchain_core.tools import tool

from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

rag = RagSummarizeService()

user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010",]
month_arr = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
             "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", ]

# 外部使用记录缓存：{user_id: {month: {字段: 值}}}
external_data = {}


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)


@tool(description="重置指定设备（高风险操作，会清除设备配置，需要人工确认）")
def reset_device(device_id: str) -> str:
    """模拟高风险操作，用于演示 human-in-the-loop 审批。"""
    print(f"[SIDE EFFECT] reset_device executed: {device_id}")
    return f"设备 {device_id} 已重置（模拟操作）"


@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="获取用户的ID，以纯字符串形式返回")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return random.choice(month_arr)


def generate_external_data():
    """把 records.csv 读入内存，结构为 {user_id: {month: {特征/效率/耗材/对比}}}。"""
    if external_data:
        return

    external_data_path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = (row.get("用户ID") or "").strip()
            month = (row.get("时间") or "").strip()
            if not user_id or not month:
                continue

            external_data.setdefault(user_id, {})[month] = {
                "特征": (row.get("特征") or "").strip(),
                "效率": (row.get("清洁效率") or "").strip(),
                "耗材": (row.get("耗材") or "").strip(),
                "对比": (row.get("对比") or "").strip(),
            }


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以JSON字符串形式返回，如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    try:
        return json.dumps(external_data[user_id][month], ensure_ascii=False)
    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}在{month}的使用记录数据")
        return ""
