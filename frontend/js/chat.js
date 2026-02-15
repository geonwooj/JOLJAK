document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const chatWrap = document.getElementById("chatWrap");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");

  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  btnMenu?.addEventListener("click", () =>
    app.classList.toggle("is-collapsed"),
  );

  const urlParams = new URLSearchParams(window.location.search);
  const chatId = urlParams.get("chatId");

  function getToken() {
    return localStorage.getItem("token") || "";
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

      const ok = confirm("이 채팅을 삭제할까요?");
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
      if (!res.ok) alert("삭제 실패: " + text);
    } catch (err) {
      console.error(err);
      alert("서버 연결 실패");
    }
  }

  async function loadRecentChats() {
    if (!myChatList) return;
    myChatList.innerHTML = "";

    const token = getToken();
    if (!token) return;

    try {
      const res = await fetch(`${API_BASE}/api/chats/recent`, {
        method: "GET",
        headers: authHeaders(),
      });
      if (!res.ok) return;

      const rooms = await res.json();
      rooms.forEach((room) => myChatList.appendChild(createChatItem(room)));
    } catch (err) {
      console.error(err);
    }
  }

  // ====== chat.html: 메시지 렌더 ======

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
      <div class="msg__text">${text ?? ""}</div>
    </div>
  `;

    chatWrap.appendChild(item);
    chatWrap.scrollTop = chatWrap.scrollHeight;
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
        alert("메시지 로드 실패: " + text);
        return;
      }

      let messages;
      try {
        messages = JSON.parse(text);
      } catch {
        alert("메시지 응답이 JSON이 아닙니다: " + text);
        return;
      }

      clearMessages();
      messages.forEach((m) => {
        // m: { role, content } 또는 { role, message } 형태 가능
        const role = m.role;
        const content = m.content ?? m.message ?? "";
        renderMessage(role, content);
      });
    } catch (err) {
      console.error(err);
      alert("서버 연결 실패");
    }
  }

  // ====== chat.html: 메시지 보내기 (추가 질문) ======

  async function sendMessage() {
    const msg = (input?.value || "").trim();
    if (!msg) return;

    const token = getToken();
    if (!token) {
      alert("로그인이 필요합니다.");
      return;
    }

    if (!chatId) {
      alert("채팅방 ID가 없습니다. index에서 새로 시작하세요.");
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
        alert("전송 실패: " + text);
        updateSendState();
        return;
      }

      let messages;
      try {
        messages = JSON.parse(text);
      } catch {
        alert("전송 응답이 JSON이 아닙니다: " + text);
        updateSendState();
        return;
      }

      input.value = "";
      updateSendState();

      // 서버에서 전체 메시지를 내려주는 방식이라면 통째로 다시 렌더
      clearMessages();
      messages.forEach((m) => {
        const role = m.role;
        const content = m.content ?? m.message ?? "";
        renderMessage(role, content);
      });

      // 최근 채팅 목록 갱신
      await loadRecentChats();
    } catch (err) {
      console.error(err);
      alert("서버 연결 실패");
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

  // 초기 실행
  loadRecentChats();
  loadMessages();
});
