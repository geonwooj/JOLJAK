package com.joljak.backend.dto.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public class EmailVerifyRequest {

    @NotBlank(message = "이메일을 입력해주세요.")
    @Email(message = "올바른 이메일 형식이 아닙니다.")
    private String email;

    @NotBlank(message = "인증코드를 입력해주세요.")
    @Pattern(regexp = "^[0-9]{6}$", message = "인증코드는 6자리 숫자입니다.")
    private String code;

    public String getEmail() { return email; }
    public String getCode() { return code; }

    public void setEmail(String email) { this.email = email; }
    public void setCode(String code) { this.code = code; }
}
