const API_BASE = "http://15.164.30.127:8080";

const form = document.getElementById("forgotForm");
const emailInput = document.getElementById("emailInput");
const codeInput = document.getElementById("codeInput");
const newPasswordInput = document.getElementById("newPasswordInput");
const newPasswordConfirmInput = document.getElementById("newPasswordConfirmInput");
const btnSendCode = document.getElementById("btnSendCode");
const resetFields = document.getElementById("resetFields");

btnSendCode?.addEventListener("click", async () => {
  const email = emailInput.value.trim();
  if (!email) {
    await CustomModal.alert("이메일을 입력해주세요.");
    return;
  }

  btnSendCode.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/auth/password/reset/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const message = await res.text();
    if (!res.ok) {
      await CustomModal.alert(message || "인증코드 전송에 실패했습니다.");
      return;
    }
    resetFields.hidden = false;
    emailInput.readOnly = true;
    await CustomModal.alert("인증코드를 이메일로 전송했습니다.");
    codeInput.focus();
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결 중 오류가 발생했습니다.");
  } finally {
    btnSendCode.disabled = false;
  }
});

form?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = emailInput.value.trim();
  const code = codeInput.value.trim();
  const newPassword = newPasswordInput.value;
  const confirmPassword = newPasswordConfirmInput.value;

  if (!email || !code || !newPassword || !confirmPassword) {
    await CustomModal.alert("모든 항목을 입력해주세요.");
    return;
  }
  if (!/^\d{6}$/.test(code)) {
    await CustomModal.alert("인증코드 6자리를 정확히 입력해주세요.");
    return;
  }
  if (newPassword !== confirmPassword) {
    await CustomModal.alert("새 비밀번호가 서로 일치하지 않습니다.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/password/reset/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code, newPassword }),
    });
    const message = await res.text();
    if (!res.ok) {
      await CustomModal.alert(message || "비밀번호 변경에 실패했습니다.");
      return;
    }
    await CustomModal.alert("비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요.");
    window.location.href = "./login.html";
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결 중 오류가 발생했습니다.");
  }
});
