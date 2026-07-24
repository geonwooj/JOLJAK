document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("forgotForm");
  const emailInput = document.getElementById("emailInput");
  const codeArea = document.getElementById("resetFields");
  const sendButton = document.getElementById("btnSendReset");
  let codeSent = false;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    if (!email) return CustomModal.alert("이메일을 입력해주세요.");

    try {
      if (!codeSent) {
        await ApiClient.post("/api/auth/password/reset/send", { email });
        codeSent = true;
        emailInput.readOnly = true;
        codeArea.hidden = false;
        sendButton.textContent = "비밀번호 재설정";
        await CustomModal.alert("인증코드를 이메일로 전송했습니다.");
        return;
      }

      const code = document.getElementById("codeInput").value.trim();
      const newPassword = document.getElementById("newPasswordInput").value;
      const confirmPassword = document.getElementById("confirmPasswordInput").value;
      if (!code || !newPassword || !confirmPassword) return CustomModal.alert("모든 항목을 입력해주세요.");
      if (newPassword !== confirmPassword) return CustomModal.alert("새 비밀번호가 일치하지 않습니다.");

      await ApiClient.post("/api/auth/password/reset/confirm", { email, code, newPassword });
      await CustomModal.alert("비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해주세요.");
      location.href = "./login.html";
    } catch (err) {
      await CustomModal.alert(err.message);
    }
  });
});
