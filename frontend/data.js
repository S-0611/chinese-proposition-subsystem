/* ═══════════ 中文发音智能诊断与评价系统 · 整合演示 V2 · 写死数据 ═══════════
   偏误体系统一为 8 类（按 10-20 会议意见新增「语调」维度）：
   字符级：sf 声韵母误读 / tone 声调偏误 / inton 语调偏误 / del 漏读 / rep 重复
   字间级：ins 增读 / fill 填充词 / pause 停顿（gap g = 第 g 个字之前的空隙） */

const ERRNAME = {sf:'声韵母误读', tone:'声调偏误', inton:'语调偏误', del:'漏读', rep:'重复',
  ins:'增读', fill:'填充词', pause:'停顿'};
const ERRNAME_EN = {sf:'Initial/Final', tone:'Tone', inton:'Intonation', del:'Missing',
  rep:'Repeated', ins:'Extra', fill:'Filler', pause:'Pause'};
const TYPE_ORDER = {sf:0, tone:1, inton:2, del:3, rep:4, ins:5, fill:6, pause:7};
const byTypeOrder = arr => (arr || []).slice().sort((a, b) => (TYPE_ORDER[a] ?? 9) - (TYPE_ORDER[b] ?? 9));

/* 分层标注面板：字符级 / 字间级 各自可见的大类与子类（含新增语调维度） */
const GROUPS_CHAR = [
  ['误读',   [['sf', '声韵母误读'], ['tone', '声调偏误']]],
  ['语调',   [['inton', '语调偏误（语气）']]],
  ['漏读',   [['del', '漏读']]],
  ['不流利', [['rep', '重复']]],
];
const GROUPS_GAP = [
  ['增读',   [['ins', '增读']]],
  ['不流利', [['fill', '填充词'], ['pause', '停顿']]],
];

/* 题目难度分层（按会议「分层命题」意见）：beginner 初级(字词) / inter 中级(句子) / advanced 高级(语篇表达) */
const LEVELS = [
  {k:'beginner',  en:'Beginner',     zh:'初级 · 字词', desc:'Words & short phrases'},
  {k:'inter',     en:'Intermediate', zh:'中级 · 句子', desc:'Sentences'},
  {k:'advanced',  en:'Advanced',     zh:'高级 · 语篇', desc:'Passages & free talk'},
];

