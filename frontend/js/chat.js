document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://15.164.30.127:8080";

  const $ = (id) => document.getElementById(id);
  const el = {
    input: $("messageInput"),
    btnSend: $("btnSend"),
    chatWrap: $("chatWrap"),
    myChatList: $("myChatList"),
    newChatBtn: $("newChatBtn"),
    btnLogin: $("btnLogin"),
    app: $("app"),
    btnMenu: $("btnMenu"),
    btnFile: $("btnFile"),
    fileInput: $("fileInput"),
    dragOverlay: $("dragOverlay"),
    aiStatus: $("aiStatus"),
    aiStatusText: $("aiStatusText"),
    signalPanel: $("signalPanel"),
    signalBadge: $("signalBadge"),
    signalCurrent: $("signalCurrent"),
    signalSteps: $("signalSteps"),
    phase1Analysis: $("phase1Analysis"),
  };

  const params = new URLSearchParams(window.location.search);
  const chatId = params.get("chatId");
  const isNewChat = params.get("new") === "1";

  const state = {
    authConfirmed: false,
    selectedFile: null,
    filePreview: null,
    dragCounter: 0,
    statusTimer: null,
    isSending: false,
    signalPanelActive: false,
    phase1ImageUrl: null,
    phase1ImageLoading: false,
    phase1ImageAvailable: false,
    phase1LastAttemptAt: 0,
  };

  const auth = {
    token() {
      return localStorage.getItem("token") || "";
    },
    jsonHeaders() {
      const token = this.token();
      return token
        ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
        : { "Content-Type": "application/json" };
    },
    multipartHeaders() {
      const token = this.token();
      return token ? { Authorization: `Bearer ${token}` } : {};
    },
    clear() {
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      state.authConfirmed = false;
      renderAuthButton();
    },
  };

  const api = {
    async request(url, options = {}) {
      const res = await fetch(`${API_BASE}${url}`, options);
      const text = await res.text();

      if (res.status === 401) {
        auth.clear();
        throw new Error("로그인이 필요합니다.");
      }

      if (!res.ok) {
        throw new Error(text || "요청 처리 중 오류가 발생했습니다.");
      }

      if (!text) return null;

      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    },
    recentChats() {
      return this.request("/api/chats/recent", {
        method: "GET",
        headers: auth.jsonHeaders(),
      });
    },
    messages() {
      return this.request(`/api/chats/${encodeURIComponent(chatId)}/messages`, {
        method: "GET",
        headers: auth.jsonHeaders(),
      });
    },
    deleteChat(id) {
      return this.request(`/api/chats/${encodeURIComponent(id)}`, {
        method: "DELETE",
        headers: auth.jsonHeaders(),
      });
    },
    status() {
      return this.request(`/api/signal/status?chatId=${encodeURIComponent(chatId)}`, {
        method: "GET",
      });
    },
    async phase1Image() {
      const res = await fetch(
        `${API_BASE}/api/signal/phase1-image?chatId=${encodeURIComponent(chatId)}&_=${Date.now()}`,
        { cache: "no-store" }
      );

      if (res.status === 404) return null;
      if (!res.ok) throw new Error("중간 분석 이미지를 불러오지 못했습니다.");
      return res.blob();
    },
    sendMessage(message, file) {
      const url = `/api/chats/${encodeURIComponent(chatId)}/messages`;

      if (file) {
        const formData = new FormData();
        formData.append("message", message);
        formData.append("file", file);

        return this.request(url, {
          method: "POST",
          headers: auth.multipartHeaders(),
          body: formData,
        });
      }

      return this.request(url, {
        method: "POST",
        headers: auth.jsonHeaders(),
        body: JSON.stringify({ message }),
      });
    },
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  const SIGNAL_ORDER = [
    "10000", "10001", "10002", "10003",
    "20000", "20001",
    "30000", "30001", "30002", "30003",
    "40000", "40001",
    "50000", "50001",
  ];

  const DEFAULT_SIGNAL_MESSAGES = {
    "10000": "PDF 텍스트/섹션 추출 시작",
    "10001": "PDF 텍스트/섹션 추출 완료",
    "10002": "도면 캡션 분석 시작",
    "10003": "도면 캡션 분석 완료",
    "20000": "사용자 입력 분석 시작",
    "20001": "사용자 입력 분석 완료",
    "30000": "유사 특허 탐색 시작",
    "30001": "유사 특허 검색 완료",
    "30002": "문서별 재구조화 시작",
    "30003": "문서별 재구조화 완료",
    "40000": "독립 청구항 생성 시작",
    "40001": "독립 청구항 생성 완료",
    "50000": "최종 답변 생성 시작",
    "50001": "최종 답변 생성 완료",
  };

  const RUNNING_MESSAGE_BY_CODE = {
    START: "AI 답변 생성을 준비 중입니다.",
    "10000": "PDF 내용을 분석하는 중입니다.",
    "10001": "PDF 내용을 분석하는 중입니다.",
    "10002": "도면 정보를 분석하는 중입니다.",
    "10003": "도면 정보를 분석하는 중입니다.",
    "20000": "사용자 입력을 분석하는 중입니다.",
    "20001": "사용자 입력을 분석하는 중입니다.",
    "30000": "유사 특허를 탐색하는 중입니다.",
    "30001": "유사 특허를 탐색하는 중입니다.",
    "30002": "유사 문서를 재구조화하는 중입니다.",
    "30003": "유사 문서를 재구조화하는 중입니다.",
    "40000": "독립 청구항을 생성하는 중입니다.",
    "40001": "독립 청구항을 생성하는 중입니다.",
    "50000": "최종 답변을 생성하는 중입니다.",
    "50001": "최종 답변을 정리하는 중입니다.",
  };

  function displayProgressMessage(status) {
    const code = String(status?.code || "IDLE");

    if (code === "ERROR") return status?.message || "AI 답변 생성 중 오류가 발생했습니다.";
    if (code === "DONE") return "AI 답변 생성이 완료되었습니다.";

    return RUNNING_MESSAGE_BY_CODE[code] || status?.message || "AI 작업을 처리 중입니다.";
  }

  function completedSignalCodes(status) {
    const code = String(status?.code || "IDLE");
    const history = Array.isArray(status?.history) ? status.history : [];
    const doneCodes = new Set(
      history
        .map((item) => String(item.code))
        .filter((itemCode) => SIGNAL_ORDER.includes(itemCode))
    );

    if (SIGNAL_ORDER.includes(code)) doneCodes.add(code);
    if (code === "DONE") SIGNAL_ORDER.forEach((itemCode) => doneCodes.add(itemCode));

    return doneCodes;
  }

  function showSignalPanel() {
    if (!el.signalPanel) return;
    state.signalPanelActive = true;
    el.signalPanel.hidden = false;
    el.signalPanel.classList.add("is-visible");
  }

  function hideSignalPanel() {
    if (!el.signalPanel) return;
    state.signalPanelActive = false;
    el.signalPanel.classList.remove("is-visible");
    el.signalPanel.hidden = true;
  }

  function resetSignalPanel() {
    if (!el.signalBadge || !el.signalCurrent || !el.signalSteps) return;

    el.signalBadge.classList.remove("is-running", "is-error");
    el.signalBadge.textContent = "진행 중";
    el.signalCurrent.textContent = "AI 답변 생성을 준비 중입니다.";

    el.signalSteps.innerHTML = SIGNAL_ORDER.map((code) => `
      <div class="signal-step">
        <span class="signal-step__dot"></span>
        <div class="signal-step__message">${escapeHtml(DEFAULT_SIGNAL_MESSAGES[code])}</div>
      </div>
    `).join("");
  }

  function renderSignalPanel(status) {
    if (!state.signalPanelActive) return;
    if (!el.signalBadge || !el.signalCurrent || !el.signalSteps) return;

    const code = String(status?.code || "IDLE");
    const running = !!status?.running;
    const steps = status?.steps || DEFAULT_SIGNAL_MESSAGES;
    const doneCodes = completedSignalCodes(status);

    el.signalBadge.classList.remove("is-running", "is-error");

    if (code === "ERROR") {
      el.signalBadge.textContent = "오류";
      el.signalBadge.classList.add("is-error");
    } else {
      el.signalBadge.textContent = running ? "진행 중" : "정리 중";
      el.signalBadge.classList.add("is-running");
    }

    el.signalCurrent.textContent = displayProgressMessage(status);

    el.signalSteps.innerHTML = SIGNAL_ORDER.map((stepCode) => {
      const stepMessage = steps[stepCode] || DEFAULT_SIGNAL_MESSAGES[stepCode] || "AI 작업 처리";
      const isDone = doneCodes.has(stepCode);
      const isCurrent = running && code === stepCode;

      let className = "signal-step";
      if (isDone) className += " is-done";
      if (isCurrent) className += " is-current";

      return `
        <div class="${className}">
          <span class="signal-step__dot"></span>
          <div class="signal-step__message">${escapeHtml(stepMessage)}</div>
        </div>
      `;
    }).join("");
  }


  function formatPatentAnswer(rawText) {
    let text = String(rawText ?? "").trim();
    if (!text) return "";

    text = text
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/\t/g, " ")
      .replace(/[ ]{2,}/g, " ")
      .replace(/\n{3,}/g, "\n\n");

    // 긴 구분선 정리
    text = text.replace(/[-━─]{8,}/g, "\n---\n");

    // [사용자의 아이디어 요약], [특허청구범위] 같은 제목 정리
    text = text.replace(/\s*(\[[^\]\n]{2,40}\])\s*/g, "\n\n$1\n");

    // 대괄호 없는 제목도 대괄호 제목처럼 처리
    text = text.replace(
      /(^|\n)\s*(사용자의 아이디어 요약|유사 특허 목록|발명의 명칭|특허청구범위|발명의 설명)\s*/g,
      "\n\n[$2]\n"
    );

    // "청구항 1 에 있어서" 깨진 거 복구
    text = text.replace(
      /청구항\s*(\d+)\s*\n+\s*에\s*있어서/g,
      "청구항 $1에 있어서"
    );

    text = text.replace(
      /청구항\s*(\d+)\s+에\s+있어서/g,
      "청구항 $1에 있어서"
    );

    // "청구항 1 또는 청구항 2에 있어서" 같은 문장 내부 표현 복구
    text = text.replace(
      /청구항\s*(\d+)\s*\n+\s*(또는|내지)\s*청구항\s*(\d+)\s*에\s*있어서/g,
      "청구항 $1 $2 청구항 $3에 있어서"
    );

    // 진짜 청구항 제목 분리
    // 단, "청구항 1에 있어서"는 제목으로 처리하지 않음
    text = text.replace(
      /(^|\n)\s*청구항\s*(\d+)\s*(?!에\s*있어서)/g,
      "\n\n청구항 $2\n"
    );

    // 괄호형 항목: (가), (나), (다)
    text = text.replace(/\s*(\([가-하]\))\s*/g, "\n$1 ");

    // bullet 정리
    text = text.replace(/\s-\s/g, "\n- ");

    // 쉼표 뒤에 무조건 줄바꿈된 경우 어느 정도 복구
    text = text.replace(/,\s*\n+\s*(?!\([가-하]\))/g, ", ");

    text = text.replace(/\n{3,}/g, "\n\n").trim();

    const escaped = escapeHtml(text).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    const lines = escaped.split("\n").map((line) => line.trim());

    const html = [];
    let listOpen = false;

    function closeList() {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
    }

    function getNextMeaningfulLine(index) {
      for (let i = index + 1; i < lines.length; i++) {
        const value = lines[i]?.trim();
        if (value) return value;
      }
      return "";
    }

    function isRealClaimTitle(line, index) {
      if (!/^청구항\s*\d+\s*$/.test(line)) return false;

      const next = getNextMeaningfulLine(index);

      // "청구항 1에 있어서" 류는 제목이 아니라 본문
      if (/^에\s*있어서/.test(next)) return false;
      if (/^(또는|내지)\s*청구항\s*\d+/.test(next)) return false;

      return true;
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (!line) {
        closeList();
        continue;
      }

      if (line === "---") {
        closeList();
        html.push('<hr class="answer-separator">');
        continue;
      }

      // [특허청구범위] 같은 큰 제목
      if (/^\[[^\]]+\]$/.test(line)) {
        closeList();
        const title = line.replace("[", "").replace("]", "");
        html.push(`<div class="answer-heading">${title}</div>`);
        continue;
      }

      // 진짜 청구항 제목
      if (isRealClaimTitle(line, i)) {
        closeList();
        html.push(`<div class="answer-claim-title">${line}</div>`);
        continue;
      }

      // "청구항 1에 있어서"는 본문 강조
      if (/^청구항\s*\d+\s*에 있어서/.test(line)) {
        closeList();
        html.push(`<p class="answer-claim-ref">${line}</p>`);
        continue;
      }

      // bullet
      if (/^[-*] /.test(line)) {
        if (!listOpen) {
          html.push('<ul class="answer-list">');
          listOpen = true;
        }
        html.push(`<li>${line.replace(/^[-*] /, "")}</li>`);
        continue;
      }

      // (가), (나), (다)
      if (/^\([가-하]\)\s+/.test(line)) {
        if (!listOpen) {
          html.push('<ul class="answer-list">');
          listOpen = true;
        }
        html.push(`<li>${line}</li>`);
        continue;
      }

      // 가. 나. 다.
      if (/^[가-하][.)]\s+/.test(line)) {
        closeList();
        html.push(`<div class="answer-subheading">${line}</div>`);
        continue;
      }

      closeList();
      html.push(`<p>${line}</p>`);
    }

    closeList();

    return html.join("");
  }

  function alertError(prefix, err) {
    CustomModal.alert(`${prefix}: ${err.message || err}`);
  }

  function renderAuthButton() {
    if (!el.btnLogin) return;

    const userName = localStorage.getItem("userName");
    const isLoggedIn = state.authConfirmed && userName;

    el.btnLogin.style.display = "inline-flex";
    el.btnLogin.innerHTML = isLoggedIn
      ? `${escapeHtml(userName)}님, 환영합니다.`
      : `
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
            stroke="currentColor" stroke-width="1.8"/>
          <path d="M4 20a8 8 0 0 1 16 0"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        로그인 하세요
      `;

    el.btnLogin.onclick = () => {
      window.location.href = isLoggedIn ? "./profile.html" : "./login.html";
    };
  }

  function closeAllDropdowns() {
    document
      .querySelectorAll(".chat-item.is-open")
      .forEach((item) => item.classList.remove("is-open"));
  }

  function createChatItem(room) {
    const id = room.chatId ?? room.id;
    const title = room.title ?? "새 채팅";

    const wrapper = document.createElement("div");
    wrapper.className = "chat-item";
    wrapper.dataset.chatId = String(id);
    wrapper.innerHTML = `
      <a class="side-item" href="./chat.html?chatId=${encodeURIComponent(id)}">
        <span class="side-item__icon">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 6.5C5 5.12 6.12 4 7.5 4h9C17.88 4 19 5.12 19 6.5v6c0 1.38-1.12 2.5-2.5 2.5H10l-3.2 2.4c-.53.4-1.3.02-1.3-.64V15c-.95-.44-1.5-1.34-1.5-2.5v-6Z"
              stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="side-item__text">${escapeHtml(title)}</span>
      </a>
      <button type="button" class="chat-item__more" aria-label="더보기">⋯</button>
      <div class="chat-item__dropdown" role="menu">
        <button type="button" class="chat-item__action" data-action="delete">삭제</button>
      </div>
    `;

    wrapper.querySelector(".chat-item__more")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isOpen = wrapper.classList.contains("is-open");
      closeAllDropdowns();
      if (!isOpen) wrapper.classList.add("is-open");
    });

    wrapper.querySelector('[data-action="delete"]')?.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeAllDropdowns();

      if (!(await CustomModal.confirm("이 채팅을 삭제할까요?"))) return;

      try {
        await api.deleteChat(id);
        await loadRecentChats();
        if (String(id) === String(chatId)) window.location.href = "../index.html";
      } catch (err) {
        alertError("삭제 실패", err);
      }
    });

    return wrapper;
  }

  async function loadRecentChats() {
    if (!el.myChatList) return;
    el.myChatList.innerHTML = "";

    if (!auth.token()) {
      state.authConfirmed = false;
      renderAuthButton();
      return;
    }

    try {
      const rooms = await api.recentChats();
      state.authConfirmed = true;
      renderAuthButton();
      rooms.forEach((room) => el.myChatList.appendChild(createChatItem(room)));
    } catch {
      state.authConfirmed = false;
      renderAuthButton();
    }
  }

  function renderMessage(message) {
    if (!el.chatWrap) return;

    const isUser = message.role === "USER";
    const item = document.createElement("div");
    item.className = isUser ? "msg msg--user" : "msg";

    item.innerHTML = `
      <div class="msg__avatar ${isUser ? "msg__avatar--q" : "msg__avatar--a"}">
        ${isUser ? "Q" : "A"}
      </div>
      <div class="msg__bubble ${isUser ? "" : "msg__bubble--a"}">
        ${message.originalFileName ? `<div class="file-bubble">📎 ${escapeHtml(message.originalFileName)}</div>` : ""}
        <div class="msg__text"></div>
      </div>
    `;

    const textEl = item.querySelector(".msg__text");
    const content = message.content ?? message.message ?? "";

    if (isUser) {
      textEl.textContent = content;
    } else {
      textEl.classList.add("msg__text--formatted");

      const formatted = message.formattedContent || formatPatentAnswer(content);
      textEl.innerHTML = formatted || `<p>${escapeHtml(content)}</p>`;
    }

    el.chatWrap.appendChild(item);
    item.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function clearMessages() {
    hideAiStatus();
    if (el.chatWrap) el.chatWrap.innerHTML = "";
  }

  async function loadMessages() {
    if (!chatId) return;

    try {
      const messages = await api.messages();
      clearMessages();
      messages.forEach(renderMessage);
      scrollToBottom(false);
    } catch (err) {
      alertError("메시지 로드 실패", err);
    }
  }

  function scrollToBottom(smooth = true) {
    const last = el.chatWrap?.lastElementChild;
    last?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" });
  }

  function showAiStatus(message, shouldScroll = false) {
    if (!el.aiStatus || !el.aiStatusText || !el.chatWrap) return;

    el.aiStatus.hidden = false;
    el.aiStatusText.textContent = message || "AI 답변을 생성 중입니다.";

    const userMessages = el.chatWrap.querySelectorAll(".msg--user");
    const lastUserMessage = userMessages[userMessages.length - 1];

    if (lastUserMessage) {
      lastUserMessage.insertAdjacentElement("afterend", el.aiStatus);
    } else {
      el.chatWrap.appendChild(el.aiStatus);
    }

    // 처음 전송했을 때만 스크롤 이동
    // polling 중에는 false라서 스크롤 고정 안 됨
    if (shouldScroll) {
      el.aiStatus.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }

  function hideAiStatus() {
    if (!el.aiStatus) return;
    el.aiStatus.hidden = true;
    el.aiStatus.remove();
  }

  function hasReachedPhase1Image(status) {
    const code = String(status?.code || "IDLE");
    const history = Array.isArray(status?.history) ? status.history : [];
    const historyCodes = history.map((item) => String(item?.code || item?.id || ""));
    return code === "DONE" || code === "ERROR" || Number(code) >= 40000 || historyCodes.includes("40000");
  }

  function revokePhase1ImageUrl() {
    if (!state.phase1ImageUrl) return;
    URL.revokeObjectURL(state.phase1ImageUrl);
    state.phase1ImageUrl = null;
  }

  function renderPhase1Analysis(collapsed = false) {
    if (!el.phase1Analysis || !state.phase1ImageAvailable || !state.phase1ImageUrl) return;

    el.phase1Analysis.hidden = false;
    el.phase1Analysis.classList.toggle("is-collapsed", collapsed);
    el.phase1Analysis.innerHTML = `
      <button type="button" class="phase1-analysis__toggle" aria-expanded="${collapsed ? "false" : "true"}">
        <span>청구항 검색 유사도 분석</span>
        <span class="phase1-analysis__chevron" aria-hidden="true">⌄</span>
      </button>
      <div class="phase1-analysis__body" ${collapsed ? "hidden" : ""}>
        <p>유사 특허 검색 결과를 시각화한 중간 분석 이미지입니다.</p>
        <img src="${state.phase1ImageUrl}" alt="청구항 검색 유사도 분석 결과" />
      </div>
    `;

    const button = el.phase1Analysis.querySelector(".phase1-analysis__toggle");
    const body = el.phase1Analysis.querySelector(".phase1-analysis__body");
    button?.addEventListener("click", () => {
      const willOpen = body?.hidden;
      if (body) body.hidden = !willOpen;
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
      el.phase1Analysis.classList.toggle("is-collapsed", !willOpen);
    });
  }

  async function ensurePhase1Analysis(collapsed = false, force = false) {
    if (!el.phase1Analysis || !chatId) return false;

    if (state.phase1ImageAvailable && state.phase1ImageUrl) {
      renderPhase1Analysis(collapsed);
      return true;
    }

    const now = Date.now();
    if (state.phase1ImageLoading) return false;
    if (!force && now - state.phase1LastAttemptAt < 2500) return false;

    state.phase1ImageLoading = true;
    state.phase1LastAttemptAt = now;

    try {
      const blob = await api.phase1Image();
      if (!blob) return false;

      revokePhase1ImageUrl();
      state.phase1ImageUrl = URL.createObjectURL(blob);
      state.phase1ImageAvailable = true;
      renderPhase1Analysis(collapsed);
      return true;
    } catch (error) {
      console.warn(error.message || error);
      return false;
    } finally {
      state.phase1ImageLoading = false;
    }
  }

  function hidePhase1Analysis() {
    if (!el.phase1Analysis) return;
    el.phase1Analysis.hidden = true;
    el.phase1Analysis.innerHTML = "";
  }

  function stopStatusPolling() {
    if (!state.statusTimer) return;
    clearInterval(state.statusTimer);
    state.statusTimer = null;
  }

  async function checkStatusOnce() {
    if (!chatId) return false;

    try {
      const status = await api.status();

      if (state.signalPanelActive) {
        renderSignalPanel(status);
      }

      if (hasReachedPhase1Image(status)) {
        await ensurePhase1Analysis(status.code === "DONE");
      }

      if (status.running) {
        showAiStatus(displayProgressMessage(status));
        return true;
      }

      if (status.code === "DONE") {
        hideAiStatus();
        stopStatusPolling();
        await loadMessages();
        await loadRecentChats();
        await ensurePhase1Analysis(true, true);
        hideSignalPanel();
        return false;
      }

      if (status.code === "ERROR") {
        showAiStatus(status.message || "AI 답변 생성 중 오류가 발생했습니다.");
        stopStatusPolling();

        setTimeout(async () => {
          hideAiStatus();
          await loadMessages();
          hideSignalPanel();
        }, 1000);

        return false;
      }

      return state.signalPanelActive;
    } catch {
      return state.signalPanelActive;
    }
  }

  async function startStatusPolling() {
    stopStatusPolling();

    if (!(await checkStatusOnce())) return;

    state.statusTimer = setInterval(async () => {
      if (!(await checkStatusOnce())) stopStatusPolling();
    }, 1000);
  }

  function ensureFilePreview() {
    if (state.filePreview) return state.filePreview;

    const composer = document.querySelector(".composer");
    if (!composer) return null;

    state.filePreview = document.createElement("div");
    state.filePreview.className = "file-preview";
    state.filePreview.style.display = "none";
    composer.parentElement?.insertBefore(state.filePreview, composer);
    return state.filePreview;
  }

  function renderSelectedFile() {
    const preview = ensureFilePreview();
    if (!preview) return;

    if (!state.selectedFile) {
      preview.style.display = "none";
      preview.innerHTML = "";
      return;
    }

    const sizeKb = Math.max(1, Math.round(state.selectedFile.size / 1024));
    preview.style.display = "flex";
    preview.innerHTML = `
      <span class="file-preview__name">📎 ${escapeHtml(state.selectedFile.name)}</span>
      <span class="file-preview__size">${sizeKb}KB</span>
      <button type="button" class="file-preview__remove" aria-label="첨부 취소">×</button>
    `;

    preview.querySelector(".file-preview__remove")?.addEventListener("click", () => {
      state.selectedFile = null;
      if (el.fileInput) el.fileInput.value = "";
      updateSendState();
    });
  }

  function updateSendState() {
    const hasText = (el.input?.value || "").trim().length > 0;
    const hasFile = !!state.selectedFile;

    if (el.btnSend) el.btnSend.disabled = state.isSending || (!hasText && !hasFile);

    if (el.btnFile) {
      el.btnFile.title = hasFile ? `첨부됨: ${state.selectedFile.name}` : "파일 첨부";
      el.btnFile.classList.toggle("has-file", hasFile);
    }

    renderSelectedFile();
  }

  function pickPdfFile(file) {
    if (!file) {
      state.selectedFile = null;
      updateSendState();
      return;
    }

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      state.selectedFile = null;
      if (el.fileInput) el.fileInput.value = "";
      CustomModal.alert("PDF 파일만 첨부할 수 있습니다.");
      updateSendState();
      return;
    }

    state.selectedFile = file;
    updateSendState();
  }

  async function sendMessage() {
    if (state.isSending) return;

    const message = (el.input?.value || "").trim();
    const file = state.selectedFile;

    if (!message && !file) return;
    if (!auth.token()) return CustomModal.alert("로그인이 필요합니다.");
    if (!chatId) return CustomModal.alert("채팅방 ID가 없습니다. index에서 새로 시작하세요.");

    renderMessage({
      role: "USER",
      content: message || `PDF 파일을 첨부했습니다: ${file.name}`,
      originalFileName: file?.name ?? null,
    });

    el.input.value = "";
    state.selectedFile = null;
    if (el.fileInput) el.fileInput.value = "";

    state.isSending = true;
    updateSendState();

    hidePhase1Analysis();
    revokePhase1ImageUrl();
    state.phase1ImageAvailable = false;
    state.phase1LastAttemptAt = 0;

    showAiStatus("AI 답변 생성을 준비 중입니다.", true);
    resetSignalPanel();
    showSignalPanel();

    stopStatusPolling();
    state.statusTimer = setInterval(async () => {
      if (!(await checkStatusOnce())) {
        stopStatusPolling();
      }
    }, 1000);

    try {
      await api.sendMessage(message, file);

      stopStatusPolling();
      hideAiStatus();

      await loadMessages();
      await loadRecentChats();
      await ensurePhase1Analysis(true, true);

      hideSignalPanel();
    } catch (err) {
      stopStatusPolling();
      hideAiStatus();
      hideSignalPanel();
      alertError("전송 실패", err);
    } finally {
      state.isSending = false;
      updateSendState();
    }
  }

  function bindEvents() {
    el.btnMenu?.addEventListener("click", () => el.app?.classList.toggle("is-collapsed"));
    el.input?.addEventListener("input", updateSendState);
    el.btnSend?.addEventListener("click", sendMessage);
    el.btnFile?.addEventListener("click", () => el.fileInput?.click());
    el.fileInput?.addEventListener("change", () => pickPdfFile(el.fileInput.files?.[0] || null));
    el.newChatBtn?.addEventListener("click", () => (window.location.href = "../index.html"));

    el.input?.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      sendMessage();
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".chat-item")) closeAllDropdowns();
    });

    el.app?.addEventListener("dragenter", (e) => {
      e.preventDefault();
      state.dragCounter += 1;
      el.dragOverlay?.classList.add("show");
    });

    el.app?.addEventListener("dragleave", (e) => {
      e.preventDefault();
      state.dragCounter -= 1;
      if (state.dragCounter <= 0) {
        state.dragCounter = 0;
        el.dragOverlay?.classList.remove("show");
      }
    });

    el.app?.addEventListener("dragover", (e) => e.preventDefault());

    el.app?.addEventListener("drop", (e) => {
      e.preventDefault();
      state.dragCounter = 0;
      el.dragOverlay?.classList.remove("show");
      pickPdfFile(e.dataTransfer.files?.[0] || null);
    });
  }

  async function init() {
    renderAuthButton();
    resetSignalPanel();
    hideSignalPanel();
    updateSendState();
    bindEvents();
    await loadRecentChats();
    await loadMessages();

    if (isNewChat && chatId) {
      showAiStatus("AI 답변 생성을 준비 중입니다.", true);
      resetSignalPanel();
      showSignalPanel();
      await startStatusPolling();
    }
  }

  init();
});
