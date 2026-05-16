"""
路由处理模块

主要功能：
- 定义所有Flask路由蓝图（Blueprint）
- 处理用户认证、用户管理、股票关注、仓位设置、涨跌幅展示等请求
- 管理登录状态和跨域请求

路由蓝图说明：
- auth_bp: 认证相关路由（登录、登出、登录检查中间件）
- user_bp: 用户管理路由（注册、删除、批量创建、导出等）
- follow_bp: 股票关注路由（添加关注、删除关注、查看列表）
- position_bp: 仓位设置路由（查看和修改仓位百分比）
- change_bp: 涨跌幅展示路由（查看涨跌幅数据、手动触发计算）


"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from werkzeug.security import generate_password_hash
import re
import json
import os
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.pool import QueuePool
from db.database import get_stock_db_uri

# ==================== 路由蓝图定义 ====================
auth_bp = Blueprint('auth', __name__)      # 认证相关路由
user_bp = Blueprint('user', __name__)      # 用户管理路由
follow_bp = Blueprint('follow', __name__)  # 股票关注路由
position_bp = Blueprint('position', __name__)  # 仓位设置路由
change_bp = Blueprint('change', __name__)  # 涨跌幅展示路由

# ==================== 登录凭据配置 ====================
LOGIN_USERNAME = 'qwer'
LOGIN_PASSWORD = '753951'

# ==================== 仓位设置文件路径 ====================
POSITION_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'position_settings.json')

# ==================== 股票数据库连接配置 ====================
stock_db_uri = get_stock_db_uri()
stock_engine = create_engine(stock_db_uri, poolclass=QueuePool, pool_recycle=3600, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_timeout=10)
StockSession = sessionmaker(bind=stock_engine)
stock_db = scoped_session(StockSession)

# ==================== 股票关注数据模型 ====================
Base = declarative_base()
class StockFollow(Base):
    """股票关注记录模型（SQLAlchemy Core）"""
    __tablename__ = 'stock_follows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100), nullable=False)
    follow_time = Column(Integer, nullable=False)


# ==================== 仓位设置文件操作 ====================
def load_position_settings():
    """从JSON文件加载仓位设置"""
    try:
        if os.path.exists(POSITION_SETTINGS_FILE):
            with open(POSITION_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[WARNING] 加载仓位设置失败：{e}")
    return {'percentage': 60, 'reminder_text': ''}

def save_position_settings(settings):
    """将仓位设置保存到JSON文件"""
    try:
        with open(POSITION_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] 保存仓位设置失败：{e}")

# 全局仓位设置变量
position_settings = load_position_settings()


# ==================== 全局中间件 ====================
@auth_bp.before_app_request
def check_login():
    """
    登录检查中间件
    
    说明：
    - 在每个请求前执行
    - 白名单路径不需要登录
    - 未登录用户重定向到登录页面
    """
    path = request.path
    white_list = ['/login', '/api/login', '/api/position-setting', '/static']
    for w in white_list:
        if path == w or path.startswith(w):
            return None
    if not session.get('logged_in'):
        return redirect('/login')


@auth_bp.after_app_request
def add_cors_headers(response):
    """添加CORS跨域请求头"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@auth_bp.route('/login')
def login_page():
    if session.get('logged_in'):
        return redirect('/')
    return render_template('login.html')


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        session['logged_in'] = True
        session['username'] = username
        return jsonify({'code': 1, 'msg': '登录成功', 'url': '/'})
    return jsonify({'code': 0, 'msg': '用户名或密码错误'})


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@position_bp.route('/api/position-setting', methods=['GET'])
def api_position_setting():
    try:
        return jsonify({"percentage": position_settings['percentage'], "reminder_text": position_settings['reminder_text']})
    except Exception:
        return jsonify({"percentage": 60, "reminder_text": ""})