/* ── 学生端练习题目（Mode A 跟读 / Mode B 自由表达；level 为难度分层） ── */
const QUESTIONS = [
  {id:'q5', mode:'A', level:'beginner', nameEn:'Read aloud · Hello', name:'跟读 · 你好', text:'你好',
   tokens:[
    {c:'你', py:'ni3', err:{t:'tone', py:'ni2', note:'应读 ni3'}},
    {c:'好', py:'hao3'}],
   gapErrs:{},
   scores:{acc:78.0, comp:100, flu:88.0, total:84.1},
   fluency:{speed:'1.8 字/秒', ratio:'6%', mlr:'1.0'},
   errTypes:['二/三声混淆'],
   rep:{
    zh:'词语朗读完整清晰。"你"字声调偏误：读成了二声（应读三声 ni3）。三声的关键是先降后升的调型，建议练习"你—泥""好—嚎"等最小对立词，先夸张读出降升调型再自然化。',
    en:'The word was read completely and clearly. One tone error: 你 (nǐ) was read with Tone 2 instead of Tone 3. Tone 3 dips down first, then rises. Tip: drill minimal pairs like nǐ (you) – ní (mud) and hǎo (good) – háo (number), exaggerating the dip-rise contour at first.',
    th:'อ่านครบถ้วนชัดเจนดี จุดที่ต้องแก้คือวรรณยุกต์ของ "你 (nǐ)" ออกเสียงวรรณยุกต์ที่ 2 แทนที่จะเป็นเสียงที่ 3 เสียงที่ 3 จะลดต่ำแล้วลอยขึ้น แนะนำให้ฝึกเทียบคำ nǐ–ní, hǎo–háo โดยออกเสียงเน้นเสียงลด–ขึ้นให้ชัดก่อน',
   }},
  {id:'q1', mode:'A', level:'inter', nameEn:'Read aloud · The weather is nice today', name:'跟读 · 今天天气很好', text:'今天天气很好',
   tokens:[
    {c:'今', py:'jin1'},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'气', py:'qi4', err:{t:'del', note:'漏读'}},
    {c:'很', py:'hen3'},
    {c:'的', py:'de5'},
    {c:'好', py:'hao3'}],
   gapErrs:{'4':{t:'pause', py:'1500ms', note:'停顿 1500ms'},
            '5':{t:'ins', py:'de5', text:'的', note:'增读'}},
   scores:{acc:47.0, comp:83.3, flu:56.0, total:57.9},
   fluency:{speed:'1.63 字/秒', ratio:'41.7%', mlr:'3.0'},
   errTypes:['二/三声混淆', '漏读'],
   rep:{
    zh:'本次跟读能够读出句子主体，完整度较好，但准确度有待提高。具体来看："天"字两处声调偏误，读成了二声（应读一声 tian1），这是本次得分偏低的主要原因；"气"字漏读；"很"后面多读了一个"的"；另外"气"与"很"之间出现了约 1.5 秒的长停顿，影响了流利度。建议：先做一声与二声的最小对立词练习（如"妈—麻""知—直"），再放慢语速逐字跟读，补齐漏读、去掉增读后连贯朗读整句。',
    en:'The main content of the sentence came through and completeness was fairly good, but pronunciation accuracy needs work. Specifically: 天 (tiān) was read with Tone 2 instead of Tone 1 twice — the main reason for the low accuracy score; 气 (qì) was omitted, and an extra 的 (de) slipped in after 很 (hěn). A pause of about 1.5 seconds also affected fluency. Suggestions: drill Tone 1 vs Tone 2 minimal pairs (mā–má, zhī–zhí), then read the sentence slowly character by character, restoring the missing syllable and dropping the extra one.',
    th:'โดยรวมอ่านได้ครบถ้วนพอสมควร แต่ความแม่นยำยังต้องปรับปรุง จุดหลัก: "天 (tiān)" ออกเสียงวรรณยุกต์ที่ 2 แทนเสียงที่ 1 รวม 2 ครั้ง เป็นสาเหตุหลักที่คะแนนต่ำ ไม่ได้ออกเสียง "气 (qì)" และออกเสียง "的 (de)" เพิ่มหลัง "很 (hěn)" และมีการหยุดยาวประมาณ 1.5 วินาที ทำให้ความคล่องแคล่วลดลง คำแนะนำ: ฝึกเทียบเสียงวรรณยุกต์ 1–2 ด้วยคำคู่ เช่น mā–má, zhī–zhí แล้วอ่านช้า ๆ ทีละพยางค์ ออกเสียงให้ครบและตัดคำที่เกินออก',
   }},
  {id:'q2', mode:'A', level:'beginner', nameEn:'Read aloud · He ran away', name:'跟读 · 他跑了', text:'他跑了',
   tokens:[
    {c:'他', py:'ta1'},
    {c:'跑', py:'pao3', err:{t:'sf', py:'bao3', note:'应读 pao3'}},
    {c:'了', py:'le5'}],
   gapErrs:{},
   scores:{acc:61.0, comp:100, flu:78.0, total:75.2},
   fluency:{speed:'2.2 字/秒', ratio:'8%', mlr:'1.2'},
   errTypes:['n/l 混淆'],
   rep:{
    zh:'本次朗读完整流利，"了"字处理自然。需要纠正的是"跑"字的声母：读成了不送气的 b（应读送气的 p），这是常见的送气与不送气混淆。建议：把手掌放在嘴前做送气感知练习，对比"跑 pǎo — 饱 bǎo"，先慢速夸张地读出送气，再逐渐恢复正常语速。',
    en:'The sentence was read fluently and completely, and 了 (le) was handled naturally. One issue to fix: the initial of 跑 (pǎo) was pronounced as an unaspirated "b" instead of the aspirated "p" — a very common confusion. Try the palm-in-front-of-the-mouth aspiration exercise, contrasting pǎo (run) with bǎo (full): exaggerate the puff of air slowly at first, then return to a natural pace.',
    th:'อ่านได้คล่องและครบถ้วนดี คำว่า "了 (le)" ออกเสียงเป็นธรรมชาติ สิ่งที่ต้องแก้คือพยัญชนะต้นของ "跑 (pǎo)" ออกเสียงเป็น b ไม่เป่าลม ทั้งที่ควรเป็นเสียงเป่า p ซึ่งเป็นข้อผิดพลาดที่พบบ่อย แนะนำให้วางมือไว้หน้าปากฝึกรู้สึกถึงลมเป่า เทียบคำ "pǎo (跑) – bǎo (饱)" ออกเสียงเน้นลมชัด ๆ ช้า ๆ ก่อน แล้วค่อยเร่งให้เป็นธรรมชาติ',
   }},
  {id:'q3', mode:'A', level:'beginner', nameEn:'Read aloud · Awesome!', name:'跟读 · 真棒', text:'真棒',
   tokens:[
    {c:'真', py:'zhen1', err:{t:'sf', py:'zheng1', note:'应读 zhen1'}},
    {c:'棒', py:'bang4'}],
   gapErrs:{},
   scores:{acc:70.0, comp:100, flu:85.0, total:82.6},
   fluency:{speed:'2.5 字/秒', ratio:'5%', mlr:'1.0'},
   errTypes:['平翘舌'],
   rep:{
    zh:'整体表现不错，"棒"字准确清晰。"真"字的韵母偏误值得注意：读成了后鼻音 zheng（应读前鼻音 zhen），前后鼻音不分是常见难点。建议：对比练习"真 zhēn — 蒸 zhēng""心 xīn — 星 xīng"，注意舌尖位置——前鼻音舌尖抵住上齿龈，后鼻音舌根向软腭抬起。',
    en:'Good overall performance — 棒 (bàng) was clear and accurate. Watch the final of 真 (zhēn): it was pronounced with the velar nasal -eng instead of the alveolar -en, a very common difficulty. Suggested drill: contrast zhēn (true) with zhēng (steam), and xīn (heart) with xīng (star), focusing on tongue position — tip of the tongue on the alveolar ridge for -en, back of the tongue raised for -eng.',
    th:'ผลโดยรวมดี คำว่า "棒 (bàng)" ออกเสียงชัดเจน จุดที่ควรสังเกตคือเสียงท้ายพยางค์ของ "真 (zhēn)" อ่านเป็นเสียง -eng แทนที่จะเป็น -en ซึ่งเป็นจุดที่ผู้เรียนมักสับสน แนะนำให้ฝึกเทียบคำ "zhēn (真) – zhēng (蒸)" และ "xīn (心) – xīng (星)" โดยเน้นตำแหน่งลิ้น ปลายลิ้นแตะเหงือกสำหรับ -en และยกโคนลิ้นสำหรับ -eng',
   }},
  {id:'q4', mode:'B', level:'inter', nameEn:'Free talk · Greetings', name:'自由表达 · 打招呼场景', text:'打招呼（如问候近况）', topic:'跟老师打招呼，说说你最近怎么样',
   tokens:[
    {c:'呃', py:'e4'},
    {c:'我', py:'wo3', err:{t:'rep', note:'重复 ×3'}},
    {c:'很', py:'hen3'},
    {c:'好', py:'hao3'},
    {c:'呀', py:'ya5'}],
   gapErrs:{'0':{t:'fill', py:'e4', text:'呃', note:'填充词'},
            '4':{t:'fill', py:'ya5', text:'呀', note:'填充词'}},
   rebuilt:'我很好',
   scores:{acc:92.0, comp:100, flu:74.0, total:86.5},
   fluency:{speed:'2.1 字/秒', ratio:'18%', mlr:'2.0'},
   errTypes:['填充词'],
   rep:{
    zh:'自由表达的内容清楚，核心句"我很好"发音准确度很高。流利度方面：句首出现了填充词"呃"，"我"重复了三次，句尾带了语气词"呀"，这些都计入了流利度统计。建议：开口前先在心里把句子组织好，减少填充词；"呀"这类语气词在正式表达中可以省略。说明：所说内容是否切题不在评价范围内。',
    en:'The free-expression task was clear in content, and the core sentence 我很好 (wǒ hěn hǎo) was pronounced with high accuracy. Fluency issues: a filler è (呃) at the start, 我 repeated three times, and the sentence-final particle ya (呀) — all counted in the fluency score. Suggestion: organize the sentence mentally before speaking to reduce fillers; the particle ya can be dropped in formal contexts. Note: content relevance is not evaluated.',
    th:'การแสดงออกอิสระชัดเจนดี ประโยคหลัก "我很好 (wǒ hěn hǎo)" ออกเสียงแม่นยำสูง ด้านความคล่องแคล่ว: มีคำฟุ่มเฟือย "呃 (è)" ตอนต้น "我" พูดซ้ำ 3 ครั้ง และมีเสียงท้ายประโยค "呀 (ya)" ซึ่งนับรวมในคะแนนความคล่องแคล่ว แนะนำให้เรียบเรียงประโยคในใจก่อนพูดเพื่อลดคำฟุ่มเฟือย (หมายเหตุ: เนื้อหาที่พูดว่าเหมาะสมหรือไม่ ไม่อยู่ในเกณฑ์การประเมิน)',
   }},
  {id:'q6', mode:'B', level:'advanced', nameEn:'Free talk · My family', name:'自由表达 · 我的家', text:'自由表达（说说你的家）', topic:'介绍一下你的家：家里有谁，他们做什么',
   tokens:[
    {c:'我', py:'wo3'},
    {c:'家', py:'jia1'},
    {c:'有', py:'you3'},
    {c:'四', py:'si4'},
    {c:'口', py:'kou3'},
    {c:'人', py:'ren2', err:{t:'inton', py:'语调上扬', note:'句末语调上扬（似疑问），应读降调'}},
    {c:'我', py:'wo3', err:{t:'rep', note:'重复 ×2'}},
    {c:'爸', py:'ba4', err:{t:'tone', py:'ba2', note:'应读 ba4'}},
    {c:'爸', py:'ba4'},
    {c:'是', py:'shi4'},
    {c:'老', py:'lao3'},
    {c:'师', py:'shi1'}],
   gapErrs:{'0':{t:'fill', py:'e4', text:'呃', note:'填充词'},
            '6':{t:'pause', py:'1200ms', note:'停顿 1200ms'}},
   rebuilt:'我家有四口人，我爸爸是老师',
   scores:{acc:81.0, comp:100, flu:68.0, total:82.3},
   fluency:{speed:'2.0 字/秒', ratio:'21%', mlr:'2.4'},
   errTypes:['填充词', '二/三声混淆'],
   rep:{
    zh:'表达内容完整，核心句清晰。需要改进："爸"字声调读成二声（应读四声 ba4）；"人"字句末语调上扬，听起来像疑问句，陈述句句末应读降调；另有填充词"呃"和一处重复、"爸爸"后有约 1.2 秒停顿，影响流利度。建议：先按单句跟读把降调练稳，再整段连贯表达。',
    en:'Your content was complete and the core sentence was clear. To improve: 爸 (bà) was read with Tone 2 instead of Tone 4; the sentence-final 人 (rén) had a rising intonation that sounds like a question — statements should end with a falling tone. There was also a filler (呃), one repetition, and a 1.2-second pause. Tip: drill the falling sentence-final tone with single sentences first, then speak the whole passage in one flow.',
    th:'เนื้อหาที่พูดครบถ้วน ประโยคหลักชัดเจน จุดที่ควรปรับปรุง: "爸 (bà)" ออกเสียงวรรณยุกต์ที่ 2 แทนที่จะเป็นเสียงที่ 4 และ "人 (rén)" ท้ายประโยคเสียงสูงขึ้นเหมือนประโยคคำถาม ประโยคบอกเล่าควรลงเสียงท้าย นอกจากนี้ยังมีคำฟุ่มเฟือย การพูดซ้ำ และการหยุด 1.2 วินาที แนะนำให้ฝึกเสียงลงท้ายประโยคด้วยประโยคสั้นก่อน แล้วจึงพูดต่อเนื่องทั้งย่อหน้า',
   }},
];

