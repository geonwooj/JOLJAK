document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnLogin = document.getElementById("btnLogin");
  const myChatList = document.getElementById("myChatList");

  // 메시지 보내기 활성화/비활성
  function updateSendState() {
    const hasText = input?.value?.trim().length > 0;
    if (btnSend) btnSend.disabled = !hasText;
  }

  input?.addEventListener("input", updateSendState);

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (btnSend && !btnSend.disabled) btnSend.click();
    }
  });

  // ✅ index.html에서 첫 질문을 보내면
  // 1) DB에 저장
  // 2) chat.html?chatId=... 로 이동
  btnSend?.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;

    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "./pages/login.html";
      return;
    }

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
        // 토큰 만료/서버오류 등
        if (res.status === 401) {
          localStorage.removeItem("token");
          localStorage.removeItem("userName");
          window.location.href = "./pages/login.html";
          return;
        }
        const err = await res.text();
        alert("채팅 저장 실패: " + err);
        return;
      }

      const data = await res.json();
      const chatId = data.chatId;
      input.value = "";
      updateSendState();

      // 사이드바 리스트 갱신
      await loadRecentChats();

      // chat 화면으로 이동
      window.location.href = `./pages/chat.html?chatId=${chatId}`;
    } catch (e) {
      alert("서버 연결 실패");
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
      window.location.href = "./pages/login.html";
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
      window.location.href = "./pages/profile.html";
    };
  }

  // ✅ 앱 시작 시 토큰 검증: token이 있어도 /me 성공해야 "로그인"
  async function bootstrapAuth() {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoggedOutUI();
      return;
    }

    try {
      const res = await fetch("http://127.0.0.1:8080/api/users/me", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        localStorage.removeItem("token");
        localStorage.removeItem("userName");
        setLoggedOutUI();
        return;
      }

      const me = await res.json();
      const name = me?.name || "사용자";

      localStorage.setItem("userName", name);
      setLoggedInUI(name);

      // ✅ 로그인 된 경우에만 내 채팅 목록 로드
      await loadRecentChats();
    } catch (e) {
      // 서버 꺼짐/네트워크 오류 포함 → 토큰 믿지 말고 로그아웃 처리
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      setLoggedOutUI();
    }
  }

  async function loadRecentChats() {
    if (!myChatList) return;
    const token = localStorage.getItem("token");
    if (!token) {
      myChatList.innerHTML =
        '<div class="side-item" style="opacity:.6; cursor:default;">로그인 후 확인</div>';
      return;
    }

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
        .map(
          (r) => `
            <a class="side-item" href="./pages/chat.html?chatId=${r.id}">
              <span class="side-item__icon">🗨️</span>
              <span class="side-item__text">${escapeHtml(r.title)}</span>
            </a>
          `
        )
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

  bootstrapAuth();

  // 사이드바 토글
  const app = document.querySelector(".app");
  const btnMenu = document.getElementById("btnMenu");

  btnMenu?.addEventListener("click", () => {
    app.classList.toggle("is-collapsed");
  });
});
