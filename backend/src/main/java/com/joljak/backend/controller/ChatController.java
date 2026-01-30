package com.joljak.backend.controller;

import com.joljak.backend.config.JwtUtil;
import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.dto.chat.AddMessageRequest;
import com.joljak.backend.dto.chat.ChatMessageResponse;
import com.joljak.backend.dto.chat.ChatRoomResponse;
import com.joljak.backend.dto.chat.StartChatRequest;
import com.joljak.backend.service.ChatService;
import io.jsonwebtoken.JwtException;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;


@RestController
@RequestMapping("/api/chats")
public class ChatController {

    private final ChatService chatService;
    private final JwtUtil jwtUtil;

    public ChatController(ChatService chatService, JwtUtil jwtUtil) {
        this.chatService = chatService;
        this.jwtUtil = jwtUtil;
    }

    // index.html에서 "첫 질문" 보내면 새 채팅방 만들고 저장
    @PostMapping("/start")
    public ResponseEntity<?> start(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @Valid @RequestBody StartChatRequest req
    ) {
        try {
            String email = extractEmail(authHeader);
            ChatRoom room = chatService.startChat(email, req.getMessage());
            return ResponseEntity.ok(Map.of("chatId", room.getId()));
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    // 사이드바 "내 채팅" 최근 5개
    @GetMapping("/recent")
    public ResponseEntity<?> recent(
            @RequestHeader(value = "Authorization", required = false) String authHeader
    ) {
        try {
            String email = extractEmail(authHeader);
            List<ChatRoomResponse> rooms = chatService.recentRooms(email)
                    .stream()
                    .map(r -> new ChatRoomResponse(r.getId(), r.getTitle(), r.getUpdatedAt()))
                    .toList();
            return ResponseEntity.ok(rooms);
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        }
    }

    // chat.html에서 채팅방 메시지 로드
    @GetMapping("/{chatId}/messages")
    public ResponseEntity<?> messages(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @PathVariable Long chatId
    ) {
        try {
            String email = extractEmail(authHeader);
            List<ChatMessageResponse> messages = chatService.getMessages(chatId, email)
                    .stream()
                    .map(ChatMessageResponse::from)
                    .toList();
            return ResponseEntity.ok(messages);
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    // chat.html에서 추가 질문
    @PostMapping("/{chatId}/messages")
    public ResponseEntity<?> add(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @PathVariable Long chatId,
            @Valid @RequestBody AddMessageRequest req
    ) {
        try {
            String email = extractEmail(authHeader);
            List<ChatMessage> all = chatService.addUserMessage(chatId, email, req.getMessage());
            List<ChatMessageResponse> messages = all.stream().map(ChatMessageResponse::from).toList();
            return ResponseEntity.ok(messages);
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    private String extractEmail(String authHeader) throws JwtException {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            throw new JwtException("No token");
        }
        String token = authHeader.substring("Bearer ".length()).trim();
        if (token.isEmpty()) {
            throw new JwtException("No token");
        }
        return jwtUtil.extractEmail(token);
    }
}
