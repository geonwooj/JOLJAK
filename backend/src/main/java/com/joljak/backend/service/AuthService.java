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

    @Value("${app.email-verification.expiry-minutes:5}")
    private int expiryMinutes;

    private final SecureRandom random = new SecureRandom();

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
        if (userRepository.findByEmail(email).isPresent()) {
            throw new RuntimeException("이미 가입된 이메일입니다.");
        }

        String code = String.format("%06d", random.nextInt(1_000_000));
        LocalDateTime expiresAt = LocalDateTime.now().plusMinutes(expiryMinutes);

        EmailVerification ev = new EmailVerification(email, code, expiresAt);
        emailVerificationRepository.save(ev);

        mailService.sendVerificationCode(email, code);
    }

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

    public User signup(SignupRequest request) {
        if (request == null) {
            throw new RuntimeException("잘못된 요청입니다.");
        }

        if (!request.isTermsAccepted()) {
            throw new RuntimeException("이용약관 및 개인정보처리방침에 동의해야 회원가입이 가능합니다.");
        }

        String pw = request.getPassword() == null ? "" : request.getPassword().trim();
        if (!pw.matches(PASSWORD_POLICY_REGEX)) {
            throw new RuntimeException("비밀번호는 8자리 이상이며 영문/숫자/특수문자를 포함해야 합니다.");
        }

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
                pw,
                request.getName(),
                true
        );

        return userRepository.save(user);
    }

    public User login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new RuntimeException("user not found"));

        if (!user.getPassword().equals(request.getPassword())) {
            throw new RuntimeException("password mismatch");
        }

        if (!user.isEmailVerified()) {
            throw new RuntimeException("이메일 인증을 완료해주세요.");
        }

        return user;
    }

    public User findByEmail(String email) {
        return userRepository.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("user not found"));
    }

    @Transactional
    public void deleteUserByEmail(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("user not found"));

        // 사용자의 채팅방/메시지 먼저 삭제
        List<ChatRoom> rooms = chatRoomRepository.findAllByUserEmail(email);
        for (ChatRoom room : rooms) {
            chatMessageRepository.deleteByRoomId(room.getId());
        }
        chatRoomRepository.deleteAll(rooms);

        // 이메일 인증 기록 삭제
        emailVerificationRepository.deleteAllByEmail(email);

        // 사용자 삭제
        userRepository.delete(user);
    }
}