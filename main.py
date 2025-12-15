# -*- coding: utf-8 -*-
"""
Created on Mon Dec 15 20:51:47 2025

@author: ffq73
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lunar_python import Lunar, Solar
import dashscope
from http import HTTPStatus
import json
import random
import time
import datetime
import math

# 尝试导入拼音库
try:
    from pypinyin import pinyin, Style
    HAS_PINYIN = True
except ImportError:
    HAS_PINYIN = False

# ==========================================
# 1. 页面配置 (沉浸式黑金交易终端)
# ==========================================
st.set_page_config(page_title="人生K线模拟交易", page_icon="🎰", layout="wide")

st.markdown("""
<style>
    /* 全局深色背景 */
    .stApp { background-color: #000000; color: #00FF00; font-family: 'Consolas', 'Courier New', monospace; }
    
    /* 侧边栏 */
    [data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #333; }
    
    /* 顶部股票代码栏 */
    .stock-ticker {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #333;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .ticker-symbol { font-size: 28px; font-weight: bold; color: #D4AF37; }
    .ticker-price { font-size: 32px; font-weight: bold; color: #FFF; }
    .ticker-change-up { color: #FF3B30; font-size: 18px; } /* 红涨 */
    .ticker-change-down { color: #00E676; font-size: 18px; } /* 绿跌 */
    
    /* 资产显示 */
    .asset-box {
        text-align: center;
        padding: 10px;
        background: #222;
        border: 1px solid #444;
        border-radius: 4px;
    }
    .asset-label { color: #888; font-size: 12px; }
    .asset-value { color: #D4AF37; font-size: 20px; font-weight: bold; }
    
    /* 按钮样式 */
    .trade-btn-long { background-color: #FF3B30 !important; color: white !important; border:none; height: 50px; font-size: 18px !important; }
    .trade-btn-short { background-color: #00E676 !important; color: white !important; border:none; height: 50px; font-size: 18px !important; }
    .trade-btn-wait { background-color: #555555 !important; color: white !important; border:none; height: 50px; font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 辅助函数
# ==========================================

def generate_stock_code(name):
    """生成股票代码"""
    abbr = "USER"
    if HAS_PINYIN:
        try:
            pys = pinyin(name, style=Style.FIRST_LETTER)
            abbr = "".join([x[0].upper() for x in pys])
        except:
            pass
    else:
        abbr = "X" + str(random.randint(10,99))
    return f"JORLIN000{abbr}"

def get_bazi_info(year, month, day, hour, gender_str):
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lunar = solar.getLunar()
    bazi = lunar.getEightChar()
    return {
        "text": f"{bazi.getYear()}年 {bazi.getMonth()}月 {bazi.getDay()}日 {bazi.getTime()}时",
        "gender": gender_str
    }

def call_ai_logic(api_key, bazi_info, age_range):
    """调用AI生成底牌数据"""
    dashscope.api_key = api_key
    prompt = f"""
    请扮演严谨的命运量化分析师。根据八字：{bazi_info['text']}。
    推演 {age_range[0]}岁 到 {age_range[1]}岁 的流年运势。
    
    【评分规则】：
    - 50分为基准（平运）。
    - 遇到三合、贵人、大运生扶：分数涨到 70-100（视为大牛市）。
    - 遇到冲克、刑害、岁运并临：分数跌到 10-40（视为股灾）。
    
    请严格返回 JSON 数组：
    [
      {{"age": 20, "score": 55, "reason": "初出茅庐，平稳起步"}},
      {{"age": 21, "score": 75, "reason": "贵人相助，崭露头角"}},
      ...
    ]
    """
    try:
        if not api_key: return mock_game_data(age_range[0], age_range[1])
        response = dashscope.Generation.call(model='qwen-turbo', prompt=prompt, result_format='message')
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            if "[" in content:
                s = content.find("[")
                e = content.rfind("]") + 1
                return json.loads(content[s:e])
        return mock_game_data(age_range[0], age_range[1])
    except:
        return mock_game_data(age_range[0], age_range[1])

def mock_game_data(start, end):
    data = []
    for age in range(start, end+1):
        trend = math.sin((age-20)/5) * 15
        score = 50 + trend + random.randint(-10, 10)
        score = max(10, min(95, score))
        data.append({"age": age, "score": int(score), "reason": "模拟推演数据"})
    return data

# ==========================================
# 3. 游戏状态管理
# ==========================================

if 'game_started' not in st.session_state: st.session_state.game_started = False
if 'current_step' not in st.session_state: st.session_state.current_step = 0
if 'balance' not in st.session_state: st.session_state.balance = 100000
if 'full_data' not in st.session_state: st.session_state.full_data = []
if 'trade_log' not in st.session_state: st.session_state.trade_log = []
if 'last_action' not in st.session_state: st.session_state.last_action = "等待开盘"

# ==========================================
# 4. 游戏逻辑 (核心修复处)
# ==========================================

def next_turn(action):
    """处理下一回合"""
    step = st.session_state.current_step
    full_data = st.session_state.full_data
    
    if step >= len(full_data) - 1:
        st.session_state.last_action = "游戏结束"
        return

    # 获取数据
    current_year_data = full_data[step]
    next_year_data = full_data[step + 1]
    
    # 【修复点】：这里改成读取 'close' 而不是 'score'
    current_price = current_year_data['close']
    next_price = next_year_data['close']
    
    # 计算盈亏 (每1分波动 = 1000元)
    price_diff = next_price - current_price
    profit = 0
    
    if action == 'long':
        profit = price_diff * 1000
        act_text = "做多 ▲"
    elif action == 'short':
        profit = -price_diff * 1000
        act_text = "做空 ▼"
    else:
        profit = 0
        act_text = "空仓 ⏹"

    st.session_state.balance += profit
    
    # 记录日志
    st.session_state.trade_log.append({
        "年龄": current_year_data['age'],
        "操作": act_text,
        "当年点数": current_price,
        "次年点数": next_price,
        "盈亏": f"{profit:+}",
        "总资产": int(st.session_state.balance)
    })
    
    st.session_state.current_step += 1
    st.session_state.last_action = f"{act_text} | 结果：{profit:+}"

# ==========================================
# 5. 界面渲染
# ==========================================

with st.sidebar:
    st.title("🕹️ 游戏设置")
    ali_api_key = st.text_input("阿里云 API Key (可选)", type="password")
    name = st.text_input("您的姓名", "张无忌")
    gender = st.selectbox("性别", ["男", "女"])
    birth_date = st.date_input("出生日期", datetime.date(1995, 6, 15))
    birth_time = st.time_input("出生时间", datetime.time(12, 00))
    
    if not st.session_state.game_started:
        if st.button("🎰 生成人生并开始交易", type="primary"):
            bazi = get_bazi_info(birth_date.year, birth_date.month, birth_date.day, birth_time.hour, gender)
            stock_code = generate_stock_code(name)
            st.session_state.stock_code = stock_code
            st.session_state.user_name = name
            
            with st.spinner("正在生成人生 K 线底牌..."):
                raw_data = call_ai_logic(ali_api_key, bazi, (20, 70))
                
                # 转换为 OHLC 数据结构
                processed_data = []
                prev_close = 50
                for item in raw_data:
                    close_p = item['score'] # 这里取 AI 返回的 score
                    open_p = prev_close
                    vol = random.randint(2, 6)
                    high_p = max(open_p, close_p) + vol
                    low_p = min(open_p, close_p) - vol
                    
                    processed_data.append({
                        "age": item['age'],
                        "open": open_p, 
                        "close": close_p, # 存为 close
                        "high": high_p, 
                        "low": low_p,
                        "reason": item['reason']
                    })
                    prev_close = close_p
            
            st.session_state.full_data = processed_data
            st.session_state.game_started = True
            st.session_state.current_step = 0
            st.session_state.balance = 100000
            st.session_state.trade_log = []
            st.rerun()
    else:
        st.success("游戏进行中...")
        if st.button("🔄 重置游戏"):
            st.session_state.game_started = False
            st.rerun()

if st.session_state.game_started:
    data = st.session_state.full_data
    step = st.session_state.current_step
    
    # 顶部行情
    current_bar = data[step]
    prev_bar = data[step-1] if step > 0 else {"close": 50}
    price_change = current_bar['close'] - prev_bar['close']
    pct_change = (price_change / prev_bar['close']) * 100 if prev_bar['close'] != 0 else 0
    
    color_class = "ticker-change-up" if price_change >= 0 else "ticker-change-down"
    sign = "+" if price_change >= 0 else ""
    
    st.markdown(f"""
    <div class="stock-ticker">
        <div>
            <div style="font-size:14px; color:#888;">股票代码</div>
            <div class="ticker-symbol">{st.session_state.stock_code}</div>
            <div style="font-size:12px; color:#666;">简称：{st.session_state.user_name}</div>
        </div>
        <div style="text-align:right;">
            <div class="ticker-price">{current_bar['close']:.2f}</div>
            <div class="{color_class}">{sign}{price_change:.2f} ({sign}{pct_change:.1f}%)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 资产数据
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="asset-box"><div class="asset-label">当前年龄</div><div class="asset-value">{current_bar["age"]} 岁</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="asset-box"><div class="asset-label">总资产 (初始10w)</div><div class="asset-value">${st.session_state.balance:,.0f}</div></div>', unsafe_allow_html=True)
    with c3: 
        pnl_pct = (st.session_state.balance - 100000) / 100000 * 100
        pnl_color = "#FF3B30" if pnl_pct >= 0 else "#00E676"
        st.markdown(f'<div class="asset-box"><div class="asset-label">总收益率</div><div class="asset-value" style="color:{pnl_color}">{pnl_pct:+.1f}%</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="asset-box"><div class="asset-label">上轮操作</div><div class="asset-value" style="font-size:16px">{st.session_state.last_action}</div></div>', unsafe_allow_html=True)

    # K线图
    visible_df = pd.DataFrame(data[:step+1])
    fig = go.Figure(data=[go.Candlestick(
        x=visible_df['age'],
        open=visible_df['open'], high=visible_df['high'],
        low=visible_df['low'], close=visible_df['close'],
        increasing_line_color='#FF3B30', decreasing_line_color='#00E676',
        name="运势"
    )])
    fig.update_layout(
        template="plotly_dark", height=500, xaxis_rangeslider_visible=False,
        title=f"人生走势 ({data[0]['age']}岁 - {current_bar['age']}岁)",
        margin=dict(t=40, b=40, l=40, r=40)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 交易区
    if step < len(data) - 1:
        st.info(f"💡 当前 ({current_bar['age']}岁) 状态：{current_bar['reason']}。你觉得明年会更好还是更差？")
        col_buy, col_wait, col_sell = st.columns(3)
        with col_buy:
            if st.button("做多 (看涨) ▲", key="btn_long", help="看涨明年"):
                next_turn('long')
                st.rerun()
        with col_wait:
             if st.button("空仓 (观望) ⏹", key="btn_wait", help="不操作"):
                next_turn('wait')
                st.rerun()
        with col_sell:
            if st.button("做空 (看跌) ▼", key="btn_short", help="看跌明年"):
                next_turn('short')
                st.rerun()
    else:
        st.success("🎉 游戏结束！你是巴菲特，还是索罗斯？抑或是退学炒股？")
        if st.session_state.balance > 100000: st.balloons()
            
    with st.expander("查看交易流水"):
        if st.session_state.trade_log:
            st.dataframe(pd.DataFrame(st.session_state.trade_log).iloc[::-1], use_container_width=True)

else:
    st.markdown("""
    <div style="text-align: center; margin-top: 50px;">
        <h1>🎰 JORLIN 命运交易所</h1>
        <p style="color: #888;">每一年的运势都是一支股票。你是选择在低谷时抄底，还是在巅峰时做空？</p>
    </div>
    """, unsafe_allow_html=True)
