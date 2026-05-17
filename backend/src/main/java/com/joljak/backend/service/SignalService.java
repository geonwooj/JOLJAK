package com.joljak.backend.service;

import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Map;

@Service
public class SignalService {

    private String currentCode = "IDLE";
    private String currentMessage = "대기 중";
    private boolean running = false;
    private LocalDateTime updatedAt = LocalDateTime.now();

    public synchronized void start() {
        this.currentCode = "START";
        this.currentMessage = "AI 답변 생성을 시작했습니다.";
        this.running = true;
        this.updatedAt = LocalDateTime.now();
    }

    public synchronized void update(String id) {
        this.currentCode = id;
        this.currentMessage = switch (id) {
            case "10001" -> "입력 내용을 특허 문서 구조로 분석 중입니다.";
            case "10002" -> "유사 특허를 검색 중입니다.";
            case "10003" -> "최종 특허 명세서를 생성 중입니다.";
            default -> "AI 작업을 처리 중입니다.";
        };
        this.running = true;
        this.updatedAt = LocalDateTime.now();

        System.out.println("시그널 수신: " + id + " - " + this.currentMessage);
    }

    public synchronized void finish() {
        this.currentCode = "DONE";
        this.currentMessage = "AI 답변 생성이 완료되었습니다.";
        this.running = false;
        this.updatedAt = LocalDateTime.now();
    }

    public synchronized void fail(String message) {
        this.currentCode = "ERROR";
        this.currentMessage = message;
        this.running = false;
        this.updatedAt = LocalDateTime.now();
    }

    public synchronized Map<String, Object> getStatus() {
        return Map.of(
                "code", currentCode,
                "message", currentMessage,
                "running", running,
                "updatedAt", updatedAt.toString()
        );
    }
}