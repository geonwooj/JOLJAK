document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:8080";

  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const myChatList = document.getElementById("myChatList");
  const newChatBtn = document.getElementById("newChatBtn");
  const btnLogin = document.getElementById("btnLogin");
  const app = document.getElementById("app");
  const btnMenu = document.getElementById("btnMenu");
  const btnFile = document.getElementById("btnFile");
  const fileInput = document.getElementById("fileInput");
  const dragOverlay = document.getElementById("dragOverlay");
  let filePreview = null;

  let authConfirmed = false;
  let selectedFile = null;
  let dragCounter = 0;

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
        window.location.href = "./pages/profile.html";
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
        window.location.href = "./pages/login.html";
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

    preview.querySelector(".file-preview__remove")?.addEventListener("click", () => {
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

    wrapper.querySelector(".chat-item__more").addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isOpen = wrapper.classList.contains("is-open");
      closeAllDropdowns();
      if (!isOpen) wrapper.classList.add("is-open");
    });

    wrapper.querySelector('[data-action="delete"]').addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeAllDropdowns();

      const ok = await CustomModal.confirm("이 채팅을 삭제할까요?");
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
        headers: jsonHeaders(),
      });

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
      console.error(err);
      authConfirmed = false;
      renderAuthUI();
    }
  }

  async function startChat(message, file) {
    let res;

    if (file) {
      const formData = new FormData();
      formData.append("message", message || "");
      formData.append("file", file);

      res = await fetch(`${API_BASE}/api/chats/start`, {
        method: "POST",
        headers: multipartHeaders(),
        body: formData,
      });
    } else {
      res = await fetch(`${API_BASE}/api/chats/start`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({ message }),
      });
    }

    const dataOrText = await res.text();

    if (res.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      authConfirmed = false;
      renderAuthUI();
      throw new Error("로그인이 만료되었습니다. 다시 로그인해주세요.");
    }

    if (!res.ok) throw new Error(dataOrText);

    try {
      return JSON.parse(dataOrText).chatId;
    } catch {
      throw new Error("서버 응답이 JSON이 아닙니다: " + dataOrText);
    }
  }

  async function onSend() {
    const msg = (input?.value || "").trim();
    const file = selectedFile;

    if (!msg && !file) return;

    const token = getToken();
    if (!token) {
      await CustomModal.alert("로그인이 필요합니다.");
      return;
    }

    btnSend.disabled = true;

    try {
      const chatId = await startChat(msg, file);
      selectedFile = null;
      window.location.href = `./pages/chat.html?chatId=${encodeURIComponent(chatId)}&new=1`;
    } catch (err) {
      console.error(err);
      const msg = err?.message === "Failed to fetch"
        ? "백엔드 서버에 연결할 수 없습니다. Spring Boot가 실행 중인지, 주소가 http://127.0.0.1:8080 인지 확인해주세요."
        : (err?.message || err);
      await CustomModal.alert("채팅 시작 실패: " + msg);
      updateSendState();
      renderAuthUI();
    }
  }

  btnMenu?.addEventListener("click", () => app.classList.toggle("is-collapsed"));

  document.addEventListener("click", (e) => {
    const clickedInside = e.target.closest(".chat-item");
    if (!clickedInside) closeAllDropdowns();
  });

  input?.addEventListener("input", updateSendState);
  btnSend?.addEventListener("click", onSend);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSend();
    }
  });

  btnFile?.addEventListener("click", () => fileInput?.click());
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

  app?.addEventListener("dragover", (e) => e.preventDefault());

  app?.addEventListener("drop", async (e) => {
    e.preventDefault();
    dragCounter = 0;
    dragOverlay?.classList.remove("show");

    selectedFile = e.dataTransfer.files?.[0] || null;
    updateSendState();
  });

  newChatBtn?.addEventListener("click", () => input?.focus());

  renderAuthUI();
  updateSendState();
  loadRecentChats();
});
