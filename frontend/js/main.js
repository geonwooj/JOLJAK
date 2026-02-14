document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");

  const btnLogin = document.getElementById("btnLogin");

  btnLogin?.addEventListener("click", () => {
    window.location.href = "./pages/login.html";
  });


  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  btnMenu?.addEventListener("click", () => app.classList.toggle("is-collapsed"));

  function getToken() {
    return localStorage.getItem("token") || "";
  }

  function authHeaders() {
    const token = getToken();
    if (!token) return { "Content-Type": "application/json" };
    return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
  }

  function updateSendState() {
    const hasText = (input?.value || "").trim().length > 0;
    if (btnSend) btnSend.disabled = !hasText;
  }

  input?.addEventListener("input", updateSendState);
  updateSendState();

  // ====== 채팅 목록 UI: 렌더 + 삭제 메뉴 ======

  function closeAllDropdowns() {
    document.querySelectorAll(".chat-item.is-open").forEach((el) => el.classList.remove("is-open"));
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
    // room: { chatId or id, title, updatedAt }
    const chatId = room.chatId ?? room.id;
    const title = room.title ?? "새 채팅";

    const wrapper = document.createElement("div");
    wrapper.className = "chat-item";
    wrapper.dataset.chatId = String(chatId);

    // 기존 사이드바 스타일(.side-item)을 그대로 사용
    wrapper.innerHTML = `
      <a class="side-item" href="./pages/chat.html?chatId=${encodeURIComponent(chatId)}">
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

    // ⋯ 버튼 토글
    const btnMore = wrapper.querySelector(".chat-item__more");
    btnMore.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isOpen = wrapper.classList.contains("is-open");
      closeAllDropdowns();
      if (!isOpen) wrapper.classList.add("is-open");
    });

    // 드롭다운 액션
    const btnDelete = wrapper.querySelector('[data-action="delete"]');
    btnDelete.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      closeAllDropdowns();

      const ok = confirm("이 채팅을 삭제할까요?");
      if (!ok) return;

      await deleteChatRoom(chatId);
      await loadRecentChats();
    });

    return wrapper;
  }

  async function deleteChatRoom(chatId) {
    try {
      const res = await fetch(`${API_BASE}/api/chats/${encodeURIComponent(chatId)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });

      const text = await res.text();
      if (!res.ok) {
        alert("삭제 실패: " + text);
      }
    } catch (err) {
      console.error(err);
      alert("서버 연결 실패");
    }
  }

  async function loadRecentChats() {
    if (!myChatList) return;
    myChatList.innerHTML = "";

    const token = getToken();
    if (!token) return; // 로그인 전이면 목록 비워둠

    try {
      const res = await fetch(`${API_BASE}/api/chats/recent`, {
        method: "GET",
        headers: authHeaders(),
      });

      if (!res.ok) {
        // 토큰 만료 등
        return;
      }

      const rooms = await res.json(); // 배열
      rooms.forEach((room) => {
        myChatList.appendChild(createChatItem(room));
      });
    } catch (err) {
      console.error(err);
    }
  }

  // ====== 새 채팅 버튼 ======
  newChatBtn?.addEventListener("click", async () => {
    // 그냥 새 대화 시작(입력 없이) 원하는 경우가 있을 수 있으니
    // 여기서는 index에서 메시지 먼저 입력하게 두고, 클릭 시 입력창 포커스만
    input?.focus();
  });

  // ====== index에서 첫 질문 보내면 새 채팅 생성 후 chat.html로 이동 ======

  async function startChat(firstMessage) {
    const res = await fetch(`${API_BASE}/api/chats/start`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ message: firstMessage }),
    });

    const dataOrText = await res.text();
    if (!res.ok) throw new Error(dataOrText);

    // text가 JSON일 것
    let data;
    try {
      data = JSON.parse(dataOrText);
    } catch {
      throw new Error("서버 응답이 JSON이 아닙니다: " + dataOrText);
    }

    return data.chatId;
  }

  async function onSend() {
    const msg = (input?.value || "").trim();
    if (!msg) return;

    const token = getToken();
    if (!token) {
      alert("로그인이 필요합니다.");
      return;
    }

    btnSend.disabled = true;

    try {
      const chatId = await startChat(msg);
      // chat.html로 이동하면서 chatId 전달
      window.location.href = `./pages/chat.html?chatId=${encodeURIComponent(chatId)}`;
    } catch (err) {
      console.error(err);
      alert("채팅 시작 실패: " + (err?.message || err));
      updateSendState();
    }
  }

  btnSend?.addEventListener("click", onSend);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSend();
    }
  });

  // 초기 로드
  loadRecentChats();
});
