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
      await CustomModal.alert("세션이 만료되었습니다. 다시 로그인해주세요.");
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
    await CustomModal.alert("서버 연결이 불안정합니다. 다시 로그인해주세요.");
    window.location.href = "./login.html";
  }

  // 로그아웃
  btnLogout?.addEventListener("click", async (e) => {
    e.preventDefault();

    const ok = await CustomModal.confirm("정말 로그아웃 하시겠습니까?");

    if (!ok) return;

    localStorage.removeItem("token");
    localStorage.removeItem("userName");

    await CustomModal.alert("로그아웃 되었습니다.");
    window.location.href = "../index.html";
  });

  const btnDelete = document.getElementById("btnDeleteAccount");

  btnDelete?.addEventListener("click", async () => {
    const ok = await CustomModal.confirm(
      "정말 계정을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."
    );

    if (!ok) return;

    const token = localStorage.getItem("token");

    try {
      const res = await fetch("http://127.0.0.1:8080/api/users/me", {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const message = await res.text();

      console.log("삭제 status =", res.status);
      console.log("삭제 response =", message);

      if (!res.ok) {
        await CustomModal.alert(message || "계정 삭제에 실패했습니다.");
        return;
      }

      localStorage.removeItem("token");
      localStorage.removeItem("userName");

      await CustomModal.alert("계정이 삭제되었습니다.");
      window.location.href = "../index.html";
    } catch (err) {
      console.error("삭제 요청 실패:", err);
      await CustomModal.alert("서버 오류가 발생했습니다.");
    }
  });
});
