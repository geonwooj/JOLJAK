const API_BASE = "http://15.164.30.127:8080";

document.addEventListener("DOMContentLoaded", async () => {
  const btnBack = document.getElementById("btnBack");
  const btnLogout = document.getElementById("btnLogout");
  const btnChangePassword = document.getElementById("btnChangePassword");
  const passwordCard = document.getElementById("passwordChangeCard");
  const btnCancelPassword = document.getElementById("btnCancelPassword");
  const btnSavePassword = document.getElementById("btnSavePassword");

  btnBack?.addEventListener("click", () => history.back());

  const clearLogin = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
  };

  const token = localStorage.getItem("token");
  if (!token) {
    await CustomModal.alert("로그인이 필요합니다.");
    window.location.href = "./login.html";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      clearLogin();
      await CustomModal.alert("세션이 만료되었습니다. 다시 로그인해주세요.");
      window.location.href = "./login.html";
      return;
    }

    const data = await res.json();
    document.getElementById("userName").textContent = data?.name ?? "-";
    document.getElementById("userEmail").textContent = data?.email ?? "-";

    const createdAtEl = document.getElementById("createdAt");
    if (createdAtEl) {
      const dt = data?.createdAt ? new Date(data.createdAt) : null;
      createdAtEl.textContent = dt && !isNaN(dt.getTime())
        ? dt.toLocaleDateString("ko-KR")
        : data?.createdAt || "-";
    }
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결이 불안정합니다.");
  }

  btnChangePassword?.addEventListener("click", () => {
    passwordCard.hidden = false;
    document.getElementById("currentPassword")?.focus();
  });

  btnCancelPassword?.addEventListener("click", () => {
    passwordCard.hidden = true;
    ["currentPassword", "newPassword", "newPasswordConfirm"].forEach((id) => {
      const input = document.getElementById(id);
      if (input) input.value = "";
    });
  });

  btnSavePassword?.addEventListener("click", async () => {
    const currentPassword = document.getElementById("currentPassword").value;
    const newPassword = document.getElementById("newPassword").value;
    const confirm = document.getElementById("newPasswordConfirm").value;

    if (!currentPassword || !newPassword || !confirm) {
      await CustomModal.alert("비밀번호를 모두 입력해주세요.");
      return;
    }
    if (newPassword !== confirm) {
      await CustomModal.alert("새 비밀번호가 서로 일치하지 않습니다.");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/users/me/password`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({ currentPassword, newPassword }),
      });
      const message = await res.text();
      if (!res.ok) {
        await CustomModal.alert(message || "비밀번호 변경에 실패했습니다.");
        return;
      }
      await CustomModal.alert("비밀번호가 변경되었습니다. 다시 로그인해주세요.");
      clearLogin();
      window.location.href = "./login.html";
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 연결 중 오류가 발생했습니다.");
    }
  });

  btnLogout?.addEventListener("click", async (e) => {
    e.preventDefault();
    const ok = await CustomModal.confirm("정말 로그아웃 하시겠습니까?");
    if (!ok) return;

    // 서버 응답 여부와 상관없이 로컬 토큰을 반드시 삭제한다.
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
    } catch (err) {
      console.warn("로그아웃 서버 요청 실패:", err);
    } finally {
      clearLogin();
    }

    await CustomModal.alert("로그아웃 되었습니다.");
    window.location.href = "../index.html";
  });

  document.getElementById("btnDeleteAccount")?.addEventListener("click", async () => {
    const ok = await CustomModal.confirm("정말 계정을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.");
    if (!ok) return;

    try {
      const res = await fetch(`${API_BASE}/api/users/me`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      const message = await res.text();
      if (!res.ok) {
        await CustomModal.alert(message || "계정 삭제에 실패했습니다.");
        return;
      }
      clearLogin();
      await CustomModal.alert("계정이 삭제되었습니다.");
      window.location.href = "../index.html";
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 오류가 발생했습니다.");
    }
  });
});
