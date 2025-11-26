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
#    修复说明：改为普通字符串模板，避免 f-string 语法错误
# ==========================================
def get_game_html(vocab_json, settings_json):
    # 使用普通字符串 (注意：JS中的花括号现在不需要双写了，直接写 { } 即可)
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { margin: 0; overflow: hidden; background-color: #222; font-family: 'Segoe UI', sans-serif; user-select: none; -webkit-user-select: none; }
            #gameCanvas { display: block; margin: 0 auto; background: linear-gradient(to bottom, #141E30, #243B55); cursor: crosshair; }
            
            #ui-layer { position: absolute; top: 0; width: 100%; height: 100%; pointer-events: none; }
            
            .hud-container { display: flex; justify-content: space-between; padding: 20px 40px; }
            .hud-box { color: white; text-shadow: 0 0 5px #00e676; font-weight: bold; font-size: 28px; font-family: monospace; }
            
            #current-word-container { position: absolute; top: 8%; width: 100%; text-align: center; }
            #current-word { 
                font-size: 64px; color: #fff; 
                text-shadow: 0 4px 10px rgba(0,0,0,0.8);
                background: rgba(255,255,255,0.1); 
                padding: 15px 50px; border-radius: 20px; display: inline-block; 
                border: 1px solid rgba(255,255,255,0.3);
                backdrop-filter: blur(4px);
            }

            #timer-bar-bg { position: absolute; bottom: 0; left: 0; width: 100%; height: 8px; background: #333; }
            #timer-bar-fill { height: 100%; background: linear-gradient(90deg, #00e676, #00C853); width: 100%; transition: width 0.1s linear; }

            #start-screen, #game-over-screen { 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(10,10,10,0.95); display: flex; flex-direction: column; 
                justify-content: center; align-items: center; z-index: 10; pointer-events: auto;
            }
            
            button { 
                font-size: 24px; padding: 15px 40px; background: #2979FF; 
                color: white; border: none; border-radius: 8px; cursor: pointer; 
                margin-top: 30px; box-shadow: 0 4px 0 #1565C0; font-family: monospace;
            }
            button:active { transform: translateY(4px); box-shadow: none; }
            
            h1 { color: #2979FF; font-size: 50px; margin: 0 0 10px 0; letter-spacing: 5px; }
            h2 { color: #eee; font-size: 24px; font-weight: normal; margin: 0 0 30px 0; opacity: 0.8; }

            .float-score { position: absolute; font-weight: bold; font-size: 32px; animation: floatUp 0.8s ease-out forwards; pointer-events: none; z-index: 5; text-shadow: 0 0 5px black; }
            @keyframes floatUp { 0% { opacity: 1; transform: translateY(0) scale(1); } 100% { opacity: 0; transform: translateY(-60px) scale(1.5); } }
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
            // 数据注入点
            const vocabList = __VOCAB_PLACEHOLDER__;
            const settings = __SETTINGS_PLACEHOLDER__;
            
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
            let lastWordChangeTime = 0;
            const speedMultiplier = settings.speed; 

            function resize() {
                width = window.innerWidth;
                height = window.innerHeight;
                canvas.width = width;
                canvas.height = height;
            }
            window.addEventListener('resize', resize);
            resize();

            // ------------------ 物理与对象 ------------------

            class Fruit {
                constructor(meaning, isCorrect) {
                    this.radius = 60;
                    this.x = Math.random() * (width - 160) + 80;
                    this.y = height + this.radius + 10;
                    
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
                }

                update() {
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vy += this.gravity;
                }

                draw() {
                    ctx.save();
                    ctx.translate(this.x, this.y);
                    
                    // 气泡
                    ctx.beginPath();
                    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
                    ctx.fillStyle = this.color;
                    ctx.fill();
                    
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
                    if (text.length > 6) {
                         ctx.fillText(text.substring(0, 6), 0, -12);
                         ctx.fillText(text.substring(6, 12) + (text.length>12?"..":""), 0, 15);
                    } else {
                        ctx.fillText(text, 0, 0);
                    }
                    ctx.restore();
                }
            }

            class ImpactRing {
                constructor(x, y) { this.x = x; this.y = y; this.radius = 10; this.alpha = 1; }
                update() { this.radius += 5; this.alpha -= 0.08; }
                draw() {
                    ctx.save();
                    ctx.globalAlpha = this.alpha;
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.radius, 0, Math.PI*2);
                    ctx.strokeStyle = "#fff";
                    ctx.lineWidth = 4;
                    ctx.stroke();
                    ctx.restore();
                }
            }

            class Particle {
                constructor(x, y, color) {
                    this.x = x; this.y = y; this.color = color;
                    this.vx = (Math.random() - 0.5) * 15;
                    this.vy = (Math.random() - 0.5) * 15;
                    this.life = 1.0;
                }
                update() {
                    this.x += this.vx; this.y += this.vy;
                    this.life -= 0.03; this.vy += 0.15;
                }
                draw() {
                    ctx.globalAlpha = this.life;
                    ctx.fillStyle = this.color;
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, Math.random()*6+2, 0, Math.PI*2);
                    ctx.fill();
                    ctx.globalAlpha = 1;
                }
            }

            // ------------------ 游戏逻辑 ------------------

            function shuffleDeck() {
                cardDeck = Array.from({length: vocabList.length}, (_, i) => i);
                for (let i = cardDeck.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [cardDeck[i], cardDeck[j]] = [cardDeck[j], cardDeck[i]];
                }
            }

            function pickNewWord() {
                if (vocabList.length === 0) return;
                if (cardDeck.length === 0) shuffleDeck();
                
                const idx = cardDeck.pop();
                currentTarget = vocabList[idx];
                document.getElementById('current-word').innerText = currentTarget.word;
                lastWordChangeTime = Date.now();
            }

            function spawnWave() {
                if (!currentTarget) return;

                const now = Date.now();
                const correctIsOnScreen = fruits.some(f => f.isCorrect);
                const inGracePeriod = (now - lastWordChangeTime) < 800;

                let waveFruits = [];
                let needCorrect = false;

                if (inGracePeriod) {
                    if (Math.random() < 0.3) waveFruits.push(createDistractor());
                } 
                else if (!correctIsOnScreen) {
                    needCorrect = true;
                }
                else {
                    if (Math.random() < 0.4) waveFruits.push(createDistractor());
                }

                if (needCorrect) {
                    waveFruits.push(new Fruit(currentTarget.meaning, true));
                    waveFruits.push(createDistractor()); 
                    if (Math.random() > 0.5) waveFruits.push(createDistractor());
                }

                waveFruits.forEach(f => fruits.push(f));
            }

            function createDistractor() {
                let r = vocabList[Math.floor(Math.random() * vocabList.length)];
                let meaning = r.meaning;
                if (meaning === currentTarget.meaning) meaning = "Thinking..."; 
                return new Fruit(meaning, false);
            }

            function startGame() {
                if (vocabList.length < 4) { alert("单词量太少(需>4个)"); return; }
                bgm.play().catch(e => console.log("Audio autoplay blocked"));
                
                score = 0;
                timeLeft = settings.duration;
                fruits = [];
                particles = [];
                impactEffects = [];
                isPlaying = true;
                
                shuffleDeck();
                document.getElementById('score-val').innerText = "0";
                document.getElementById('time-val').innerText = timeLeft;
                document.getElementById('start-screen').style.display = 'none';
                document.getElementById('game-over-screen').style.display = 'none';
                
                pickNewWord();
                requestAnimationFrame(loop);
            }

            // ------------------ 交互 ------------------

            function handleInput(x, y) {
                if (!isPlaying) return;
                impactEffects.push(new ImpactRing(x, y));
                for (let i = fruits.length - 1; i >= 0; i--) {
                    let f = fruits[i];
                    let dx = x - f.x; let dy = y - f.y;
                    if (dx*dx + dy*dy < f.radius*f.radius) {
                        hitFruit(f, i);
                        break; 
                    }
                }
            }

            canvas.addEventListener('mousedown', e => {
                const r = canvas.getBoundingClientRect();
                handleInput(e.clientX - r.left, e.clientY - r.top);
            });
            canvas.addEventListener('touchstart', e => {
                e.preventDefault();
                const r = canvas.getBoundingClientRect();
                handleInput(e.touches[0].clientX - r.left, e.touches[0].clientY - r.top);
            }, {passive: false});

            function hitFruit(f, index) {
                playHitSound(f.isCorrect);
                createExplosion(f.x, f.y, f.color);
                fruits.splice(index, 1);

                if (f.isCorrect) {
                    score += 10;
                    showFloatingText("+10", f.x, f.y, "#00e676");
                    pickNewWord(); 
                } else {
                    score -= 5;
                    showFloatingText("-5", f.x, f.y, "#ff4444");
                }
                document.getElementById('score-val').innerText = score;
            }

            const AudioContext = window.AudioContext || window.webkitAudioContext;
            const audioCtx = new AudioContext();
            function playHitSound(isGood) {
                if(audioCtx.state === 'suspended') audioCtx.resume();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                if (isGood) {
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(800, audioCtx.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.1);
                } else {
                    osc.type = 'square';
                    osc.frequency.setValueAtTime(150, audioCtx.currentTime);
                    osc.frequency.linearRampToValueAtTime(50, audioCtx.currentTime + 0.15);
                }
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
                osc.start(); osc.stop(audioCtx.currentTime + 0.15);
            }

            function showFloatingText(text, x, y, color) {
                const el = document.createElement('div');
                el.className = 'float-score'; el.innerText = text;
                el.style.left = x + 'px'; el.style.top = y + 'px'; el.style.color = color;
                document.body.appendChild(el);
                setTimeout(() => el.remove(), 800);
            }
            function createExplosion(x, y, color) {
                for(let i=0; i<12; i++) particles.push(new Particle(x, y, color));
            }

            function loop(timestamp) {
                if (!isPlaying) return;
                const dt = timestamp - lastTime; lastTime = timestamp;
                ctx.clearRect(0, 0, width, height);

                if (Math.floor(timestamp/1000) > Math.floor((timestamp-dt)/1000)) {
                    timeLeft--;
                    document.getElementById('time-val').innerText = timeLeft;
                    document.getElementById('timer-bar-fill').style.width = (timeLeft/settings.duration)*100 + "%";
                    if (timeLeft <= 0) {
                        isPlaying = false; bgm.pause(); bgm.currentTime = 0;
                        document.getElementById('final-score').innerText = "Score: " + score;
                        document.getElementById('game-over-screen').style.display = 'flex';
                        return;
                    }
                }

                if (timestamp - spawnTimer > 1000) { 
                    spawnTimer = timestamp;
                    spawnWave();
                }

                impactEffects.forEach((e, i) => { e.update(); e.draw(); if(e.alpha<=0) impactEffects.splice(i,1); });
                fruits.forEach((f, i) => { f.update(); f.draw(); if(f.y > height+100) fruits.splice(i,1); });
                particles.forEach((p, i) => { p.update(); p.draw(); if(p.life<=0) particles.splice(i,1); });
                requestAnimationFrame(loop);
            }
        </script>
    </body>
    </html>
    """
    
    # 手动替换数据占位符，安全且无语法错误
    return html_template.replace("__VOCAB_PLACEHOLDER__", vocab_json).replace("__SETTINGS_PLACEHOLDER__", settings_json)

# ==========================================
# 3. Streamlit 主程序
# ==========================================
st.set_page_config(layout="wide", page_title="Vocab Tap Final")

st.title("🎵 节奏单词 (Final Ver.)")

with st.sidebar:
    st.header("游戏设置")
    uploaded_file = st.file_uploader("1. 上传 PDF", type="pdf")
    st.markdown("---")
    speed_setting = st.slider("下落重力 (速度)", 0.5, 1.5, 0.9, 0.1)
    duration_setting = st.slider("游戏时长 (秒)", 30, 300, 60, 10)
    st.markdown("---")
    st.info("💡 机制更新：\n- 正确答案绝不单独出现\n- 正确答案会反复刷新直到答对\n- 新词有短暂观察期")

if uploaded_file is not None:
    vocab_data = parse_pdf(uploaded_file)
    if len(vocab_data) > 0:
        vocab_json = json.dumps(vocab_data, ensure_ascii=False)
        settings_json = json.dumps({"speed": speed_setting, "duration": duration_setting})
        
        import streamlit.components.v1 as components
        components.html(get_game_html(vocab_json, settings_json), height=800, scrolling=False)
    else:
        st.error("未能识别单词，请检查PDF格式。")
else:
    st.write("👈 请先上传 PDF 开始游戏")