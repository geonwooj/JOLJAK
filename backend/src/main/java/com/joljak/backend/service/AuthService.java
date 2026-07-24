package com.joljak.backend.service;

import com.joljak.backend.domain.auth.EmailVerification;
import com.joljak.backend.domain.auth.EmailVerificationRepository;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import com.joljak.backend.domain.user.User;
import com.joljak.backend.domain.user.UserRepository;
import com.joljak.backend.dto.auth.LoginRequest;
import com.joljak.backend.dto.auth.SignupRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class AuthService {
    private final UserRepository userRepository;
    private final EmailVerificationRepository emailVerificationRepository;
    private final MailService mailService;
    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();

    @Value("${app.email-verification.expiry-minutes:5}")
    private int expiryMinutes;

    private static final String PASSWORD_POLICY_REGEX =
            "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[^A-Za-z0-9]).{8,}$";

    public AuthService(UserRepository userRepository,
                       EmailVerificationRepository emailVerificationRepository,
                       MailService mailService,
                       ChatRoomRepository chatRoomRepository,
                       ChatMessageRepository chatMessageRepository) {
        this.userRepository = userRepository;
        this.emailVerificationRepository = emailVerificationRepository;
        this.mailService = mailService;
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
    }

    public void sendEmailVerificationCode(String email) {
        String normalized = normalizeEmail(email);
        if (userRepository.existsByEmail(normalized)) throw new RuntimeException("이미 가입된 이메일입니다.");
        saveAndSendCode(normalized, false);
    }

    public void verifyEmailCode(String email, String code) {
        EmailVerification ev = getValidVerification(normalizeEmail(email), code);
        ev.setVerified(true);
        emailVerificationRepository.save(ev);
    }

    public User signup(SignupRequest request) {
        if (request == null) throw new RuntimeException("잘못된 요청입니다.");
        if (!request.isTermsAccepted()) throw new RuntimeException("이용약관 및 개인정보처리방침에 동의해야 회원가입이 가능합니다.");

        String email = normalizeEmail(request.getEmail());
        String password = requireValidPassword(request.getPassword());
        String name = requireValidName(request.getName());
        if (userRepository.existsByEmail(email)) throw new RuntimeException("이미 가입된 이메일입니다.");

        EmailVerification ev = emailVerificationRepository.findTopByEmailOrderByCreatedAtDesc(email)
                .orElseThrow(() -> new RuntimeException("이메일 인증을 먼저 진행해주세요."));
        if (!ev.isVerified() || ev.getExpiresAt().isBefore(LocalDateTime.now()))
            throw new RuntimeException("이메일 인증을 다시 진행해주세요.");

        return userRepository.save(new User(email, passwordEncoder.encode(password), name, true));
    }

    @Transactional
    public User login(LoginRequest request) {
        String email = normalizeEmail(request.getEmail());
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("이메일 또는 비밀번호가 올바르지 않습니다."));

        String stored = user.getPassword();
        String raw = request.getPassword() == null ? "" : request.getPassword();
        boolean encoded = stored != null && stored.startsWith("$2");
        boolean matches = encoded ? passwordEncoder.matches(raw, stored) : stored != null && stored.equals(raw);
        if (!matches) throw new RuntimeException("이메일 또는 비밀번호가 올바르지 않습니다.");
        if (!user.isEmailVerified()) throw new RuntimeException("이메일 인증을 완료해주세요.");

        // 기존 평문 저장 계정은 로그인 성공 시 BCrypt로 자동 전환
        if (!encoded) {
            user.setPassword(passwordEncoder.encode(raw));
            userRepository.save(user);
        }
        return user;
    }

    public User findByEmail(String email) {
        return userRepository.findByEmail(normalizeEmail(email))
                .orElseThrow(() -> new RuntimeException("사용자를 찾을 수 없습니다."));
    }

    @Transactional
    public User updateProfile(String email, String name) {
        User user = findByEmail(email);
        user.setName(requireValidName(name));
        return userRepository.save(user);
    }

    @Transactional
    public void changePassword(String email, String currentPassword, String newPassword) {
        User user = findByEmail(email);
        if (!matchesPassword(currentPassword, user.getPassword()))
            throw new RuntimeException("현재 비밀번호가 올바르지 않습니다.");
        String valid = requireValidPassword(newPassword);
        if (matchesPassword(valid, user.getPassword()))
            throw new RuntimeException("새 비밀번호는 현재 비밀번호와 달라야 합니다.");
        user.setPassword(passwordEncoder.encode(valid));
        userRepository.save(user);
    }

    public void sendPasswordResetCode(String email) {
        String normalized = normalizeEmail(email);
        if (!userRepository.existsByEmail(normalized))
            throw new RuntimeException("가입된 이메일을 찾을 수 없습니다.");
        saveAndSendCode(normalized, true);
    }

    @Transactional
    public void resetPassword(String email, String code, String newPassword) {
        String normalized = normalizeEmail(email);
        User user = userRepository.findByEmail(normalized)
                .orElseThrow(() -> new RuntimeException("가입된 이메일을 찾을 수 없습니다."));
        EmailVerification ev = getValidVerification(normalized, code);
        user.setPassword(passwordEncoder.encode(requireValidPassword(newPassword)));
        userRepository.save(user);
        ev.setVerified(true);
        emailVerificationRepository.save(ev);
    }

    private void saveAndSendCode(String email, boolean passwordReset) {
        String code = String.format("%06d", random.nextInt(1_000_000));
        EmailVerification ev = new EmailVerification(email, code, LocalDateTime.now().plusMinutes(expiryMinutes));
        emailVerificationRepository.save(ev);
        if (passwordReset) mailService.sendPasswordResetCode(email, code);
        else mailService.sendVerificationCode(email, code);
    }

    private EmailVerification getValidVerification(String email, String code) {
        EmailVerification ev = emailVerificationRepository.findTopByEmailOrderByCreatedAtDesc(email)
                .orElseThrow(() -> new RuntimeException("인증코드를 먼저 요청해주세요."));
        if (ev.getExpiresAt().isBefore(LocalDateTime.now())) throw new RuntimeException("인증코드가 만료되었습니다. 다시 요청해주세요.");
        if (code == null || !ev.getCode().equals(code.trim())) throw new RuntimeException("인증코드가 올바르지 않습니다.");
        return ev;
    }

    private boolean matchesPassword(String raw, String stored) {
        if (raw == null || stored == null) return false;
        return stored.startsWith("$2") ? passwordEncoder.matches(raw, stored) : stored.equals(raw);
    }

    private String requireValidPassword(String password) {
        String value = password == null ? "" : password.trim();
        if (!value.matches(PASSWORD_POLICY_REGEX))
            throw new RuntimeException("비밀번호는 8자리 이상이며 영문, 숫자, 특수문자를 포함해야 합니다.");
        return value;
    }

    private String requireValidName(String name) {
        String value = name == null ? "" : name.trim();
        if (value.isBlank()) throw new RuntimeException("이름을 입력해주세요.");
        if (value.length() > 30) throw new RuntimeException("이름은 30자 이하로 입력해주세요.");
        return value;
    }

    private String normalizeEmail(String email) {
        String value = email == null ? "" : email.trim().toLowerCase();
        if (value.isBlank()) throw new RuntimeException("이메일을 입력해주세요.");
        return value;
    }

    @Transactional
    public void deleteUserByEmail(String email) {
        User user = findByEmail(email);
        List<ChatRoom> rooms = chatRoomRepository.findAllByUserEmail(user.getEmail());
        for (ChatRoom room : rooms) chatMessageRepository.deleteByRoomId(room.getId());
        chatRoomRepository.deleteAll(rooms);
        emailVerificationRepository.deleteAllByEmail(user.getEmail());
        userRepository.delete(user);
    }
}
