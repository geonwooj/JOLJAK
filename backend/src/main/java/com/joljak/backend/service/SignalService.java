package com.joljak.backend.service;

import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class SignalService {

    private final Map<Long, AiStatus> statusByRoom = new ConcurrentHashMap<>();
    private AiStatus globalStatus = AiStatus.idle();

    private static final Map<String, String> SIGNAL_MESSAGES = new LinkedHashMap<>();

    static {
        SIGNAL_MESSAGES.put("10000", "PDF 텍스트/섹션 추출 시작");
        SIGNAL_MESSAGES.put("10001", "PDF 텍스트/섹션 추출 완료");
        SIGNAL_MESSAGES.put("10002", "도면 캡션 분석 시작");
        SIGNAL_MESSAGES.put("10003", "도면 캡션 분석 완료");

        SIGNAL_MESSAGES.put("20000", "사용자 입력 분석 시작");
        SIGNAL_MESSAGES.put("20001", "사용자 입력 분석 완료");

        SIGNAL_MESSAGES.put("30000", "유사 특허 탐색 시작");
        SIGNAL_MESSAGES.put("30001", "유사 특허 검색 완료");
        SIGNAL_MESSAGES.put("30002", "문서별 재구조화 시작");
        SIGNAL_MESSAGES.put("30003", "문서별 재구조화 완료");

        SIGNAL_MESSAGES.put("40000", "독립 청구항 생성 시작");
        SIGNAL_MESSAGES.put("40001", "독립 청구항 생성 완료");

        SIGNAL_MESSAGES.put("50000", "최종 답변 생성 시작");
        SIGNAL_MESSAGES.put("50001", "최종 답변 생성 완료");
    }

    public synchronized void start(Long chatId) {
        AiStatus status = AiStatus.running("START", "AI 답변 생성을 시작했습니다.");
        put(chatId, status);
        globalStatus = status.copy();
    }

    public synchronized void start() {
        start(null);
    }

    public synchronized void update(String id, Long chatId) {
        if (chatId == null) {
            updateGlobalAndRunningRooms(id);
            return;
        }

        AiStatus status = getMutableStatus(chatId);
        applySignal(status, id);
        put(chatId, status);
        globalStatus = status.copy();

        System.out.println("시그널 수신: " + id + " - " + status.message + " chatId=" + chatId);
    }

    public synchronized void update(String id) {
        update(id, null);
    }

    public synchronized void finish(Long chatId) {
        AiStatus status = getMutableStatus(chatId);

        status.code = "DONE";
        status.message = "AI 답변 생성이 완료되었습니다.";
        status.running = false;
        status.updatedAt = LocalDateTime.now();

        put(chatId, status);
        globalStatus = status.copy();
    }

    public synchronized void finish() {
        finish(null);
    }

    public synchronized void fail(Long chatId, String message) {
        AiStatus status = getMutableStatus(chatId);

        status.code = "ERROR";
        status.message = message;
        status.running = false;
        status.updatedAt = LocalDateTime.now();

        put(chatId, status);
        globalStatus = status.copy();
    }

    public synchronized void fail(String message) {
        fail(null, message);
    }

    public synchronized Map<String, Object> getStatus(Long chatId) {
        AiStatus status;

        if (chatId == null) {
            status = globalStatus;
        } else {
            status = statusByRoom.get(chatId);

            if (status == null || status.isIdle()) {
                status = globalStatus;
            }
        }

        return status.toMap();
    }

    public synchronized Map<String, Object> getStatus() {
        return getStatus(null);
    }

    private void updateGlobalAndRunningRooms(String id) {
        AiStatus global = globalStatus == null ? AiStatus.idle() : globalStatus.copy();
        applySignal(global, id);
        globalStatus = global;

        statusByRoom.replaceAll((roomId, status) -> {
            if (status == null) {
                status = AiStatus.idle();
            }

            AiStatus copied = status.copy();

            if (copied.running || copied.isIdle() || "START".equals(copied.code)) {
                applySignal(copied, id);
            }

            return copied;
        });

        System.out.println("시그널 수신: " + id + " - " + global.message + " chatId=null");
    }

    private void applySignal(AiStatus status, String id) {
        status.code = id;
        status.message = messageBySignal(id);
        status.running = true;
        status.updatedAt = LocalDateTime.now();
        status.addHistory(id, status.message);
    }

    private AiStatus getMutableStatus(Long chatId) {
        if (chatId == null) {
            return globalStatus == null ? AiStatus.idle() : globalStatus.copy();
        }

        AiStatus status = statusByRoom.get(chatId);
        if (status == null) {
            status = AiStatus.idle();
        }

        return status.copy();
    }

    private void put(Long chatId, AiStatus status) {
        if (chatId == null) {
            globalStatus = status;
            return;
        }

        statusByRoom.put(chatId, status);
    }

    private String messageBySignal(String id) {
        return SIGNAL_MESSAGES.getOrDefault(id, "AI 작업을 처리 중입니다.");
    }

    private static class AiStatus {
        private String code;
        private String message;
        private boolean running;
        private LocalDateTime updatedAt;
        private final List<Map<String, Object>> history;

        private AiStatus(String code, String message, boolean running, LocalDateTime updatedAt) {
            this.code = code;
            this.message = message;
            this.running = running;
            this.updatedAt = updatedAt;
            this.history = new ArrayList<>();
        }

        private AiStatus(String code, String message, boolean running, LocalDateTime updatedAt,
                         List<Map<String, Object>> history) {
            this.code = code;
            this.message = message;
            this.running = running;
            this.updatedAt = updatedAt;
            this.history = new ArrayList<>(history);
        }

        static AiStatus idle() {
            return new AiStatus("IDLE", "대기 중", false, LocalDateTime.now());
        }

        static AiStatus running(String code, String message) {
            return new AiStatus(code, message, true, LocalDateTime.now());
        }

        boolean isIdle() {
            return "IDLE".equals(code) && history.isEmpty();
        }

        AiStatus copy() {
            return new AiStatus(code, message, running, updatedAt, history);
        }

        void addHistory(String code, String message) {
            if (!SIGNAL_MESSAGES.containsKey(code)) {
                return;
            }

            boolean alreadyExists = history.stream()
                    .anyMatch(item -> code.equals(String.valueOf(item.get("code"))));

            if (alreadyExists) {
                return;
            }

            Map<String, Object> item = new LinkedHashMap<>();
            item.put("code", code);
            item.put("message", message);
            item.put("time", LocalDateTime.now().toString());
            history.add(item);
        }

        Map<String, Object> toMap() {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("code", code);
            map.put("message", message);
            map.put("running", running);
            map.put("updatedAt", updatedAt.toString());
            map.put("history", new ArrayList<>(history));
            map.put("steps", SIGNAL_MESSAGES);
            return map;
        }
    }
}