/* ── 作业批改：汉语一班《今天天气很好》全班成绩（机器初评，写死） ──
   linkTask：关联的标注任务（机器判别失误 → 进入标注工作台复核） */
const HW = [
  {n:'学生A', total:57.9, acc:47.0, comp:83.3, flu:56.0, st:'pending', submitted:'10-11 20:31', linkTask:'A-032',
   tokens:[
    {c:'今', py:'jin1'},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'气', py:'qi4', err:{t:'del', note:'漏读'}},
    {c:'很', py:'hen3'},
    {c:'的', py:'de5'},
    {c:'好', py:'hao3'}],
   gapErrs:{'4':{t:'pause', py:'1500ms', note:'停顿 1500ms'},
            '5':{t:'ins', py:'de5', text:'的', note:'增读'}},
   scores:{acc:47.0, comp:83.3, flu:56.0, total:57.9},
   comment:'本次朗读总体清晰。"天"两处声调误读为二声，"气"字漏读，"很"后多读"的"；句中停顿约1.5秒偏长。建议针对一声/二声对比做专项练习。'},
  {n:'学生B', total:88.4, acc:85.0, comp:100, flu:82.0, st:'ok', submitted:'10-11 19:02',
   tokens:[{c:'今', py:'jin1'}, {c:'天', py:'tian1'},
           {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
           {c:'气', py:'qi4'}, {c:'很', py:'hen3'}, {c:'好', py:'hao3'}],
   gapErrs:{}, scores:{acc:85.0, comp:100, flu:82.0, total:88.4},
   comment:'朗读流利自然，仅"天"一处声调偏误，注意保持一声调值到位。'},
  {n:'学生C', total:91.2, acc:90.0, comp:100, flu:94.0, st:'ok', submitted:'10-11 18:40',
   tokens:[{c:'今', py:'jin1'}, {c:'天', py:'tian1'}, {c:'天', py:'tian1'},
           {c:'气', py:'qi4'}, {c:'很', py:'hen3'}, {c:'好', py:'hao3'}],
   gapErrs:{}, scores:{acc:90.0, comp:100, flu:94.0, total:91.2},
   comment:'发音清晰，语速适中，无偏误检出，可作为班级示范音频。'},
  {n:'学生D', total:63.5, acc:58.0, comp:83.3, flu:60.0, st:'flag', submitted:'10-11 21:15',
   tokens:[{c:'今', py:'jin1'},
           {c:'天', py:'tian1', err:{t:'sf', py:'cin1', note:'应读 tian1'}},
           {c:'天', py:'tian1'},
           {c:'气', py:'qi4', err:{t:'del', note:'漏读'}},
           {c:'很', py:'hen3'}, {c:'好', py:'hao3'}],
   gapErrs:{}, scores:{acc:58.0, comp:83.3, flu:60.0, total:63.5},
   comment:'"天"声母偏误（舌尖位置偏前）需重点纠正；"气"漏读。建议做 z/zh、j/q 专项听辨与跟读。'},
  {n:'学生E', total:76.8, acc:72.0, comp:100, flu:78.0, st:'pending', submitted:'10-12 09:20',
   tokens:[{c:'今', py:'jin1'}, {c:'天', py:'tian1'}, {c:'天', py:'tian1'},
           {c:'气', py:'qi4'}, {c:'很', py:'hen3'},
           {c:'好', py:'hao3', err:{t:'sf', py:'hao2', note:'应读 hao3'}}],
   gapErrs:{}, scores:{acc:72.0, comp:100, flu:78.0, total:76.8},
   comment:'整体良好。"好"韵母调值不稳，注意三声半上读法。'},
  {n:'学生F', total:82.0, acc:80.0, comp:100, flu:85.0, st:'ok', submitted:'10-11 22:05',
   tokens:[{c:'今', py:'jin1'}, {c:'天', py:'tian1'},
           {c:'天', py:'tian1', err:{t:'tone', py:'tian4', note:'应读 tian1'}},
           {c:'气', py:'qi4'}, {c:'很', py:'hen3'}, {c:'好', py:'hao3'}],
   gapErrs:{}, scores:{acc:80.0, comp:100, flu:85.0, total:82.0},
   comment:'仅一处声调偏误且已接近目标调值，继续保持朗读习惯。'},
  {n:'学生H', total:69.3, acc:65.0, comp:83.3, flu:66.0, st:'pending', submitted:'10-12 08:12',
   tokens:[{c:'今', py:'jin1'}, {c:'天', py:'tian1'},
           {c:'天', py:'tian1', err:{t:'del', note:'漏读'}},
           {c:'气', py:'qi4'}, {c:'很', py:'hen3'}, {c:'的', py:'de5'}, {c:'好', py:'hao3'}],
   gapErrs:{'5':{t:'ins', py:'de5', text:'的', note:'增读'}},
   scores:{acc:65.0, comp:83.3, flu:66.0, total:69.3},
   comment:'漏读与增读各一处，建议放慢语速逐字跟读，先保证完整度。'},
  {n:'学生G', total:84.6, acc:82.0, comp:100, flu:88.0, st:'ok', submitted:'10-11 20:58',
   tokens:[{c:'今', py:'jin1'},
           {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
           {c:'天', py:'tian1'}, {c:'气', py:'qi4'}, {c:'很', py:'hen3'}, {c:'好', py:'hao3'}],
   gapErrs:{}, scores:{acc:82.0, comp:100, flu:88.0, total:84.6},
   comment:'总体清晰流畅，一声调值偶有上扬，注意收稳。'},
];

/* ── 学情统计（教师端，写死） ── */
const CLASS_BARS = [
  {lb:'二/三声混淆', v:12}, {lb:'n/l 混淆', v:8},
  {lb:'平翘舌', v:6}, {lb:'漏读/增读', v:3},
];
const TREND = [62, 65, 68, 71, 74];
const STUDENTS = [
  {n:'学生A', cnt:14, avg:61.2, main:'二/三声混淆', tr:1, comp:{sf:20, tone:70, other:10}, wk:[9, 8, 6, 5],
   tip:'声调类占比 70%，四周由 9 处降至 5 处；声韵母类无明显变化——建议保持二/三声对比专项，并增加听辨练习。'},
  {n:'学生D', cnt:11, avg:64.8, main:'平翘舌', tr:0, comp:{sf:55, tone:25, other:20}, wk:[8, 8, 7, 7],
   tip:'声韵母类（平翘舌）占 55% 且四周无改善——建议安排 z/zh、c/ch 最小对立词集中训练，并降低单次练习量、提高频次。'},
  {n:'学生H', cnt:16, avg:70.5, main:'漏读/增读', tr:1, comp:{sf:15, tone:20, other:50}, wk:[10, 8, 6, 4],
   tip:'完整度类偏误四周由 10 处降至 4 处，改善明显——建议逐步恢复常速朗读。'},
  {n:'学生E', cnt:9, avg:75.3, main:'二/三声混淆', tr:1, comp:{sf:25, tone:60, other:15}, wk:[6, 5, 5, 4],
   tip:'声调类缓慢改善——建议结合手势调型辅助记忆三声全上。'},
  {n:'学生B', cnt:12, avg:86.9, main:'声调偏误', tr:1, comp:{sf:10, tone:80, other:10}, wk:[4, 3, 2, 1],
   tip:'整体优秀，仅剩零星声调偏误——可进入篇章朗读巩固。'},
  {n:'学生C', cnt:10, avg:91.5, main:'—', tr:1, comp:{sf:30, tone:50, other:20}, wk:[2, 1, 1, 0],
   tip:'偏误基本清零——可作为班级示范音频提供者。'},
];

/* ── 错题本（学生端，写死；学生测评后「加入错题本」会实时累加） ── */
const MIST = [
  {t:'二/三声混淆', cnt:3, ex:'妈—麻、知—直、你—李'},
  {t:'n/l 混淆', cnt:2, ex:'你—李、牛—刘'},
  {t:'漏读', cnt:1, ex:'逐字指读跟读训练'},
];
const MIST_LOG = [
  {d:'10-08', q:'跟读 · 今天天气很好', t:'声调偏误', det:'"天"tian1 读成 tian2（2 处）'},
  {d:'10-08', q:'跟读 · 今天天气很好', t:'漏读', det:'漏读"气"'},
  {d:'10-06', q:'跟读 · 他跑了', t:'声韵母误读', det:'"跑"pao3 读成 bao3'},
  {d:'10-05', q:'自由表达 · 打招呼', t:'填充词', det:'句首"呃"、句尾"呀"'},
];

/* ── 标注任务（教师端标注工作台 / 管理端任务分配，含机器预标） ── */
const TASKS = [
  {id:'A-029', canonical:'星期天妈妈带我去公园玩', speaker:'S-117（脱敏）', dur:'0:06',
   batch:'B-04', mode:'B', status:'done', annotatedBy:'标注员A',
   tokens:[
    {c:'呃', py:'e4'},
    {c:'星', py:'xing1', err:{t:'sf', py:'xin1', note:'应读 xing1'}},
    {c:'期', py:'qi1'},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'妈', py:'ma1', err:{t:'sf', py:'na1', note:'应读 ma1'}},
    {c:'妈', py:'ma1', err:{t:'del', note:'漏读'}},
    {c:'带', py:'dai4', err:{t:'sf', py:'tiao3', note:'应读 dai4'}},
    {c:'我', py:'wo3', err:{t:'rep', note:'重复 ×2'}},
    {c:'就', py:'jiu4'},
    {c:'去', py:'qu4'},
    {c:'公', py:'gong1'},
    {c:'园', py:'yuan2'},
    {c:'玩', py:'wan2'}],
   gapErrs:{'0':{t:'fill', py:'e4', text:'呃', note:'填充词'},
            '8':{t:'ins', py:'jiu4', text:'就', note:'增读'},
            '10':{t:'pause', py:'900ms', note:'停顿 900ms'}}},
  {id:'A-030', canonical:'周末我和朋友一起去公园玩', speaker:'S-121（脱敏）', dur:'0:06',
   batch:'B-04', mode:'A', status:'pending', assignee:'标注员A',
   tokens:[
    {c:'周', py:'zhou1', err:{t:'tone', py:'zhou2', note:'应读 zhou1'}},
    {c:'末', py:'mo4'},
    {c:'我', py:'wo3'},
    {c:'和', py:'he2'},
    {c:'朋', py:'peng2', err:{t:'sf', py:'beng2', note:'应读 peng2'}},
    {c:'友', py:'you3'},
    {c:'一', py:'yi1', err:{t:'rep', note:'重复 ×2'}},
    {c:'起', py:'qi3'},
    {c:'去', py:'qu4', err:{t:'del', note:'漏读'}},
    {c:'公', py:'gong1', err:{t:'sf', py:'dong1', note:'应读 gong1'}},
    {c:'园', py:'yuan2'},
    {c:'玩', py:'wan2', err:{t:'inton', py:'语调上扬', note:'句末语调上扬，应读降调'}}],
   gapErrs:{'0':{t:'fill', py:'e4', text:'呃', note:'填充词'},
            '9':{t:'pause', py:'1200ms', note:'停顿 1200ms'},
            '12':{t:'ins', py:'le5', text:'了', note:'增读'}}},
  {id:'A-031', canonical:'真棒', speaker:'S-126（脱敏）', dur:'0:02',
   batch:'B-04', mode:'A', status:'pending', assignee:'标注员B',
   tokens:[
    {c:'真', py:'zhen1', err:{t:'sf', py:'zheng1', note:'应读 zhen1'}},
    {c:'棒', py:'bang4'}],
   gapErrs:{}},
  {id:'A-032', canonical:'今天天气很好', speaker:'S-130（脱敏）', dur:'0:04',
   batch:'B-05', mode:'A', status:'pending', assignee:'标注员A',
   tokens:[
    {c:'今', py:'jin1'},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'天', py:'tian1', err:{t:'tone', py:'tian2', note:'应读 tian1'}},
    {c:'气', py:'qi4', err:{t:'del', note:'漏读'}},
    {c:'很', py:'hen3'},
    {c:'的', py:'de5'},
    {c:'好', py:'hao3'}],
   gapErrs:{'4':{t:'pause', py:'900ms', note:'停顿 900ms'},
            '5':{t:'ins', py:'de5', text:'的', note:'增读'}}},
];
/* 管理端「导入音频数据」后追加的任务（演示一次） */
const IMPORT_TASK = {id:'A-033', canonical:'我坐公交车去上学', speaker:'S-133（脱敏）', dur:'0:05',
  batch:'B-05', mode:'A', status:'pending',
  tokens:[
   {c:'我', py:'wo3'}, {c:'坐', py:'zuo4'}, {c:'公', py:'gong1'},
   {c:'交', py:'jiao1'}, {c:'车', py:'che1'}, {c:'去', py:'qu4'},
   {c:'上', py:'shang4', err:{t:'tone', py:'shang2', note:'应读 shang4'}},
   {c:'学', py:'xue2'}],
  gapErrs:{}};

