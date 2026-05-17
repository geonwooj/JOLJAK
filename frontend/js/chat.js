document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const chatWrap = document.getElementById("chatWrap");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");
  const aiStatus = document.getElementById("aiStatus");
  const aiStatusText = document.getElementById("aiStatusText");

  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  const btnLogin = document.getElementById("btnLogin");
  const btnFile = document.getElementById("btnFile");
  const fileInput = document.getElementById("fileInput");
  const dragOverlay = document.getElementById("dragOverlay");

  btnMenu?.addEventListener("click", () =>
    app.classList.toggle("is-collapsed"),
  );

  const urlParams = new URLSearchParams(window.location.search);
  const chatId = urlParams.get("chatId");

  function getToken() {
    return localStorage.getItem("token") || "";
  }

  let authConfirmed = false;

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
        <path
          d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
          stroke="currentColor"
          stroke-width="1.8"
        />
        <path
          d="M4 20a8 8 0 0 1 16 0"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
        />
      </svg>
      로그인 하세요
    `;
      btnLogin.onclick = () => {
        window.location.href = "./login.html";
      };
    }
  }

  function authHeaders() {
    const token = getToken();
    if (!token) return { "Content-Type": "application/json" };
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  function updateSendState() {
    const hasText = (input?.value || "").trim().length > 0;
    if (btnSend) btnSend.disabled = !hasText;
  }

  input?.addEventListener("input", updateSendState);
  updateSendState();

  // ====== 채팅 목록 UI: 렌더 + 삭제 메뉴(메인과 동일) ======

  function closeAllDropdowns() {
    document
      .querySelectorAll(".chat-item.is-open")
      .forEach((el) => el.classList.remove("is-open"));
  }

  document.addEventListener("click", (e) => {
    const clickedInside = e.target.closest(".chat-item");
    if (!clickedInside) closeAllDropdowns();
  });

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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

    const btnMore = wrapper.querySelector(".chat-item__more");
    btnMore.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isOpen = wrapper.classList.contains("is-open");
      closeAllDropdowns();
      if (!isOpen) wrapper.classList.add("is-open");
    });

    const btnDelete = wrapper.querySelector('[data-action="delete"]');
    btnDelete.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeAllDropdowns();

      const ok = await CustomModal.confirm("이 채팅을 삭제할까요?");
      if (!ok) return;

      await deleteChatRoom(id);
      await loadRecentChats();

      // 현재 보고 있는 채팅을 삭제한 경우 → index로
      if (String(id) === String(chatId)) {
        window.location.href = "../index.html";
      }
    });

    return wrapper;
  }

  async function deleteChatRoom(id) {
    try {
      const res = await fetch(
        `${API_BASE}/api/chats/${encodeURIComponent(id)}`,
        {
          method: "DELETE",
          headers: authHeaders(),
        },
      );
      const text = await res.text();
      if (!res.ok) await CustomModal.alert("삭제 실패: " + text);
    } catch (err) {
      console.error(err);
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
        headers: authHeaders(),
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
      console.error(err);
      authConfirmed = false;
      renderAuthUI();
    }
  }

  // ====== chat.html: 메시지 렌더 ======

  async function typeText(element, text, speed = 20) {
    element.textContent = "";

    for (let i = 0; i < text.length; i++) {
      element.textContent += text[i];
      await new Promise((resolve) => setTimeout(resolve, speed));
    }
  }

  function formatAiAnswer(text) {
    let formatted = String(text ?? "");

    // 구분선 제거
    formatted = formatted.replaceAll("----------------------------------------------------------------", "");

    // 혹시 이전 포맷팅 때문에 깨진 단어 복구
    formatted = formatted.replace(/([가-힣])\s*\n+\s*다\./g, "$1다.");
    formatted = formatted.replace(/([가-힣])\s*\n+\s*법\./g, "$1법.");
    formatted = formatted.replace(/([가-힣])\s*\n+\s*템\./g, "$1템.");

    // 쉼표 뒤 줄바꿈은 다시 붙임
    formatted = formatted.replace(/,\s*\n+\s*/g, ", ");

    // 괄호형 항목 "(가)", "(나)", "(다)"는 문장 안 항목으로 처리
    formatted = formatted.replace(/\s*\n+\s*(\([가-하]\))/g, " $1");
    formatted = formatted.replace(/(\([가-하]\))\s*\n+\s*/g, "$1 ");

    // 큰 섹션 제목 줄바꿈
    formatted = formatted.replace(/\[사용자의 아이디어 요약\]/g, "\n\n[사용자의 아이디어 요약]\n");
    formatted = formatted.replace(/\[유사 특허 목록\]/g, "\n\n[유사 특허 목록]\n");
    formatted = formatted.replace(/\[발명의 명칭\]/g, "\n\n[발명의 명칭]\n");
    formatted = formatted.replace(/\[특허청구범위\]/g, "\n\n[특허청구범위]\n");
    formatted = formatted.replace(/\[발명의 설명\]/g, "\n\n[발명의 설명]\n");

    // "방법. 청구항 2", "시스템. 청구항 9"처럼 다음 청구항 제목이 앞 문장에 붙어 나온 경우만 분리
    // 단, "청구항 1에 있어서"는 여기서 제목 처리하지 않음
    formatted = formatted.replace(
      /(방법\.|시스템\.|장치\.|매체\.|것\.|단계\.|수단\.)\s+청구항\s*(\d+)(?=\s+(?!에 있어서)[가-힣A-Za-z])/g,
      "$1\n\n청구항 $2\n"
    );

    // 이미 줄 시작에 단독으로 있는 "청구항 1", "청구항 2"만 제목으로 정리
    formatted = formatted.replace(
      /(^|\n)\s*청구항\s*(\d+)\s*$/gm,
      "\n\n청구항 $2"
    );

    // 혹시 "청구항 1"과 "에 있어서"가 줄바꿈으로 깨진 경우 복구
    formatted = formatted.replace(
      /\n+\s*청구항\s*(\d+)\s*\n+\s*에 있어서/g,
      "\n\n청구항 $1에 있어서"
    );

    // 발명의 설명 번호별 줄바꿈
    formatted = formatted.replace(
      /(\d+)\.\s*(기술분야|배경기술|발명의 내용|발명의 실시를 위한 구체적인 내용|산업상 이용가능성)/g,
      "\n\n$1. $2\n"
    );

    // 가. 나. 다. 라. 소제목 처리
    // 문장 끝의 "다."는 건드리지 않도록, 정해진 소제목만 처리
    formatted = formatted.replace(
      /(^|\n)\s*([가-하])\.\s*(해결하고자 하는 과제|과제의 해결 수단|발명의 효과|전체 처리 흐름|Dynamic Weights Algorithm 적용|RAG 기반 컨텍스트 및 few-shot 예시 구성의 구체화|시스템 구성의 예)/g,
      "\n\n$2. $3"
    );

    // 유사 특허 목록 bullet 줄바꿈
    formatted = formatted.replace(/\s-\s/g, "\n- ");

    // 번호 목록 줄바꿈: (1), (2), (3)
    formatted = formatted.replace(/\s\((\d+)\)\s/g, "\n($1) ");

    // 너무 많은 빈 줄 정리
    formatted = formatted.replace(/\n{3,}/g, "\n\n").trim();

    return formatted;
  }

  function renderFormattedAiAnswer(container, text) {
    const formatted = formatAiAnswer(text);
    const lines = formatted.split("\n");

    lines.forEach((line) => {
      const trimmed = line.trim();

      if (!trimmed) {
        container.appendChild(document.createElement("br"));
        return;
      }

      const p = document.createElement("p");

      if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
        p.className = "ai-section-title";
        p.textContent = trimmed.replace("[", "").replace("]", "");

      } else if (/^청구항\s*\d+\s*$/.test(trimmed)) {
        // 진짜 제목용 "청구항 1", "청구항 2"만 크게 표시
        p.className = "ai-claim-title";
        p.textContent = trimmed;

      } else if (/^청구항\s*\d+\s*에 있어서/.test(trimmed)) {
        // "청구항 1에 있어서"는 제목이 아니라 본문
        p.className = "ai-paragraph";
        p.textContent = trimmed;

      } else if (/^\d+\.\s*/.test(trimmed)) {
        p.className = "ai-sub-title";
        p.textContent = trimmed;

      } else if (/^[가-하]\.\s*/.test(trimmed)) {
        p.className = "ai-sub-title";
        p.textContent = trimmed;

      } else if (trimmed.startsWith("-")) {
        p.className = "ai-list-item";
        p.textContent = trimmed;

      } else {
        p.className = "ai-paragraph";
        p.textContent = trimmed;
      }

      container.appendChild(p);
    });
  }

  function renderMessage(role, text) {
    if (!chatWrap) return;

    const isUser = role === "USER";

    const item = document.createElement("div");
    item.className = isUser ? "msg msg--user" : "msg";

    item.innerHTML = `
    <div class="msg__avatar ${isUser ? "msg__avatar--q" : "msg__avatar--a"}">
      ${isUser ? "Q" : "A"}
    </div>
    <div class="msg__bubble ${!isUser ? "msg__bubble--a" : ""}">
      <div class="msg__text"></div>
    </div>
  `;

    chatWrap.appendChild(item);

    const textEl = item.querySelector(".msg__text");

    if (isUser) {
      textEl.textContent = text;
    } else {
      renderFormattedAiAnswer(textEl, text);
    }

    // 마지막 메시지로 스크롤
    item.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }

  function clearMessages() {
    if (chatWrap) chatWrap.innerHTML = "";
  }

  async function loadMessages() {
    if (!chatId) return;

    try {
      const res = await fetch(
        `${API_BASE}/api/chats/${encodeURIComponent(chatId)}/messages`,
        {
          method: "GET",
          headers: authHeaders(),
        },
      );

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
      messages.forEach((m) => {
        // m: { role, content } 또는 { role, message } 형태 가능
        const role = m.role;
        const content = m.content ?? m.message ?? "";
        renderMessage(role, content);
      });
      setTimeout(() => {
        const last = chatWrap.lastElementChild;
        if (last) {
          last.scrollIntoView({ behavior: "auto", block: "end" });
        }
      }, 0);
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 연결 실패");
    }
  }

  let statusTimer = null;

  function showAiStatus(message) {
    if (!aiStatus || !aiStatusText) return;

    aiStatus.hidden = false;
    aiStatusText.textContent = message || "AI가 답변을 생성 중입니다.";
  }

  function hideAiStatus() {
    if (!aiStatus) return;

    aiStatus.hidden = true;
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

      if (status.running) {
        showAiStatus(status.message);
        return true;
      }

      if (status.code === "DONE") {
        showAiStatus("AI 답변 생성이 완료되었습니다.");

        setTimeout(async () => {
          hideAiStatus();
          await loadMessages();
          await loadRecentChats();
        }, 700);

        return false;
      }

      if (status.code === "ERROR") {
        showAiStatus(status.message || "AI 답변 생성 중 오류가 발생했습니다.");

        setTimeout(async () => {
          hideAiStatus();
          await loadMessages();
        }, 1000);

        return false;
      }

      hideAiStatus();
      return false;
    } catch (err) {
      console.error(err);
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

  // ====== chat.html: 메시지 보내기 (추가 질문) ======

  async function sendMessage() {
    const msg = (input?.value || "").trim();
    if (!msg) return;

    renderMessage("USER", msg);

    input.value = "";
    updateSendState();

    const token = getToken();
    if (!token) {
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    if (!chatId) {
      await CustomModal.alert(
        "채팅방 ID가 없습니다. index에서 새로 시작하세요.",
      );
      return;
    }

    btnSend.disabled = true;

    try {
      const res = await fetch(
        `${API_BASE}/api/chats/${encodeURIComponent(chatId)}/messages`,
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ message: msg }),
        },
      );

      const text = await res.text();
      if (!res.ok) {
        await CustomModal.alert("전송 실패: " + text);
        updateSendState();
        return;
      }

      let messages;
      try {
        messages = JSON.parse(text);
      } catch {
        await CustomModal.alert("전송 응답이 JSON이 아닙니다: " + text);
        updateSendState();
        return;
      }

      clearMessages();

      messages.forEach((m) => {
        const role = m.role;
        const content = m.content ?? m.message ?? "";
        renderMessage(role, content);
      });

      startStatusPolling();

      await loadRecentChats();
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 연결 실패");
      updateSendState();
    }
  }

  btnSend?.addEventListener("click", sendMessage);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  // ====== 새 채팅 버튼 ======
  newChatBtn?.addEventListener("click", () => {
    // 채팅 페이지에서 새 채팅은 index로 보내는게 UX 깔끔
    window.location.href = "../index.html";
  });

  let dragCounter = 0;

  app?.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragCounter++;
    dragOverlay?.classList.add("show");
  });

  app?.addEventListener("dragleave", (e) => {
    dragCounter--;
    if (dragCounter === 0) {
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

    const file = e.dataTransfer.files[0];
    if (!file) return;

    uploadFile(file);
  });
  function renderFileMessage(role, fileName) {
    if (!chatWrap) return;

    const isUser = role === "USER";

    const item = document.createElement("div");
    item.className = isUser ? "msg msg--user" : "msg";

    item.innerHTML = `
    <div class="msg__avatar ${isUser ? "msg__avatar--q" : "msg__avatar--a"}">
      ${isUser ? "Q" : "A"}
    </div>
    <div class="msg__bubble file-bubble">
      📎 ${fileName}
    </div>
  `;

    chatWrap.appendChild(item);

    item.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }

  fileInput?.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const token = getToken();

    if (!token) {
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/files/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const text = await res.text();

      if (!res.ok) {
        await CustomModal.alert("파일 업로드 실패: " + text);
        return;
      }

      // 채팅창에 파일 표시
      renderFileMessage("USER", file.name);
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 연결 실패");
    }

    fileInput.value = "";
  });

  async function uploadFile(file) {
    const token = getToken();

    if (!token) {
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/files/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const text = await res.text();

      if (!res.ok) {
        await CustomModal.alert("파일 업로드 실패: " + text);
        return;
      }

      renderFileMessage("USER", file.name);
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 연결 실패");
    }
  }

  // 초기 실행
  renderAuthUI();
  loadRecentChats();
  loadMessages();
  startStatusPolling();
});
