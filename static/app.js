(function () {
  const MAX_TEXT = 2000;
  const LS_KEY = "tts_gateway_api_key";
  const LS_THEME = "tts_gateway_theme";
  const LS_HISTORY = "tts_gateway_history_v1";
  const LANGS = [
    { v: "zh", l: "中文" },
    { v: "en", l: "English" },
    { v: "ja", l: "日本語" },
    { v: "ko", l: "한국어" },
    { v: "yue", l: "粤语" },
  ];

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  let lastBlob = null;
  let lastObjectUrl = null;
  let refsCache = [];

  function getApiKey() {
    return localStorage.getItem(LS_KEY) || "";
  }

  function setApiKey(v) {
    if (v) localStorage.setItem(LS_KEY, v);
    else localStorage.removeItem(LS_KEY);
  }

  function getTheme() {
    const t = localStorage.getItem(LS_THEME);
    return t === "light" ? "light" : "dark";
  }

  function applyTheme(theme) {
    const t = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem(LS_THEME, t);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "light" ? "#f4f6fa" : "#0a0d12");
  }

  function toggleTheme() {
    applyTheme(getTheme() === "light" ? "dark" : "light");
    toast(getTheme() === "light" ? "已切换为浅色" : "已切换为深色");
  }

  function authHeaders(json) {
    const h = {};
    if (json) h["Content-Type"] = "application/json";
    const k = getApiKey();
    if (k) h["X-API-Key"] = k;
    return h;
  }

  function toast(msg, type) {
    const host = $("#toastHost");
    const el = document.createElement("div");
    el.className = "toast" + (type === "error" ? " error" : "");
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  function setStatus(text, kind) {
    const el = $("#status");
    el.textContent = text;
    el.className = "status-line" + (kind ? " " + kind : "");
  }

  async function apiJson(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { ...authHeaders(opts.body != null), ...opts.headers },
    });
    if (res.status === 401) {
      throw new Error("401 未授权：请在右上角「密钥」填写 API Key（与服务器 API_KEY 一致）");
    }
    if (!res.ok) {
      const t = await res.text();
      throw new Error(res.status + " " + t.slice(0, 280));
    }
    return res.json();
  }

  function revokeLastUrl() {
    if (lastObjectUrl) {
      URL.revokeObjectURL(lastObjectUrl);
      lastObjectUrl = null;
    }
  }

  function updateCharCount() {
    const ta = $("#text");
    const n = ta.value.length;
    const el = $("#charCount");
    el.textContent = n + " / " + MAX_TEXT;
    el.classList.toggle("warn", n > MAX_TEXT * 0.9 && n <= MAX_TEXT);
    el.classList.toggle("over", n > MAX_TEXT);
  }

  function fillSelect(sel, options, placeholder) {
    sel.innerHTML = "";
    if (!options.length) {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = placeholder || "（无数据）";
      sel.appendChild(o);
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    options.forEach((opt) => sel.appendChild(opt));
  }

  async function loadIndexMeta() {
    try {
      const data = await apiJson("/v1/index");
      const pill = $("#indexPill");
      const t = data.built_at
        ? new Date(data.built_at * 1000).toLocaleString("zh-CN", { hour12: false })
        : "—";
      pill.textContent = data.character_count + " 角色 · " + t;
      pill.title = "索引构建时间";
    } catch {
      $("#indexPill").textContent = "索引未知";
    }
  }

  async function loadChars() {
    const charSel = $("#char");
    const filter = ($("#charFilter")?.value || "").trim().toLowerCase();
    charSel.classList.add("loading");
    try {
      const data = await apiJson("/v1/characters");
      let chars = data.characters || [];
      if (filter) {
        chars = chars.filter(
          (c) =>
            String(c.id).toLowerCase().includes(filter) ||
            String(c.genie_character || "").toLowerCase().includes(filter)
        );
      }
      const opts = chars.map((c) => {
        const o = document.createElement("option");
        o.value = c.id;
        const rc = c.reference_count != null ? " · " + c.reference_count + " ref" : "";
        o.textContent = c.id + " → " + (c.genie_character || "") + rc;
        return o;
      });
      fillSelect(charSel, opts, "未扫描到角色，请挂载 CHARACTERS_ROOT 后刷新索引");
      if (opts.length) await loadRefs();
      else {
        fillSelect($("#ref"), [], "无参考音");
        $("#refMeta").textContent = "";
      }
    } finally {
      charSel.classList.remove("loading");
    }
  }

  async function loadRefs() {
    const id = $("#char").value;
    if (!id) return;
    const refSel = $("#ref");
    try {
      const data = await apiJson("/v1/characters/" + encodeURIComponent(id) + "/references");
      refsCache = data.references || [];
      const byEm = new Map();
      refsCache.forEach((r) => {
        const em = r.emotion || "default";
        if (!byEm.has(em)) byEm.set(em, []);
        byEm.get(em).push(r);
      });
      const opts = [];
      [...byEm.keys()].sort().forEach((em) => {
        byEm.get(em).forEach((r) => {
          const o = document.createElement("option");
          o.value = r.id;
          o.dataset.path = r.path || "";
          o.dataset.prompt = r.prompt_text || "";
          o.dataset.emotion = r.emotion || "";
          o.dataset.source = r.prompt_source || "";
          const label = (r.emotion ? "[" + r.emotion + "] " : "") + (r.filename || r.id);
          o.textContent = label;
          opts.push(o);
        });
      });
      fillSelect(refSel, opts, "该角色无参考音频");
      updateRefMeta();
    } catch (e) {
      fillSelect(refSel, [], "加载失败");
      setStatus(String(e.message), "err");
    }
  }

  function updateRefMeta() {
    const o = $("#ref").selectedOptions[0];
    const box = $("#refMeta");
    if (!o || !o.value) {
      box.textContent = "";
      return;
    }
    box.textContent =
      "emotion: " +
      (o.dataset.emotion || "") +
      "\nprompt: " +
      (o.dataset.prompt || "") +
      "\nsource: " +
      (o.dataset.source || "") +
      "\n" +
      (o.dataset.path || "");
  }

  function buildTtsBody() {
    const text = $("#text").value.trim();
    if (!text) throw new Error("请输入台词");
    if (text.length > MAX_TEXT) throw new Error("超过 " + MAX_TEXT + " 字限制");
    const char = $("#char").value;
    if (!char) throw new Error("请选择角色");
    const useEmotion = $("#useEmotionOnly").checked;
    const body = {
      text,
      character_id: char,
      language: $("#language").value,
      split_sentence: $("#splitSentence").checked,
    };
    if (useEmotion) {
      const o = $("#ref").selectedOptions[0];
      body.emotion = (o && o.dataset.emotion) || $("#emotionOverride").value || "default";
    } else {
      const refId = $("#ref").value;
      if (!refId) throw new Error("请选择参考音，或开启「仅按情绪匹配」");
      body.ref_id = refId;
      const pt = $("#promptOverride").value.trim();
      if (pt) body.prompt_text = pt;
    }
    return body;
  }

  function saveHistory(entry) {
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    } catch {
      list = [];
    }
    list.unshift(entry);
    list = list.slice(0, 12);
    localStorage.setItem(LS_HISTORY, JSON.stringify(list));
    renderHistory();
  }

  function renderHistory() {
    const ul = $("#history");
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    } catch {
      list = [];
    }
    ul.innerHTML = "";
    if (!list.length) {
      ul.innerHTML = '<li class="empty-hint" style="border:none">合成记录会显示在这里（仅文案摘要，音频需重新合成）</li>';
      return;
    }
    list.forEach((item, i) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = item.snippet;
      btn.title = "点击填入台词";
      btn.onclick = () => {
        $("#text").value = item.text;
        updateCharCount();
        toast("已填入历史台词");
      };
      const time = document.createElement("span");
      time.className = "time";
      time.textContent = item.time;
      li.append(btn, time);
      ul.appendChild(li);
    });
  }

  async function synthesize() {
    const btn = $("#go");
    const spin = $("#goSpinner");
    btn.disabled = true;
    spin.hidden = false;
    setStatus("正在连接 Genie 并合成…", "");
    $("#dl").disabled = true;
    revokeLastUrl();
    lastBlob = null;
    $("#player").removeAttribute("src");
    $("#playerWrap").classList.remove("visible");

    try {
      const body = buildTtsBody();
      const t0 = performance.now();
      const res = await fetch("/v1/tts", {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify(body),
      });
      if (res.status === 401) {
        throw new Error("401 未授权：请配置 API Key");
      }
      if (!res.ok) {
        const err = await res.text();
        throw new Error(res.status + " " + err.slice(0, 280));
      }
      lastBlob = await res.blob();
      lastObjectUrl = URL.createObjectURL(lastBlob);
      const player = $("#player");
      player.src = lastObjectUrl;
      $("#playerWrap").classList.add("visible");
      if ($("#autoPlay").checked) {
        try {
          await player.play();
        } catch {
          /* autoplay policy */
        }
      }
      $("#dl").disabled = false;
      const sec = ((performance.now() - t0) / 1000).toFixed(1);
      const kb = (lastBlob.size / 1024).toFixed(0);
      setStatus("完成 " + sec + "s · " + kb + " KB WAV", "ok");
      toast("合成成功");

      const snippet =
        body.text.length > 36 ? body.text.slice(0, 36) + "…" : body.text;
      saveHistory({
        text: body.text,
        snippet: body.character_id + " · " + snippet,
        time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      });
    } catch (e) {
      setStatus("失败: " + e.message, "err");
      toast(e.message, "error");
      if (String(e.message).includes("401")) openKeyModal();
    } finally {
      btn.disabled = false;
      spin.hidden = true;
    }
  }

  function downloadWav() {
    if (!lastBlob) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(lastBlob);
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    a.download = "tts_" + ($("#char").value || "out") + "_" + stamp + ".wav";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function copyShareLink() {
    try {
      const body = buildTtsBody();
      const params = new URLSearchParams();
      params.set("text", body.text);
      params.set("char_name", body.character_id);
      params.set("text_lang", body.language);
      if (body.emotion) params.set("emotion", body.emotion);
      const ref = refsCache.find((r) => r.id === body.ref_id);
      if (ref && ref.path) {
        params.set("ref_audio_path", ref.path);
        params.set("prompt_text", ref.prompt_text || "");
      }
      const url = location.origin + "/v1/tts?" + params.toString();
      navigator.clipboard.writeText(url).then(
        () => toast("已复制 GET 试听链接（需 API Key 时链接本身不含密钥）"),
        () => toast("复制失败", "error")
      );
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function refreshIndex() {
    const btn = $("#refresh");
    btn.disabled = true;
    setStatus("扫描目录并重建索引…", "");
    try {
      await apiJson("/v1/index/refresh", { method: "POST" });
      await loadIndexMeta();
      await loadChars();
      setStatus("索引已更新", "ok");
      toast("索引已刷新");
    } catch (e) {
      setStatus("刷新失败: " + e.message, "err");
      toast(e.message, "error");
    } finally {
      btn.disabled = false;
    }
  }

  function openKeyModal() {
    $("#apiKeyInput").value = getApiKey();
    $("#keyOverlay").classList.add("open");
  }

  function closeKeyModal() {
    $("#keyOverlay").classList.remove("open");
  }

  function bind() {
    $("#char").addEventListener("change", loadRefs);
    $("#ref").addEventListener("change", updateRefMeta);
    $("#charFilter")?.addEventListener("input", () => {
      clearTimeout(bind._filterT);
      bind._filterT = setTimeout(loadChars, 280);
    });
    $("#text").addEventListener("input", updateCharCount);
    $("#go").addEventListener("click", synthesize);
    $("#dl").addEventListener("click", downloadWav);
    $("#refresh").addEventListener("click", refreshIndex);
    $("#copyLink").addEventListener("click", copyShareLink);
    $("#themeToggle")?.addEventListener("click", toggleTheme);
    $("#openKey").addEventListener("click", openKeyModal);
    $("#closeKey").addEventListener("click", closeKeyModal);
    $("#keyOverlay").addEventListener("click", (e) => {
      if (e.target.id === "keyOverlay") closeKeyModal();
    });
    $("#saveKey").addEventListener("click", () => {
      setApiKey($("#apiKeyInput").value.trim());
      closeKeyModal();
      toast("密钥已保存到本机");
      loadChars().catch(() => {});
    });
    $("#useEmotionOnly").addEventListener("change", (e) => {
      $("#ref").disabled = e.target.checked;
      $("#emotionOverride").disabled = !e.target.checked;
    });

    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        synthesize();
      }
    });
  }

  async function init() {
    applyTheme(getTheme());
    bind();
    updateCharCount();
    renderHistory();
    const langSel = $("#language");
    LANGS.forEach(({ v, l }) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = l;
      langSel.appendChild(o);
    });
    if (!getApiKey()) {
      try {
        const ping = await fetch("/v1/characters", { headers: authHeaders() });
        if (ping.status === 401) openKeyModal();
      } catch {
        /* offline */
      }
    }
    try {
      await loadIndexMeta();
      await loadChars();
      setStatus("就绪 · " + (getApiKey() ? "已配置密钥" : "未配置密钥（若服务端启用 API_KEY 需填写）"), "");
    } catch (e) {
      setStatus("加载失败: " + e.message, "err");
      if (String(e.message).includes("401")) openKeyModal();
    }
  }

  init();
})();