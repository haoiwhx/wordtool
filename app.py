import streamlit as st
import pdfplumber
import pandas as pd
import json
import re
import base64


# ==========================================
# 1. PDF 解析逻辑 (针对你的双栏表格格式)
# ==========================================
def parse_pdf(uploaded_file):
    vocab_list = []

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                # 尝试提取表格
                # 你的PDF看起来有明显的边框，extract_tables 应该效果不错
                tables = page.extract_tables()

                for table in tables:
                    for row in table:
                        # 过滤无效行 (例如表头 No. Word Meaning)
                        # 我们假设一行里有数据，且不是表头
                        if not row or row[0] == 'No.' or row[1] == 'Word':
                            continue

                        # 处理左栏 (索引 0, 1, 2)
                        if len(row) >= 3 and row[1] and row[2]:
                            word = str(row[1]).strip()
                            meaning = str(row[2]).strip().replace('\n', ' ')  # 去除换行符
                            if word and meaning:
                                vocab_list.append({"word": word, "meaning": meaning})

                        # 处理右栏 (索引 3, 4, 5) - 如果表格被识别为一行6列
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
# 2. 前端游戏代码 (HTML/JS/CSS)
# ==========================================
def get_game_html(vocab_json):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; overflow: hidden; background-color: #222; font-family: 'Segoe UI', sans-serif; }}
            #gameCanvas {{ display: block; margin: 0 auto; background: linear-gradient(to bottom, #1a2a6c, #b21f1f, #fdbb2d); }}
            #ui-layer {{ position: absolute; top: 10px; width: 100%; text-align: center; pointer-events: none; }}
            .hud-text {{ color: white; text-shadow: 2px 2px 4px #000; font-weight: bold; }}
            #current-word {{ font-size: 48px; color: #fff; background: rgba(0,0,0,0.5); padding: 10px 20px; border-radius: 10px; display: inline-block; }}
            #score {{ font-size: 24px; position: absolute; left: 20px; top: 20px; }}
            #lives {{ font-size: 24px; position: absolute; right: 20px; top: 20px; }}
            #start-btn {{ pointer-events: auto; font-size: 24px; padding: 15px 40px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 200px; }}
            #game-over {{ display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 10; }}
        </style>
    </head>
    <body>
        <div id="ui-layer">
            <div id="score">Score: 0</div>
            <div id="lives">Lives: ❤️❤️❤️</div>
            <br/>
            <div id="current-word">Ready?</div>
        </div>

        <div id="game-over" style="display:none;">
            <h1 class="hud-text" style="font-size: 60px; color: #ff4444;">GAME OVER</h1>
            <h2 class="hud-text" id="final-score">Score: 0</h2>
            <button id="start-btn" onclick="startGame()">Restart</button>
        </div>

        <canvas id="gameCanvas"></canvas>

        <script>
            // 1. 获取 Python 传来的数据
            const vocabList = {vocab_json};

            // 游戏配置
            const canvas = document.getElementById('gameCanvas');
            const ctx = canvas.getContext('2d');
            let width, height;

            // 状态变量
            let score = 0;
            let lives = 3;
            let isPlaying = false;
            let currentTarget = null; // 当前需要找的单词对象
            let fruits = []; // 屏幕上的水果
            let particles = []; // 切割特效
            let bladePath = []; // 刀光轨迹
            let difficulty = 1.0;
            let lastSpawnTime = 0;

            // 初始化 Canvas
            function resize() {{
                width = window.innerWidth;
                height = window.innerHeight;
                canvas.width = width;
                canvas.height = height;
            }}
            window.addEventListener('resize', resize);
            resize();

            // ------------------ 游戏逻辑核心 ------------------

            class Fruit {{
                constructor(meaning, isCorrect) {{
                    this.x = Math.random() * (width - 100) + 50;
                    this.y = height + 50;
                    // 物理抛射: 向上速度 + 水平随机速度
                    this.vx = (Math.random() - 0.5) * 4; 
                    this.vy = -(Math.random() * 5 + 10 + (difficulty * 0.5)); 
                    this.radius = 60;
                    this.meaning = meaning;
                    this.isCorrect = isCorrect;
                    this.color = isCorrect ? '#4CAF50' : '#FF5722'; // 调试用: 正确绿，错误红 (实际为了游戏性可以统一颜色，或者用不同水果图)
                    // 为了增加难度，我们让颜色随机，不让颜色提示答案
                    this.renderColor = `hsl(${{Math.random() * 360}}, 70%, 60%)`;
                    this.gravity = 0.2;
                    this.rotation = 0;
                    this.rotSpeed = (Math.random() - 0.5) * 0.2;
                    this.sliced = false;
                }}

                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vy += this.gravity;
                    this.rotation += this.rotSpeed;
                }}

                draw() {{
                    ctx.save();
                    ctx.translate(this.x, this.y);
                    ctx.rotate(this.rotation);

                    // 绘制水果背景 (圆形)
                    ctx.beginPath();
                    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
                    ctx.fillStyle = this.renderColor;
                    ctx.fill();
                    ctx.lineWidth = 3;
                    ctx.strokeStyle = "#fff";
                    ctx.stroke();

                    // 绘制文字 (自动换行逻辑简化)
                    ctx.fillStyle = "#fff";
                    ctx.font = "bold 16px Arial";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";

                    // 简单截断过长文字
                    let text = this.meaning;
                    if(text.length > 8) text = text.substring(0, 8) + '...';
                    ctx.fillText(text, 0, 0);

                    ctx.restore();
                }}
            }}

            class Particle {{
                constructor(x, y, color) {{
                    this.x = x;
                    this.y = y;
                    this.vx = (Math.random() - 0.5) * 10;
                    this.vy = (Math.random() - 0.5) * 10;
                    this.life = 1.0;
                    this.color = color;
                }}
                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.life -= 0.05;
                }}
                draw() {{
                    ctx.globalAlpha = this.life;
                    ctx.fillStyle = this.color;
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, 5, 0, Math.PI*2);
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                }}
            }}

            // ------------------ 控制逻辑 ------------------

            // 鼠标/触摸追踪
            let mouseX = 0, mouseY = 0;
            let isMouseDown = false;

            canvas.addEventListener('mousedown', () => isMouseDown = true);
            canvas.addEventListener('mouseup', () => isMouseDown = false);
            canvas.addEventListener('mousemove', (e) => {{
                const rect = canvas.getBoundingClientRect();
                mouseX = e.clientX - rect.left;
                mouseY = e.clientY - rect.top;

                if (isMouseDown) {{
                    bladePath.push({{x: mouseX, y: mouseY, life: 10}});
                    checkCollision(mouseX, mouseY);
                }}
            }});

            // 触摸支持
            canvas.addEventListener('touchstart', (e) => {{ isMouseDown = true; }}, {{passive: false}});
            canvas.addEventListener('touchend', (e) => {{ isMouseDown = false; }}, {{passive: false}});
            canvas.addEventListener('touchmove', (e) => {{
                e.preventDefault(); 
                const rect = canvas.getBoundingClientRect();
                mouseX = e.touches[0].clientX - rect.left;
                mouseY = e.touches[0].clientY - rect.top;
                bladePath.push({{x: mouseX, y: mouseY, life: 10}});
                checkCollision(mouseX, mouseY);
            }}, {{passive: false}});

            function checkCollision(mx, my) {{
                if (!isPlaying) return;

                for (let i = fruits.length - 1; i >= 0; i--) {{
                    let f = fruits[i];
                    let dx = mx - f.x;
                    let dy = my - f.y;
                    let dist = Math.sqrt(dx*dx + dy*dy);

                    if (dist < f.radius && !f.sliced) {{
                        sliceFruit(f, i);
                    }}
                }}
            }}

            function sliceFruit(f, index) {{
                f.sliced = true;
                createExplosion(f.x, f.y, f.renderColor);
                fruits.splice(index, 1);

                if (f.isCorrect) {{
                    // 切对了
                    score += 10;
                    difficulty += 0.1;
                    document.getElementById('score').innerText = "Score: " + score;
                    // 立即生成下一个单词
                    pickNewWord();
                }} else {{
                    // 切错了
                    lives--;
                    updateLives();
                    if (lives <= 0) gameOver();
                }}
            }}

            function createExplosion(x, y, color) {{
                for(let i=0; i<15; i++) {{
                    particles.push(new Particle(x, y, color));
                }}
            }}

            function updateLives() {{
                let s = "";
                for(let i=0; i<lives; i++) s += "❤️";
                document.getElementById('lives').innerText = "Lives: " + s;
            }}

            // ------------------ 游戏流程 ------------------

            function pickNewWord() {{
                if (vocabList.length === 0) return;
                const idx = Math.floor(Math.random() * vocabList.length);
                currentTarget = vocabList[idx];
                document.getElementById('current-word').innerText = currentTarget.word;

                // 清空当前水果，准备发射新的一波
                // fruits = []; (保留这个注释，如果不希望清空屏幕上的水果可以不去掉，增加混乱度)
            }}

            function spawnWave() {{
                if (!currentTarget) return;

                // 决定抛出几个水果 (1个正确 + 1~2个干扰)
                const correctMeaning = currentTarget.meaning;

                // 选取干扰项
                let distractors = [];
                while(distractors.length < 2) {{
                    let r = vocabList[Math.floor(Math.random() * vocabList.length)];
                    if (r.meaning !== correctMeaning) {{
                        distractors.push(r.meaning);
                    }}
                }}

                // 创建水果对象
                let wave = [];
                wave.push(new Fruit(correctMeaning, true));
                distractors.forEach(d => wave.push(new Fruit(d, false)));

                // 只有当屏幕上正确答案很少时才发射
                // 这里的逻辑：随机时间间隔发射
                wave.forEach(f => fruits.push(f));
            }}

            function startGame() {{
                if (vocabList.length < 4) {{
                    alert("单词表太少，无法开始游戏！请至少上传包含4个单词的PDF。");
                    return;
                }}
                score = 0;
                lives = 3;
                difficulty = 1.0;
                fruits = [];
                particles = [];
                bladePath = [];
                isPlaying = true;

                document.getElementById('game-over').style.display = 'none';
                document.getElementById('score').innerText = "Score: 0";
                updateLives();

                pickNewWord();
                loop();
            }}

            function gameOver() {{
                isPlaying = false;
                document.getElementById('final-score').innerText = "Final Score: " + score;
                document.getElementById('game-over').style.display = 'flex';
            }}

            function loop(timestamp) {{
                if (!isPlaying) return;

                ctx.clearRect(0, 0, width, height);

                // 生成逻辑: 每隔一段时间抛出一波
                // 随着难度增加，间隔变短
                if (timestamp - lastSpawnTime > (2000 / difficulty)) {{
                    spawnWave();
                    lastSpawnTime = timestamp;
                }}

                // 更新和绘制水果
                for (let i = fruits.length - 1; i >= 0; i--) {{
                    let f = fruits[i];
                    f.update();
                    f.draw();
                    // 掉出屏幕移除
                    if (f.y > height + 100) {{
                        fruits.splice(i, 1);
                        // 如果漏掉了正确的，不扣分，但是得重新抛出，或者扣分？
                        // 简单起见：漏掉不扣分，等待下次抛出
                    }}
                }}

                // 更新和绘制粒子
                for (let i = particles.length - 1; i >= 0; i--) {{
                    let p = particles[i];
                    p.update();
                    p.draw();
                    if (p.life <= 0) particles.splice(i, 1);
                }}

                // 绘制刀光
                if (bladePath.length > 0) {{
                    ctx.beginPath();
                    ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
                    ctx.lineWidth = 5;
                    ctx.lineCap = "round";
                    ctx.moveTo(bladePath[0].x, bladePath[0].y);
                    for (let i = 1; i < bladePath.length; i++) {{
                        ctx.lineTo(bladePath[i].x, bladePath[i].y);
                        bladePath[i].life--;
                    }}
                    ctx.stroke();
                    // 移除旧轨迹
                    bladePath = bladePath.filter(p => p.life > 0);
                }}

                requestAnimationFrame(loop);
            }}

            // 初始显示开始界面
            document.getElementById('game-over').style.display = 'flex';
            document.getElementById('start-btn').innerText = "Start Game";

        </script>
    </body>
    </html>
    """


# ==========================================
# 3. Streamlit 主程序
# ==========================================
st.set_page_config(layout="wide", page_title="Vocab Ninja")

st.title("🥷 单词切水果 (Vocab Ninja)")
st.markdown("上传你的PDF单词表，通过切水果游戏来记忆单词含义！")

# 侧边栏：文件上传
with st.sidebar:
    uploaded_file = st.file_uploader("上传 PDF 文件", type="pdf")
    st.info("提示：PDF格式需如截图所示（表格，包含Word和Meaning列）")

if uploaded_file is not None:
    # 1. 解析 PDF
    with st.spinner("正在解析单词书..."):
        vocab_data = parse_pdf(uploaded_file)

    if len(vocab_data) > 0:
        st.success(f"成功提取 {len(vocab_data)} 个单词！")

        # 将数据转为JSON字符串传给前端
        vocab_json = json.dumps(vocab_data, ensure_ascii=False)

        # 2. 嵌入游戏
        # 使用 components.html 渲染自定义 HTML/JS
        # height 设置高一点以容纳全屏游戏体验
        import streamlit.components.v1 as components

        components.html(get_game_html(vocab_json), height=800, scrolling=False)

    else:
        st.error("未能识别单词，请检查PDF格式是否符合要求（需包含表格结构）。")

else:
    st.write("👈 请在左侧上传 PDF 开始游戏")