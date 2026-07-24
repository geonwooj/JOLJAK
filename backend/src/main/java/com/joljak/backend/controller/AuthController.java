package com.joljak.backend.controller;

import com.joljak.backend.dto.auth.EmailSendRequest;
import com.joljak.backend.dto.auth.EmailVerifyRequest;
import com.joljak.backend.dto.auth.LoginRequest;
import com.joljak.backend.dto.auth.LoginResponse;
import com.joljak.backend.dto.auth.SignupRequest;
import com.joljak.backend.service.AuthService;
import com.joljak.backend.config.JwtUtil;

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

    // ✅ 이메일 인증코드 전송
    @PostMapping("/email/send")
    public ResponseEntity<?> sendEmailCode(@Valid @RequestBody EmailSendRequest request) {
        authService.sendEmailVerificationCode(request.getEmail());
        return ResponseEntity.ok("인증코드를 전송했습니다.");
    }

    // ✅ 이메일 인증코드 확인
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

    // ✅ @Valid 에러 메시지 깔끔히 반환
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
        return ResponseEntity.badRequest().body(msg);
    }
}
