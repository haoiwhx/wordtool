import streamlit as st
import pdfplumber
import pandas as pd
import json
import random

# ==========================================
# 1. PDF 解析逻辑
# ==========================================
def parse_pdf(uploaded_file):
    vocab_list = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or row[0] == 'No.' or row[1] == 'Word':
                            continue
                        # 提取左栏
                        if len(row) >= 3 and row[1] and row[2]:
                            word = str(row[1]).strip()
                            meaning = str(row[2]).strip().replace('\n', ' ')
                            if word and meaning:
                                vocab_list.append({"word": word, "meaning": meaning})
                        # 提取右栏
                        if len(row) >= 6 and row[4] and row[5]:
                            word = str(row[4]).strip()
                            meaning = str(row[5]).strip().replace('\n', ' ')
                            if word and meaning:
                                vocab_list.append({"word": word, "meaning": meaning})
    except Exception as e:
        st.error(f"解析出错: {e}")
        return []
    
    random.shuffle(vocab_list)
    return vocab_list

# ==========================================
# 2. 前端游戏代码 (HTML/JS/CSS)
# ==========================================
def get_game_html(vocab_json, settings_json):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; overflow: hidden; background-color: #222; font-family: 'Segoe UI', sans-serif; user-select: none; -webkit-user-select: none; }}
            #gameCanvas {{ display: block; margin: 0 auto; background: linear-gradient(to bottom, #141E30, #243B55); cursor: crosshair; }}
            
            #ui-layer {{ position: absolute; top: 0; width: 100%; height: 100%; pointer-events: none; }}
            
            .hud-container {{ display: flex; justify-content: space-between; padding: 20px 40px; }}
            .hud-box {{ color: white; text-shadow: 0 0 5px #00e676; font-weight: bold; font-size: 28px; font-family: monospace; }}
            
            #current-word-container {{ position: absolute; top: 8%; width: 100%; text-align: center; }}
            #current-word {{ 
                font-size: 64px; color: #fff; 
                text-shadow: 0 4px 10px rgba(0,0,0,0.8);
                background: rgba(255,255,255,0.1); 
                padding: 15px 50px; border-radius: 20px; display: inline-block; 
                border: 1px solid rgba(255,255,255,0.3);
                backdrop-filter: blur(4px);
            }}

            #timer-bar-bg {{ position: absolute; bottom: 0; left: 0; width: 100%; height: 8px; background: #333; }}
            #timer-bar-fill {{ height: 100%; background: linear-gradient(90deg, #00e676, #00C853); width: 100%; transition: width 0.1s linear; }}

            #start-screen, #game-over-screen {{ 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(10,10,10,0.95); display: flex; flex-direction: column; 
                justify-content: center; align-items: center; z-index: 10; pointer-events: auto;
            }}
            
            button {{ 
                font-size: 24px; padding: 15px 40px; background: #2979FF; 
                color: white; border: none; border-radius: 8px; cursor: pointer; 
                margin-top: 30px; box-shadow: 0 4px 0 #1565C0; font-family: monospace;
            }}
            button:active {{ transform: translateY(4px); box-shadow: none; }}
            
            h1 {{ color: #2979FF; font-size: 50px; margin: 0 0 10px 0; letter-spacing: 5px; }}
            h2 {{ color: #eee; font-size: 24px; font-weight: normal; margin: 0 0 30px 0; opacity: 0.8; }}

            .float-score {{ position: absolute; font-weight: bold; font-size: 32px; animation: floatUp 0.8s ease-out forwards; pointer-events: none; z-index: 5; text-shadow: 0 0 5px black; }}
            @keyframes floatUp {{ 0% {{ opacity: 1; transform: translateY(0) scale(1); }} 100% {{ opacity: 0; transform: translateY(-60px) scale(1.5); }} }}
        </style>
    </head>
    <body>
        <canvas id="gameCanvas"></canvas>
        <audio id="bgm" loop>
            <source src="https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=relaxed-vlog-night-street-131746.mp3" type="audio/mpeg">
        </audio>

        <div id="ui-layer">
            <div class="hud-container">
                <div class="hud-box">SCORE: <span id="score-val">0</span></div>
                <div class="hud-box">TIME: <span id="time-val">0</span></div>
            </div>
            <div id="current-word-container">
                <div id="current-word">Loading...</div>
            </div>
            <div id="timer-bar-bg"><div id="timer-bar-fill"></div></div>
        </div>

        <div id="start-screen">
            <h1>VOCAB TAP</h1>
            <h2>点击正确释义 · 辨析干扰项</h2>
            <button onclick="startGame()">START GAME</button>
        </div>

        <div id="game-over-screen" style="display:none;">
            <h1 style="color: #ff4444;">TIME UP</h1>
            <h2 id="final-score">Score: 0</h2>
            <button onclick="startGame()">RETRY</button>
        </div>

        <script>
            const vocabList = {vocab_json};
            const settings = {settings_json};
            
            const canvas = document.getElementById('gameCanvas');
            const ctx = canvas.getContext('2d');
            const bgm = document.getElementById('bgm');
            bgm.volume = 0.3;

            let width, height;
            let score = 0;
            let timeLeft = settings.duration;
            let isPlaying = false;
            let currentTarget = null;
            let fruits = [];
            let particles = [];
            let impactEffects = [];
            let lastTime = 0;
            let spawnTimer = 0;
            
            let cardDeck = [];
            let lastWordChangeTime = 0; // 记录单词切换的时间
            const speedMultiplier = settings.speed; 

            function resize() {{
                width = window.innerWidth;
                height = window.innerHeight;
                canvas.width = width;
                canvas.height = height;
            }}
            window.addEventListener('resize', resize);
            resize();

            // ------------------ 物理与对象 ------------------

            class Fruit {{
                constructor(meaning, isCorrect) {{
                    this.radius = 60;
                    this.x = Math.random() * (width - 160) + 80;
                    this.y = height + this.radius + 10;
                    
                    // 统一跳跃高度到屏幕 45% 处
                    const targetY = height * 0.45; 
                    const distance = this.y - targetY;
                    
                    this.gravity = 0.25 * speedMultiplier;
                    const requiredVy = Math.sqrt(2 * this.gravity * distance);
                    const randomFactor = 0.98 + Math.random() * 0.04; 
                    this.vy = -requiredVy * randomFactor;
                    this.vx = (Math.random() - 0.5) * 2; 

                    this.meaning = meaning;
                    this.isCorrect = isCorrect;
                    
                    const colors = ['#00B0FF', '#00E676', '#FFEA00', '#FF1744', '#AA00FF', '#FF9100'];
                    this.color = colors[Math.floor(Math.random() * colors.length)];
                    this.sliced = false;
                }}

                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vy += this.gravity;
                }}

                draw() {{
                    ctx.save();
                    ctx.translate(this.x, this.y);
                    
                    // 气泡
                    ctx.beginPath();
                    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
                    ctx.fillStyle = this.color;
                    ctx.fill();
                    
                    // 去除了白色反光，仅保留淡淡的内发光/描边，视觉更干净
                    ctx.lineWidth = 3;
                    ctx.strokeStyle = "rgba(255,255,255,0.3)";
                    ctx.stroke();

                    // 文字
                    ctx.fillStyle = "#fff";
                    ctx.font = "bold 24px 'Segoe UI', sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.shadowColor = "rgba(0,0,0,0.6)";
                    ctx.shadowBlur = 4;
                    ctx.shadowOffsetX = 1;
                    ctx.shadowOffsetY = 1;
                    
                    let text = this.meaning;
                    if (text.length > 6) {{
                         ctx.fillText(text.substring(0, 6), 0, -12);
                         ctx.fillText(text.substring(6, 12) + (text.length>12?"..":""), 0, 15);