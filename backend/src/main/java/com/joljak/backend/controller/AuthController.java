package com.joljak.backend.controller;

import com.joljak.backend.config.JwtUtil;
import com.joljak.backend.dto.auth.*;
import com.joljak.backend.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final JwtUtil jwtUtil;

    public AuthController(AuthService authService, JwtUtil jwtUtil) {
        this.authService = authService;
        this.jwtUtil = jwtUtil;
    }

    @PostMapping("/email/send")
    public ResponseEntity<?> sendEmailCode(@Valid @RequestBody EmailSendRequest request) {
        authService.sendEmailVerificationCode(request.getEmail());
        return ResponseEntity.ok("인증코드를 전송했습니다.");
    }

    @PostMapping("/email/verify")
    public ResponseEntity<?> verifyEmailCode(@Valid @RequestBody EmailVerifyRequest request) {
        authService.verifyEmailCode(request.getEmail(), request.getCode());
        return ResponseEntity.ok("이메일 인증이 완료되었습니다.");
    }

    @PostMapping("/signup")
    public ResponseEntity<?> signup(@RequestBody SignupRequest request) {
        authService.signup(request);
        return ResponseEntity.ok("회원가입 성공");
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        try {
            var user = authService.login(request);
            String token = jwtUtil.generateToken(user.getEmail());
            return ResponseEntity.ok(new LoginResponse(token, user.getName()));
        } catch (RuntimeException e) {
            return ResponseEntity.status(401).body(e.getMessage());
        }
    }

    // JWT는 서버 세션을 저장하지 않으므로, 로그아웃 요청은 항상 성공 처리한다.
    @PostMapping("/logout")
    public ResponseEntity<?> logout() {
        return ResponseEntity.ok("로그아웃 되었습니다.");
    }

    @PostMapping("/password/reset/send")
    public ResponseEntity<?> sendPasswordResetCode(@RequestBody PasswordResetSendRequest request) {
        try {
            authService.sendPasswordResetCode(request.getEmail());
            return ResponseEntity.ok("비밀번호 재설정 인증코드를 전송했습니다.");
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @PostMapping("/password/reset/confirm")
    public ResponseEntity<?> resetPassword(@RequestBody PasswordResetConfirmRequest request) {
        try {
            authService.resetPassword(request.getEmail(), request.getCode(), request.getNewPassword());
            return ResponseEntity.ok("비밀번호가 변경되었습니다.");
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
        return ResponseEntity.badRequest().body(msg);
    }
}
