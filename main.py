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

# ==========================================
# 1. 页面配置 (回归黑金风格)
# ==========================================
st.set_page_config(page_title="天机·AI全自动算命", page_icon="🔮", layout="wide")

st.markdown("""
<style>
    /* 全局深色背景 */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* 侧边栏深色 */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* 标题金色 */
    h1, h2, h3 {
        color: #D4AF37 !important;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 600;
    }
    
    /* 输入框美化 */
    .stTextInput>div>div>input {
        background-color: #0E1117;
        color: #fff;
        border: 1px solid #30363D;
    }
    
    /* 按钮美化 - 金色 */
    .stButton>button {
        background-color: #D4AF37;
        color: #000;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #F1C40F;
        box-shadow: 0 0 10px rgba(212, 175, 55, 0.5);
    }
    
    /* 提示框背景 */
    .stAlert {
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid #30363D;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心：八字排盘与大运 (已修复Bug)
# ==========================================

def get_bazi_data(year, month, day, hour, gender_str):
    """计算八字和大运时间表 - 修复 getStartAge 问题"""
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lunar = solar.getLunar()
    bazi = lunar.getEightChar()
    gender_num = 1 if gender_str == "男" else 0
    yun = bazi.getYun(gender_num)
    
    # 获取大运列表 (取前10步)
    da_yun_arr = yun.getDaYun()
    dayun_list = []
    
    # 修复点：直接从第一步大运获取起运年龄，而不是从 Yun 对象获取
    first_start_age = da_yun_arr[0].getStartAge() if len(da_yun_arr) > 0 else 0
    
    for i in range(10): 
        dy = da_yun_arr[i]
        dayun_list.append({
            "ganzhi": dy.getGanZhi(),
            "start_age": dy.getStartAge(),
            "end_age": dy.getEndAge()
        })
        
    return {
        "text": f"{bazi.getYear()}年 {bazi.getMonth()}月 {bazi.getDay()}日 {bazi.getTime()}时",
        "dayun": dayun_list,
        "start_age": first_start_age
    }

# ==========================================
# 3. 核心：AI 严谨算命 (强逻辑版)
# ==========================================

def call_ai_prediction(api_key, bazi_info, gender, age_range):
    """
    强制AI按照严格的评分标准输出。
    """
    dashscope.api_key = api_key
    
    prompt = f"""
    你是一位严谨的命理量化分析师。请根据八字：{bazi_info['text']} (性别：{gender})。
    请推算从 {age_range[0]}岁 到 {age_range[1]}岁 的每一年的流年吉凶。
    
    【评分标准 - 请严格执行】：
    1. **基准分**：50分 (平运/无事)。
    2. **大吉/发财/升官/结婚**：80-100分 (分数越高越好)。
    3. **小吉/顺遂**：60-79分。
    4. **小凶/破财/小病/口舌**：30-49分。
    5. **大凶/灾难/重病/意外/大破财**：0-29分 (分数越低越严重)。
    
    【K线逻辑要求】：
    - 必须体现“程度”。如果是大灾之年，分数必须打得很低（如 15分）。
    - 必须结合“神煞”与“冲克”。如遇“天克地冲”、“岁运并临”，必须大跌；如遇“三合贵人”，必须大涨。
    
    请严格返回 JSON 数组，不要包含Markdown格式，直接返回JSON字符串：
    [
        {{"age": 20, "score": 45, "reason": "流年冲太岁，小破财"}},
        {{"age": 21, "score": 85, "reason": "三合贵人，升职加薪"}},
        ...
    ]
    """

    try:
        response = dashscope.Generation.call(
            model='qwen-turbo', prompt=prompt, result_format='message'
        )
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            # 清洗数据
            content = content.replace("```json", "").replace("```", "").strip()
            # 有时候模型会啰嗦，尝试截取JSON部分
            if "[" in content and "]" in content:
                start = content.find("[")
                end = content.rfind("]") + 1
                content = content[start:end]
            return json.loads(content)
        else:
            st.error(f"AI 连接失败: {response.message}")
            return None
    except Exception as e:
        st.error(f"AI 数据解析错误: {e}")
        return None

# ==========================================
# 4. 界面与绘图
# ==========================================

with st.sidebar:
    st.header("⚙️ 参数设置")
    # API Key 输入框 (放在最显眼的位置)
    ali_api_key = st.text_input("阿里云 API Key (必填)", type="password", help="没有Key无法进行AI推演")
    
    st.markdown("---")
    st.subheader("👤 命主信息")
    name = st.text_input("姓名", "张三")
    gender = st.selectbox("性别", ["男", "女"])
    birth_date = st.date_input("出生日期", datetime.date(1995, 6, 15), min_value=datetime.date(1900,1,1), max_value=datetime.date(2024,12,31))
    birth_time = st.time_input("出生时间", datetime.time(12, 30))
    
    st.markdown("---")
    st.write("推演范围 (建议40年以内以防超时)")
    age_range = st.slider("年龄区间", 0, 100, (20, 60))
    
    btn = st.button("🔮 启动排盘推演")

# 主区域
st.title(f"🌌 {name} · 人生流年大运 K 线图")

if btn:
    if not ali_api_key:
        st.error("❌ 必须输入阿里云 API Key 才能启动 AI 推演！")
        st.stop()

    # 1. 基础排盘 (修复版)
    try:
        bazi_data = get_bazi_data(birth_date.year, birth_date.month, birth_date.day, birth_time.hour, gender)
        st.success(f"排盘成功：{bazi_data['text']} | {bazi_data['start_age']}岁起运")
    except Exception as e:
        st.error(f"排盘出错，请检查日期: {e}")
        st.stop()

    # 2. AI 推演
    with st.spinner("🤖 AI 正在深度推算每一年的吉凶祸福..."):
        ai_data = call_ai_prediction(ali_api_key, bazi_data, gender, age_range)

    if ai_data:
        # 3. 数据处理 (转为K线)
        df = pd.DataFrame(ai_data)
        
        ohlc_data = []
        # 初始锚点
        prev_close = df.iloc[0]['score'] 
        
        for index, row in df.iterrows():
            current_score = row['score']
            age = row['age']
            reason = row['reason']
            
            # K线逻辑：连贯性
            open_p = prev_close
            close_p = current_score
            
            # 波动幅度：极端分数波动大
            volatility = 2
            if current_score > 75 or current_score < 35:
                volatility = 6
            
            high_p = max(open_p, close_p) + random.randint(0, volatility)
            low_p = min(open_p, close_p) - random.randint(0, volatility)
            
            # 限制上下界
            high_p = min(100, high_p)
            low_p = max(0, low_p)
            
            ohlc_data.append({
                "age": age,
                "open": open_p,
                "close": close_p,
                "high": high_p,
                "low": low_p,
                "reason": reason
            })
            prev_close = close_p 
            
        chart_df = pd.DataFrame(ohlc_data)
        
        # 4. 绘图 (深色模式 + 大运线)
        fig = go.Figure()
        
        # 颜色配置：绿涨(吉) 红跌(凶) —— 符合你的参考图习惯
        COLOR_UP = "#00E676"   # 亮绿色
        COLOR_DOWN = "#FF1744" # 亮红色
        
        # 绘制 K 线
        fig.add_trace(go.Candlestick(
            x=chart_df['age'],
            open=chart_df['open'], high=chart_df['high'],
            low=chart_df['low'], close=chart_df['close'],
            increasing_line_color=COLOR_UP, increasing_fillcolor=COLOR_UP,
            decreasing_line_color=COLOR_DOWN, decreasing_fillcolor=COLOR_DOWN,
            name="运势",
            hovertext=chart_df['reason']
        ))
        
        # 添加大运分割线 (核心功能)
        shapes = []
        annotations = []
        dayun_list = bazi_data['dayun']
        max_age = chart_df['age'].max()
        min_age = chart_df['age'].min()
        
        for dy in dayun_list:
            start = dy['start_age']
            if min_age <= start <= max_age:
                # 竖虚线 (白色虚线，适应黑底)
                shapes.append(dict(
                    type="line", x0=start, y0=0, x1=start, y1=1,
                    xref="x", yref="paper",
                    line=dict(color="#444444", width=1, dash="dash")
                ))
                # 顶部大运名 (金色文字)
                annotations.append(dict(
                    x=start + 5, y=1.05, xref="x", yref="paper",
                    text=f"<b>{dy['ganzhi']}大运</b>", showarrow=False,
                    font=dict(size=14, color="#D4AF37")
                ))

        # 布局设置 (plotly_dark)
        fig.update_layout(
            template="plotly_dark", # 强制黑底模板
            height=600,
            paper_bgcolor='#0E1117', # 与网页背景融合
            plot_bgcolor='#0E1117',
            xaxis_rangeslider_visible=False,
            shapes=shapes, annotations=annotations,
            showlegend=False,
            margin=dict(t=60, b=20, l=40, r=40),
            hovermode="x unified"
        )
        
        # 坐标轴
        fig.update_xaxes(title="年龄", showgrid=False, gridcolor="#333")
        fig.update_yaxes(title="吉凶评分 (0-100)", showgrid=True, gridcolor="#222", range=[0, 110])
        
        # 图例说明
        st.markdown(f"""
        <div style="display:flex; justify-content:flex-end; gap:20px; font-size:14px; margin-bottom:10px;">
            <span style="color:{COLOR_UP}">█ 运势上升 (大吉/顺遂)</span>
            <span style="color:{COLOR_DOWN}">█ 运势下跌 (凶/劫/灾)</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部显示详细数据表
        with st.expander("📜 查看 AI 详细流年批注"):
            st.dataframe(
                chart_df[['age', 'close', 'reason']].rename(columns={'age':'年龄', 'close':'吉凶分', 'reason':'断语'}), 
                use_container_width=True
            )

    else:
        st.warning("AI 似乎在思考人生... 未能返回数据，请重试。")
else:
    st.info("👈 请在左侧侧边栏输入信息，开启你的命运 K 线。")
