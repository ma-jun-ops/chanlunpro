# final2 项目说明

## 项目简介

`final` 是一个由两个 Python 子项目组成的本地量化分析工作区：

- `Mange`：用户管理、股票关注、仓位提醒、涨跌幅统计系统
- `chanlun-pro`：缠论行情分析与图表展示系统

这两个项目已经做了联动：

- `Mange` 负责维护关注股票、涨跌幅统计等数据
- `chanlun-pro` 页面会读取 `Mange` 维护的关注列表与涨幅结果


## 项目结构

```text
final/
├── Mange/                      # 用户管理 / 股票关注 / 涨跌幅统计
│   ├── db/
│   │   └── database.py         # MySQL 数据库配置
│   └── src/
│       ├── app.py              # Flask 入口
│       ├── models/             # ORM 模型
│       ├── routes/             # 路由与页面逻辑
│       ├── services/           # 股票代码/名称/行情接口
│       ├── stock_change/       # 涨跌幅计算与调度
│       ├── templates/          # HTML 模板
│       └── tools/              # Redis / 缓存工具
├── chanlun-pro/                # 缠论分析与 Web 图表系统
│   ├── src/                    # 核心缠论逻辑、策略、交易适配
│   ├── web/chanlun_chart/      # Web 页面与接口入口
│   ├── notebook/               # 回测/图表 notebook
│   ├── cookbook/               # 原项目文档
│   └── package/                # 本地 wheel 依赖
└── LICENSE
```


## 主要功能

### Mange

- 用户注册、登录、用户管理
- 股票关注列表维护
- 仓位设置与提醒
- 关注股票涨跌幅统计
- 自动清理取消关注后的统计结果
- 通过腾讯/东方财富等接口获取股票名称、行情与历史价格

### chanlun-pro

- 缠论 K 线分析与图表展示
- 自选股 / 鱼池展示
- 多市场支持：A 股、港股、美股、期货、外汇、数字货币
- 选股、监控、回测、交易扩展
- 支持策略开发、回测与部分交易接口集成


## 运行环境

建议环境：

- Linux / Ubuntu
- Python `3.11+`
- MySQL `8.x`
- Redis `6.x+`


## 数据库说明

`Mange/db/database.py` 中当前约定了以下数据库：

- `chanlun_klines`：用户管理数据库
- `stokedb`：关注股票与涨跌幅统计数据库
- `chanlun_db`：`chanlun-pro` 使用的缠论分析数据库

当前默认连接配置位于：

- `Mange/db/database.py`

默认值示例：

```python
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = '123456'
```

如果本地数据库账号密码不同，请先修改这里。


## 依赖安装

### 1. 安装 Mange 依赖

```bash
cd /home/shengge/桌面/final2/Mange/src
pip install -r requirements.txt
```

### 2. 安装 chanlun-pro 依赖

推荐使用 `uv` 或 `pip`。

```bash
cd /home/shengge/桌面/final2/chanlun-pro
pip install -r requirements.txt
```

如果使用 `uv`：

```bash
cd /home/shengge/桌面/final2/chanlun-pro
uv sync
```


## 启动方式

### 启动 Mange

```bash
cd /home/shengge/桌面/final2/Mange/src
python app.py
```

默认地址：

- `http://127.0.0.1:5000`

启动时会自动尝试：

- 初始化用户表
- 初始化关注股票表
- 初始化涨跌幅统计表
- 启动涨跌幅定时任务


### 启动 chanlun-pro

```bash
cd /home/shengge/桌面/final2/chanlun-pro/web/chanlun_chart
python app.py
```

说明：

- `chanlun-pro` 依赖自身配置与数据库环境
- 页面中的“鱼池”已经接入 `stokedb.stock_follows` 与 `stokedb.stock_change`


## 关键联动关系

当前这套项目已经打通了以下数据链路：

1. 在 `Mange` 中添加股票关注
2. 数据写入 `stokedb.stock_follows`
3. `Mange` 计算涨跌幅后写入 `stokedb.stock_change`
4. `chanlun-pro` 首页鱼池读取这两张表
5. 鱼池新增“涨幅比”列，并按涨幅比降序展示


## 近期已完成的定制功能

- 股票名称接口增加失败降级与重试机制
- 行情接口增加重试机制
- 涨跌幅计算支持回溯最近有效交易日，不再只查单日
- 删除关注时同步清理涨跌幅数据
- 涨跌幅查询只返回当前仍在关注的股票
- 修复 MySQL 字符集 / 排序规则冲突
- `chanlun-pro` 鱼池新增“涨幅比”列，并按涨幅比排序


## 常见问题

### 1. 为什么“最新日期”不是今天？

因为系统取的是行情接口返回的“最新交易日”而不是系统当天日期。
如果当天是周末或节假日，接口通常会返回上一个交易日。

### 2. 为什么删了关注后涨跌幅页面还有记录？

现在已经做了同步清理逻辑：

- 删除单条关注时同步删除对应涨跌幅
- 清空关注时同步清空涨跌幅
- 计算涨跌幅前也会自动清理孤儿记录

### 3. 如果鱼池页面没有显示最新涨幅比怎么办？

可以按以下顺序排查：

1. 确认 `Mange` 的涨跌幅计算已经执行
2. 确认 `stokedb.stock_change` 表内有数据
3. 重启 `chanlun-pro`
4. 刷新首页鱼池区域


## 参考入口

- `Mange/src/app.py`
- `Mange/db/database.py`
- `Mange/src/stock_change/calculator.py`
- `chanlun-pro/web/chanlun_chart/app.py`
- `chanlun-pro/web/chanlun_chart/cl_app/__init__.py`
- `chanlun-pro/README.md`


## 备注

`chanlun-pro` 本身已经包含较完整的原始文档、安装说明与使用说明，可继续参考：

- `chanlun-pro/README.md`
- `chanlun-pro/cookbook/docs/`

