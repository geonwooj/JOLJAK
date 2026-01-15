const form = document.querySelector(".login-form");
const inputs = document.querySelectorAll(".login-form .input");

const emailInput = document.getElementById("emailInput");
const sendCodeBtn = document.getElementById("sendCodeBtn");
const verifyBox = document.getElementById("verifyBox");
const codeInput = document.getElementById("codeInput");
const verifyCodeBtn = document.getElementById("verifyCodeBtn");
const verifyStatus = document.getElementById("verifyStatus");
const signupBtn = document.getElementById("signupBtn");

let emailVerified = false;
let verifiedEmail = "";

function setVerifyStatus(msg, ok = false) {
  verifyStatus.textContent = msg;
  verifyStatus.style.color = ok ? "green" : "crimson";
}

function resetVerificationUI() {
  emailVerified = false;
  verifiedEmail = "";
  signupBtn.disabled = true;
  verifyBox.style.display = "none";
  codeInput.value = "";
  setVerifyStatus("", false);
}

// ✅ 이메일이 변경되면 인증 무효화
emailInput.addEventListener("input", () => {
  resetVerificationUI();
});

sendCodeBtn.addEventListener("click", async () => {
  const email = emailInput.value.trim();

  if (!email) {
    await CustomModal.alert("이메일을 입력해주세요.");
    return;
  }

  try {
    const res = await fetch("http://127.0.0.1:8080/api/auth/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const text = await res.text();

    if (!res.ok) {
      await CustomModal.alert("인증코드 전송 실패: " + text);
      return;
    }

    verifyBox.style.display = "block";
    setVerifyStatus("인증코드를 전송했습니다. 메일함을 확인하세요.", true);
    await CustomModal.alert(text);
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결 실패. 백엔드 실행 상태를 확인하세요.");
  }
});

verifyCodeBtn.addEventListener("click", async () => {
  const email = emailInput.value.trim();
  const code = codeInput.value.trim();

  if (!email) {
    await CustomModal.alert("이메일을 입력해주세요.");
    return;
  }
  if (!/^[0-9]{6}$/.test(code)) {
    await CustomModal.alert("인증코드는 6자리 숫자입니다.");
    return;
  }

  try {
    const res = await fetch("http://127.0.0.1:8080/api/auth/email/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });

    const text = await res.text();

    if (!res.ok) {
      setVerifyStatus(text, false);
      await CustomModal.alert("인증 실패: " + text);
      return;
    }

    emailVerified = true;
    verifiedEmail = email;
    signupBtn.disabled = false;

    setVerifyStatus("이메일 인증 완료 ✅", true);
    await CustomModal.alert(text);
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결 실패. 백엔드 실행 상태를 확인하세요.");
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const name = document.getElementById("nameInput").value.trim();       // 닉네임 input에 id 부여 필요
  const email = document.getElementById("emailInput").value.trim();
  const password = document.getElementById("passwordInput").value.trim(); // 비번 input에 id 부여 필요
  const passwordConfirm = document.getElementById("passwordConfirmInput").value.trim(); // 확인 input id

  if (!name || !email || !password || !passwordConfirm) {
    await CustomModal.alert("모든 필드를 입력해주세요.");
    return;
  }

  if (password !== passwordConfirm) {
    await CustomModal.alert("비밀번호가 일치하지 않습니다.");
    return;
  }

  if (!emailVerified || verifiedEmail !== email) {
    await CustomModal.alert("이메일 인증을 완료해주세요.");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:8080/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });

    const resultText = await response.text();

    if (!response.ok) {
      await CustomModal.alert("회원가입 실패: " + resultText);
      return;
    }

    await CustomModal.alert("회원가입 성공: " + resultText);
    window.location.href = "./login.html";
  } catch (err) {
    console.error(err);
    await CustomModal.alert("회원가입 요청 실패. 서버 확인 필요.");
  }
});
