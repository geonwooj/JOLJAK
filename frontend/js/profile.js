document.addEventListener("DOMContentLoaded", () => {
  const btnBack = document.getElementById("btnBack");
  const btnLogout = document.getElementById("btnLogout");
  const editProfileBtn = document.querySelector(".profile-card .btn");
  const emailChangeBtn = document.querySelectorAll(".link-btn")[0];
  const passwordChangeBtn = document.querySelectorAll(".link-btn")[1];
  const deleteAccountBtn = document.querySelector(".btn-danger");

  // 뒤로 가기
  btnBack.addEventListener("click", () => {
    history.back(); // 이전 페이지로 이동
  });

  // 프로필 편집
  editProfileBtn.addEventListener("click", () => {
    // 예: profile_edit.html 페이지로 이동
    window.location.href = "/frontend/profile_edit.html";
  });

  // 이메일 변경
  emailChangeBtn.addEventListener("click", () => {
    window.location.href = "/frontend/email_change.html";
  });

  // 비밀번호 변경
  passwordChangeBtn.addEventListener("click", () => {
    window.location.href = "/frontend/password_change.html";
  });

  // 로그아웃
  btnLogout.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/logout", { method: "POST" });
      if (res.ok) {
        await CustomModal.alert("로그아웃 되었습니다.");
        window.location.href = "/frontend/login.html";
      } else {
        await CustomModal.alert("로그아웃에 실패했습니다.");
      }
    } catch (err) {
      console.error(err);
      await CustomModal.alert("서버 오류가 발생했습니다.");
    }
  });

  // 계정 삭제
  deleteAccountBtn.addEventListener("click", async () => {
    if (
      await CustomModal.alert(
        "정말 계정을 삭제하시겠습니까? 모든 데이터가 삭제됩니다."
      )
    ) {
      try {
        const res = await fetch("/api/users/delete", { method: "DELETE" });
        if (res.ok) {
          await CustomModal.alert("계정이 삭제되었습니다.");
          window.location.href = "/frontend/login.html";
        } else {
          await CustomModal.alert("계정 삭제에 실패했습니다.");
        }
      } catch (err) {
        console.error(err);
        await CustomModal.alert("서버 오류가 발생했습니다.");
      }
    }
  });
});
