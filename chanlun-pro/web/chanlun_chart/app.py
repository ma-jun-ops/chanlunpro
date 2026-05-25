import pymysql
pymysql.install_as_MySQLdb()
import pathlib
import sys
import os
import time
import traceback
import webbrowser
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.wsgi import WSGIContainer
from flask_mysqldb import MySQL
from flask import Flask, render_template, request, jsonify, session, redirect, make_response

from werkzeug.security import generate_password_hash, check_password_hash
from cl_app import create_app
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64

# 新增：获取本机局域网IP的工具函数
import socket
def get_local_ip():
    """获取本机局域网地址"""
    try:
        # 创建UDP连接（不实际连接）来获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"



# def log_startup(msg):
#     """记录启动日志到文件"""
#     try:
#         elapsed = time.time() - _startup_time
#         log_line = f"[{elapsed:.2f}s] {msg}\n"
#         with open(_startup_log_file, "a", encoding="utf-8") as f:
#             f.write(log_line)
#     except:
#         pass
#
# # 清空旧日志文件
# try:
#     with open(_startup_log_file, "w", encoding="utf-8") as f:
#         f.write("=== 应用启动日志 ===\n")
# except:
#     pass



import chanlun.encodefix
from chanlun import config



# 路径配置
src_path = pathlib.Path(__file__).parent.parent / ".." / "src"
sys.path.append(str(src_path))
web_server_path = pathlib.Path(__file__).parent
sys.path.append(str(web_server_path))

is_wpf_launcher = False
try:
    if "wpf_launcher" in sys.argv:
        is_wpf_launcher = True
except Exception:
    pass


# 全局验证码字符库
CAPTCHA_CHARS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W',
                 'X', 'Y', 'Z', '2', '3', '4', '5', '6', '7', '8', '9']