@position_bp.route('/position-setting', methods=['GET', 'POST'])
def position_setting():
    if request.method == 'POST':
        try:
            percentage = request.form.get('percentage', '').strip()
            if not percentage or not percentage.isdigit():
                flash('请输入有效的仓位百分比', 'danger')
                return redirect(url_for('position.position_setting'))
            percentage = int(percentage)
            if percentage < 0 or percentage > 100:
                flash('仓位百分比必须在0-100之间', 'danger')
                return redirect(url_for('position.position_setting'))
            reminder_text = request.form.get('reminder_text', '').strip()
            position_settings['percentage'] = percentage
            position_settings['reminder_text'] = reminder_text
            save_position_settings(position_settings)
            flash('仓位设置更新成功！', 'success')
            return redirect(url_for('position.position_setting'))
        except Exception as e:
            print(f"[ERROR] 仓位设置失败：{e}")
            flash(f'仓位设置失败：{str(e)}', 'danger')
            return redirect(url_for('position.position_setting'))
    return render_template('position_setting.html',
                           current_percentage=position_settings['percentage'],
                           current_reminder_text=position_settings['reminder_text'])


@user_bp.route('/', methods=['GET', 'POST'])
def index():
    from models import db, User, UserPlainPassword
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not username:
            flash('用户名不能为空', 'danger')
        elif not password:
            flash('密码不能为空', 'danger')
        elif not confirm_password:
            flash('确认密码不能为空', 'danger')
        elif not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            flash('用户名只能包含字母、数字和下划线，长度3-20位', 'danger')
        elif len(password) < 6:
            flash('密码长度不能少于6位', 'danger')
        elif password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
        else:
            try:
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    flash('用户名已存在，请选择其他用户名', 'danger')
                else:
                    password_hash = generate_password_hash(password)
                    new_user = User(username=username, password=password_hash)
                    db.session.add(new_user)
                    db.session.commit()
                    new_plain_pwd = UserPlainPassword(username=username, mingwen=password)
                    db.session.add(new_plain_pwd)
                    db.session.commit()
                    flash('注册成功！', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] 注册失败：{e}")
                flash(f'注册失败：{str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    per_page = 10
    try:
        total = User.query.count()
        pagination = User.query.order_by(User.id.asc()).paginate(page=page, per_page=per_page, error_out=False)
        users = pagination.items
        for user in users:
            plain_pwd = UserPlainPassword.query.filter_by(username=user.username).first()
            user.password = plain_pwd.mingwen if plain_pwd else '【无明文记录】'
    except Exception as e:
        print(f"⚠️  获取用户列表失败：{e}")
        users, pagination, total = [], None, 0
        flash('数据库连接失败，显示模拟数据', 'warning')
    return render_template('index.html', users=users, pagination=pagination, total=total)


@user_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    from models import db, User, UserPlainPassword
    try:
        user = User.query.get(user_id)
        if user:
            plain_pwd = UserPlainPassword.query.filter_by(username=user.username).first()
            if plain_pwd:
                db.session.delete(plain_pwd)
            db.session.delete(user)
            db.session.commit()
            flash('用户删除成功！', 'success')
        else:
            flash('用户不存在', 'danger')
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] 删除失败：{e}")
        flash(f'删除失败：{str(e)}', 'danger')
    return redirect(url_for('user.index'))


@user_bp.route('/toggle-status/<int:user_id>', methods=['POST'])
def toggle_user_status(user_id):
    from models import db, User
    try:
        user = User.query.get(user_id)
        if user:
            user.is_active = not user.is_active
            db.session.commit()
            status = '启用' if user.is_active else '停用'
            flash(f'用户{status}成功！', 'success')
        else:
            flash('用户不存在', 'danger')
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] 切换状态失败：{e}")
        flash(f'切换状态失败：{str(e)}', 'danger')
    return redirect(url_for('user.index'))


