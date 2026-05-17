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
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

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

    @PostMapping(value = "/start", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> startJson(
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

    @PostMapping(value = "/start", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> startMultipart(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @RequestParam(value = "message", required = false) String message,
            @RequestPart(value = "file", required = false) MultipartFile file
    ) {
        try {
            String email = extractEmail(authHeader);
            ChatRoom room = chatService.startChat(email, message, file);
            return ResponseEntity.ok(Map.of("chatId", room.getId()));
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

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

    @PostMapping(value = "/{chatId}/messages", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> addJson(
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

    @PostMapping(value = "/{chatId}/messages", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> addMultipart(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @PathVariable Long chatId,
            @RequestParam(value = "message", required = false) String message,
            @RequestPart(value = "file", required = false) MultipartFile file
    ) {
        try {
            String email = extractEmail(authHeader);
            List<ChatMessage> all = chatService.addUserMessage(chatId, email, message, file);
            List<ChatMessageResponse> messages = all.stream().map(ChatMessageResponse::from).toList();
            return ResponseEntity.ok(messages);
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @DeleteMapping("/{chatId}")
    public ResponseEntity<?> delete(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @PathVariable Long chatId
    ) {
        try {
            String email = extractEmail(authHeader);
            chatService.deleteRoom(chatId, email);
            return ResponseEntity.ok("삭제 완료");
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