/* ── 已入库的金标记录（管理端标注记录管理；教师复核保存后实时追加） ── */
const RECORDS = [
  {taskId:'A-031', annotator:'标注员B',
   edits:[{i:0, type:'sf', py:'zheng1', c:'真'}],
   savedAt:'2026-10-16 09:12:05'},
  {taskId:'A-029', annotator:'标注员A',
   edits:[
    {g:0, type:'fill', py:'e4', c:'呃'},
    {i:1, type:'sf', py:'xin1', c:'星'},
    {i:3, type:'tone', py:'tian2', c:'天'},
    {i:4, type:'sf', py:'na1', c:'妈'},
    {i:5, type:'del', py:'ma1', c:'妈'},
    {i:6, type:'sf', py:'tiao3', c:'带'},
    {i:7, type:'rep', py:'wo3', c:'我'},
    {g:8, type:'ins', py:'jiu4', c:'就'}],
   savedAt:'2026-10-15 15:00:16'},
];

/* ── 管理端：批改任务分配（作业一进度与 HW 已发布数联动） ── */
const GRADING = [
  {teacher:'教师A', batch:'作业一 · 朗读《今天天气很好》', total:8, dyn:true},
  {teacher:'教师B', batch:'作业二 · 跟读《他跑了》', total:8, done:8},
];
const UNASSIGNED_BATCHES = ['作业三 · 自由表达《我的家》'];