if __name__ == "__main__":
    try:

        app = create_app()

        app.secret_key = 'chanlun_secure_login_2024'

        # ==========================================
        # 【终极方案：强制临时会话】
        # ==========================================
        app.config['SESSION_COOKIE_NAME'] = 'chanlun_session_id'
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

        # 新增：允许跨域（局域网访问需要）
        @app.after_request
        def add_cors_headers(response):
            # 允许所有局域网地址访问
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response

        # 核心：每次请求后强制设置 Cookie 为临时（不设置过期时间）
        @app.after_request
        def force_temporary_session(response):
            # 只有登录后才操作
            if 'logged_in' in session:
                # 重新设置 Cookie，不设置 expires/max_age，浏览器关闭即删
                response.set_cookie(
                    app.config['SESSION_COOKIE_NAME'],
                    request.cookies.get(app.config['SESSION_COOKIE_NAME'], ''),
                    httponly=True,
                    samesite='Lax',
                    max_age=None  # 关键：None 表示临时 Cookie
                )
            return response

        # --- MySQL 配置 ---
        # app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost:3306/chanlun_klines?charset=utf8mb4'
        # app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        # 创建 SQLAlchemy 实例
        # db = SQLAlchemy(app)
        app.config['MYSQL_HOST'] = '127.0.0.1'
        app.config['MYSQL_USER'] = 'root'
        app.config['MYSQL_PASSWORD'] = '123456'
        app.config['MYSQL_DB'] = 'chanlun_klines'
        app.config['MYSQL_CHARSET'] = 'utf8mb4'
        mysql = MySQL(app)
        # ==========================================
        # 全局登录校验
        # ==========================================
        @app.before_request
        def global_login_check():
            path = request.path

            special_white_list = [
                '/my_login_page',
                '/api/my_captcha',
                '/api/my_login',
                '/my_logout'
            ]
            if path.startswith('/static'):
                return None

            if path in special_white_list:
                return None

            if 'logged_in' not in session:
                return redirect('/my_login_page')

            return None

        # --- 登录页面 ---
        @app.route('/my_login_page', methods=['GET'])
        def my_login_page():
            if 'logged_in' in session:
                return redirect('/')
            return render_template('login.html')

        # --- 验证码 ---
        @app.route('/api/my_captcha', methods=['GET'])
        def api_my_captcha():
            try:
                selected_words = random.sample(CAPTCHA_CHARS, 4)
                width, height = 300, 150
                image = Image.new('RGB', (width, height), (255, 255, 255))
                draw = ImageDraw.Draw(image)

                for _ in range(5):
                    x1 = random.randint(0, width)
                    y1 = random.randint(0, height)
                    x2 = random.randint(0, width)
                    y2 = random.randint(0, height)
                    draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=2)

                try:
                    font_paths = ["arial.ttf", "simhei.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
                    font = None
                    for fp in font_paths:
                        try:
                            font = ImageFont.truetype(fp, 48)
                            break
                        except:
                            continue
                    if not font:
                        font = ImageFont.load_default()
                except:
                    font = ImageFont.load_default()

                word_data = []
                for i, word in enumerate(selected_words):
                    x = 40 + i * 65 + random.randint(-10, 10)
                    y = 45 + random.randint(-10, 10)
                    color = (random.randint(30, 100), random.randint(30, 100), random.randint(30, 100))
                    draw.text((x, y), word, font=font, fill=color)

                    try:
                        bbox = draw.textbbox((x, y), word, font=font)
                    except AttributeError:
                        w, h = draw.textsize(word, font=font)
                        bbox = (x, y, x + w, y + h)

                    word_data.append({
                        'word': word,
                        'x': (bbox[0] + bbox[2]) / 2,
                        'y': (bbox[1] + bbox[3]) / 2
                    })

                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                session['captcha_answer'] = [w['word'] for w in word_data]

                return jsonify({
                    'code': 1,
                    'image': f'data:image/png;base64,{img_str}',
                    'prompt': f"请依次点击：{' '.join(selected_words)}",
                    'words': word_data
                })
            except Exception as e:
                print(f"验证码错误：{e}")
                traceback.print_exc()
                return jsonify({'code': 0, 'msg': '验证码生成失败'}), 500

        # --- 登录接口 ---
        @app.route('/api/my_login', methods=['POST'])
        def api_my_login():
            try:
                data = request.json or {}
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                clicked = data.get('clicked', [])

                if not username or not password:
                    return jsonify({'code': 0, 'msg': '用户名/密码不能为空'})

                if 'captcha_answer' not in session:
                    return jsonify({'code': 0, 'msg': '验证码已过期，请刷新'})

                if clicked != session['captcha_answer']:
                    return jsonify({'code': 0, 'msg': '验证码错误'})

                cur = mysql.connection.cursor()
                cur.execute("SELECT id, username, password, is_active FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                cur.close()

                if user:
                    user_id = user[0]
                    db_username = user[1]
                    stored_password_hash = user[2]
                    is_active = user[3]

                    if check_password_hash(stored_password_hash, password):
                        if is_active == 0:
                            return jsonify({'code': 0, 'msg': '该用户已被禁用'})
                        session['logged_in'] = True
                        session['username'] = db_username
                        session.pop('captcha_answer', None)

                        # 登录成功时，强制生成响应并设置临时 Cookie
                        resp = jsonify({'code': 1, 'msg': '登录成功', 'url': '/'})
                        resp.set_cookie(
                            app.config['SESSION_COOKIE_NAME'],
                            request.cookies.get(app.config['SESSION_COOKIE_NAME'], ''),
                            httponly=True,
                            samesite='Lax',
                            max_age=None  # 临时
                        )
                        return resp
                    else:
                        return jsonify({'code': 0, 'msg': '用户名或密码错误'})
                else:
                    return jsonify({'code': 0, 'msg': '用户名或密码错误'})

            except Exception as e:
                print(f"登录错误：{e}")
                traceback.print_exc()
                return jsonify({'code': 0, 'msg': '服务器内部错误'}), 500

        # --- 退出登录 ---
        @app.route('/my_logout', methods=['GET'])
        def my_logout():
            session.clear()
            resp = redirect('/my_login_page')
            # 彻底删除 Cookie
            resp.delete_cookie(app.config['SESSION_COOKIE_NAME'])
            return resp

        # ==========================================
        # 启动服务 - 支持多进程模式
        # ==========================================

        
        # 获取本机局域网IP
        local_ip = get_local_ip()
        # 绑定到0.0.0.0（所有网络接口），而不是仅本地回环
        bind_ip = "0.0.0.0"
        
        # 固定端口号配置（12001-12004）
        # 可以通过环境变量 CHANLUN_PORT 设置，默认为12001
        bind_port = int(os.environ.get('CHANLUN_PORT', 12001))

        
        # CPU绑定功能（使用psutil）
        # try:
        #     import psutil
        #     current_process = psutil.Process(os.getpid())
        #     cpu_count = psutil.cpu_count(logical=False)
        #
        #     # 根据端口号计算CPU核心（12001->0, 12002->1, 12003->2, 12004->3）
        #     cpu_id = (bind_port - 12001) % cpu_count
        #     if cpu_id < 0 or cpu_id >= cpu_count:
        #         cpu_id = 0
        #
        #     # 绑定到指定CPU核心
        #     current_process.cpu_affinity([cpu_id])

        #     print(f"进程已绑定到CPU核心: {cpu_id}")
        #     print(f"当前CPU亲和性: {current_process.cpu_affinity()}")
        # except Exception as e:

        #     print(f"CPU绑定失败: {e}")
        #     print(f"将以默认模式运行")

        # 开启调试模式
        # app.debug = False

        s = HTTPServer(WSGIContainer(app, executor=ThreadPoolExecutor(20)))
        s.bind(bind_port, bind_ip)  # 修改：绑定到0.0.0.0

        print("\n" + "=" * 60)
        print("【外部模板版启动成功 - 局域网可访问】")
        print(f"端口号: {bind_port}")
        print(f"本机访问：http://127.0.0.1:{bind_port}/my_login_page")
        print(f"局域网访问：http://{local_ip}:{bind_port}/my_login_page")
        print("【终极模式：关闭页面强制登出】")
        print("=" * 60 + "\n")

        s.start(1)

        # 默认打开本机地址
        if len(sys.argv) < 2 or sys.argv[1] != "nobrowser":
            if bind_port ==12001:
                webbrowser.open(f"http://127.0.0.1:{bind_port}/my_login_page")

        IOLoop.instance().start()

    except Exception as e:
        print(f"启动失败：{e}")
        traceback.print_exc()
        if is_wpf_launcher is False:
            input("出现异常，按回车键退出")
