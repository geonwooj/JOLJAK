package com.joljak.backend.service;

import com.joljak.backend.domain.auth.EmailVerification;
import com.joljak.backend.domain.auth.EmailVerificationRepository;
import com.joljak.backend.domain.user.User;
import com.joljak.backend.domain.user.UserRepository;
import com.joljak.backend.dto.auth.LoginRequest;
import com.joljak.backend.dto.auth.SignupRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.LocalDateTime;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final EmailVerificationRepository emailVerificationRepository;
    private final MailService mailService;

    @Value("${app.email-verification.expiry-minutes:5}")
    private int expiryMinutes;

    private final SecureRandom random = new SecureRandom();

    public AuthService(UserRepository userRepository,
            EmailVerificationRepository emailVerificationRepository,
            MailService mailService) {
        this.userRepository = userRepository;
        this.emailVerificationRepository = emailVerificationRepository;
        this.mailService = mailService;
    }

    // ✅ 이메일 인증코드 발송
    public void sendEmailVerificationCode(String email) {
        // 이미 가입된 이메일이면 막기(원하면 이 정책은 바꿀 수 있음)
        if (userRepository.findByEmail(email).isPresent()) {
            throw new RuntimeException("이미 가입된 이메일입니다.");
        }

        String code = String.format("%06d", random.nextInt(1_000_000));
        LocalDateTime expiresAt = LocalDateTime.now().plusMinutes(expiryMinutes);

        // 기존 기록이 있어도 "최신 것"만 인정할 거라 그냥 새로 저장
        EmailVerification ev = new EmailVerification(email, code, expiresAt);
        emailVerificationRepository.save(ev);

        mailService.sendVerificationCode(email, code);
    }

    // ✅ 이메일 인증코드 검증
    public void verifyEmailCode(String email, String code) {
        EmailVerification ev = emailVerificationRepository.findTopByEmailOrderByCreatedAtDesc(email)
                .orElseThrow(() -> new RuntimeException("인증코드를 먼저 요청해주세요."));

        if (ev.getExpiresAt().isBefore(LocalDateTime.now())) {
            throw new RuntimeException("인증코드가 만료되었습니다. 다시 요청해주세요.");
        }

        if (!ev.getCode().equals(code)) {
            throw new RuntimeException("인증코드가 올바르지 않습니다.");
        }

        ev.setVerified(true);
        emailVerificationRepository.save(ev);
    }

    // ✅ 회원가입 (이메일 인증 완료된 이메일만 허용)
    public User signup(SignupRequest request) {
        if (userRepository.findByEmail(request.getEmail()).isPresent()) {
            throw new RuntimeException("email already exists");
        }

        EmailVerification ev = emailVerificationRepository
                .findTopByEmailOrderByCreatedAtDesc(request.getEmail())
                .orElseThrow(() -> new RuntimeException("이메일 인증을 먼저 진행해주세요."));

        if (!ev.isVerified()) {
            throw new RuntimeException("이메일 인증을 완료해주세요.");
        }

        if (ev.getExpiresAt().isBefore(LocalDateTime.now())) {
            throw new RuntimeException("이메일 인증이 만료되었습니다. 다시 인증해주세요.");
        }

        User user = new User(
                request.getEmail(),
                request.getPassword(),
                request.getName(),
                true);

        return userRepository.save(user);
    }

    public User login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new RuntimeException("user not found"));

        if (!user.getPassword().equals(request.getPassword())) {
            throw new RuntimeException("password mismatch");
        }

        // ✅ 이메일 인증 안 된 계정은 로그인 막기(정석)
        if (!user.isEmailVerified()) {
            throw new RuntimeException("이메일 인증을 완료해주세요.");
        }

        return user;
    }

    public User findByEmail(String email) {
        return userRepository.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("user not found"));
    }
}