/* ── 管理端：用户管理（写死名单，可增删改查） ── */
const USERS = {
  teachers:[
    {id:'T-001', name:'教师A', user:'li',   cls:'汉语一班', status:'在职'},
    {id:'T-002', name:'教师B', user:'demo_teacher_b', cls:'汉语二班', status:'在职'},
    {id:'T-003', name:'教师C', user:'demo_teacher_c', cls:'汉语三班', status:'休假'},
  ],
  students:[
    {id:'S-001', name:'学生A', user:'demo_student', cls:'汉语一班', status:'在读'},
    {id:'S-002', name:'学生B', user:'demo_student_b', cls:'汉语一班', status:'在读'},
    {id:'S-003', name:'学生C', user:'demo_student_c', cls:'汉语一班', status:'在读'},
    {id:'S-004', name:'学生D', user:'demo_student_d', cls:'汉语一班', status:'在读'},
    {id:'S-005', name:'学生E', user:'demo_student_e', cls:'汉语一班', status:'在读'},
    {id:'S-006', name:'学生F', user:'demo_student_f', cls:'汉语一班', status:'在读'},
    {id:'S-007', name:'学生H', user:'demo_student_g', cls:'汉语一班', status:'在读'},
    {id:'S-008', name:'学生G', user:'demo_student_h', cls:'汉语一班', status:'在读'},
  ],
};

