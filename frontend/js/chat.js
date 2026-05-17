document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const chatWrap = document.getElementById("chatWrap");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");
  const btnLogin = document.getElementById("btnLogin");
  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  const btnFile = document.getElementById("btnFile");
  const fileInput = document.getElementById("fileInput");
  const dragOverlay = document.getElementById("dragOverlay");

  // 있으면 사용, 없어도 오류 안 나게 처리
  const aiStatus = document.getElementById("aiStatus");
  const aiStatusText = document.getElementById("aiStatusText");

  let filePreview = null;

  const urlParams = new URLSearchParams(window.location.search);
  const chatId = urlParams.get("chatId");
  const shouldTypeLatestAi = urlParams.get("new") === "1";

  let authConfirmed = false;
  let selectedFile = null;
  let dragCounter = 0;
  let statusTimer = null;
  let isSending = false;
  let lastStatusCode = "";

  function getToken() {
    return localStorage.getItem("token") || "";
  }

  function jsonHeaders() {
    const token = getToken();
    if (!token) return { "Content-Type": "application/json" };

    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  function multipartHeaders() {
    const token = getToken();
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }

  function renderAuthUI() {
    if (!btnLogin) return;

    const userName = localStorage.getItem("userName");

    if (authConfirmed && userName) {
      btnLogin.style.display = "inline-flex";
      btnLogin.innerHTML = `${userName}님, 환영합니다.`;
      btnLogin.onclick = () => {
        window.location.href = "./profile.html";
      };
    } else {
      btnLogin.style.display = "inline-flex";
      btnLogin.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
            stroke="currentColor" stroke-width="1.8"/>
          <path d="M4 20a8 8 0 0 1 16 0"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        로그인 하세요
      `;
      btnLogin.onclick = () => {
        window.location.href = "./login.html";
      };
    }
  }

  function ensureFilePreview() {
    if (filePreview) return filePreview;

    const composer = document.querySelector(".composer");
    if (!composer) return null;

    filePreview = document.createElement("div");
    filePreview.className = "file-preview";
    filePreview.style.display = "none";

    composer.parentElement?.insertBefore(filePreview, composer);
    return filePreview;
  }

  function renderSelectedFile() {
    const preview = ensureFilePreview();
    if (!preview) return;

    if (!selectedFile) {
      preview.style.display = "none";
      preview.innerHTML = "";
      return;
    }

    const sizeKb = Math.max(1, Math.round(selectedFile.size / 1024));
    preview.style.display = "flex";
    preview.innerHTML = `
      <span class="file-preview__name">📎 ${escapeHtml(selectedFile.name)}</span>
      <span class="file-preview__size">${sizeKb}KB</span>
      <button type="button" class="file-preview__remove" aria-label="첨부 취소">×</button>
    `;

    preview
      .querySelector(".file-preview__remove")
      ?.addEventListener("click", () => {
        selectedFile = null;
        if (fileInput) fileInput.value = "";
        updateSendState();
      });
  }

  function updateSendState() {
    const hasText = (input?.value || "").trim().length > 0;
    const hasFile = selectedFile !== null;

    if (btnSend) btnSend.disabled = !hasText && !hasFile;

    if (btnFile) {
      btnFile.title = selectedFile ? `첨부됨: ${selectedFile.name}` : "파일 첨부";
      btnFile.classList.toggle("has-file", !!selectedFile);
    }

    renderSelectedFile();
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function closeAllDropdowns() {
    document
      .querySelectorAll(".chat-item.is-open")
      .forEach((el) => el.classList.remove("is-open"));
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

    wrapper
      .querySelector('[data-action="delete"]')
      ?.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeAllDropdowns();

        const ok = await CustomModal.confirm("이 채팅을 삭제할까요?");
        if (!ok) return;

        await deleteChatRoom(id);
        await loadRecentChats();

        if (String(id) === String(chatId)) {
          window.location.href = "../index.html";
        }
      });

    return wrapper;
  }

  async function deleteChatRoom(id) {
    try {
      const res = await fetch(`${API_BASE}/api/chats/${encodeURIComponent(id)}`, {
        method: "DELETE",
        headers: jsonHeaders(),
      });

      const text = await res.text();

      if (!res.ok) {
        await CustomModal.alert("삭제 실패: " + text);
      }
    } catch (err) {
      await CustomModal.alert("서버 연결 실패");
    }
  }

  async function loadRecentChats() {
    if (!myChatList) return;

    myChatList.innerHTML = "";

    const token = getToken();

    if (!token) {
      authConfirmed = false;
      renderAuthUI();
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/chats/recent`, {
        method: "GET",
        headers: jsonHeaders(),
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("userName");
        authConfirmed = false;
        renderAuthUI();
        return;
      }

      if (!res.ok) {
        authConfirmed = false;
        renderAuthUI();
        return;
      }

      authConfirmed = true;
      renderAuthUI();

      const rooms = await res.json();
      rooms.forEach((room) => myChatList.appendChild(createChatItem(room)));
    } catch (err) {
      authConfirmed = false;
      renderAuthUI();
    }
  }

  function formatPatentAnswer(rawText) {
    let text = String(rawText ?? "").trim();
    if (!text) return "";

    text = text
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/\n{3,}/g, "\n\n");

    // 긴 구분선 제거 또는 구분선으로 정리
    text = text.replace(/[-━─]{8,}/g, "\n---\n");

    // 이전 포맷팅 때문에 깨진 단어 복구
    text = text.replace(/([가-힣])\s*\n+\s*다\./g, "$1다.");
    text = text.replace(/([가-힣])\s*\n+\s*법\./g, "$1법.");
    text = text.replace(/([가-힣])\s*\n+\s*템\./g, "$1템.");

    // 쉼표 뒤 줄바꿈은 보통 다시 붙임
    // 단, 다음 줄이 "(가)", "(나)", "(다)" 같은 괄호형 항목이면 줄바꿈 유지
    text = text.replace(/,\s*\n+\s*(?!\([가-하]\))/g, ", ");

    // 괄호형 항목 "(가)", "(나)", "(다)"는 줄 시작에 오도록 정리
    // 예: "... 데이터는, (가) ..." → "... 데이터는,\n(가) ..."
    text = text.replace(/\s*(\([가-하]\))\s*/g, "\n$1 ");

    // "(다) 종속항 확장 규칙" 다음에 "을 포함하도록" 같은 조사가 떨어지면 붙임
    text = text.replace(
      /(\([가-하]\)[^\n]+)\n+\s*(을|를|은|는|이|가|과|와|의)\s+/g,
      "$1$2 "
    );

    // 대괄호 제목은 문단 제목으로 분리
    text = text.replace(/\s*(\[[^\]\n]{2,40}\])\s*/g, "\n\n$1\n");

    // 대괄호가 빠진 주요 섹션 제목도 처리
    text = text.replace(
      /(^|\n)\s*(사용자의 아이디어 요약|유사 특허 목록|발명의 명칭|특허청구범위|발명의 설명)\s*/g,
      "\n\n[$2]\n"
    );

    // 번호 제목 분리: 1. 기술분야, 2. 배경기술 등
    text = text.replace(
      /(^|\n)\s*(\d{1,2}\.\s*(기술분야|배경기술|발명의 내용|발명의 실시를 위한 구체적인 내용|산업상 이용가능성))/g,
      "\n\n$2\n"
    );

    // "방법. 청구항 2"처럼 다음 청구항 제목이 앞 문장에 붙어 나온 경우만 분리
    // "청구항 1에 있어서"는 절대 제목 처리하지 않음
    text = text.replace(
      /(방법\.|시스템\.|장치\.|매체\.|것\.|단계\.|수단\.)\s+청구항\s*(\d+)(?=\s+(?!에\s*있어서)[가-힣A-Za-z])/g,
      "$1\n\n청구항 $2\n"
    );

    // 줄 시작에 단독으로 있는 "청구항 1", "청구항 2"만 제목으로 정리
    text = text.replace(
      /(^|\n)\s*청구항\s*(\d+)\s*$/gm,
      "\n\n청구항 $2"
    );

    // "청구항 1"과 "에 있어서"가 줄바꿈으로 깨진 경우 복구
    text = text.replace(
      /\n+\s*청구항\s*(\d+)\s*\n+\s*에 있어서/g,
      "\n\n청구항 $1에 있어서"
    );

    // 가. 나. 다. 라. 소제목 처리
    // 문장 끝의 "다."는 건드리지 않기 위해 정해진 소제목만 처리
    text = text.replace(
      /(^|\n)\s*([가-하])\.\s*(해결하고자 하는 과제|과제의 해결 수단|발명의 효과|전체 처리 흐름|Dynamic Weights Algorithm 적용|RAG 기반 컨텍스트 및 few-shot 예시 구성의 구체화|시스템 구성의 예)/g,
      "\n\n$2. $3"
    );

    // 유사 특허 목록 bullet 줄바꿈
    text = text.replace(/\s-\s/g, "\n- ");

    // 번호 목록 줄바꿈: (1), (2), (3)
    text = text.replace(/\s\((\d+)\)\s/g, "\n($1) ");

    // 너무 많은 빈 줄 정리
    text = text.replace(/\n{3,}/g, "\n\n").trim();

    const escaped = escapeHtml(text);
    const lines = escaped.split("\n");
    const html = [];
    let listOpen = false;

    function closeList() {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
    }

    for (const lineRaw of lines) {
      const line = lineRaw.trim();

      if (!line) {
        closeList();
        continue;
      }

      if (line === "---") {
        closeList();
        html.push('<hr class="answer-separator">');
        continue;
      }

      if (/^\[[^\]]+\]$/.test(line)) {
        closeList();
        html.push(`<div class="answer-heading">${line.replace("[", "").replace("]", "")}</div>`);
        continue;
      }

      // 진짜 단독 청구항 제목만 claim 스타일
      if (/^청구항\s*\d+\s*$/.test(line)) {
        closeList();
        html.push(`<div class="answer-claim">${line}</div>`);
        continue;
      }

      // "청구항 1에 있어서"는 제목이 아니라 일반 본문
      if (/^청구항\s*\d+\s*에 있어서/.test(line)) {
        closeList();
        html.push(`<p>${line}</p>`);
        continue;
      }

      // 괄호형 하위 항목: (가), (나), (다)
      if (/^\([가-하]\)\s+/.test(line)) {
        if (!listOpen) {
          html.push('<ul class="answer-list">');
          listOpen = true;
        }
        html.push(`<li>${line}</li>`);
        continue;
      }

      // 가. 나. 다. 같은 소제목
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

  async function typeFormattedText(element, text) {
    // 긴 AI 답변을 한 글자씩 innerHTML로 다시 그리면 브라우저 메모리/CPU가 크게 올라감.
    // 그래서 타이핑 애니메이션은 끄고 완성된 답변만 한 번 렌더링함.
    element.classList.add("msg__text--formatted");
    element.innerHTML = formatPatentAnswer(text);
  }

  function renderMessage(role, text, fileName = null, typing = true) {
    if (!chatWrap) return;

    const isUser = role === "USER";

    const item = document.createElement("div");
    item.className = isUser ? "msg msg--user" : "msg";

    const safeFileName = fileName ? escapeHtml(fileName) : "";

    item.innerHTML = `
      <div class="msg__avatar ${isUser ? "msg__avatar--q" : "msg__avatar--a"}">
        ${isUser ? "Q" : "A"}
      </div>
      <div class="msg__bubble ${!isUser ? "msg__bubble--a" : ""}">
        ${fileName ? `<div class="file-bubble">📎 ${safeFileName}</div>` : ""}
        <div class="msg__text"></div>
      </div>
    `;

    chatWrap.appendChild(item);

    const textEl = item.querySelector(".msg__text");
    const content = text || "";

    if (isUser) {
      textEl.textContent = content;
    } else if (typing) {
      typeFormattedText(textEl, content);
    } else {
      textEl.classList.add("msg__text--formatted");
      textEl.innerHTML = formatPatentAnswer(content);
    }

    item.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function clearMessages() {
    hideAiStatus();
    if (chatWrap) chatWrap.innerHTML = "";
  }

  async function loadMessages() {
    if (!chatId) return;

    try {
      const res = await fetch(`${API_BASE}/api/chats/${encodeURIComponent(chatId)}/messages`, {
        method: "GET",
        headers: jsonHeaders(),
      });

      const text = await res.text();

      if (!res.ok) {
        await CustomModal.alert("메시지 로드 실패: " + text);
        return;
      }

      let messages;

      try {
        messages = JSON.parse(text);
      } catch {
        await CustomModal.alert("메시지 응답이 JSON이 아닙니다: " + text);
        return;
      }

      clearMessages();

      const latestAiIndex = shouldTypeLatestAi
        ? messages.map((m) => m.role).lastIndexOf("AI")
        : -1;

      messages.forEach((m, index) => {
        const content = m.content ?? m.message ?? "";
        const typing = index === latestAiIndex;
        renderMessage(m.role, content, m.originalFileName ?? null, typing);
      });

      if (shouldTypeLatestAi) {
        const cleanUrl = `./chat.html?chatId=${encodeURIComponent(chatId)}`;
        window.history.replaceState({}, "", cleanUrl);
      }

      setTimeout(() => {
        const last = chatWrap.lastElementChild;
        if (last) {
          last.scrollIntoView({ behavior: "auto", block: "end" });
        }
      }, 0);
    } catch (err) {
      await CustomModal.alert("서버 연결 실패");
    }
  }

  function showAiStatus(message) {
  if (!aiStatus || !aiStatusText || !chatWrap) return;

  aiStatus.hidden = false;

  // ✅ 텍스트만 변경
  aiStatusText.textContent =
    message || "AI가 답변을 생성 중입니다.";

  // ✅ 이미 붙어있으면 재삽입 금지
  if (!aiStatus.parentElement) {

    const userMessages =
      chatWrap.querySelectorAll(".msg--user");

    const lastUserMessage =
      userMessages[userMessages.length - 1];

    if (lastUserMessage) {
      lastUserMessage.insertAdjacentElement(
        "afterend",
        aiStatus
      );
    } else {
      chatWrap.appendChild(aiStatus);
    }
  }
}

  function hideAiStatus() {
    if (!aiStatus) return;

    aiStatus.hidden = true;

    if (aiStatus.parentElement) {
      aiStatus.parentElement.removeChild(aiStatus);
    }
  }

  function stopStatusPolling() {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  }

  async function checkStatusOnce() {
    try {
      const res = await fetch(`${API_BASE}/api/signal/status`, {
        method: "GET",
      });

      if (!res.ok) {
        hideAiStatus();
        return false;
      }

      const status = await res.json();

      // 다른 채팅방의 시그널이면 현재 화면에는 표시하지 않음
      if (status.chatId && chatId && String(status.chatId) !== String(chatId)) {
        return false;
      }

      if (status.running) {
        showAiStatus(status.message);
        return true;
      }

      if (status.code === "DONE") {
        hideAiStatus();
        await loadMessages();
        await loadRecentChats();
        return false;
      }

      if (status.code === "ERROR") {
        const errorMessage = status.message || "AI 답변 생성 중 오류가 발생했습니다.";
        showAiStatus(errorMessage);
        setTimeout(async () => {
          hideAiStatus();
          await loadMessages();
        }, 1000);

        return false;
      }

      hideAiStatus();
      return false;
    } catch (err) {
      hideAiStatus();
      return false;
    }
  }

  async function startStatusPolling() {
    stopStatusPolling();

    const shouldPoll = await checkStatusOnce();

    if (!shouldPoll) {
      return;
    }

    statusTimer = setInterval(async () => {
      const stillRunning = await checkStatusOnce();

      if (!stillRunning) {
        stopStatusPolling();
      }
    }, 1000);
  }

  async function sendMessage() {
    if (isSending) return;

    const msg = (input?.value || "").trim();
    const file = selectedFile;

    if (!msg && !file) return;

    const token = getToken();

    if (!token) {
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    if (!chatId) {
      await CustomModal.alert("채팅방 ID가 없습니다. index에서 새로 시작하세요.");
      return;
    }

    renderMessage("USER", msg || `파일을 첨부했습니다: ${file.name}`, file?.name ?? null, false);

    input.value = "";
    selectedFile = null;

    if (fileInput) fileInput.value = "";

    isSending = true;
    btnSend.disabled = true;
    updateSendState();
    showAiStatus("AI 답변 생성을 준비 중입니다.");

    try {
      let res;

      if (file) {
        const formData = new FormData();
        formData.append("message", msg);
        formData.append("file", file);

        res = await fetch(`${API_BASE}/api/chats/${encodeURIComponent(chatId)}/messages`, {
          method: "POST",
          headers: multipartHeaders(),
          body: formData,
        });
      } else {
        res = await fetch(`${API_BASE}/api/chats/${encodeURIComponent(chatId)}/messages`, {
          method: "POST",
          headers: jsonHeaders(),
          body: JSON.stringify({ message: msg }),
        });
      }

      const text = await res.text();

      if (!res.ok) {
        await CustomModal.alert("전송 실패: " + text);
        hideAiStatus();
        updateSendState();
        return;
      }

      let messages;

      try {
        messages = JSON.parse(text);
      } catch {
        await CustomModal.alert("전송 응답이 JSON이 아닙니다: " + text);
        hideAiStatus();
        updateSendState();
        return;
      }

      // 서버가 즉시 AI 답변까지 반환하는 구조면 마지막 메시지를 표시
      // 서버가 비동기 구조면 USER 메시지만 오고, 이후 polling에서 loadMessages()로 AI 답변 표시
      const lastMessage = messages[messages.length - 1];

      if (lastMessage && lastMessage.role === "AI") {
        renderMessage(
          lastMessage.role,
          lastMessage.content ?? lastMessage.message ?? "",
          lastMessage.originalFileName ?? null,
          true
        );
      }

      startStatusPolling();
      await loadRecentChats();
    } catch (err) {
      await CustomModal.alert("서버 연결 실패");
      hideAiStatus();
      updateSendState();
    } finally {
      isSending = false;
    }
  }

  btnMenu?.addEventListener("click", () => {
    app?.classList.toggle("is-collapsed");
  });

  document.addEventListener("click", (e) => {
    const clickedInside = e.target.closest(".chat-item");

    if (!clickedInside) {
      closeAllDropdowns();
    }
  });

  input?.addEventListener("input", updateSendState);

  btnSend?.addEventListener("click", sendMessage);

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  btnFile?.addEventListener("click", () => {
    fileInput?.click();
  });

  fileInput?.addEventListener("change", async () => {
    selectedFile = fileInput.files?.[0] || null;
    updateSendState();
  });

  app?.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragCounter++;
    dragOverlay?.classList.add("show");
  });

  app?.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dragCounter--;

    if (dragCounter <= 0) {
      dragCounter = 0;
      dragOverlay?.classList.remove("show");
    }
  });

  app?.addEventListener("dragover", (e) => {
    e.preventDefault();
  });

  app?.addEventListener("drop", async (e) => {
    e.preventDefault();

    dragCounter = 0;
    dragOverlay?.classList.remove("show");

    selectedFile = e.dataTransfer.files?.[0] || null;
    updateSendState();
  });

  newChatBtn?.addEventListener("click", () => {
    window.location.href = "../index.html";
  });

  renderAuthUI();
  updateSendState();
  loadRecentChats();
  loadMessages();
  startStatusPolling();
});