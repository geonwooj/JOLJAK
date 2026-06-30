package com.joljak.backend.service;

import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class SignalService {

    private final Map<Long, AiStatus> statusByRoom = new ConcurrentHashMap<>();
    private AiStatus globalStatus = AiStatus.idle();

    public void start(Long chatId) {
        put(chatId, AiStatus.running("START", "AI 답변 생성을 시작했습니다."));
    }

    public void start() {
        globalStatus = AiStatus.running("START", "AI 답변 생성을 시작했습니다.");
    }

    public void update(String id, Long chatId) {
        put(chatId, AiStatus.running(id, messageBySignal(id)));
        System.out.println("시그널 수신: " + id + " chatId=" + chatId);
    }

    public void update(String id) {
        globalStatus = AiStatus.running(id, messageBySignal(id));
        System.out.println("시그널 수신: " + id);
    }

    public void finish(Long chatId) {
        put(chatId, AiStatus.done());
    }

    public void finish() {
        globalStatus = AiStatus.done();
    }

    public void fail(Long chatId, String message) {
        put(chatId, AiStatus.error(message));
    }

    public void fail(String message) {
        globalStatus = AiStatus.error(message);
    }

    public Map<String, Object> getStatus(Long chatId) {
        AiStatus status = chatId == null
                ? globalStatus
                : statusByRoom.getOrDefault(chatId, AiStatus.idle());

        return status.toMap();
    }

    public Map<String, Object> getStatus() {
        return getStatus(null);
    }

    private void put(Long chatId, AiStatus status) {
        if (chatId == null) {
            globalStatus = status;
            return;
        }
        statusByRoom.put(chatId, status);
    }

    private String messageBySignal(String id) {
        return switch (id) {
            case "10001" -> "입력 내용을 특허 문서 구조로 분석 중입니다.";
            case "10002" -> "유사 특허를 검색 중입니다.";
            case "10003" -> "최종 특허 명세서를 생성 중입니다.";
            default -> "AI 작업을 처리 중입니다.";
        };
    }

    private record AiStatus(String code, String message, boolean running, LocalDateTime updatedAt) {
        static AiStatus idle() {
            return new AiStatus("IDLE", "대기 중", false, LocalDateTime.now());
        }

        static AiStatus running(String code, String message) {
            return new AiStatus(code, message, true, LocalDateTime.now());
        }

        static AiStatus done() {
            return new AiStatus("DONE", "AI 답변 생성이 완료되었습니다.", false, LocalDateTime.now());
        }

        static AiStatus error(String message) {
            return new AiStatus("ERROR", message, false, LocalDateTime.now());
        }

        Map<String, Object> toMap() {
            return Map.of(
                    "code", code,
                    "message", message,
                    "running", running,
                    "updatedAt", updatedAt.toString()
            );
        }
    }
}
