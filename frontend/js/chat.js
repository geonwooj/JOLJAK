document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnLogin = document.getElementById("btnLogin");
  const chatWrap = document.getElementById("chatWrap");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");

  newChatBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    localStorage.removeItem("chatId");
    window.location.href = "../index.html";
  });

  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  btnMenu?.addEventListener("click", () => app.classList.toggle("is-collapsed"));

  const urlParams = new URLSearchParams(window.location.search);
  const chatId = urlParams.get("chatId");

  function updateSendState() {
    const hasText = input.value.trim().length > 0;
    btnSend.disabled = !hasText;
  }

  input.addEventListener("input", updateSendState);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!btnSend.disabled) btnSend.click();
    }
  });

  function setLoggedOutUI() {
    if (!btnLogin) return;

    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" stroke="currentColor" stroke-width="1.8" />
        <path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      로그인 하세요
    `;

    btnLogin.onclick = () => {
      window.location.href = "./login.html";
    };
  }

  function setLoggedInUI(name) {
    if (!btnLogin) return;

    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" stroke="currentColor" stroke-width="1.8" />
        <path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      ${name}님 환영합니다.
    `;

    btnLogin.onclick = () => {
      window.location.href = "./profile.html";
    };
  }

  async function bootstrapAuth() {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoggedOutUI();
      renderEmptyHint();
      return null;
    }

    try {
      const res = await fetch(`${API_BASE}/api/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        localStorage.removeItem("token");
        localStorage.removeItem("userName");
        setLoggedOutUI();
        renderEmptyHint();
        return null;
      }

      const me = await res.json();
      const name = me?.name || "사용자";
      localStorage.setItem("userName", name);
      setLoggedInUI(name);

      return token;
    } catch (e) {
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      setLoggedOutUI();
      renderEmptyHint();
      return null;
    }
  }

  function renderEmptyHint() {
    if (!chatWrap) return;
    chatWrap.innerHTML = `
      <div class="msg msg--a">
        <div class="msg__avatar msg__avatar--a" aria-hidden="true">A</div>
        <div class="msg__bubble msg__bubble--a">
          <div class="msg__text">index.html에서 질문을 입력하고 전송하면 이곳에 대화가 표시됩니다.</div>
        </div>
      </div>
    `;
  }

  function renderMessages(messages) {
    if (!chatWrap) return;
    chatWrap.innerHTML = "";

    if (!Array.isArray(messages) || messages.length === 0) {
      renderEmptyHint();
      return;
    }

    messages.forEach((m) => {
      if (m.role === "USER") {
        appendUserMessage(m.content);
      } else {
        appendAiMessage(m.content);
      }
    });

    scrollToBottom();
  }

  function appendUserMessage(text) {
    const q = document.createElement("div");
    q.className = "msg msg--q";
    q.innerHTML = `
      <div class="msg__avatar msg__avatar--q" aria-hidden="true">Q</div>
      <div class="msg__bubble"><div class="msg__title"></div></div>
    `;
    q.querySelector(".msg__title").textContent = text;
    chatWrap.appendChild(q);
  }

  function appendAiMessage(text) {
    const a = document.createElement("div");
    a.className = "msg msg--a";
    a.innerHTML = `
      <div class="msg__avatar msg__avatar--a" aria-hidden="true">A</div>
      <div class="msg__bubble msg__bubble--a">
        <div class="msg__text"></div>
      </div>
    `;
    a.querySelector(".msg__text").textContent = text;
    chatWrap.appendChild(a);
  }

  function scrollToBottom() {
    const container = chatWrap?.parentElement;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }

  async function loadMessages(token) {
    if (!chatId) {
      renderEmptyHint();
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem("token");
          localStorage.removeItem("userName");
          window.location.href = "./login.html";
          return;
        }
        renderEmptyHint();
        return;
      }

      const messages = await res.json();
      renderMessages(messages);
    } catch (e) {
      renderEmptyHint();
    }
  }

  async function loadRecentChats(token) {
    if (!myChatList) return;

    try {
      const res = await fetch(`${API_BASE}/api/chats/recent`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        myChatList.innerHTML =
          '<div class="side-item" style="opacity:.6; cursor:default;">채팅 없음</div>';
        return;
      }

      const rooms = await res.json();
      if (!Array.isArray(rooms) || rooms.length === 0) {
        myChatList.innerHTML =
          '<div class="side-item" style="opacity:.6; cursor:default;">채팅 없음</div>';
        return;
      }

      myChatList.innerHTML = rooms
        .map((r) => {
          const active = String(r.id) === String(chatId) ? "is-active" : "";
          return `
            <a class="side-item ${active}" href="./chat.html?chatId=${r.id}">
              <span class="side-item__icon">🗨️</span>
              <span class="side-item__text">${escapeHtml(r.title)}</span>
            </a>
          `;
        })
        .join("");
    } catch (e) {
      myChatList.innerHTML =
        '<div class="side-item" style="opacity:.6; cursor:default;">불러오기 실패</div>';
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  btnSend.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;

    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "./login.html";
      return;
    }

    if (!chatId) {
      // chatId가 없으면 새 채팅을 start로 만들고 현재 페이지를 그 chatId로 이동
      try {
        const res = await fetch(`${API_BASE}/api/chats/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message: text }),
        });

        if (!res.ok) {
          alert("채팅 저장 실패");
          return;
        }

        const data = await res.json();
        window.location.href = `./chat.html?chatId=${data.chatId}`;
        return;
      } catch (e) {
        alert("서버 연결 실패");
        return;
      }
    }

    try {
      const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem("token");
          localStorage.removeItem("userName");
          window.location.href = "./login.html";
          return;
        }
        const err = await res.text();
        alert("전송 실패: " + err);
        return;
      }

      const messages = await res.json();
      input.value = "";
      updateSendState();

      // 전체 다시 렌더 (가장 단순/안전)
      renderMessages(messages);
      await loadRecentChats(token);
    } catch (e) {
      alert("서버 연결 실패");
    }
  });

  (async () => {
    const token = await bootstrapAuth();
    updateSendState();

    if (token) {
      await loadRecentChats(token);
      await loadMessages(token);
    }
  })();

});
