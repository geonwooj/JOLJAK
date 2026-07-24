document.addEventListener("DOMContentLoaded", async () => {
  const $ = (id) => document.getElementById(id);
  const goLogin = async (message) => {
    ApiClient.clearSession();
    if (message) await CustomModal.alert(message);
    location.href = "./login.html";
  };

  $("btnBack")?.addEventListener("click", () => history.back());
  if (!ApiClient.token()) return goLogin("로그인이 필요합니다.");

  const loadProfile = async () => {
    try {
      const data = await ApiClient.get("/api/users/me");
      $("userName").textContent = data.name || "-";
      $("userEmail").textContent = data.email || "-";
      const dt = data.createdAt ? new Date(data.createdAt) : null;
      $("createdAt").textContent = dt && !isNaN(dt) ? dt.toLocaleDateString("ko-KR") : "-";
    } catch (e) {
      await goLogin(e.message === "Unauthorized" ? "세션이 만료되었습니다. 다시 로그인해주세요." : e.message);
    }
  };

  await loadProfile();

  $("btnEditProfile")?.addEventListener("click", async () => {
    const current = $("userName").textContent;
    const name = prompt("변경할 이름을 입력해주세요.", current);
    if (name === null) return;
    try {
      const data = await ApiClient.patch("/api/users/me", { name });
      localStorage.setItem("userName", data.name);
      $("userName").textContent = data.name;
      await CustomModal.alert("프로필이 변경되었습니다.");
    } catch (e) { await CustomModal.alert(e.message); }
  });

  $("btnChangePassword")?.addEventListener("click", async () => {
    const currentPassword = prompt("현재 비밀번호를 입력해주세요.");
    if (currentPassword === null) return;
    const newPassword = prompt("새 비밀번호를 입력해주세요.\n8자 이상, 영문·숫자·특수문자 포함");
    if (newPassword === null) return;
    const confirmPassword = prompt("새 비밀번호를 한 번 더 입력해주세요.");
    if (confirmPassword === null) return;
    if (newPassword !== confirmPassword) return CustomModal.alert("새 비밀번호가 일치하지 않습니다.");
    try {
      await ApiClient.patch("/api/users/me/password", { currentPassword, newPassword });
      await CustomModal.alert("비밀번호가 변경되었습니다.");
    } catch (e) { await CustomModal.alert(e.message); }
  });

  $("btnLogout")?.addEventListener("click", async (e) => {
    e.preventDefault();
    if (!(await CustomModal.confirm("정말 로그아웃 하시겠습니까?"))) return;
    ApiClient.clearSession();
    await CustomModal.alert("로그아웃 되었습니다.");
    location.href = "../index.html";
  });

  $("btnDeleteAccount")?.addEventListener("click", async () => {
    if (!(await CustomModal.confirm("정말 계정을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."))) return;
    try {
      await ApiClient.delete("/api/users/me");
      ApiClient.clearSession();
      await CustomModal.alert("계정이 삭제되었습니다.");
      location.href = "../index.html";
    } catch (e) { await CustomModal.alert(e.message); }
  });
});
