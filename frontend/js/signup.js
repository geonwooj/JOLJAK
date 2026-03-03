const form = document.querySelector(".login-form");

const nameInput = document.getElementById("nameInput");
const emailInput = document.getElementById("emailInput");

const sendCodeBtn = document.getElementById("sendCodeBtn");
const verifyBox = document.getElementById("verifyBox");
const codeInput = document.getElementById("codeInput");
const verifyCodeBtn = document.getElementById("verifyCodeBtn");
const verifyStatus = document.getElementById("verifyStatus");

const passwordInput = document.getElementById("passwordInput");
const passwordConfirmInput = document.getElementById("passwordConfirmInput");

const pwHint = document.getElementById("pwHint");
const pwMatchHint = document.getElementById("pwMatchHint");

const termsCheck = document.getElementById("termsCheck");

// ✅ 대문자 필수 없음: 8자 이상 + 영문 + 숫자 + 특수문자
const PASSWORD_POLICY = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;

let emailVerified = false;
let verifiedEmail = "";

function setVerifyStatus(msg, ok = false) {
  verifyStatus.textContent = msg;
  verifyStatus.style.color = ok ? "green" : "crimson";
}

function resetVerificationUI() {
  emailVerified = false;
  verifiedEmail = "";
  verifyBox.style.display = "none";
  codeInput.value = "";
  setVerifyStatus("");
}

function updatePasswordHints() {
  const pw = (passwordInput.value || "").trim();
  const pw2 = (passwordConfirmInput.value || "").trim();

  // 비밀번호 정책 힌트
  if (!pw) {
    pwHint.style.display = "none";
  } else {
    pwHint.style.display = PASSWORD_POLICY.test(pw) ? "none" : "block";
  }

  // 비밀번호 확인 일치 힌트
  if (!pw2) {
    pwMatchHint.style.display = "none";
  } else {
    pwMatchHint.style.display = pw && pw === pw2 ? "none" : "block";
  }
}

// ===== 실시간 힌트 =====
passwordInput.addEventListener("input", updatePasswordHints);
passwordConfirmInput.addEventListener("input", updatePasswordHints);

// 이메일 변경 시 인증 무효
emailInput.addEventListener("input", () => {
  resetVerificationUI();
});

// ===== 이메일 인증 =====
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
    setVerifyStatus("이메일 인증 완료", true);
    await CustomModal.alert(text);
  } catch (err) {
    console.error(err);
    await CustomModal.alert("서버 연결 실패. 백엔드 실행 상태를 확인하세요.");
  }
});

// ===== 회원가입 =====
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const name = nameInput.value.trim();
  const email = emailInput.value.trim();
  const password = passwordInput.value.trim();
  const passwordConfirm = passwordConfirmInput.value.trim();

  // 기본 입력 체크
  if (!name || !email || !password || !passwordConfirm) {
    await CustomModal.alert("모든 항목을 입력해주세요.");
    return;
  }

  // 이메일 인증 체크
  if (!emailVerified || verifiedEmail !== email) {
    await CustomModal.alert("이메일 인증을 완료해주세요.");
    return;
  }

  // 비밀번호 정책 체크 (✅ 여기서만 모달 띄우고, 힌트는 입력창 아래 빨간 글씨)
  updatePasswordHints();
  if (!PASSWORD_POLICY.test(password)) {
    // 힌트가 보이게만 하고, 모달은 짧게
    await CustomModal.alert("비밀번호 형식이 올바르지 않습니다.");
    return;
  }

  if (password !== passwordConfirm) {
    await CustomModal.alert("비밀번호가 일치하지 않습니다.");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:8080/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        email,
        password,
        termsAccepted: true,
      }),
    });

    const resultText = await response.text();

    if (!response.ok) {
      // ✅ 여기 문장이 진짜 원인(만료/중복 등)
      await CustomModal.alert("회원가입 실패: " + resultText);
      return;
    }

    await CustomModal.alert("회원가입 성공!");
    window.location.href = "./login.html";
  } catch (err) {
    console.error(err);
    await CustomModal.alert("회원가입 요청 실패. 서버 확인 필요.");
  }
});
