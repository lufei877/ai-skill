"use strict";

const labels = {1: "每日", 2: "每两天", 7: "每周"};
const availability = {available: "已检测", stale: "检测已过期", missing: "目录不可用", error: "检测不完整", disabled: "注册已停用", not_observed: "待检测"};
const results = {completed: "已整理", no_change: "检查完成，无新增知识", failed: "执行失败"};
const skillStates = {detected: "发现框架", partial: "发现部分标记", not_detected: "未发现安装标记", unavailable: "目录不可读"};
const workflowStates = {enabled: "已启用", disabled: "已关闭", unselected: "未配置", unknown: "配置待检查"};
let board;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function date(value) {
  return value ? new Date(value).toLocaleString("zh-CN", {month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"}) : "尚无记录";
}

function notice(text, error = false) {
  const target = document.getElementById("notice");
  target.textContent = text;
  target.className = error ? "error" : "";
}

async function request(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Cadence-Token": board.csrf},
    body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "请求失败");
  return result;
}

function checkbox(text, checked) {
  const label = node("label");
  const input = node("input");
  input.type = "checkbox";
  input.checked = checked;
  label.append(input, node("span", text));
  return {label, input};
}

function connectionText(connection) {
  return `Skill：${skillStates[connection.skill]} · 工作流：${workflowStates[connection.workflow]}`;
}

function renderDiscovery(discovery) {
  document.getElementById("discovery-summary").textContent = `发现 ${discovery.projects.length} 个有接入标记、尚未登记的项目`;
  document.getElementById("discovery-source").textContent = `来源：${discovery.source} · ${discovery.known_count} 个已知路径 · 清单导入：${date(discovery.imported_at)}。刷新会重新检查这些路径的接入标记；新增 Codex 项目需更新清单或直接在上方粘贴路径。`;
  const candidates = discovery.projects.map(project => {
    const row = node("div", undefined, "candidate");
    const description = node("div");
    description.append(node("strong", project.name), node("p", project.path, "path"),
      node("p", connectionText(project.connection), "caption"));
    const select = node("button", "选择此项目", "secondary");
    select.type = "button";
    select.addEventListener("click", () => {
      document.getElementById("register-name").value = project.name;
      document.getElementById("register-path").value = project.path;
      document.getElementById("register").focus();
      notice(`已填入 ${project.name}，点击“登记到看板”完成登记。`);
    });
    row.append(description, select);
    return row;
  });
  document.getElementById("discovered-projects").replaceChildren(...candidates);
  document.getElementById("discovery-errors").replaceChildren(...discovery.errors.map(item =>
    node("p", `${item.path}：${item.error}`)));
}

function projectRow(project) {
  const article = node("article", undefined, "project");
  const top = node("div", undefined, "project-top");
  const identity = node("div");
  identity.append(node("div", project.name, "project-name"), node("div", project.path, "path"));
  identity.append(node("p", `${connectionText(project.connection)} · 中央：已登记`, "caption"));
  if (project.connection.error) identity.append(node("p", project.connection.error, "caption"));
  top.append(identity, node("span", project.active_run ? "整理中" : project.due ? "已到期" : availability[project.availability], "status"));
  const body = node("div", undefined, "project-body");
  const chart = node("div");
  const bars = node("div", undefined, "bars");
  bars.setAttribute("role", "img");
  bars.setAttribute("aria-label", `${project.name} 最近14天内容变化；近48小时${project.events_48h}次`);
  const maximum = Math.max(1, ...project.history.map(day => day.events));
  for (const day of project.history) {
    const column = node("div", undefined, "bar");
    const fill = node("div", undefined, day.events ? "bar-fill" : "bar-fill bar-empty");
    fill.classList.add(`level-${Math.ceil(day.events / maximum * 10)}`);
    column.title = `${day.date}：${day.observed ? `${day.events} 次内容变化` : "未采样"}`;
    column.append(node("small", day.events || ""), fill);
    bars.append(column);
  }
  chart.append(bars);
  const dates = node("div", undefined, "chart-label");
  dates.append(node("span", project.history[0].date.slice(5)), node("span", "今天"));
  chart.append(dates, node("p", `48小时：${project.events_48h} 次变化 · ${project.knowledge_changes_48h} 个知识文件变化`, "caption"));
  const timing = node("div");
  const frequency = node("div", labels[project.effective_days], "frequency");
  frequency.append(node("small", project.adaptive ? "自动调频" : "人工固定"));
  timing.append(frequency, node("p", project.reason, "reason"),
    node("p", `下次整理：${project.selected ? date(project.next_due_at) : "待选择项目"}`, "meta"),
    node("p", `上次完成：${date(project.last_completed_at)} · ${results[project.last_result] || "未执行"}`, "meta"),
    node("p", `项目知识：${project.knowledge_files} 个文件 · ${project.pending_changes ? "有待检查内容" : "无待检查变化"}`, "meta"));
  body.append(chart, timing);
  const settings = node("div", undefined, "settings");
  const selected = checkbox("重点项目", project.selected);
  const adaptive = checkbox("自动调频", project.adaptive);
  const baseLabel = node("label", "基础日程");
  const base = node("select");
  base.setAttribute("aria-label", `${project.name} 基础日程`);
  for (const [value, label] of Object.entries(labels)) {
    const option = node("option", label);
    option.value = value;
    option.selected = Number(value) === project.base_days;
    base.append(option);
  }
  baseLabel.append(base);
  const save = node("button", "保存设置", "secondary save");
  save.type = "button";
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await request("/api/settings", {project: project.name, revision: board.revision,
        policy: {selected: selected.input.checked, base_days: Number(base.value), adaptive: adaptive.input.checked}});
      await refresh();
      notice(`${project.name} 设置已保存。外部日程仍由你安排。`);
    } catch (error) { notice(error.message, true); }
    finally { save.disabled = false; }
  });
  settings.append(selected.label, baseLabel, adaptive.label, save);
  article.append(top, body, settings);
  return article;
}

async function refresh() {
  board = await request("/api/state");
  document.getElementById("selected").textContent = board.projects.filter(project => project.selected).length;
  document.getElementById("due").textContent = board.projects.filter(project => project.due).length;
  document.getElementById("observed").textContent = date(board.last_tick_at);
  document.getElementById("projects").replaceChildren(...board.projects.map(projectRow));
  document.getElementById("release-gate").textContent = board.release_gate;
  renderDiscovery(board.discovery);
  if (!board.projects.length) notice("没有已注册项目，请先将项目加入中央注册表。");
}

document.getElementById("observe").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  notice("正在检测已注册项目的源码与知识变化…");
  try {
    await request("/api/observe", {});
    await refresh();
    notice("检测完成。频率已重新计算，未执行知识整理或中央发布。");
  } catch (error) { notice(error.message, true); }
  finally { button.disabled = false; }
});

document.getElementById("register-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = document.getElementById("register");
  button.disabled = true;
  try {
    const result = await request("/api/register", {
      path: document.getElementById("register-path").value.trim(),
      name: document.getElementById("register-name").value.trim()
    });
    await refresh();
    document.getElementById("register-form").reset();
    notice(`${result.name} ${result.created ? "已登记" : "已在看板中，无需重复登记"}。可在项目卡片选择重点日程；登记不会安装或升级 Skill。`);
  } catch (error) { notice(error.message, true); }
  finally { button.disabled = false; }
});

async function initialize() {
  try {
    await refresh();
    if (board.projects.length) notice("选择重点项目并保存基础日程。自动调频在每次检测后更新。");
  } catch (error) { notice(error.message, true); }
}

initialize();