@user_bp.route('/batch-create', methods=['GET', 'POST'])
def batch_create_users():
    from models import db, User, UserPlainPassword
    import string
    import random
    if request.method == 'POST':
        try:
            count = request.form.get('count', '').strip()
            if not count or not count.isdigit():
                flash('请输入有效的用户数量', 'danger')
                return redirect(url_for('user.batch_create_users'))
            count = int(count)
            if count <= 0:
                flash('用户数量必须大于0', 'danger')
                return redirect(url_for('user.batch_create_users'))
            max_num = 0
            users = User.query.filter(User.username.like('usr%')).all()
            for user in users:
                try:
                    num = int(user.username[3:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            created_count = 0
            for i in range(1, count + 1):
                username = f"usr{max_num + i}"
                password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    continue
                try:
                    password_hash = generate_password_hash(password)
                    new_user = User(username=username, password=password_hash)
                    db.session.add(new_user)
                    db.session.commit()
                    new_plain_pwd = UserPlainPassword(username=username, mingwen=password)
                    db.session.add(new_plain_pwd)
                    db.session.commit()
                    created_count += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"[ERROR] 创建用户 {username} 失败：{e}")
            flash(f'批量创建成功！共创建 {created_count} 个用户', 'success')
        except Exception as e:
            print(f"[ERROR] 批量创建用户失败：{e}")
            flash(f'批量创建失败：{str(e)}', 'danger')
        return redirect(url_for('user.index'))
    return render_template('batch_create.html')


@user_bp.route('/export-users')
def export_users():
    from models import db, User, UserPlainPassword
    try:
        users = User.query.order_by(User.id.asc()).all()
        export_content = "用户ID,用户名,密码,激活状态,注册时间\n"
        for user in users:
            plain_pwd = UserPlainPassword.query.filter_by(username=user.username).first()
            password = plain_pwd.mingwen if plain_pwd else '【无明文记录】'
            is_active = '已激活' if user.is_active else '已禁用'
            created_at = user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else '未知'
            export_content += f"{user.id},{user.username},{password},{is_active},{created_at}\n"
        response = make_response(export_content)
        response.headers['Content-Disposition'] = 'attachment; filename=users_export.txt'
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        return response
    except Exception as e:
        print(f"[ERROR] 导出用户信息失败：{e}")
        flash(f'导出失败：{str(e)}', 'danger')
        return redirect(url_for('user.index'))


@user_bp.route('/test-db')
def test_db():
    from models import db, User, UserPlainPassword
    try:
        user_count = User.query.count()
        plain_pwd_count = UserPlainPassword.query.count()
        return f'✅ 数据库连接成功！当前用户数：{user_count}，明文密码记录数：{plain_pwd_count}'
    except Exception as e:
        return f'❌ 数据库连接失败：{str(e)}'


@follow_bp.route('/follow', methods=['GET', 'POST'])
def follow_page():
    import time
    from services.stock_api import get_stock_data_batch
    from services.stock_name import get_stock_name_by_code, get_stock_code_by_name
    try:
        follows = stock_db.query(StockFollow).order_by(StockFollow.follow_time.desc()).all()
        stock_codes = [follow.stock_code for follow in follows]
        batch_data = get_stock_data_batch(stock_codes)
        for follow in follows:
            stock_data = batch_data.get(follow.stock_code)
            if stock_data:
                follow.price = stock_data.get('last', 'N/A')
                follow.change = stock_data.get('last', 'N/A')
                follow.change_percent = f"{stock_data.get('rate', 0):.2f}%"
            else:
                follow.price = follow.change = follow.change_percent = 'N/A'
    except Exception as e:
        print(f"⚠️  获取股票关注列表失败：{e}")
        stock_db.rollback()
        follows = []
        flash('股票数据库连接失败，显示模拟数据', 'warning')

    if request.method == 'POST':
        input_value = request.form.get('stock_code', '').strip()
        if not input_value:
            flash('请输入股票代码、基金代码、期货代码或名称', 'danger')
        else:
            code_pattern = r'^\d+$'
            alpha_code_pattern = r'^[a-zA-Z]+\d+$'
            mixed_code_pattern = r'^[a-zA-Z0-9]+$'
            if re.match(code_pattern, input_value) or re.match(alpha_code_pattern, input_value) or re.match(mixed_code_pattern, input_value):
                product_code = input_value
                full_code = None
                if re.match(r'^[a-zA-Z]+$', product_code):
                    full_code = f"us.{product_code}"
                elif re.match(r'^0\d{4}$', product_code):
                    full_code = f"hk.{product_code}"
                elif re.match(r'^6\d{5}$', product_code):
                    full_code = f"SH.{product_code}"
                elif re.match(r'^00[0-9]{4}$', product_code):
                    full_code = f"SZ.{product_code}"
                elif re.match(r'^300\d{3}$', product_code):
                    full_code = f"SZ.{product_code}"
                elif re.match(r'^688\d{3}$', product_code):
                    full_code = f"SH.{product_code}"
                elif re.match(r'^5\d{5}$', product_code):
                    full_code = f"SH.{product_code}"
                elif re.match(r'^1\d{5}$', product_code):
                    full_code = f"SZ.{product_code}"
                elif re.match(r'^159\d{3}$', product_code):
                    full_code = f"SZ.{product_code}"
                elif re.match(r'^588\d{3}$', product_code):
                    full_code = f"SH.{product_code}"
                elif re.match(r'^[a-zA-Z]+\d+$', product_code):
                    full_code = f"FUT.{product_code}"
                else:
                    full_code = f"SZ.{product_code}"

                product_name = get_stock_name_by_code(full_code)

                stock_code, stock_name = full_code, product_name
            else:
                full_code = get_stock_code_by_name(input_value)
                if not full_code:
                    flash('未找到该名称，请尝试输入代码', 'danger')
                    return redirect(url_for('follow.follow_page'))
                product_name = get_stock_name_by_code(full_code)

            stock_code, stock_name = full_code, product_name
            existing_follow = stock_db.query(StockFollow).filter_by(stock_code=full_code).first()
            if existing_follow:
                flash('已经关注过该股票', 'danger')
            else:
                follow_time = int(time.time())
                new_follow = StockFollow(stock_code=full_code, stock_name=stock_name, follow_time=follow_time)
                stock_db.add(new_follow)
                stock_db.commit()
                flash(f'关注成功！股票代码：{full_code}，股票名称：{stock_name}', 'success')
                return redirect(url_for('follow.follow_page'))

    return render_template('follow.html', follows=follows)


@follow_bp.route('/follow/delete/<int:follow_id>', methods=['POST'])
def delete_stock_follow(follow_id):
    try:
        follow = stock_db.query(StockFollow).filter_by(id=follow_id).first()
        if follow:
            stock_code = follow.stock_code
            stock_db.delete(follow)
            stock_db.commit()
            from db.database import get_db_connection
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM stock_change WHERE stock_code = %s", (stock_code,))
                conn.commit()
            finally:
                conn.close()
            flash('删除成功！', 'success')
        else:
            flash('记录不存在', 'danger')
    except Exception as e:
        stock_db.rollback()
        print(f"❌ 删除股票关注失败：{e}")
        flash(f'删除失败：{str(e)}', 'danger')
    return redirect(url_for('follow.follow_page'))


@follow_bp.route('/follow/clear', methods=['POST'])
def clear_stock_follows():
    try:
        delete_num = stock_db.query(StockFollow).delete()
        stock_db.commit()
        from db.database import get_db_connection
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stock_change")
            change_num = conn.rowcount
            conn.commit()
        finally:
            conn.close()
        flash(f'清空成功！共删除 {delete_num} 条关注记录，{change_num} 条涨跌幅记录', 'success')
    except Exception as e:
        stock_db.rollback()
        print(f"[ERROR] 清空失败：{e}")
        flash(f'清空失败：{str(e)}', 'danger')
    return redirect(url_for('follow.follow_page'))


@change_bp.route('/change')
def change_page():
    return render_template('change.html')


@change_bp.route('/api/stock_change')
def api_stock_change():
    from stock_change.calculator import get_change_data
    try:
        data = get_change_data()
        return jsonify({'code': 0, 'msg': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e), 'data': []})


@change_bp.route('/api/stock_change/calculate', methods=['POST'])
def api_stock_change_calculate():
    from stock_change.calculator import calculate_all_changes
    try:
        calculate_all_changes()
        return jsonify({'code': 0, 'msg': '计算完成'})
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)})
