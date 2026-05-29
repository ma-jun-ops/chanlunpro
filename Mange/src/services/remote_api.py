"""
远程Z-Blog用户API封装

用于在创建/删除用户时同步远程数据库
API文档: /home/cl/桌面/final22222/aaaaasssss/
"""

import hashlib
import time
import requests

API_BASE_URL = "http://www.chanlun-diary.com/zb_system/api.php"
USERNAME = "stock_system"
PASSWORD = "ksmDPaQHDbecQWRXpY"
DEFAULT_LEVEL = "4"
REQUEST_TIMEOUT = 15

_token = None
_token_time = 0


def _md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _ensure_login():
    global _token, _token_time
    if _token and time.time() - _token_time < 3600:
        return _token

    login_url = f"{API_BASE_URL}?mod=member&act=login"
    body = {"username": USERNAME, "password": _md5(PASSWORD), "savedate": 365}
    resp = requests.post(login_url, json=body, headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT)
    result = resp.json()
    if result.get("code") != 200:
        raise Exception(f"远程登录失败: {result.get('message')}")

    _token = result["data"]["token"]
    _token_time = time.time()
    return _token


def create_remote_user(username, password):
    """
    在远程Z-Blog创建用户，返回远程用户ID
    """
    token = _ensure_login()

    create_url = f"{API_BASE_URL}?mod=member&act=post&token={token}"
    body = {
        "ID": "0",
        "Level": DEFAULT_LEVEL,
        "Name": username,
        "Password": _md5(password),
        "PasswordRe": _md5(password),
    }
    resp = requests.post(create_url, json=body, headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT)
    result = resp.json()

    if result.get("code") != 200:
        raise Exception(f"远程创建用户失败: {result.get('message')}")

    remote_id = result["data"]["member"]["ID"]
    return remote_id


def delete_remote_user(remote_id):
    """
    在远程Z-Blog删除用户
    """
    token = _ensure_login()

    delete_url = f"{API_BASE_URL}?mod=member&act=delete&id={remote_id}&token={token}"
    resp = requests.get(delete_url, headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT)
    result = resp.json()

    if result.get("code") != 200:
        raise Exception(f"远程删除用户失败: {result.get('message')}")

    return True


def list_remote_user_ids():
    """
    获取远程Z-Blog所有用户的ID集合
    """
    token = _ensure_login()

    list_url = f"{API_BASE_URL}?mod=member&act=list&token={token}"
    resp = requests.get(list_url, headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT)
    result = resp.json()

    if result.get("code") != 200:
        raise Exception(f"远程获取用户列表失败: {result.get('message')}")

    return {u["ID"] for u in result["data"]["list"]}
