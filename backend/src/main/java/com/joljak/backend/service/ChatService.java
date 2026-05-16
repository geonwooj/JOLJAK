package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ChatService {

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AiService aiService;

    public ChatService(
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            AiService aiService
    ) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.aiService = aiService;
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage) {
        String title = makeTitle(firstMessage);
        ChatRoom room = chatRoomRepository.save(new ChatRoom(userEmail, title));

        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.USER, userEmail, firstMessage));

        String aiAnswer = aiService.generateAnswer(firstMessage);
        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, aiAnswer));

        room.touch();
        return room;
    }

    @Transactional
    public List<ChatMessage> addUserMessage(Long roomId, String userEmail, String message) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.USER, userEmail, message));

        String aiAnswer = aiService.generateAnswer(message);
        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, aiAnswer));

        room.touch();
        return chatMessageRepository.findByRoomIdOrderByCreatedAtAsc(roomId);
    }

    @Transactional(readOnly = true)
    public List<ChatRoom> recentRooms(String userEmail) {
        return chatRoomRepository.findTop5ByUserEmailOrderByUpdatedAtDesc(userEmail);
    }

    @Transactional(readOnly = true)
    public List<ChatMessage> getMessages(Long roomId, String userEmail) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        return chatMessageRepository.findByRoomIdOrderByCreatedAtAsc(roomId);
    }

    @Transactional
    public void deleteRoom(Long roomId, String userEmail) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        chatMessageRepository.deleteByRoomId(roomId);
        chatRoomRepository.delete(room);
    }

    private String makeTitle(String message) {
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isEmpty()) return "새 채팅";
        return trimmed.length() <= 20 ? trimmed : trimmed.substring(0, 20) + "…";
    }
}