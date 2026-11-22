/* ═══════════ 中文发音智能诊断与评价系统 · 整合演示 · 前端逻辑 ═══════════
   三角色：student 学生端 / teacher 教师端 / admin 管理端
   全部数据为预先准备的示例，存于 data.js；跨角色联动通过共享内存数组实现：
     QUESTIONS  教师题目管理 ⇄ 学生测评题目列表
     HW         教师作业批改（发布评语）⇄ 学生「我的作业」评语
     MIST/MIST_LOG  学生「加入错题本」实时累加
     TASKS      管理端任务分配 / 音频导入 ⇄ 教师标注工作台队列
     RECORDS    教师/标注员保存金标 ⇄ 管理端「标注记录管理」 */

const $ = id => document.getElementById(id);
let toastTimer;
function toast(msg){
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}
function nowStr(){
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function downloadFile(name, content, mime){
  const blob = new Blob([content], {type: mime || 'application/octet-stream'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
function toCsv(rows){
  return '\ufeff' + rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
}

/* ── 偏误统计（字符级 + 字间级统一口径） ── */
function errStats(tokens, gapErrs){
  const cnt = {};
  (tokens || []).forEach(t => { if (t.err) cnt[t.err.t] = (cnt[t.err.t] || 0) + 1; });
  Object.values(gapErrs || {}).forEach(e => { cnt[e.t] = (cnt[e.t] || 0) + 1; });
  return cnt;
}
function errSummary(tokens, gapErrs){
  const cnt = errStats(tokens, gapErrs);
  const parts = byTypeOrder(Object.keys(cnt)).map(k => `${ERRNAME[k]} ×${cnt[k]}`);
  return parts.length ? parts.join(' · ') : '未检出偏误';
}
function errTotal(tokens, gapErrs){
  return Object.values(errStats(tokens, gapErrs)).reduce((a, b) => a + b, 0);
}

/* ── 句子渲染：字间空隙 + 字符 交错（诊断 / 批改 / 标注工作台共用） ──
   opts: { ziErr(i)->err|null, ziPre(i), ziSel(i), ziId(i), gapErr(g), gapPre(g), gapSel(g), gapId(g), ro, en } */
function renderSentence(el, tokens, gapErrs, opts){
  opts = opts || {};
  const NM = opts.en ? ERRNAME_EN : ERRNAME;
  const gap = g => {
    const e = opts.gapErr ? opts.gapErr(g) : (gapErrs || {})[g] || null;
    const pre = opts.gapPre ? opts.gapPre(g) : false;
    const sel = opts.gapSel && opts.gapSel(g);
    const id = opts.gapId ? ` id="${opts.gapId(g)}"` : '';
    let cls = 'gap' + (opts.ro ? ' ro' : '');
    if (e) cls += ` t-err g-${e.t}`;
    if (pre) cls += ' pre';
    if (sel) cls += ' sel2';
    const inner = e ? (e.t === 'pause'
      ? '⏸ ' + (opts.en ? 'Pause' : '停顿') + (e.py ? ' ' + e.py : '')
      : `${NM[e.t]}${e.py ? ' ' + e.py : ''}`) : '＋';
    return `<span class="${cls}"${id} title="${opts.en ? 'Between-word mark: extra / filler / pause' : '字间标注：增读 / 填充词 / 停顿'}">${inner}</span>`;
  };
  const zi = i => {
    const ch = tokens[i];
    const e = opts.ziErr ? opts.ziErr(i) : ch.err || null;
    const pre = opts.ziPre ? opts.ziPre(i) : false;
    const sel = opts.ziSel && opts.ziSel(i);
    const id = opts.ziId ? ` id="${opts.ziId(i)}"` : '';
    let cls = 'zi';
    if (e) cls += ` t-${e.t}`;
    if (pre) cls += ' pre';
    if (sel) cls += ' sel2';
    const em = e
      ? `<em>${NM[e.t]}${e.py ? ' ' + e.py : ''}</em>`
      : `<em class="py">${ch.py || ''}</em>`;
    return `<span class="${cls}"${id}>${ch.c}${em}</span>`;
  };
  let html = '';
  for (let i = 0; i < tokens.length; i++){ html += gap(i) + zi(i); }
  html += gap(tokens.length);
  el.innerHTML = html;
}
function scoreCards(sc, en){
  const L = en ? ['Accuracy', 'Completeness', 'Fluency', 'Total'] : ['准确度', '完整度', '流利度', '总分'];
  return `<div class="scores">
    <div class="score"><b>${sc.acc.toFixed(1)}</b><span>${L[0]}</span></div>
    <div class="score"><b>${sc.comp.toFixed(1)}</b><span>${L[1]}</span></div>
    <div class="score"><b>${sc.flu.toFixed(1)}</b><span>${L[2]}</span></div>
    <div class="score total"><b>${sc.total.toFixed(1)}</b><span>${L[3]}</span></div>
  </div>`;
}

/* ═══════════ 登录 / 导航 ═══════════ */
const NAVS = {
  student:[['view-practice', 'Practice'], ['view-progress', 'My Progress'], ['view-mist', 'My Mistakes'], ['view-shw', 'Homework']],
  teacher:[['view-stat', '学情统计'], ['view-research', '研究统计'], ['view-class', '我的班级'], ['view-hw', '作业批改'], ['view-anno', '标注工作台'], ['view-ques', '题目管理'], ['view-pipeline', '命题流水线']],
  admin:  [['view-users', '用户管理'], ['view-assign', '任务分配'], ['view-records', '标注记录管理']],
};
const ROLE_INFO = {
  student:{badge:'Student', cls:'b-stu'},
  teacher:{badge:'教师 · 研究员', cls:'b-tea'},
  admin:  {badge:'管理员', cls:'b-admin'},
};
let LOGIN_ROLE = 'student';
let AUTH = {role:'', name:''};
let NAV_CURRENT = [];

function pickRole(r){
  LOGIN_ROLE = r;
  ['student', 'teacher', 'admin'].forEach(k =>
    $('rt' + k[0].toUpperCase() + k.slice(1)).classList.toggle('active', k === r));
  const acc = ACCOUNTS[r];
  $('liUser').value = acc.user;
  $('liPwd').value = acc.pwd;
}
function doLogin(){
  const acc = ACCOUNTS[LOGIN_ROLE];
  const user = $('liUser').value.trim(), pwd = $('liPwd').value;
  if (user === acc.user && pwd.trim()){
    AUTH = {role: LOGIN_ROLE, name: acc.name};
    $('liPwd').value = '';
    toast('欢迎，' + acc.name);
    enterApp();
  } else {
    toast('账号或密码错误（演示账号见下方提示）');
  }
}
function logout(){
  AUTH = {role:'', name:''};
  $('nav').innerHTML = '';
  $('whoami').style.display = 'none';
  document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
  $('view-login').classList.add('active');
}
function enterApp(){
  const info = ROLE_INFO[AUTH.role];
  NAV_CURRENT = NAVS[AUTH.role];
  $('nav').innerHTML = NAV_CURRENT.map(([id, name], i) =>
    `<button onclick="showViewById('${id}')" class="${i === 0 ? 'active' : ''}">${name}</button>`).join('');
  $('roleBadge').textContent = info.badge;
  $('roleBadge').className = 'badge ' + info.cls;
  $('whoName').textContent = AUTH.name;
  $('whoami').style.display = 'flex';
  showViewById(NAV_CURRENT[0][0]);
}
function navBtnOf(id){
  const btns = $('nav').querySelectorAll('button');
  const idx = NAV_CURRENT.findIndex(x => x[0] === id);
  return idx >= 0 ? btns[idx] : null;
}
function showViewById(id){ showView(id, navBtnOf(id)); }
function showView(id, btn){
  document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  $(id).classList.add('active');
  if (btn) btn.classList.add('active');
  const R = {
    'view-practice': renderPractice, 'view-progress': renderProgress, 'view-mist': renderMist, 'view-shw': renderSHW,
    'view-stat': renderStat, 'view-research': renderResearch, 'view-class': renderClass,
    'view-hw': renderHw, 'view-anno': renderAnnoState,
    'view-ques': renderQues, 'view-pipeline': renderPropositionPipeline, 'view-users': renderUsers,
    'view-assign': renderAssign, 'view-records': renderRecords,
  };
  if (R[id]) R[id]();
}

/* ═══════════ 学生端 · Practice / Instant feedback（V2 · 英语界面 · 免选择直接录音） ═══════════ */
let curQ = QUESTIONS[0], recing = false, recP = 0, recTimer = null;
let lastDiag = null;   // {d, q, archived}
let matchTries = 0;    // 跟读对比尝试次数（演示：62% → 84% → 96%）

const MIST_EN = {'二/三声混淆':'Tone 2/3 confusion', 'n/l 混淆':'n/l confusion', '平翘舌':'Flat vs retroflex',
  '漏读/增读':'Missing / extra syllable', '声调偏误':'Tone errors', '填充词':'Filler words', '漏读':'Missing syllable'};
const stars = t => t >= 90 ? '★★★' : t >= 75 ? '★★☆' : '★☆☆';

/* 趣味化音效（WebAudio 合成，无外部资源；参考多邻国的即时正反馈） */
function playChime(good){
  try{
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const notes = good ? [523, 659, 784] : [330, 262];
    notes.forEach((f, i) => {
      const o = ac.createOscillator(), g = ac.createGain();
      o.frequency.value = f; o.type = 'sine';
      g.gain.setValueAtTime(0.001, ac.currentTime + i * 0.12);
      g.gain.exponentialRampToValueAtTime(0.15, ac.currentTime + i * 0.12 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + i * 0.12 + 0.3);
      o.connect(g); g.connect(ac.destination);
      o.start(ac.currentTime + i * 0.12); o.stop(ac.currentTime + i * 0.12 + 0.32);
    });
  }catch(e){ /* 浏览器不支持时静默跳过 */ }
}

function curLevelQs(){ return QUESTIONS.filter(q => q.level === STUDENT.level); }
function pickLevel(k){
  STUDENT.level = k;
  const qs = curLevelQs();
  curQ = qs.includes(curQ) ? curQ : (qs[0] || QUESTIONS[0]);
  renderPractice(); resetDiag();
  toast('Level set to ' + ((LEVELS.find(l => l.k === k) || {}).en || k) + ' — just tap Speak!');
}
function renderPractice(){
  const lv = LEVELS.find(l => l.k === STUDENT.level) || LEVELS[0];
  $('lvlNow').textContent = lv.en;
  $('streakN').textContent = STUDENT.streak;
  $('xpN').textContent = STUDENT.xp;
  LEVELS.forEach(l => { const b = $('lv-' + l.k); if (b) b.classList.toggle('on', l.k === STUDENT.level); });
  const qs = curLevelQs();
  if (!qs.includes(curQ)) curQ = qs[0] || QUESTIONS[0];
  if (curQ){
    $('recoCard').innerHTML = `
      <div class="recocard">
        <div class="rcname">${curQ.nameEn || curQ.name}</div>
        <div class="rctext">${curQ.mode === 'A' ? curQ.text : (curQ.topic || curQ.text)}</div>
        ${curQ.mode === 'A' && curQ.tokens.length
          ? `<div class="rcpy">${curQ.tokens.map(t => t.py).filter(Boolean).join('  ')}</div>` : ''}
        <span class="chip" style="margin:8px 0 0;">${curQ.mode === 'A' ? '📖 Read aloud' : '💬 Free talk'}</span>
      </div>`;
    $('recTip').textContent = 'Ready — just tap Speak! (No need to choose word or sentence)';
  }
  $('qListLv').innerHTML = qs.map(q =>
    `<div class="chip pick${curQ && curQ.id === q.id ? ' onchip' : ''}" onclick="pickLvQ('${q.id}')">${q.nameEn || q.name}</div>`).join('')
    || '<div class="mut">No exercises in this level yet — ask your teacher.</div>';
}
function pickLvQ(id){
  if (recing){ toast('Recording — stop first'); return; }
  curQ = QUESTIONS.find(q => q.id === id) || null;
  renderPractice(); resetDiag();
  if (curQ) toast('Switched to 「' + (curQ.nameEn || curQ.name) + '」');
}
function toggleRec(){
  const btn = $('micBtn');
  if (!QUESTIONS.length){ toast('No exercises yet — ask your teacher'); return; }
  if (!curQ){ curQ = QUESTIONS[0]; renderPractice(); }
  if (!recing){
    recing = true; recP = 0;
    btn.classList.add('recging'); btn.innerHTML = '●<br>Rec';
    $('diagBtn').disabled = false;
    recTimer = setInterval(() => {
      recP += 4 + Math.random() * 6;
      $('recBar').style.width = Math.min(recP, 100) + '%';
      $('recTip').textContent = 'Recording… ' + (recP / 25).toFixed(1) + ' s (simulated)';
      if (recP >= 100){ stopRec(); runDiag(); }
    }, 220);
  } else { stopRec(); }
}
function stopRec(){
  recing = false; clearInterval(recTimer);
  const btn = $('micBtn');
  btn.classList.remove('recging'); btn.innerHTML = '🎙️<br>Speak';
  $('recTip').textContent = 'Done! Tap "Stop & check".';
}
function uploadAudio(input){
  const f = input.files && input.files[0];
  input.value = '';
  if (!f) return;
  toast(`Uploaded "${f.name}" — analyzing… (demo: sample result)`);
  if (!curQ){ curQ = QUESTIONS[0]; renderPractice(); }
  setTimeout(runDiag, 600);
}
function resetDiag(){
  lastDiag = null; matchTries = 0;
  $('diagBody').innerHTML = '<div class="mut" style="padding:60px 0; text-align:center;">Record first — you will get your score, main errors and what to do next.</div>';
}
function playStd(){ toast('Playing the standard recording (demo)'); }

/* 教师新增题目（无偏误预设）→ 生成满分示例诊断结果 */
function genericResult(q){
  return {
    name:q.name, nameEn:q.nameEn, level:q.level, mode:q.mode, text:q.text, rebuilt:q.mode === 'B' ? (q.text || '') : null,
    tokens:q.tokens.map(t => ({c:t.c, py:t.py})), gapErrs:{},
    scores:{acc:96.5, comp:100, flu:95.0, total:96.8},
    fluency:{speed:'2.5 字/秒', ratio:'2%', mlr:'1.0'}, errTypes:[],
    rep:{
      zh:'本次朗读完整、流利，未检出声韵母、声调、漏读或增读偏误，准确度与完整度均达到优秀水平。建议保持当前朗读习惯，逐步提高语速至 2.5 字/秒左右，并尝试更长篇章的朗读巩固。',
      en:'The recitation was complete and fluent. No mispronunciation, tone error, omission or insertion was detected; accuracy and completeness are both excellent. Keep up the current reading habits, gradually raise the speaking rate to about 2.5 syllables per second, and move on to longer passages.',
      th:'การอ่านครบถ้วนและคล่องแคล่ว ไม่พบความผิดพลาดของพยัญชนะต้น เสียงท้าย วรรณยุกต์ หรือการอ่านขาด/อ่านเกิน ความแม่นยำและความครบถ้วนอยู่ในระดับดีเยี่ยม แนะนำให้รักษานิสัยการอ่านปัจจุบัน เร่งความเร็วขึ้นประมาณ 2.5 พยางค์ต่อวินาที และลองอ่านบทยาวขึ้น',
    },
  };
}

function errLineMain(d){
  const out = [];
  (d.tokens || []).forEach(t => { if (t.err) out.push({c:t.c, py:t.py, e:t.err}); });
  Object.entries(d.gapErrs || {}).forEach(([g, e]) => out.push({gap:Number(g), e}));
  return out;
}
function runDiag(){
  if (recing) stopRec();
  if (!curQ){ toast('Pick an exercise first'); return; }
  const q = curQ;
  const d = q.generic ? genericResult(q) : q;
  lastDiag = {d, q, archived:false};
  const gains = d.scores.total >= 75 ? 20 : 10;
  STUDENT.xp += gains;
  $('xpN').textContent = STUDENT.xp;
  const errs = errLineMain(d);
  const shown = errs.slice(0, 4);

  let html = `<h2 class="sec" style="margin-top:0;">${d.nameEn || d.name}</h2>`;
  html += `<div class="scorering">
      <div class="ring" style="--p:${Math.max(0, Math.min(100, d.scores.total))}"><b>${d.scores.total.toFixed(0)}</b></div>
      <div style="text-align:center;">
        <div class="ststars">${stars(d.scores.total)}</div>
        <div class="cheer">${d.scores.total >= 90 ? 'Excellent! 🎉' : d.scores.total >= 75 ? 'Good job! 👍' : 'Nice try — let&#39;s fix a few sounds 💪'}</div>
        <div class="xpgain">+${gains} 积分</div>
      </div></div>`;
  if (d.mode === 'B' && d.rebuilt){
    html += `<div class="kv"><b>You said：</b>${d.rebuilt} <span class="mut">(we only check pronunciation & fluency — not the topic)</span></div>`;
  }
  if (errs.length){
    html += `<h2 class="sec" style="margin-top:10px;">Your main errors（主要错误 · 只列最要紧的）</h2><div class="errlist">`;
    shown.forEach(x => {
      if (x.c !== undefined){
        html += `<div class="errow"><span class="echar">${x.c}</span>
          <span class="edesc"><b>${ERRNAME_EN[x.e.t]}</b> — you said <b class="bad">${x.e.py || '?'}</b>, should be <b class="good">${x.py || '?'}</b></span></div>`;
      } else {
        const gNote = x.e.t === 'pause' ? `a long pause ${x.e.py || ''}`
          : x.e.t === 'ins' ? `an extra "${x.e.text || x.e.py || ''}"`
          : `a filler "${x.e.text || x.e.py || ''}"`;
        html += `<div class="errow"><span class="echar echar-gap">＋</span>
          <span class="edesc"><b>${ERRNAME_EN[x.e.t]}</b> — ${gNote}</span></div>`;
      }
    });
    if (errs.length > shown.length)
      html += `<div class="mut" style="font-size:12.5px;">…and ${errs.length - shown.length} more, see the marks below</div>`;
    html += `</div>`;
  } else {
    html += `<div class="note" style="margin:6px 0;">No errors detected — brilliant! 🎉</div>`;
  }
  html += `<div class="sent" style="margin-top:8px;" id="diagSent"></div>
    <div class="legend">
      <span class="lg errsw"></span>error character
      <span class="lg gdemo"></span>between words (extra / filler / pause)
      <span style="margin-left:10px;">Tap an error to replay that part (demo)</span>
    </div>`;
  html += `<h2 class="sec" style="margin-top:14px;">Summary &amp; next step（总体归纳与注意方向）</h2>
    <div class="repbox">${d.rep.en || d.rep.zh}</div>`;
  html += `<h2 class="sec" style="margin-top:14px;">Listen &amp; repeat（跟读标准音 · 基本一致即可通过）</h2>
    <div class="wavebox">
      <div class="waverow"><span class="wlab">Standard</span><div class="wave" id="waveStd"></div></div>
      <div class="waverow"><span class="wlab">You</span><div class="wave" id="waveYou"></div></div>
    </div>
    <div style="display:flex; align-items:center; gap:12px; margin-top:10px; flex-wrap:wrap;">
      <button class="btn ghost" onclick="playStd()">▶ Play standard</button>
      <button class="btn" onclick="tryRepeat()">🎙️ Try again</button>
      <span class="matchmeter"><i id="matchBar"></i></span>
      <b id="matchTxt" class="mut" style="font-size:13px;">Not tried yet</b>
      <span id="passTxt" style="font-size:13px;"></span>
    </div>`;
  html += `<h2 class="sec" style="margin-top:14px;">Practice similar（按你的错误推荐同类练习）</h2>
    <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
      ${(d.errTypes || []).map(t => `<span class="chip">${MIST_EN[t] || t}</span>`).join('')}
      <button class="btn sm" onclick="similarDrill()">🎯 Start similar practice</button>
    </div>`;
  html += `<div style="margin-top:14px; border-top:1px solid var(--line); padding-top:12px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <button class="btn ghost" id="archBtn" onclick="archToMist()">Add to My Mistakes</button>
      <button class="btn gray" onclick="exportDiagReport()">Export report</button>
      <span class="mut" style="font-size:12.5px;">逐字分析与流利度等专业明细在教师 / 研究员后台查看（学生端只看重点）</span></div>`;
  $('diagBody').innerHTML = html;
  renderSentence($('diagSent'), d.tokens, d.gapErrs, {ro:true, en:true});
  $('diagBody').querySelectorAll('.zi, .gap').forEach(z => {
    z.addEventListener('click', () => {
      if (z.className.includes('t-')) toast('Replaying that part… (demo)');
    });
  });
  drawWave('waveStd', 7); drawWave('waveYou', 11);
  playChime(d.scores.total >= 75);
  toast('Check done — total ' + d.scores.total.toFixed(1));
}
function drawWave(id, seed){
  const el = $(id); if (!el) return;
  let bars = '';
  for (let i = 0; i < 34; i++){
    const h = 14 + ((seed * 31 + i * 17) % 46);
    bars += `<i style="height:${h}%"></i>`;
  }
  el.innerHTML = bars;
}
function tryRepeat(){
  if (!lastDiag) return;
  matchTries++;
  const vals = [62, 84, 96];
  const v = vals[Math.min(matchTries - 1, 2)];
  const bar = $('matchBar'), txt = $('matchTxt'), pass = $('passTxt');
  if (bar) bar.style.width = v + '%';
  if (txt){
    txt.textContent = 'Match ' + v + '%';
    txt.classList.remove('mut');
    txt.style.color = v >= 84 ? 'var(--ok)' : 'var(--warn)';
  }
  if (v >= 96){
    if (pass) pass.innerHTML = '🎉 96% — great! Try a <b>Free talk</b> exercise next!';
    STUDENT.xp += 5; $('xpN').textContent = STUDENT.xp;
    playChime(true);
  } else {
    if (pass) pass.textContent = matchTries === 1 ? 'Closer! Listen once more and repeat.' : 'Almost there — one more time!';
  }
}
function similarDrill(){
  if (!lastDiag) return;
  const types = lastDiag.d.errTypes || [];
  const cand = QUESTIONS.find(x => x.id !== lastDiag.q.id && x.level === STUDENT.level &&
      (x.errTypes || []).some(t => types.includes(t)))
    || QUESTIONS.find(x => x.id !== lastDiag.q.id && (x.errTypes || []).some(t => types.includes(t)));
  if (cand){ STUDENT.level = cand.level; pickLvQ(cand.id); toast('Similar practice ready — same error type, new exercise!'); }
  else toast('More similar exercises coming — pick another one in this level');
}
function archToMist(){
  if (!lastDiag) return;
  const {d} = lastDiag;
  if (lastDiag.archived){ toast('Already in My Mistakes'); return; }
  if (!d.errTypes.length){ toast('No errors this time — nothing to add'); return; }
  lastDiag.archived = true;
  d.errTypes.forEach(t => {
    const m = MIST.find(x => x.t === t);
    if (m) m.cnt++;
    else MIST.push({t, cnt:1, ex:'—'});
  });
  const bits = [];
  d.tokens.forEach(t => { if (t.err) bits.push(`"${t.c}" ${ERRNAME_EN[t.err.t]}${t.err.py ? ' → ' + t.err.py : ''}`); });
  Object.values(d.gapErrs || {}).forEach(e => bits.push(ERRNAME_EN[e.t]));
  MIST_LOG.unshift({d:nowStr().slice(0, 5), q:d.nameEn || d.name, t:d.errTypes[0],
    det:bits.slice(0, 3).join('; ') + (bits.length > 3 ? ' …' : '')});
  const btn = $('archBtn');
  if (btn){ btn.disabled = true; btn.textContent = 'Added ✓'; }
  toast('Added to My Mistakes — see the My Mistakes page');
}
function exportDiagReport(){
  if (!lastDiag) return;
  const {d} = lastDiag;
  const out = {
    系统:'中文发音智能诊断与评价系统', 导出时间:nowStr(),
    题目:d.name, 模式:d.mode === 'A' ? '跟读（提供参考文本）' : '自由表达（无参考文本）',
    参考文本:d.mode === 'A' ? d.text : d.rebuilt,
    多维评分:d.scores, 流利度:d.fluency,
    偏误汇总:errSummary(d.tokens, d.gapErrs),
    逐字偏误:d.tokens.map((t, i) => t.err ? {字:t.c, 下标:i, 类型:ERRNAME[t.err.t], 实际读音:t.err.py || ''} : null).filter(Boolean),
    字间偏误:Object.entries(d.gapErrs || {}).map(([g, e]) => ({位置:g, 类型:ERRNAME[e.t], 说明:e.py || e.note || ''})),
    诊断报告:d.rep,
  };
  downloadFile(`诊断报告_${d.name.replace(/[·\s]/g, '_')}.json`, JSON.stringify(out, null, 1), 'application/json');
  toast('Report exported (JSON)');
}

/* ═══════════ 学生端 · My Mistakes（英语界面） ═══════════ */
function renderMist(){
  const max = Math.max(...MIST.map(m => m.cnt), 1);
  $('mistSum').innerHTML = MIST.map(m =>
    `<div class="brow"><span class="lb" style="width:170px;">${MIST_EN[m.t] || m.t}</span>
     <div class="track"><div class="fill" style="width:${m.cnt / max * 100}%"></div></div>
     <span class="val">${m.cnt}×</span></div>`).join('') || '<div class="mut">No mistakes yet 🎉</div>';
  $('mistDrill').innerHTML = MIST.map(m =>
    `<div style="margin-bottom:12px;">
      <b style="color:var(--blue);">${MIST_EN[m.t] || m.t}</b>
      <div style="margin:5px 0;">${m.ex.split('、').map(w => `<span class="chip">${w}</span>`).join('')}</div>
      <button class="btn ghost" style="padding:5px 14px; font-size:12.5px;"
        onclick="toast('Drill started: ${m.t} (demo — instant score)')">Practice</button>
    </div>`).join('');
  $('mistTable').innerHTML = '<tr><th>Date</th><th>Exercise</th><th>Type</th><th>Detail</th></tr>' +
    MIST_LOG.map(m => `<tr><td>${m.d}</td><td>${m.q}</td>
      <td><span class="chip" style="margin:0;"><b>${MIST_EN[m.t] || m.t}</b></span></td><td class="mut">${m.det}</td></tr>`).join('');
}

/* ═══════════ 学生端 · Homework（英语界面） ══════════ */
const SHW = [
  {hw:0,  name:'Homework 1 · Read aloud: The weather is nice today', deadline:'10-26', submitted:'10-25 20:31'},
  {hw:-1, name:'Homework 2 · Read aloud: He ran away', deadline:'11-09', submitted:''},
];
function renderSHW(){
  $('shwTable').innerHTML = '<tr><th>Homework</th><th>Deadline</th><th>Submitted</th><th>Score</th><th>Status</th><th>Action</th></tr>' +
    SHW.map((s, i) => {
      const h = s.hw >= 0 ? HW[s.hw] : null;
      let st, ops = '';
      if (!s.submitted){
        st = '<span class="status st-pending">To submit</span>';
        ops = `<button class="btn ghost sm" onclick="submitShw(${i})">Submit</button>`;
      } else if (h && h.st === 'ok'){
        st = '<span class="status st-ok">Graded · comment ready</span>';
        ops = `<button class="btn ghost sm" onclick="openShw(${i})">View comment</button>`;
      } else {
        st = '<span class="status st-pending">Submitted · grading</span>';
        ops = `<button class="btn ghost sm" onclick="openShw(${i})">View detail</button>`;
      }
      return `<tr><td><b>${s.name}</b></td><td>${s.deadline}</td><td>${s.submitted || '—'}</td>
        <td>${h ? `<b style="color:${h.total < 65 ? 'var(--red)' : 'var(--navy)'}">${h.total.toFixed(1)}</b>` : '—'}</td>
        <td>${st}</td><td>${ops}</td></tr>`;
    }).join('');
}
function submitShw(i){
  SHW[i].submitted = nowStr();
  renderSHW();
  toast('Submitted! Machine pre-check and teacher grading come next (demo).');
}
function openShw(i){
  const s = SHW[i], h = s.hw >= 0 ? HW[s.hw] : null;
  $('shwDetailCard').style.display = '';
  $('shwName').textContent = s.name;
  let html = '';
  if (h){
    html += `<div class="kv"><b>Submitted:</b>${s.submitted}　<b>Machine pre-check:</b> done (total ${h.total.toFixed(1)})</div>`;
    html += `<div class="sent" id="shwSent"></div>`;
    html += scoreCards(h.scores, true);
    html += h.st === 'ok'
      ? `<div class="note" style="margin-top:6px;"><b>Teacher's comment:</b>${h.comment}</div>`
      : `<div class="mut" style="padding:8px 0;">Your teacher's comment will appear here after grading.</div>`;
  } else {
    html = '<div class="mut">Not submitted yet.</div>';
  }
  $('shwDetail').innerHTML = html;
  if (h) renderSentence($('shwSent'), h.tokens, h.gapErrs, {ro:true, en:true});
  $('shwDetailCard').scrollIntoView({behavior:'smooth', block:'nearest'});
}

/* ═══════════ 教师端 · 学情统计 ══════════ */
let stuFilter = '';
function renderStat(){
  const avg = k => HW.reduce((s, h) => s + h[k], 0) / HW.length;
  const needHelp = STUDENTS.filter(s => s.avg < 70).length;
  $('statKpis').innerHTML = `
    <div class="card"><div class="bd"><div class="big">312</div><div class="cap">本月练习人次</div></div></div>
    <div class="card"><div class="bd"><div class="big">${avg('total').toFixed(1)}</div><div class="cap">班级平均总分（实时统计作业）</div></div></div>
    <div class="card"><div class="bd"><div class="big">${CLASS_BARS[0].v}</div><div class="cap">高发偏误：${CLASS_BARS[0].lb}（人次）</div></div></div>
    <div class="card"><div class="bd"><div class="big">${needHelp}</div><div class="cap">需重点辅导学生（均分 &lt; 70）</div></div></div>`;
  const max = Math.max(...CLASS_BARS.map(b => b.v));
  $('classBars').innerHTML = CLASS_BARS.map(b => `
    <div class="brow"><span class="lb">${b.lb}</span>
      <div class="track"><div class="fill" style="width:${b.v / max * 100}%"></div></div>
      <span class="val">${b.v} 人次</span></div>`).join('');
  const maxT = Math.max(...TREND);
  $('trendChart').innerHTML = TREND.map((v, i) => `
    <div class="tcol"><b>${v}</b><i style="height:${v / maxT * 100}%"></i><span>第${i + 1}周</span></div>`).join('');
  renderStuTable();
}
function renderStuTable(){
  const list = STUDENTS.filter(s => !stuFilter || s.main === stuFilter);
  $('stuTable').innerHTML = '<tr><th>学生</th><th>练习次数</th><th>平均总分</th><th>主要偏误</th><th>近四周</th></tr>' +
    (list.length ? list.map(s => `<tr class="click" onclick="showStu('${s.n}')">
      <td><b>${s.n}</b></td><td>${s.cnt}</td>
      <td><b style="color:var(--navy)">${s.avg.toFixed(1)}</b></td>
      <td>${s.main}</td>
      <td>${s.tr ? '<span class="arrowup">↑ 改善</span>' : '<span class="arrowdn">→ 停滞</span>'}</td></tr>`).join('')
    : '<tr><td colspan="5" class="mut" style="text-align:center; padding:20px;">该类型暂无学生</td></tr>');
}
function filterStat(){
  stuFilter = $('clsFilter').value;
  renderStuTable();
  if (stuFilter) toast('已筛选主要偏误 = ' + stuFilter);
}
function showStu(name){
  const s = STUDENTS.find(x => x.n === name); if (!s) return;
  $('stuName').textContent = name;
  const maxC = Math.max(...Object.values(s.comp));
  const row = (lb, v) => `<div class="brow"><span class="lb">${lb}</span>
    <div class="track"><div class="fill" style="width:${v / maxC * 100}%; ${v === maxC ? '' : 'background:#3B74B8;'}"></div></div>
    <span class="val">${v}%</span></div>`;
  $('stuProfile').innerHTML =
    row('声韵母类', s.comp.sf) + row('声调类', s.comp.tone) + row('完整度/其他', s.comp.other) +
    `<div style="display:flex; gap:8px; margin:12px 0 4px;">
      ${s.wk.map((w, i) => `<div class="score" style="flex:1;"><b>${w}</b><span>第${i + 1}周</span></div>`).join('')}
     </div>
     <div class="note" style="margin-top:6px;"><b>辅导建议：</b>${s.tip}</div>`;
}
function exportStatCsv(){
  const rows = [['学生', '练习次数', '平均总分', '主要偏误', '近四周偏误数', '趋势']];
  STUDENTS.forEach(s => rows.push([s.n, s.cnt, s.avg.toFixed(1), s.main, s.wk.join('/'), s.tr ? '改善' : '停滞']));
  downloadFile('学情统计_全班.csv', toCsv(rows), 'text/csv');
  toast('已导出全班学情（CSV，可直接用 Excel 打开）');
}

/* ═══════════ 教师端 · 作业批改 ══════════ */
let hwSel = -1;
function hwStatus(h){
  return h.st === 'ok' ? '<span class="status st-ok">已发布</span>'
    : h.st === 'flag' ? '<span class="status st-flag">存疑待复核</span>'
    : '<span class="status st-pending">待复核</span>';
}
function renderHw(){
  $('hwTable').innerHTML = '<tr><th>学生</th><th>总分</th><th>准确度</th><th>完整度</th><th>流利度</th><th>偏误明细</th><th>状态</th></tr>' +
    HW.map((h, i) => `<tr class="click ${i === hwSel ? 'sel' : ''}" onclick="openHw(${i})">
      <td><b>${h.n}</b></td><td><b style="color:${h.total < 65 ? 'var(--red)' : 'var(--navy)'}">${h.total.toFixed(1)}</b></td>
      <td>${h.acc.toFixed(1)}</td><td>${h.comp.toFixed(1)}</td><td>${h.flu.toFixed(1)}</td>
      <td class="mut">${errSummary(h.tokens, h.gapErrs)}</td><td>${hwStatus(h)}</td></tr>`).join('');
}
function openHw(i){
  hwSel = i; const h = HW[i];
  renderHw();
  $('hwDetailCard').style.display = '';
  $('hwDetailCard').scrollIntoView({behavior:'smooth', block:'nearest'});
  $('hwStuName').textContent = `${h.n}（总分 ${h.total.toFixed(1)} · 提交于 ${h.submitted}）`;
  renderSentence($('hwSent'), h.tokens, h.gapErrs, {ro:true});
  $('hwScores').innerHTML = scoreCards(h.scores);
  $('hwComment').value = h.comment;
  $('hwAnnoBtn').style.display = h.linkTask ? '' : 'none';
}
function flagDoubt(){
  if (hwSel < 0) return;
  HW[hwSel].st = 'flag'; renderHw();
  toast('已标记存疑：' + HW[hwSel].n + '（进入人工复核队列）');
}
function publishHw(){
  if (hwSel < 0) return;
  HW[hwSel].st = 'ok';
  HW[hwSel].comment = $('hwComment').value;
  renderHw();
  toast('评语已保存并发布给 ' + HW[hwSel].n + '（学生端「我的作业」同步可见）');
}
function gotoAnnoFromHw(){
  const h = HW[hwSel];
  if (h && h.linkTask){
    showViewById('view-anno');
    openAnnoTask(h.linkTask);
    toast('已进入标注工作台复核 ' + h.n + ' 的作业（任务 ' + h.linkTask + '）');
  }
}
function exportHwCsv(){
  const rows = [['学生', '总分', '准确度', '完整度', '流利度', '偏误明细', '状态', '教师评语']];
  HW.forEach(h => rows.push([h.n, h.total.toFixed(1), h.acc.toFixed(1), h.comp.toFixed(1), h.flu.toFixed(1),
    errSummary(h.tokens, h.gapErrs),
    h.st === 'ok' ? '已发布' : h.st === 'flag' ? '存疑待复核' : '待复核', h.comment]));
  downloadFile('作业一_全班成绩.csv', toCsv(rows), 'text/csv');
  toast('已导出全班作业（CSV，可直接用 Excel 打开）');
}
function exportHwJson(){
  const out = HW.map(h => ({学生:h.n, 评分:h.scores, 偏误:errSummary(h.tokens, h.gapErrs),
    状态:h.st, 评语:h.comment,
    字符级偏误:h.tokens.map((t, i) => t.err ? {i, type:t.err.t, py:t.err.py || '', c:t.c} : null).filter(Boolean),
    字间级偏误:Object.entries(h.gapErrs || {}).map(([g, e]) => ({g:Number(g), type:e.t, py:e.py || ''}))}));
  downloadFile('作业一_全班成绩.json', JSON.stringify(out, null, 1), 'application/json');
  toast('已导出全班作业（JSON）');
}

/* ═══════════ 教师端 · 标注工作台（分层标注：字符级 + 字间级） ══════════ */
let TASK = null, anno = [], gapAnno = [], annoSel = -1, gapSel = -1;
let popKind = null, popIdx = -1, popType = '';
let playTimer = null, playing = false, audioImported = false;

function renderAnnoState(){
  if ($('annoWork').style.display !== 'none' && TASK) return;  // 正在工作台中
  renderAnnoQueue();
}
function renderAnnoQueue(){
  $('annoQueue').style.display = '';
  $('annoWork').style.display = 'none';
  const done = TASKS.filter(t => t.status === 'done').length;
  const errs = TASKS.reduce((s, t) => s + errTotal(t.tokens, t.gapErrs), 0);
  $('annoCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${TASKS.length}</div><div class="cap">复核任务总数</div></div></div>
    <div class="card"><div class="bd"><div class="big">${done}</div><div class="cap">已保存金标</div></div></div>
    <div class="card"><div class="bd"><div class="big">${TASKS.length - done}</div><div class="cap">待复核</div></div></div>
    <div class="card"><div class="bd"><div class="big">${errs}</div><div class="cap">机器预标偏误总数</div></div></div>`;
  $('annoTable').innerHTML = '<tr><th>任务</th><th>参考文本</th><th>模式</th><th>说话人</th><th>时长</th><th>批次</th><th>机器预标偏误</th><th>状态</th><th>操作</th></tr>' +
    TASKS.map(t => `<tr>
      <td><b>${t.id}</b></td><td>${t.canonical}</td>
      <td>${t.mode === 'A' ? '跟读' : '自由表达'}</td><td>${t.speaker}</td><td>${t.dur}</td><td>${t.batch}</td>
      <td class="mut">${errSummary(t.tokens, t.gapErrs)}</td>
      <td>${t.status === 'done'
        ? `<span class="status st-ok">已复核 · ${t.annotatedBy || ''}</span>`
        : '<span class="status st-pending">待复核</span>'}</td>
      <td><button class="btn ghost sm" onclick="openAnnoTask('${t.id}')">${t.status === 'done' ? '查看' : '复核标注'}</button></td></tr>`).join('');
}
function openAnnoTask(id){
  TASK = TASKS.find(t => t.id === id);
  if (!TASK){ toast('任务不存在'); return; }
  anno = TASK.tokens.map(() => ({t:'', py:'', touched:false}));
  gapAnno = Array.from({length: TASK.tokens.length + 1}, () => ({t:'', py:'', touched:false}));
  annoSel = -1; gapSel = -1;
  $('annoQueue').style.display = 'none';
  $('annoWork').style.display = '';
  $('wTaskId').textContent = TASK.id;
  $('wMeta').textContent = `题目（参考文本）：${TASK.canonical} · 说话人：${TASK.speaker} · 时长：${TASK.dur} · 模式：${TASK.mode === 'A' ? '跟读' : '自由表达'} · 批次：${TASK.batch}`;
  $('wNote').textContent = '点击字符 → 标 误读（声韵母/声调/语调）、漏读、重复；点击字间「＋」空隙 → 标 增读、填充词、停顿。语调偏误用于标注句末语调（如疑问/陈述语气不当）。机器预标可「确认」，人工可修改或选「无偏误」删除。';
  renderAnno();
  renderSaved(TASK.id);
  $('annoWork').scrollIntoView({behavior:'smooth', block:'nearest'});
}
function backToAnnoQueue(){ renderAnnoQueue(); }

function mergedErr(i){
  const a = anno[i];
  if (a && a.touched) return a.t ? {t:a.t, py:a.py} : null;
  return TASK.tokens[i].err || null;
}
function mergedGapErr(g){
  const a = gapAnno[g];
  if (a && a.touched) return a.t ? {t:a.t, py:a.py} : null;
  return (TASK.gapErrs || {})[g] || null;
}
function renderAnno(){
  renderSentence($('annoSent'), TASK.tokens, TASK.gapErrs, {
    ziErr:mergedErr,
    ziPre:i => !!TASK.tokens[i].err && !(anno[i] && anno[i].touched),
    ziSel:i => i === annoSel, ziId:i => 'az' + i,
    gapErr:mergedGapErr,
    gapPre:g => !!(TASK.gapErrs || {})[g] && !(gapAnno[g] && gapAnno[g].touched),
    gapSel:g => g === gapSel, gapId:g => 'gp' + g,
  });
  TASK.tokens.forEach((_, i) => { const el = $('az' + i); if (el) el.onclick = () => clickZi(i); });
  for (let g = 0; g <= TASK.tokens.length; g++){ const el = $('gp' + g); if (el) el.onclick = () => clickGap(g); }
}
function refreshAll(){ if (TASK) renderAnno(); }

function clickZi(i){ openPop('char', i); }
function clickGap(g){ openPop('gap', g); }
function openPop(kind, idx){
  closePop();
  popKind = kind; popIdx = idx; gapSel = -1; annoSel = -1;
  if (kind === 'char') annoSel = idx; else gapSel = idx;
  renderAnno();
  const groups = kind === 'char' ? GROUPS_CHAR : GROUPS_GAP;
  const ge = (TASK.gapErrs || {})[idx];
  const cur = kind === 'char' ? mergedErr(idx) : mergedGapErr(idx);
  popType = cur ? cur.t : '';
  const curPy = kind === 'char'
    ? (anno[idx].touched ? anno[idx].py : (TASK.tokens[idx].err && TASK.tokens[idx].err.py) || TASK.tokens[idx].py || '')
    : (gapAnno[idx] && gapAnno[idx].touched ? gapAnno[idx].py : (ge && ge.py) || '');
  const hasPre = kind === 'char' ? !!TASK.tokens[idx].err : !!ge;
  const head = kind === 'char'
    ? `字符「${TASK.tokens[idx].c}」`
    : `字间（${idx === 0 ? '句首' : '「' + TASK.tokens[idx - 1].c + '」'} 与 ${idx === TASK.tokens.length ? '句尾' : '「' + TASK.tokens[idx].c + '」'} 之间）`;
  const preInfo = hasPre
    ? (kind === 'char'
        ? '· 机器预标：' + ERRNAME[TASK.tokens[idx].err.t] + (TASK.tokens[idx].err.py ? ' ' + TASK.tokens[idx].err.py : '')
        : '· 机器预标：' + ERRNAME[ge.t] + (ge.py ? ' ' + ge.py : '') + (ge.text ? '「' + ge.text + '」' : ''))
    : (kind === 'char' ? '· 机器未标错' : '· 无机器预标');
  const pyLabel = kind === 'char' ? '实际读音（拼音，可修改）'
    : '实际读音 / 说明（如 jiu4、e4；停顿可填时长如 900ms）';
  const pop = document.createElement('div');
  pop.className = 'editpop'; pop.id = 'annoPop';
  pop.innerHTML = `
    <h4>${head} <span class="preinfo">${preInfo}</span></h4>
    ${groups.map(([gname, items]) => `
      <div class="trow"><span class="gname">${gname}</span>
        <span class="tbtns">${items.map(([k, v]) =>
          `<button type="button" class="tb${popType === k ? ' on' : ''}" data-t="${k}" onclick="pickT(this,'${k}')">${v}</button>`).join('')}
        </span></div>`).join('')}
    <div class="trow"><span class="gname"></span>
      <span class="tbtns"><button type="button" class="tb none${popType === '' ? ' on' : ''}" data-t="" onclick="pickNone(this)">无偏误</button></span></div>
    <label>${pyLabel}</label>
    <input id="apPy" value="${curPy}" placeholder="如 tian2">
    <div class="ops">
      ${hasPre ? '<button class="btn ghost" onclick="confirmPre()">确认预标</button>' : ''}
      <button class="btn" onclick="savePop()">保存</button>
      <button class="btn gray" onclick="closePop()">取消</button>
    </div>`;
  document.body.appendChild(pop);
  const vw = window.innerWidth || 1280, vh = window.innerHeight || 800;
  const pw = pop.offsetWidth || 330, ph = pop.offsetHeight || 340;
  const el = kind === 'char' ? $('az' + idx) : $('gp' + idx);
  const r = el.getBoundingClientRect();
  let left = Math.min(Math.max(r.left - 10, 8), Math.max(8, vw - pw - 8));
  let top = r.bottom + 8;
  if (top + ph > vh - 8) top = Math.max(8, r.top - ph - 8);
  pop.style.left = left + 'px';
  pop.style.top = top + 'px';
}
document.addEventListener('mousedown', e => {
  const p = $('annoPop'); if (!p) return;
  if (p.contains(e.target)) return;
  if (e.target.closest && e.target.closest('.zi, .gap')) return;
  closePop();
  annoSel = -1; gapSel = -1;
  renderAnno();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePop(); });
function pickT(btn, k){
  popType = k;
  document.querySelectorAll('#annoPop .tb').forEach(b => b.classList.toggle('on', b.dataset.t === k));
}
function pickNone(btn){ pickT(btn, ''); }
function confirmPre(){
  if (popKind === 'char'){
    const ch = TASK.tokens[popIdx];
    anno[popIdx] = {t:ch.err.t, py:ch.err.py || ch.py || '', touched:true};
    toast('已确认机器预标：' + ERRNAME[ch.err.t]);
  } else {
    const ge = (TASK.gapErrs || {})[popIdx];
    gapAnno[popIdx] = {t:ge.t, py:ge.py || '', touched:true};
    toast('已确认机器预标：字间 ' + ERRNAME[ge.t]);
  }
  closePop(); renderAnno();
}
function savePop(){
  const py = $('apPy').value.trim();
  if (popKind === 'char'){
    const ch = TASK.tokens[popIdx];
    anno[popIdx] = {t:popType, py, touched:true};
    toast(popType ? `「${ch.c}」已标注：${ERRNAME[popType]}${py ? ' ' + py : ''}` : `「${ch.c}」已删除偏误标注（无偏误）`);
  } else {
    gapAnno[popIdx] = {t:popType, py, touched:true};
    toast(popType ? `字间已标注：${ERRNAME[popType]}${py ? ' ' + py : ''}` : '字间已删除标注');
  }
  closePop(); renderAnno();
}
function closePop(){ const p = $('annoPop'); if (p) p.remove(); }

function saveAnnotation(){
  if (!TASK) return;
  const edits = anno.map((a, i) => a.t ? {i, type:a.t, py:a.py} : null).filter(Boolean)
    .concat(gapAnno.map((a, g) => a.t ? {g, type:a.t, py:a.py} : null).filter(Boolean));
  if (!edits.length){ toast('尚无任何偏误标注，请先点击字符或字间空隙标注'); return; }
  const record = {taskId:TASK.id, annotator:AUTH.name, edits, savedAt:nowStr()};
  RECORDS.unshift(record);
  TASK.status = 'done';
  TASK.annotatedBy = AUTH.name;
  $('savedJson').textContent = JSON.stringify(record, null, 1);
  $('wNote').innerHTML = `<b style="color:var(--ok);">金标已保存入库</b>：共 ${edits.length} 处（字符 ${edits.filter(e => e.i !== undefined).length} + 字间 ${edits.filter(e => e.g !== undefined).length}），署名「${AUTH.name}」。管理端「标注记录管理」已同步可见。`;
  toast('金标已保存：' + edits.length + ' 处标注入库');
}
function renderSaved(id){
  const r = RECORDS.find(x => x.taskId === id);
  $('savedJson').textContent = r ? JSON.stringify(r, null, 1) : '尚无保存记录';
}
function gotoNextTask(){
  const next = TASKS.find(t => t.status !== 'done' && (!TASK || t.id !== TASK.id));
  if (!next){ toast('都复核完啦，没有待处理的任务了'); return; }
  openAnnoTask(next.id);
  toast('已切换到 ' + next.id);
}
function togglePlay(){
  const bar = $('playBar'), txt = $('playTxt');
  if (playing){
    playing = false; clearInterval(playTimer);
    txt.textContent = '播放音频'; bar.style.width = '0';
    return;
  }
  playing = true; txt.textContent = '播放中…';
  let p = 0;
  playTimer = setInterval(() => {
    p += 4; bar.style.width = p + '%';
    if (p >= 100){
      clearInterval(playTimer); playing = false;
      txt.textContent = '播放音频'; bar.style.width = '0';
    }
  }, 120);
}

/* ═══════════ 教师端 · 题目管理 ══════════ */
function renderQues(){
  $('quesTable').innerHTML = '<tr><th>题目</th><th>模式</th><th>文本 / 话题</th><th>机器预标偏误</th><th>操作</th></tr>' +
    QUESTIONS.map((q, i) => `<tr>
      <td><b>${q.name}</b>${q.generic ? ' <span class="chip" style="margin:0;">教师新增</span>' : ''}</td>
      <td>${q.mode === 'A' ? '跟读（提供参考文本）' : '自由表达（无参考文本）'}</td>
      <td class="mut">${q.mode === 'A' ? q.text : (q.topic || q.text || '—')}</td>
      <td class="mut">${errSummary(q.tokens, q.gapErrs)}</td>
      <td style="white-space:nowrap;">
        <button class="btn ghost sm" onclick="openQuesModal(${i})">编辑</button>
        <button class="btn warn sm" onclick="delQues(${i})">删除</button></td></tr>`).join('');
}
function buildTokens(text, pys){
  const chars = (text || '').replace(/\s+/g, '').split('');
  const pyArr = (pys || '').trim().split(/\s+/).filter(Boolean);
  return chars.map((c, i) => ({c, py:pyArr[i] || ''}));
}
function openQuesModal(idx){
  const q = idx !== undefined ? QUESTIONS[idx] : null;
  openModal(`
    <div class="hd">${q ? '编辑题目' : '新增题目'}</div>
    <div class="bd">
      <label class="fl">题目名称（如：跟读 · 我去上学）</label>
      <input id="qmName" value="${q ? q.name : ''}" placeholder="跟读 · 新题目">
      <label class="fl">模式</label>
      <select id="qmMode">
        <option value="A" ${q && q.mode === 'A' ? 'selected' : ''}>跟读（提供参考文本）</option>
        <option value="B" ${q && q.mode === 'B' ? 'selected' : ''}>自由表达（无参考文本）</option>
      </select>
      <label class="fl" id="qmTextLabel">参考文本（逐字，用于对齐）</label>
      <input id="qmText" value="${q ? (q.mode === 'A' ? q.text : (q.topic || '')) : ''}" placeholder="如：我去上学">
      <label class="fl">拼音（可选，空格分隔，与文本逐字对应）</label>
      <input id="qmPy" placeholder="如：wo3 qu4 shang4 xue2">
      <div class="ops">
        <button class="btn gray" onclick="closeModal()">取消</button>
        <button class="btn" onclick="saveQuesModal(${idx === undefined ? -1 : idx})">保存</button>
      </div>
    </div>`);
  $('qmMode').addEventListener('change', e => {
    $('qmTextLabel').textContent = e.target.value === 'A' ? '参考文本（逐字，用于对齐）' : '表达话题（供学生参考，不做内容评价）';
  });
}
function saveQuesModal(idx){
  const name = $('qmName').value.trim();
  const mode = $('qmMode').value;
  const text = $('qmText').value.trim();
  const pys = $('qmPy').value.trim();
  if (!name || !text){ toast('请填写题目名称和文本'); return; }
  const base = {name, mode, text, level:'beginner', generic:true,
    tokens:buildTokens(text, pys), gapErrs:{},
    errTypes:[],
    scores:{acc:96.5, comp:100, flu:95.0, total:96.8},
    fluency:{speed:'2.5 字/秒', ratio:'2%', mlr:'1.0'}};
  if (mode === 'B'){ base.topic = text; base.text = '自由表达'; base.rebuilt = text; }
  if (idx >= 0){
    Object.assign(QUESTIONS[idx], base);
    toast('题目已更新：' + name);
  } else {
    base.id = 'q' + Date.now();
    QUESTIONS.push(base);
    toast('题目已新增：' + name + '（学生端题目列表已同步）');
  }
  if (curQ && !QUESTIONS.find(x => x.id === curQ.id)) curQ = QUESTIONS[0] || null;
  closeModal();
  renderQues();
}
function delQues(idx){
  const q = QUESTIONS[idx];
  if (!q) return;
  if (!confirm(`确认删除题目「${q.name}」？学生端将同步移除。`)) return;
  QUESTIONS.splice(idx, 1);
  if (curQ && curQ.id === q.id) curQ = QUESTIONS[0] || null;
  toast('题目已删除：' + q.name);
  renderQues();
}

/* ═══════════ 中央弹窗 ═══════════ */
function openModal(html){ $('modalBox').innerHTML = html; $('modalMask').style.display = 'flex'; }
function closeModal(){ $('modalMask').style.display = 'none'; }

/* ═══════════ 管理端 · 用户管理 ══════════ */
function userMatch(u, kw){
  return !kw || (u.name + u.user + (u.cls || '')).includes(kw);
}
function renderUsers(){
  const kw = ($('userSearch').value || '').trim();
  const opBtns = (role, i) => `<span style="white-space:nowrap;">
    <button class="btn ghost sm" onclick="openUserModal('${role}',${i})">编辑</button>
    <button class="btn warn sm" onclick="delUser('${role}',${i})">删除</button></span>`;
  const ts = USERS.teachers.filter(u => userMatch(u, kw));
  const ss = USERS.students.filter(u => userMatch(u, kw));
  $('teacherTable').innerHTML = '<tr><th>工号</th><th>姓名</th><th>账号</th><th>任教班级</th><th>状态</th><th>操作</th></tr>' +
    (ts.length ? ts.map(u => `<tr><td>${u.id}</td><td><b>${u.name}</b></td><td>${u.user}</td>
      <td>${u.cls || '—'}</td>
      <td><span class="status ${u.status === '在职' ? 'st-ok' : 'st-pending'}">${u.status}</span></td>
      <td>${opBtns('teacher', USERS.teachers.indexOf(u))}</td></tr>`).join('')
    : '<tr><td colspan="6" class="mut" style="text-align:center; padding:18px;">无匹配教师</td></tr>');
  $('studentTable').innerHTML = '<tr><th>学号</th><th>姓名</th><th>账号</th><th>班级</th><th>状态</th><th>操作</th></tr>' +
    (ss.length ? ss.map(u => `<tr><td>${u.id}</td><td><b>${u.name}</b></td><td>${u.user}</td>
      <td>${u.cls || '—'}</td>
      <td><span class="status ${u.status === '在读' ? 'st-ok' : 'st-pending'}">${u.status}</span></td>
      <td>${opBtns('student', USERS.students.indexOf(u))}</td></tr>`).join('')
    : '<tr><td colspan="6" class="mut" style="text-align:center; padding:18px;">无匹配学生</td></tr>');
}
function openUserModal(role, idx){
  const isT = role === 'teacher';
  const u = idx !== undefined ? (isT ? USERS.teachers[idx] : USERS.students[idx]) : null;
  openModal(`
    <div class="hd">${u ? '编辑' : '新增'}${isT ? '教师' : '学生'}</div>
    <div class="bd">
      <label class="fl">姓名</label>
      <input id="umName" value="${u ? u.name : ''}" placeholder="姓名">
      <label class="fl">账号</label>
      <input id="umUser" value="${u ? u.user : ''}" placeholder="登录账号">
      <label class="fl">班级</label>
      <input id="umCls" value="${u ? (u.cls || '') : (isT ? '' : '汉语一班')}" placeholder="如：汉语一班">
      <label class="fl">状态</label>
      <select id="umStatus">
        <option ${u && u.status === (isT ? '休假' : '休学') ? '' : 'selected'}>${isT ? '在职' : '在读'}</option>
        <option ${u && u.status === (isT ? '休假' : '休学') ? 'selected' : ''}>${isT ? '休假' : '休学'}</option>
      </select>
      <div class="ops">
        <button class="btn gray" onclick="closeModal()">取消</button>
        <button class="btn" onclick="saveUserModal('${role}',${idx === undefined ? -1 : idx})">保存</button>
      </div>
    </div>`);
}
function saveUserModal(role, idx){
  const isT = role === 'teacher';
  const name = $('umName').value.trim(), user = $('umUser').value.trim();
  const cls = $('umCls').value.trim(), status = $('umStatus').value;
  if (!name || !user){ toast('请填写姓名和账号'); return; }
  const list = isT ? USERS.teachers : USERS.students;
  if (idx >= 0){
    Object.assign(list[idx], {name, user, cls, status});
    toast((isT ? '教师' : '学生') + '已更新：' + name);
  } else {
    const prefix = isT ? 'T' : 'S';
    const id = prefix + '-' + String(list.length + 1).padStart(3, '0');
    list.push({id, name, user, cls, status});
    toast((isT ? '教师' : '学生') + '已新增：' + name + '（' + id + '）');
  }
  closeModal();
  renderUsers();
}
function delUser(role, idx){
  const list = role === 'teacher' ? USERS.teachers : USERS.students;
  const u = list[idx];
  if (!u) return;
  if (!confirm(`确认删除${role === 'teacher' ? '教师' : '学生'}「${u.name}」（${u.id}）？`)) return;
  list.splice(idx, 1);
  toast('已删除：' + u.name);
  renderUsers();
}

/* ═══════════ 管理端 · 任务分配 ══════════ */
function gradingDone(g){
  return g.dyn ? HW.filter(h => h.st === 'ok').length : (g.done || 0);
}
function renderAssign(){
  const un = TASKS.filter(t => !t.assignee);
  const doneN = TASKS.filter(t => t.status === 'done').length;
  $('asgCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${GRADING.length + UNASSIGNED_BATCHES.length}</div><div class="cap">批改批次</div></div></div>
    <div class="card"><div class="bd"><div class="big">${UNASSIGNED_BATCHES.length}</div><div class="cap">待指派批次</div></div></div>
    <div class="card"><div class="bd"><div class="big">${TASKS.length}</div><div class="cap">标注任务总数</div></div></div>
    <div class="card"><div class="bd"><div class="big">${TASKS.length - un.length}/${TASKS.length}</div><div class="cap">标注已分配（已完成 ${doneN}）</div></div></div>`;
  $('gradingTable').innerHTML = '<tr><th>教师</th><th>批改批次</th><th>作业份数</th><th>已批改</th><th>待批改</th><th>批改进度</th></tr>' +
    GRADING.map(g => {
      const done = gradingDone(g);
      return `<tr><td><b>${g.teacher}</b></td><td>${g.batch}</td><td>${g.total}</td>
        <td>${done}</td><td>${g.total - done}</td>
        <td><span class="pgs"><span class="track"><span class="fill" style="display:block; width:${g.total ? done / g.total * 100 : 0}%"></span></span><b>${done}/${g.total}</b></span></td></tr>`;
    }).join('');
  $('unassignedTable').innerHTML = '<tr><th>批次</th><th>指派给（选择即保存）</th></tr>' +
    (UNASSIGNED_BATCHES.length ? UNASSIGNED_BATCHES.map(b => `<tr><td>${b}</td>
      <td><select class="asgsel" onchange="assignBatch('${b}', this.value)">
        <option value="">选择教师…</option>
        ${USERS.teachers.filter(t => t.status === '在职').map(t => `<option value="${t.name}">${t.name}</option>`).join('')}
      </select></td></tr>`).join('')
    : '<tr><td colspan="2" class="mut" style="text-align:center; padding:18px;">所有批次均已指派</td></tr>');
  const names = ['标注员A', '标注员B'];
  const chip = t => `<span class="chip ${t.status === 'done' ? '' : ''}" style="cursor:default;">${t.id}·${t.status === 'done' ? '已复核' : '待复核'}</span>`;
  let rows = '';
  if (un.length) rows += `<tr><td><b>未分配</b></td><td>${un.length}</td><td>${un.length}</td><td>0</td><td>${un.map(chip).join('')}</td></tr>`;
  names.forEach(n => {
    const mine = TASKS.filter(t => t.assignee === n);
    rows += `<tr><td><b>${n}</b></td>
      <td>${mine.length}</td>
      <td>${mine.filter(t => t.status !== 'done').length}</td>
      <td>${mine.filter(t => t.status === 'done').length}</td>
      <td>${mine.map(chip).join('') || '<span class="mut">暂无</span>'}</td></tr>`;
  });
  $('asgTable').innerHTML = '<tr><th>标注员</th><th>分配任务数</th><th>待标注</th><th>已标注</th><th>任务明细</th></tr>' + rows;
  $('asgOpTable').innerHTML = '<tr><th>任务</th><th>参考文本</th><th>状态</th><th>分配给（选择即保存）</th></tr>' +
    TASKS.map(t => `<tr><td><b>${t.id}</b></td><td>${t.canonical}</td>
      <td>${t.status === 'done' ? '<span class="status st-ok">已标注</span>' : '<span class="status st-pending">待标注</span>'}</td>
      <td><select class="asgsel" onchange="assignTaskTo('${t.id}', this.value)">
        <option value="" ${!t.assignee ? 'selected' : ''}>未分配</option>
        ${names.map(n => `<option value="${n}" ${t.assignee === n ? 'selected' : ''}>${n}</option>`).join('')}
      </select></td></tr>`).join('');
}
function assignBatch(batch, teacher){
  if (!teacher) return;
  GRADING.push({teacher, batch, total:8, done:0});
  const i = UNASSIGNED_BATCHES.indexOf(batch);
  if (i >= 0) UNASSIGNED_BATCHES.splice(i, 1);
  renderAssign();
  toast(`已将「${batch}」指派给 ${teacher}（该教师任务量 +1）`);
}
function assignTaskTo(tid, who){
  const t = TASKS.find(x => x.id === tid);
  if (!t) return;
  t.assignee = who;
  renderAssign();
  toast(who ? `已将 ${tid} 分配给 ${who}` : `${tid} 已取消分配`);
}
function autoAssign(){
  const names = ['标注员A', '标注员B'];
  const targets = TASKS.filter(t => t.status !== 'done' && !t.assignee);
  if (!targets.length){ toast('没有待分配的任务（全部已分配或已完成）'); return; }
  const plan = {};
  targets.forEach((t, i) => {
    const who = names[i % names.length];
    t.assignee = who;
    plan[who] = (plan[who] || []).concat(t.id);
  });
  renderAssign();
  toast('自动分配完成：' + Object.entries(plan).map(([k, v]) => `${k} ${v.length} 个（${v.join('、')}）`).join('；'));
}
function importAudio(){
  if (audioImported){ toast('演示数据仅导入一次（任务 A-033 已在列表中）'); return; }
  audioImported = true;
  TASKS.push(JSON.parse(JSON.stringify(IMPORT_TASK)));
  $('importBtn').disabled = true;
  renderAssign();
  toast('已导入 3 条音频，机器预标完成（演示）→ 生成标注任务 A-033');
}

/* ═══════════ 管理端 · 标注记录管理 ══════════ */
function renderRecords(){
  const annotators = [...new Set(RECORDS.map(r => r.annotator))];
  const savedEdits = RECORDS.reduce((s, r) => s + r.edits.length, 0);
  const machineErrs = TASKS.reduce((s, t) => s + errTotal(t.tokens, t.gapErrs), 0);
  $('recCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${RECORDS.length}</div><div class="cap">金标记录总数</div></div></div>
    <div class="card"><div class="bd"><div class="big">${annotators.length}</div><div class="cap">参与标注人员</div></div></div>
    <div class="card"><div class="bd"><div class="big">${savedEdits}</div><div class="cap">入库偏误总数</div></div></div>
    <div class="card"><div class="bd"><div class="big">${machineErrs}</div><div class="cap">机器预标偏误总数</div></div></div>`;
  const workload = {};
  RECORDS.forEach(r => {
    const w = workload[r.annotator] = workload[r.annotator] || {count:0, edits:0};
    w.count++; w.edits += r.edits.length;
  });
  const wl = Object.entries(workload).sort((a, b) => b[1].count - a[1].count);
  $('workTable').innerHTML = '<tr><th>标注员 / 复核教师</th><th>完成任务数</th><th>入库偏误数</th></tr>' +
    (wl.length ? wl.map(([n, w]) => `<tr><td><b>${n}</b></td><td>${w.count}</td><td>${w.edits}</td></tr>`).join('')
    : '<tr><td colspan="3" class="mut" style="text-align:center; padding:18px;">尚无记录</td></tr>');
  const dist = {};
  RECORDS.forEach(r => r.edits.forEach(e => { dist[e.type] = (dist[e.type] || 0) + 1; }));
  const max = Math.max(...Object.values(dist), 1);
  $('savedBars').innerHTML = byTypeOrder(Object.keys(dist)).map(k => `
    <div class="brow"><span class="lb">${ERRNAME[k]}</span>
      <div class="track"><div class="fill" style="width:${dist[k] / max * 100}%"></div></div>
      <span class="val">${dist[k]} 处</span></div>`).join('')
    || '<div class="mut">尚无入库金标</div>';
  $('recTable').innerHTML = '<tr><th>时间</th><th>任务</th><th>标注员 / 复核教师</th><th>偏误明细</th></tr>' +
    (RECORDS.length ? RECORDS.map(a => `<tr><td>${a.savedAt}</td><td><b>${a.taskId}</b></td>
      <td>${a.annotator}</td>
      <td>${a.edits.map(e => `<span class="chip">${e.g !== undefined && e.g !== null ? '字间·' : ''}${ERRNAME[e.type] || e.type}${e.py ? ' ' + e.py : ''}${e.c ? '「' + e.c + '」' : ''}</span>`).join('') || '<span class="mut">无</span>'}</td></tr>`).join('')
    : '<tr><td colspan="4" class="mut" style="text-align:center; padding:18px;">尚无保存记录</td></tr>');
}
function exportRecordsJson(){
  downloadFile('标注金标_' + new Date().toISOString().slice(0, 10) + '.json',
    JSON.stringify(RECORDS, null, 1), 'application/json');
  toast('已导出 ' + RECORDS.length + ' 条金标记录（JSON）');
}

/* ═══════════ 学生端 · My Progress（进步曲线 + 系统性错误归纳） ═══════════ */
function renderProgress(){
  const lv = LEVELS.find(l => l.k === STUDENT.level) || LEVELS[0];
  $('progCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${STUDENT.xp}</div><div class="cap">累计积分 ⭐</div></div></div>
    <div class="card"><div class="bd"><div class="big">${STUDENT.streak} 天</div><div class="cap">连续打卡 🔥</div></div></div>
    <div class="card"><div class="bd"><div class="big">${lv.en}</div><div class="cap">当前等级</div></div></div>
    <div class="card"><div class="bd"><div class="big">100</div><div class="cap">已完成练习</div></div></div>`;
  const W = 520, H = 150, pad = 26;
  const data = STUDENT.scoreTrend;
  const mn = Math.min(...data) - 8, mx = Math.max(...data) + 4;
  const px = i => pad + i * (W - pad * 2) / (data.length - 1);
  const py = v => H - pad - (v - mn) / (mx - mn) * (H - pad * 2);
  const pts = data.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(' ');
  $('scoreSvg').innerHTML = `
    <line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="#C8DDE2" stroke-width="1.5"/>
    <polyline points="${pts}" fill="none" stroke="#014DA5" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
    ${data.map((v, i) => `<circle cx="${px(i).toFixed(1)}" cy="${py(v).toFixed(1)}" r="4.5" fill="#fff" stroke="#014DA5" stroke-width="2.5"/>
      <text x="${px(i).toFixed(1)}" y="${(py(v) - 10).toFixed(1)}" font-size="12" fill="#003399" text-anchor="middle" font-weight="700">${v}</text>`).join('')}`;
  $('scoreWk').textContent = STUDENT.weekly.join(' · ');
  const maxE = Math.max(...STUDENT.errTrend);
  $('errTrendChart').innerHTML = STUDENT.errTrend.map((v, i) => `
    <div class="tcol"><b>${v}</b><i style="height:${v / maxE * 100}%; background:linear-gradient(180deg,#E08A8A,#C00000);"></i>
      <span>${STUDENT.weekly[i].replace('Week', 'W')}</span></div>`).join('');
  $('sysErrList').innerHTML = STUDENT.sysErrs.map(s => `
    <div class="sysrow">
      <span class="syschip ${s.status}">${s.status === 'fixed' ? '✔ fixed' : '↗ improving'}</span>
      <div style="flex:1; min-width:0;"><b>${s.pat}</b>
        <div class="mut" style="font-size:12.5px; line-height:1.8;">${s.note}</div></div>
    </div>`).join('');
  $('badgeRow').innerHTML = STUDENT.badges.map(b => `<span class="badgechip">${b}</span>`).join('');
}

/* ═══════════ 教师/研究员端 · 研究统计（匿名化 · 按国籍/母语背景） ═══════════ */
function renderResearch(){
  const total = NAT_STATS.reduce((s, r) => s + r.n, 0);
  const errs = TASKS.reduce((s, t) => s + errTotal(t.tokens, t.gapErrs), 0);
  $('resCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${NAT_STATS.length}</div><div class="cap">覆盖国家 / 母语背景</div></div></div>
    <div class="card"><div class="bd"><div class="big">${total}</div><div class="cap">匿名样本学习者总数</div></div></div>
    <div class="card"><div class="bd"><div class="big">${RECORDS.length}</div><div class="cap">金标记录（人工核验）</div></div></div>
    <div class="card"><div class="bd"><div class="big">${errs}</div><div class="cap">机器预标偏误总数</div></div></div>`;
  const max = Math.max(...NAT_STATS.map(r => r.n));
  $('natBars').innerHTML = NAT_STATS.map(r => `
    <div class="brow"><span class="lb" style="width:180px;">${r.nat} · ${r.n}人</span>
      <div class="track"><div class="fill" style="width:${r.n / max * 100}%"></div></div>
      <span class="val" style="width:210px; font-size:12px; font-weight:400; color:var(--ink);">${r.main}</span></div>`).join('');
  $('natTable').innerHTML = '<tr><th>国籍</th><th>匿名样本</th><th>声调类</th><th>声韵母类</th><th>流利类</th><th>主要偏误</th></tr>' +
    NAT_STATS.map(r => `<tr><td><b>${r.nat}</b></td><td>${r.n}</td><td>${r.tone}%</td><td>${r.sf}%</td><td>${r.flu}%</td>
      <td class="mut">${r.main}</td></tr>`).join('');
}
function exportResearchCsv(){
  const rows = [['国籍', '匿名样本数', '声调类%', '声韵母类%', '流利类%', '主要偏误']];
  NAT_STATS.forEach(r => rows.push([r.nat, r.n, r.tone, r.sf, r.flu, r.main]));
  downloadFile('研究统计_按国籍_匿名.csv', toCsv(rows), 'text/csv');
  toast('已导出匿名统计结果（不含任何个人原始数据）');
}

/* ═══════════ 教师/研究员端 · 我的班级（不预设 · 自主创建） ═══════════ */
function renderClass(){
  $('classEmpty').style.display = CLASS_STATE.created ? 'none' : '';
  $('classBuilt').style.display = CLASS_STATE.created ? '' : 'none';
  if (!CLASS_STATE.created) return;
  const avg = HW.reduce((s, h) => s + h.total, 0) / HW.length;
  $('clsCards').innerHTML = `
    <div class="card"><div class="bd"><div class="big">${USERS.students.length}</div><div class="cap">已加入学生</div></div></div>
    <div class="card"><div class="bd"><div class="big">312</div><div class="cap">本月自主练习人次</div></div></div>
    <div class="card"><div class="bd"><div class="big">${avg.toFixed(1)}</div><div class="cap">班级平均总分</div></div></div>
    <div class="card"><div class="bd"><div class="big">${HW.filter(h => h.st === 'ok').length}</div><div class="cap">已发布评语</div></div></div>`;
  $('clsCode').textContent = CLASS_STATE.code;
  $('clsTable').innerHTML = '<tr><th>学号</th><th>姓名</th><th>国籍</th><th>近期趋势</th></tr>' +
    USERS.students.map((u, i) => `<tr><td>${u.id}</td><td><b>${u.name}</b></td>
      <td>${['示例国家','示例国家','Vietnam','Korea','USA','Indonesia','Japan','示例国家'][i % 8]}</td>
      <td>${i % 3 === 0 ? '<span class="arrowup">↑ improving</span>' : i % 3 === 1 ? '<span class="arrowdn">→ steady</span>' : '<span class="arrowup">↑ fast</span>'}</td></tr>`).join('');
}
function createClass(){
  if (CLASS_STATE.created) return;
  CLASS_STATE.created = true;
  CLASS_STATE.name = '李老师的班级';
  CLASS_STATE.code = 'BQ7K2M';
  renderClass();
  toast('班级已创建（邀请码 ' + CLASS_STATE.code + '）。不创建班级同样可使用全部其他功能。');
}

/* ═══════════ 注册（采集背景信息：国籍 / 汉语水平，说明用途） ═══════════ */
function openReg(){
  openModal(`
    <div class="hd">Student sign up · 注册学生账号</div>
    <div class="bd">
      <label class="fl">Name / 姓名</label>
      <input id="rgName" placeholder="e.g. Arisa Suwan">
      <label class="fl">Nationality / 国籍（用于归纳同母语背景学习者的常见偏误）</label>
      <select id="rgNat">
        <option>示例国家</option><option>Vietnam</option><option>Korea</option>
        <option>USA</option><option>Japan</option><option>Indonesia</option><option>Other</option>
      </select>
      <label class="fl">Chinese level / 汉语水平（用于分层命题）</label>
      <select id="rgLvl">
        <option value="beginner">Beginner · 初级（字词）</option>
        <option value="inter">Intermediate · 中级（句子）</option>
        <option value="advanced">Advanced · 高级（语篇）</option>
      </select>
      <div class="note" style="text-align:left;">🔒 Privacy note: we collect your nationality and level <b>only to give you better feedback</b>. All research statistics are anonymized — nobody can see your raw recordings.</div>
      <div class="ops">
        <button class="btn gray" onclick="closeModal()">取消</button>
        <button class="btn" onclick="saveReg()">Create account</button>
      </div>
    </div>`);
}
function saveReg(){
  const name = $('rgName').value.trim();
  if (!name){ toast('Please enter your name'); return; }
  const acc = 'stu' + String(Math.floor(Math.random() * 900) + 100);
  STUDENT.level = $('rgLvl').value;
  liUser.value = acc; liPwd.value = '';
  closeModal();
  toast('Account created: ' + acc + '（已自动填入登录框）');
  pickRole('student');
}

/* ═══════════ 初始化 ═══════════ */
pickRole('student');


const PROPOSITION_API_BASE = window.PROPOSITION_API_BASE || 'http://127.0.0.1:8001';
const PROPOSITION_LEVEL_GROUPS = {
  1: [1], 2: [2], 3: [3], 4: [4], 5: [5], 6: [6],
  7: [7, 8, 9], // 页面合并展示，后端仍按实际等级分别调用
};
let propositionLevels = [];

function selectedPropositionLevels(){
  const selected = Number(($('propLevel') || {}).value || 1);
  return PROPOSITION_LEVEL_GROUPS[selected] || [1];
}
function propositionLabel(level){
  return level === 7 ? '七—九级' : `${level}级`;
}
function propositionStatusLabel(status){
  if (status === 'available') return '已入库';
  if (status === 'partial') return '部分可用';
  return '待接入';
}
function propositionResult(value){
  const el = $('propPipelineResult');
  if (el) el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}
function propositionError(data, fallback){
  return (data && (data.detail || data.message)) || fallback || '请求失败';
}
async function propositionFetch(path, options){
  try{
    const response = await fetch(`${PROPOSITION_API_BASE}${path}`, options);
    let data = null;
    try { data = await response.json(); } catch (_) { /* 空响应 */ }
    return {ok: response.ok, status: response.status, data};
  }catch(e){
    return {ok:false, status:0, data:{detail:'无法连接命题后端，请确认 8001 服务已启动'}};
  }
}
function renderPropositionPipeline(){
  const t = $('propQuestionTable');
  if (t) t.innerHTML = '<tr><th>编号</th><th>等级</th><th>文本</th><th>拼音</th><th>语法点</th><th>状态</th><th>录音数</th></tr><tr><td colspan="7" class="mut">选择等级后加载题库</td></tr>';
  propositionResult('正在读取九级题库状态…');
  loadPropositionLevels();
}
async function loadPropositionLevels(){
  const r = await propositionFetch('/api/levels');
  if (!r.ok){
    renderPropositionLevelStatus([]);
    propositionResult(propositionError(r.data, '读取等级状态失败'));
    pipelineNotice(propositionError(r.data, '后端不可用'));
    return;
  }
  propositionLevels = Array.isArray(r.data) ? r.data : (r.data.items || []);
  renderPropositionLevelStatus(propositionLevels);
  onPropositionLevelChange();
}
function renderPropositionLevelStatus(items){
  const t = $('nineLevelStatusTable');
  if (!t) return;
  const byLevel = Object.fromEntries((items || []).map(x => [Number(x.level), x]));
  const groups = [[1],[2],[3],[4],[5],[6],[7,8,9]];
  let html = '<tr><th>等级</th><th>配置</th><th>题目数</th><th>状态</th></tr>';
  groups.forEach(group => {
    const rows = group.map(n => byLevel[n] || {level:n, question_count:0, status:'pending'});
    const total = rows.reduce((sum, x) => sum + Number(x.question_count || 0), 0);
    const ready = rows.filter(x => x.status === 'available').length;
    const status = group.length === 1 ? rows[0].status : (ready === group.length ? 'available' : (ready ? 'partial' : 'pending'));
    const config = group.length === 1 ? (status === 'available' ? '已配置' : '待数据侧整理') : `${ready}/${group.length} 个等级可用`;
    html += `<tr><td>${safeProp(propositionLabel(group[0]))}</td><td>${safeProp(config)}</td><td>${total}</td><td>${safeProp(propositionStatusLabel(status))}</td></tr>`;
  });
  t.innerHTML = html;
}
function onPropositionLevelChange(load = true){
  const levels = selectedPropositionLevels();
  const hint = $('propLevelHint');
  if (hint) hint.textContent = levels.length === 1
    ? `当前调用后端 ${levels[0]} 级接口`
    : '页面合并展示 7—9 级，抽题时随机选择一个实际等级';
  const source = $('propSource');
  if (source) source.textContent = '等待加载';
  if (load) loadPropositionQuestions();
}
async function loadPropositionQuestions(){
  const levels = selectedPropositionLevels();
  const responses = await Promise.all(levels.map(level => propositionFetch(`/api/questions?level=${level}`)));
  const rows = [], errors = [];
  responses.forEach((r, i) => {
    const level = levels[i];
    if (r.ok){
      const items = Array.isArray(r.data) ? r.data : (r.data.items || r.data.questions || []);
      rows.push(...items.map(q => ({...q, level: Number(q.level || level)})));
      if (r.data.detail) errors.push(`${level}级：${r.data.detail}`);
    }else errors.push(`${level}级：${propositionError(r.data, `HTTP ${r.status || '网络错误'}`)}`);
  });
  const source = errors.length && !rows.length ? errors.join('；') : `真实后端数据${errors.length ? `（${errors.join('；')}）` : ''}`;
  renderPropositionRows(rows, source);
  if (!rows.length) pipelineNotice(source);
}
async function runPropositionPipeline(kind){
  const levels = selectedPropositionLevels();
  const results = [];
  for (const level of levels){
    const r = await propositionFetch(`/api/pipeline/${kind}?level=${level}`, {method:'POST'});
    results.push({level, ok:r.ok, status:r.status, result:r.data});
  }
  propositionResult({operation: kind, levels, results});
  const failed = results.filter(x => !x.ok);
  pipelineNotice(failed.length ? `${kind === 'validate' ? '校验' : '统计'}完成，但有 ${failed.length} 个等级未成功` : `${kind === 'validate' ? '校验' : '统计'}完成`);
}
function validatePropositionPipeline(){ return runPropositionPipeline('validate'); }
function statsPropositionPipeline(){ return runPropositionPipeline('stats'); }
async function drawPropositionQuestion(){
  const configured = selectedPropositionLevels();
  const level = configured.length === 1 ? configured[0] : configured[Math.floor(Math.random() * configured.length)];
  const mode = (($('propMode') || {}).value || 'recommend') === 'random' ? 'random' : 'recommend';
  const r = await propositionFetch(`/api/questions/${mode}?level=${level}&n=1`);
  if (!r.ok){
    const message = `${level}级：${propositionError(r.data, `HTTP ${r.status || '网络错误'}`)}`;
    renderPropositionRows([], message);
    propositionResult({operation: mode, level, ok:false, status:r.status, error:message});
    pipelineNotice(message);
    return;
  }
  const questions = Array.isArray(r.data) ? r.data : (r.data.items || r.data.questions || []);
  renderPropositionRows(questions, `真实${mode === 'random' ? '随机' : '推荐'}抽题 · ${level}级`);
  propositionResult(r.data);
  pipelineNotice(`${level}级抽题成功`);
}
function renderPropositionRows(rows, source){
  const t = $('propQuestionTable');
  if (!t) return;
  t.innerHTML = '<tr><th>编号</th><th>等级</th><th>文本</th><th>拼音</th><th>语法点</th><th>状态</th><th>录音数</th></tr>';
  if (!rows.length){
    t.innerHTML += `<tr><td colspan="7" class="mut">${safeProp(source || '没有可显示的题目')}</td></tr>`;
  }else rows.forEach(q => {
    const py = (q.tokens || []).map(x => x.display_py || x.py || '').join(' ');
    t.innerHTML += `<tr><td>${safeProp(q.question_id || q.id)}</td><td>${safeProp(q.level)}</td><td>${safeProp(q.display_text || q.text)}</td><td>${safeProp(py)}</td><td>${safeProp((q.grammar || []).join(', '))}</td><td>${safeProp(q.status || '')}</td><td>${Number(q.rec_count || 0)}</td></tr>`;
  });
  const sourceEl = $('propSource');
  if (sourceEl) sourceEl.textContent = `${source || '真实后端数据'} · ${rows.length}题`;
}
function pipelineNotice(m){if(typeof toast==='function')toast(m);}
function safeProp(v){return String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');}