/* ── 登录账号（演示写死；点角色页签可自动填充） ── */
const ACCOUNTS = {
  student:{user:'demo_student', pwd:'', name:'学生A'},
  teacher:{user:'li',           pwd:'', name:'教师A'},
  admin:  {user:'admin',        pwd:'', name:'管理员'},
};

/* ═══════════ V2 新增数据（按 10-20 会议意见落实） ═══════════ */

/* 学生端个人资料与学习画像（注册采集背景信息 + 进步曲线 + 系统性错误归纳） */
const STUDENT = {
  name:'Student A', native:'示例母语', nationality:'示例国家', level:'beginner',
  xp:1240, streak:6, weekly:['Week1','Week2','Week3','Week4','Week5','Week6'],
  scoreTrend:[58, 61, 64, 70, 74, 79],
  errTrend:[14, 12, 9, 7, 5, 3],
  sysErrs:[
    {pat:'Tone 2 → Tone 1 confusion (tiān → tiān1)', status:'improving',
     note:'Common systematic error for 示例母语 speakers — your tone-1 rate rose from 46% to 81% in 6 weeks.'},
    {pat:'Aspiration p / b confusion (pǎo → bǎo)', status:'improving',
     note:'Much better after minimal-pair drills — keep 5 minutes a day.'},
    {pat:'n / l confusion (nǐ → lǐ)', status:'fixed',
     note:'Fixed in Week 4. 🎉 We will keep checking it in reviews.'},
  ],
  badges:['🔥 6-day streak', '⭐ 100 exercises done', '🎯 Tone master Lv.2', '🧩 First free talk'],
};

/* 研究统计（教师/研究员端 · 数据经去隐私化处理，仅呈现群体统计结果） */
const NAT_STATS = [
  {nat:'示例国家',  n:86,  main:'二/三声混淆', tone:58, sf:22, flu:20},
  {nat:'Vietnam',   n:64,  main:'声调偏误（入声归派）', tone:47, sf:31, flu:22},
  {nat:'Korea',     n:52,  main:'平翘舌不分', tone:26, sf:52, flu:22},
  {nat:'USA',       n:38,  main:'四声调值偏平', tone:44, sf:28, flu:28},
  {nat:'Japan',     n:27,  main:'送气/不送气混淆', tone:24, sf:55, flu:21},
  {nat:'Indonesia', n:19,  main:'ü / u 混淆', tone:30, sf:49, flu:21},
];

/* 我的班级（不预设：教师愿意才创建；创建前不影响任何功能） */
const CLASS_STATE = {created:false, name:'', code:'', invite:''};

