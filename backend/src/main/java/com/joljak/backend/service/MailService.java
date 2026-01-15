package com.joljak.backend.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Service
public class MailService {

    private final JavaMailSender mailSender;

    @Value("${app.mail.from}")
    private String from;

    public MailService(JavaMailSender mailSender) {
        this.mailSender = mailSender;
    }

    public void sendVerificationCode(String to, String code) {
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(from);
        msg.setTo(to);
        msg.setSubject("[AI Patent Office] 이메일 인증코드");
        msg.setText(
                "회원가입 이메일 인증코드입니다.\n\n" +
                "인증코드: " + code + "\n\n" +
                "※ 유효시간 내에 입력해주세요."
        );
        mailSender.send(msg);
    }
}
