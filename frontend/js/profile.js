document.addEventListener("DOMContentLoaded", async () => {
  const btnBack = document.getElementById("btnBack");
  const btnLogout = document.getElementById("btnLogout");

  btnBack?.addEventListener("click", () => history.back());

  const token = localStorage.getItem("token");
  if (!token) {
    await CustomModal.alert("로그인이 필요합니다.");
    window.location.href = "./login.html";
    return;
  }

  try {
    const res = await fetch("http://127.0.0.1:8080/api/users/me", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      // ✅ 서버 재시작으로 토큰 무효화되면 여기로 옴(401)
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      alert("세션이 만료되었습니다. 다시 로그인해주세요.");
      window.location.href = "./login.html";
      return;
    }

    const data = await res.json();

    document.getElementById("userName").textContent = data?.name ?? "-";
    document.getElementById("userEmail").textContent = data?.email ?? "-";

    // 가입일 표시
    const createdAtEl = document.getElementById("createdAt");
    if (createdAtEl) {
      if (data?.createdAt) {
        const dt = new Date(data.createdAt);
        createdAtEl.textContent = isNaN(dt.getTime())
          ? String(data.createdAt)
          : dt.toLocaleDateString("ko-KR");
      } else {
        createdAtEl.textContent = "-";
      }
    }
  } catch (err) {
    console.error(err);
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
    alert("서버 연결이 불안정합니다. 다시 로그인해주세요.");
    window.location.href = "./login.html";
  }

  // 로그아웃
  btnLogout?.addEventListener("click", (e) => {
    e.preventDefault();
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
    alert("로그아웃 되었습니다.");
    window.location.href = "../index.html";
  });
});
