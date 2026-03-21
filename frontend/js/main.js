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
  btnMenu?.addEventListener("click", () =>
    app.classList.toggle("is-collapsed"),
  );

  function getToken() {
    return localStorage.getItem("token") || "";
  }

  // ✅ 토큰이 "있다"가 아니라, 서버에서 200으로 확인됐을 때만 로그인으로 간주
  let authConfirmed = false;

  function renderAuthUI() {
    if (!btnLogin) return;

    const userName = localStorage.getItem("userName");

    if (authConfirmed && userName) {
      btnLogin.style.display = "inline-flex";
      btnLogin.innerHTML = `${userName}님, 환영합니다.`;
      btnLogin.onclick = () => {
        window.location.href = "./pages/profile.html";
      };
    } else {
      btnLogin.style.display = "inline-flex";
      btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
          stroke="currentColor" stroke-width="1.8"/>
        <path d="M4 20a8 8 0 0 1 16 0"
          stroke="currentColor" stroke-width="1.8"
          stroke-linecap="round"/>
      </svg>
      로그인 하세요
    `;
      btnLogin.onclick = () => {
        window.location.href = "./pages/login.html";
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

  // ====== 채팅 목록 UI: 렌더 + 삭제 메뉴 ======

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
    const chatId = room.chatId ?? room.id;
    const title = room.title ?? "새 채팅";

    const wrapper = document.createElement("div");
    wrapper.className = "chat-item";
    wrapper.dataset.chatId = String(chatId);

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

      await deleteChatRoom(chatId);
      await loadRecentChats();
    });

    return wrapper;
  }

  async function deleteChatRoom(chatId) {
    try {
      const res = await fetch(
        `${API_BASE}/api/chats/${encodeURIComponent(chatId)}`,
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

    // ✅ 토큰 없으면: 로그인 미확인 상태, 버튼 보여주고 종료
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

      // ✅ 401이면 토큰 만료/무효 → 토큰 삭제 + 로그인 버튼 유지
      if (res.status === 401) {
        localStorage.removeItem("token");
        authConfirmed = false;
        renderAuthUI();
        return;
      }

      if (!res.ok) {
        // 다른 에러면 로그인 확인 실패로 처리(버튼 보이게 유지)
        authConfirmed = false;
        renderAuthUI();
        return;
      }

      // ✅ 200 OK면 로그인 확인 완료 → 버튼 숨김
      authConfirmed = true;
      renderAuthUI();

      const rooms = await res.json();
      rooms.forEach((room) => myChatList.appendChild(createChatItem(room)));
    } catch (err) {
      console.error(err);
      // 네트워크 에러도 로그인 확인 실패로 처리
      authConfirmed = false;
      renderAuthUI();
    }
  }

  // ====== 새 채팅 버튼 ======
  newChatBtn?.addEventListener("click", () => {
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

    // 토큰 만료면 처리
    if (res.status === 401) {
      localStorage.removeItem("token");
      authConfirmed = false;
      renderAuthUI();
      throw new Error("로그인이 만료되었습니다. 다시 로그인해주세요.");
    }

    if (!res.ok) throw new Error(dataOrText);

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
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    btnSend.disabled = true;

    try {
      const chatId = await startChat(msg);
      window.location.href = `./pages/chat.html?chatId=${encodeURIComponent(chatId)}`;
    } catch (err) {
      console.error(err);
      await CustomModal.alert("채팅 시작 실패: " + (err?.message || err));
      updateSendState();
      renderAuthUI();
    }
  }

  btnSend?.addEventListener("click", onSend);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSend();
    }
  });

  // ✅ 초기 로드
  renderAuthUI(); // 일단 보여주고
  loadRecentChats(); // 서버 확인 후 숨길지 결정
});
