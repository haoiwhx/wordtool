import streamlit as st
import pdfplumber
import pandas as pd
import json
import base64


# ==========================================
# 1. PDF 解析逻辑 (保持不变)
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
                        if len(row) >= 3 and row[1] and row[2]:
                            word = str(row[1]).strip()
                            meaning = str(row[2]).strip().replace('\n', ' ')
                            if word and meaning:
                                vocab_list.append({"word": word, "meaning": meaning})
                        if len(row) >= 6 and row[4] and row[5]:
                            word = str(row[4]).strip()
                            meaning = str(row[5]).strip().replace('\n', ' ')
                            if word and meaning:
                                vocab_list.append({"word": word, "meaning": meaning})
    except Exception as e:
        st.error(f"解析出错: {e}")
        return []
    return vocab_list


# ==========================================
# 2. 前端游戏代码 (HTML/JS/CSS - 核心修改部分)
# ==========================================
def get_game_html(vocab_json, settings_json):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; overflow: hidden; background-color: #222; font-family: 'Segoe UI', sans-serif; user-select: none; -webkit-user-select: none; }}
            #gameCanvas {{ display: block; margin: 0 auto; background: linear-gradient(to bottom, #2b5876, #4e4376); }}

            /* UI 布局优化 */
            #ui-layer {{ position: absolute; top: 0; width: 100%; height: 100%; pointer-events: none; }}

            .hud-container {{ display: flex; justify-content: space-between; padding: 20px 40px; }}
            .hud-box {{ color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.6); font-weight: bold; font-size: 28px; }}
            .hud-sub {{ font-size: 16px; color: #ddd; opacity: 0.8; }}

            #current-word-container {{ position: absolute; top: 100px; width: 100%; text-align: center; }}
            #current-word {{ 
                font-size: 56px; color: #fff; background: rgba(0,0,0,0.4); 
                padding: 10px 40px; border-radius: 15px; display: inline-block; 
                backdrop-filter: blur(5px); border: 2px solid rgba(255,255,255,0.2);
            }}

            #timer-bar-bg {{ position: absolute; bottom: 0; left: 0; width: 100%; height: 10px; background: #333; }}
            #timer-bar-fill {{ height: 100%; background: #00e676; width: 100%; transition: width 0.1s linear; }}

            #start-screen, #game-over-screen {{ 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.85); display: flex; flex-direction: column; 
                justify-content: center; align-items: center; z-index: 10; pointer-events: auto;
            }}

            button {{ 
                font-size: 28px; padding: 15px 50px; background: #FF5722; 
                color: white; border: none; border-radius: 50px; cursor: pointer; 
                margin-top: 20px; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.4);
                transition: transform 0.1s;
            }}
            button:active {{ transform: scale(0.95); }}

            h1 {{ color: white; font-size: 60px; margin: 0 0 20px 0; }}
            h2 {{ color: #eee; font-size: 32px; margin: 0 0 40px 0; }}

            /* 飘分动画 */
            .float-score {{ position: absolute; font-weight: bold; font-size: 30px; animation: floatUp 1s ease-out forwards; pointer-events: none; }}
            @keyframes floatUp {{ 0% {{ opacity: 1; transform: translateY(0); }} 100% {{ opacity: 0; transform: translateY(-50px); }} }}
        </style>
    </head>
    <body>
        <canvas id="gameCanvas"></canvas>

        <div id="ui-layer">
            <div class="hud-container">
                <div class="hud-box">Score: <span id="score-val">0</span></div>
                <div class="hud-box" style="text-align:right;">
                    <div>Time: <span id="time-val">0</span>s</div>
                    <div class="hud-sub">Best: <span id="best-val">0</span></div>
                </div>
            </div>

            <div id="current-word-container">
                <div id="current-word">Vocab Ninja</div>
            </div>

            <div id="timer-bar-bg"><div id="timer-bar-fill"></div></div>
        </div>

        <div id="start-screen">
            <h1>VOCAB NINJA</h1>
            <h2>切中正确释义得分，切错扣分</h2>
            <button onclick="startGame()">Start Game</button>
        </div>

        <div id="game-over-screen" style="display:none;">
            <h1>TIME UP</h1>
            <h2 id="final-score">Final Score: 0</h2>
            <button onclick="startGame()">Play Again</button>
        </div>

        <script>
            const vocabList = {vocab_json};
            const settings = {settings_json}; // 获取 Python 传来的设置 (速度/时间)

            const canvas = document.getElementById('gameCanvas');
            const ctx = canvas.getContext('2d');
            let width, height;

            // 游戏状态
            let score = 0;
            let timeLeft = settings.duration;
            let isPlaying = false;
            let currentTarget = null;
            let fruits = [];
            let particles = [];
            let bladePath = [];
            let lastTime = 0;
            let spawnTimer = 0;

            // 速度控制
            const speedMultiplier = settings.speed; 

            // 本地最高分
            let highScore = localStorage.getItem('vocabNinjaHighScore') || 0;
            document.getElementById('best-val').innerText = highScore;

            function resize() {{
                width = window.innerWidth;
                height = window.innerHeight;
                canvas.width = width;
                canvas.height = height;
            }}
            window.addEventListener('resize', resize);
            resize();

            // ------------------ 类定义 ------------------

            class Fruit {{
                constructor(meaning, isCorrect) {{
                    this.x = Math.random() * (width - 140) + 70;
                    this.y = height + 60;

                    // 物理参数 - 受 Multiplier 影响
                    // 垂直初速度: 基础值 * 系数
                    this.vy = -(Math.random() * 5 + 11) * speedMultiplier; 
                    // 水平速度保持较小，防止飘太远
                    this.vx = (Math.random() - 0.5) * 3; 

                    // 重力: 基础值 * 系数平方 (为了保持抛物线手感)
                    this.gravity = 0.25 * (speedMultiplier * speedMultiplier);

                    this.radius = 55; // 稍微变小一点
                    this.meaning = meaning;
                    this.isCorrect = isCorrect;

                    // 颜色：不再随机，给个好点的配色
                    // 干扰项用一种色系，正确项用另一种？不，为了游戏难度，应该统一或者随机
                    // 这里使用暖色系随机，方便阅读文字
                    const hue = Math.floor(Math.random() * 40) + 30; // 橙色/黄色区间
                    this.color = `hsl(${{hue}}, 85%, 60%)`; 
                    this.sliced = false;

                    // 【修改点2】取消旋转
                    this.rotation = 0;
                }}

                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vy += this.gravity;
                }}

                draw() {{
                    ctx.save();
                    ctx.translate(this.x, this.y);
                    // 不旋转 ctx.rotate(...)

                    // 水果本体
                    ctx.beginPath();
                    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
                    ctx.fillStyle = this.color;
                    ctx.fill();

                    // 高光效果
                    ctx.beginPath();
                    ctx.arc(-15, -15, 10, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(255,255,255,0.3)";
                    ctx.fill();

                    // 边框
                    ctx.lineWidth = 3;
                    ctx.strokeStyle = "#fff";
                    ctx.stroke();

                    // 文字
                    ctx.fillStyle = "#333";
                    ctx.font = "bold 20px 'Microsoft YaHei', sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";

                    // 简单换行处理
                    let text = this.meaning;
                    if (text.length > 5) {{
                         ctx.fillText(text.substring(0, 5), 0, -8);
                         ctx.fillText(text.substring(5, 10) + (text.length>10?"..":""), 0, 12);
                    }} else {{
                        ctx.fillText(text, 0, 0);
                    }}

                    ctx.restore();
                }}
            }}

            class Particle {{
                constructor(x, y, color) {{
                    this.x = x;
                    this.y = y;
                    this.vx = (Math.random() - 0.5) * 12;
                    this.vy = (Math.random() - 0.5) * 12;
                    this.life = 1.0;
                    this.color = color;
                }}
                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.life -= 0.04;
                }}
                draw() {{
                    ctx.globalAlpha = this.life;
                    ctx.fillStyle = this.color;
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, Math.random()*5 + 2, 0, Math.PI*2);
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                }}
            }}

            // ------------------ 输入逻辑 ------------------

            // 鼠标/触摸处理
            let isDragging = false;

            function handleInput(x, y) {{
                // 【修改点3】刀光优化: 只保留最近的几个点，且消失极快
                bladePath.push({{x: x, y: y, life: 6}}); // life 从 10 降到 6

                if (isPlaying) {{
                    checkCollision(x, y);
                }}
            }}

            ['mousemove', 'touchmove'].forEach(evt => {{
                canvas.addEventListener(evt, (e) => {{
                    e.preventDefault();
                    let cx, cy;
                    if(e.touches) {{
                        const rect = canvas.getBoundingClientRect();
                        cx = e.touches[0].clientX - rect.left;
                        cy = e.touches[0].clientY - rect.top;
                    }} else {{
                        cx = e.offsetX;
                        cy = e.offsetY;
                        // 只有按下鼠标时才算切
                        if(evt === 'mousemove' && e.buttons !== 1) return; 
                    }}
                    handleInput(cx, cy);
                }}, {{passive: false}});
            }});

            // ------------------ 游戏逻辑 ------------------

            function checkCollision(mx, my) {{
                for (let i = fruits.length - 1; i >= 0; i--) {{
                    let f = fruits[i];
                    let dx = mx - f.x;
                    let dy = my - f.y;

                    if (dx*dx + dy*dy < f.radius*f.radius && !f.sliced) {{
                        sliceFruit(f, i);
                    }}
                }}
            }}

            function sliceFruit(f, index) {{
                f.sliced = true;
                createExplosion(f.x, f.y, f.color);
                fruits.splice(index, 1);

                // 【修改点4】得分机制：+10 / -5
                if (f.isCorrect) {{
                    score += 10;
                    showFloatingText("+10", f.x, f.y, "#00e676");
                    pickNewWord(); // 只有切对了才换词
                    // 清空屏幕上其他干扰项，避免误切？
                    // 也可以不清空，看难度。这里选择不清空，更有趣
                }} else {{
                    score -= 5;
                    showFloatingText("-5", f.x, f.y, "#ff4444");
                    // 切错了不换词，直到切对为止
                }}

                document.getElementById('score-val').innerText = score;
            }}

            function showFloatingText(text, x, y, color) {{
                const el = document.createElement('div');
                el.className = 'float-score';
                el.innerText = text;
                el.style.left = x + 'px';
                el.style.top = y + 'px';
                el.style.color = color;
                document.body.appendChild(el);
                setTimeout(() => el.remove(), 1000);
            }}

            function createExplosion(x, y, color) {{
                for(let i=0; i<12; i++) particles.push(new Particle(x, y, color));
            }}

            function pickNewWord() {{
                if (vocabList.length === 0) return;
                const idx = Math.floor(Math.random() * vocabList.length);
                currentTarget = vocabList[idx];
                document.getElementById('current-word').innerText = currentTarget.word;
            }}

            function spawnWave() {{
                if (!currentTarget) return;

                // 确保屏幕上始终有机会切到正确的
                // 如果屏幕上已经有正确的了，就只发射干扰项
                const hasCorrectOnScreen = fruits.some(f => f.isCorrect);

                let count = Math.random() > 0.5 ? 1 : 2; // 一次发射1-2个

                for(let i=0; i<count; i++) {{
                    let isTarget = false;

                    if (!hasCorrectOnScreen && i === 0) {{
                        isTarget = true; // 强制生成一个正确的
                    }} else {{
                        // 20% 概率生成正确的（如果屏幕上已经有了）
                        // 主要是为了混淆
                        isTarget = (Math.random() < 0.2);
                    }}

                    let meaning = "";
                    if (isTarget) {{
                        meaning = currentTarget.meaning;
                    }} else {{
                        // 随机找个错误的
                        let r = vocabList[Math.floor(Math.random() * vocabList.length)];
                        meaning = r.meaning;
                        // 简单防止随机到了正确意思
                        if(meaning === currentTarget.meaning) meaning = "Wrong"; 
                    }}

                    fruits.push(new Fruit(meaning, isTarget));
                }}
            }}

            function startGame() {{
                if (vocabList.length < 4) {{
                    alert("单词太少啦！"); return;
                }}
                score = 0;
                timeLeft = settings.duration;
                fruits = [];
                particles = [];
                bladePath = [];
                isPlaying = true;

                document.getElementById('score-val').innerText = "0";
                document.getElementById('time-val').innerText = timeLeft;
                document.getElementById('start-screen').style.display = 'none';
                document.getElementById('game-over-screen').style.display = 'none';

                pickNewWord();
                requestAnimationFrame(loop);
            }}

            function gameOver() {{
                isPlaying = false;
                document.getElementById('final-score').innerText = "Final Score: " + score;
                document.getElementById('game-over-screen').style.display = 'flex';

                // 更新最高分
                if (score > highScore) {{
                    highScore = score;
                    localStorage.setItem('vocabNinjaHighScore', highScore);
                    document.getElementById('best-val').innerText = highScore;
                }}
            }}

            function loop(timestamp) {{
                if (!isPlaying) return;

                const dt = timestamp - lastTime;
                lastTime = timestamp;

                ctx.clearRect(0, 0, width, height);

                // 计时器逻辑
                // 使用 Date 或者 frame 计数不准，这里简单用帧减
                // 最好是用 timestamp 差值
                // 简单处理：每秒调用一次的逻辑
                if (Math.floor(timestamp / 1000) > Math.floor((timestamp - dt) / 1000)) {{
                    timeLeft--;
                    document.getElementById('time-val').innerText = timeLeft;

                    // 进度条
                    const pct = (timeLeft / settings.duration) * 100;
                    document.getElementById('timer-bar-fill').style.width = pct + "%";

                    if (timeLeft <= 0) {{
                        gameOver();
                        return;
                    }}
                }}

                // 生成逻辑
                if (timestamp - spawnTimer > 1500) {{ // 每1.5秒检查一次生成
                    spawnTimer = timestamp;
                    spawnWave();
                }}

                // 绘制物体
                fruits.forEach((f, i) => {{
                    f.update();
                    f.draw();
                    if (f.y > height + 100) fruits.splice(i, 1);
                }});

                particles.forEach((p, i) => {{
                    p.update();
                    p.draw();
                    if (p.life <= 0) particles.splice(i, 1);
                }});

                // 绘制刀光 - 快速消失
                if (bladePath.length > 1) {{
                    ctx.beginPath();
                    ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
                    ctx.lineWidth = 4;
                    ctx.lineCap = "round";
                    ctx.lineJoin = "round";

                    // 绘制平滑曲线
                    ctx.moveTo(bladePath[0].x, bladePath[0].y);
                    for (let i = 1; i < bladePath.length; i++) {{
                        const p = bladePath[i];
                        ctx.lineTo(p.x, p.y);
                        // 【修改点3】加速生命衰减，产生“一闪而过”的效果
                        p.life -= 1; 
                    }}
                    ctx.stroke();
                    // 移除过期的点
                    bladePath = bladePath.filter(p => p.life > 0);
                }}

                requestAnimationFrame(loop);
            }}

        </script>
    </body>
    </html>
    """


# ==========================================
# 3. Streamlit 主程序 (包含新的设置项)
# ==========================================
st.set_page_config(layout="wide", page_title="Vocab Ninja Pro")

st.title("🥷 单词切水果 (Arcade Mode)")

# 侧边栏布局
with st.sidebar:
    st.header("⚙️ 游戏设置")
    uploaded_file = st.file_uploader("1. 上传 PDF", type="pdf")

    st.markdown("---")
    st.write("2. 难度调节")
    # 速度滑块：0.5 (慢) -> 1.5 (快)
    speed_setting = st.slider("水果下落速度", 0.5, 1.5, 0.8, 0.1)

    # 时间滑块：30秒 -> 5分钟
    duration_setting = st.slider("每局时间 (秒)", 30, 300, 60, 10)

    st.markdown("---")
    st.info("提示：\n- 砍对 +10分\n- 砍错 -5分\n- 倒计时结束游戏")

if uploaded_file is not None:
    # 解析 PDF
    vocab_data = parse_pdf(uploaded_file)

    if len(vocab_data) > 0:
        # 准备数据包
        vocab_json = json.dumps(vocab_data, ensure_ascii=False)
        settings_json = json.dumps({
            "speed": speed_setting,
            "duration": duration_setting
        })

        # 渲染游戏
        import streamlit.components.v1 as components

        # 这里的 key 参数很重要，当设置改变时，强制重新渲染组件
        components.html(
            get_game_html(vocab_json, settings_json),
            height=800,
            scrolling=False
        )
    else:
        st.error("未能从PDF中识别出单词，请确保PDF包含表格数据。")
else:
    st.write("👈 请先在左侧上传 PDF 文件")