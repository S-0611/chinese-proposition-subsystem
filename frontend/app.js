const API_BASE = "http://127.0.0.1:8000";

const sampleQuestions = [
  {
    id: "L1-001",
    level: 1,
    text: "我姓王，你姓什么？",
    tokens: [
      { c: "我", py: "wǒ" }, { c: "姓", py: "xìng" }, { c: "王", py: "Wáng" },
      { c: "你", py: "nǐ" }, { c: "姓", py: "xìng" }, { c: "什", py: "shén" }, { c: "么", py: "me" }
    ],
    grammar: ["G1-04"], status: "published", rec_count: 0
  },
  {
    id: "L1-002",
    level: 1,
    text: "你吃饭了吗？",
    tokens: [
      { c: "你", py: "nǐ" }, { c: "吃", py: "chī" }, { c: "饭", py: "fàn" },
      { c: "了", py: "le" }, { c: "吗", py: "ma" }
    ],
    grammar: ["G1-08"], status: "published", rec_count: 1
  }
];

const levelSelect = document.getElementById("levelSelect");
const loadButton = document.getElementById("loadButton");
const tableBody = document.getElementById("questionTableBody");
const message = document.getElementById("message");
const sourceStatus = document.getElementById("sourceStatus");
const questionCount = document.getElementById("questionCount");
const publishedCount = document.getElementById("publishedCount");
const averageRecordCount = document.getElementById("averageRecordCount");

loadButton.addEventListener("click", loadQuestions);

async function loadQuestions() {
  const level = levelSelect.value;
  setLoading(true);
  try {
    const response = await fetch(`${API_BASE}/api/questions?level=${level}`);
    if (!response.ok) throw new Error(`接口返回 ${response.status}`);
    const data = await response.json();
    const questions = Array.isArray(data) ? data : (data.questions || []);
    renderQuestions(questions, "真实后端数据");
  } catch (error) {
    renderQuestions(sampleQuestions.filter((q) => String(q.level) === level), "示例数据");
    message.textContent = "后端接口暂不可用，当前显示示例数据";
    console.info("后端接口暂不可用：", error.message);
  } finally {
    setLoading(false);
  }
}

function renderQuestions(questions, source) {
  tableBody.innerHTML = "";
  questionCount.textContent = questions.length;
  publishedCount.textContent = questions.filter((q) => q.status === "published").length;
  const totalRecords = questions.reduce((sum, q) => sum + Number(q.rec_count || 0), 0);
  averageRecordCount.textContent = questions.length ? (totalRecords / questions.length).toFixed(1) : "0";
  sourceStatus.textContent = source;

  if (!questions.length) {
    tableBody.innerHTML = '<tr><td class="empty" colspan="7">没有找到题目</td></tr>';
    message.textContent = "当前等级暂无题目";
    return;
  }

  questions.forEach((question) => {
    const row = document.createElement("tr");
    const tokens = Array.isArray(question.tokens) ? question.tokens : [];
    const pinyin = tokens.map((token) => token.py || "").join(" ");
    const grammar = Array.isArray(question.grammar) ? question.grammar.join(", ") : (question.grammar || "");
    row.innerHTML = `
      <td>${escapeHtml(question.id)}</td>
      <td>等级 ${escapeHtml(question.level)}</td>
      <td>${escapeHtml(question.text)}</td>
      <td class="pinyin">${escapeHtml(pinyin)}</td>
      <td>${escapeHtml(grammar)}</td>
      <td><span class="status">${escapeHtml(question.status || "待处理")}</span></td>
      <td>${Number(question.rec_count || 0)}</td>
    `;
    tableBody.appendChild(row);
  });
  message.textContent = `已加载 ${questions.length} 道题目`;
}

function setLoading(isLoading) {
  loadButton.disabled = isLoading;
  loadButton.textContent = isLoading ? "加载中..." : "加载题库";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
