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

    private static final String DEMO_AI_ANSWER = "데모 답변입니다";

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;

    public ChatService(ChatRoomRepository chatRoomRepository, ChatMessageRepository chatMessageRepository) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage) {
        String title = makeTitle(firstMessage);
        ChatRoom room = chatRoomRepository.save(new ChatRoom(userEmail, title));

        // USER message
        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.USER, userEmail, firstMessage));

        // AI demo message도 같이 저장(프론트가 그대로 렌더)
        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, DEMO_AI_ANSWER));

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
        chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, DEMO_AI_ANSWER));

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

    private String makeTitle(String message) {
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isEmpty()) return "새 채팅";
        return trimmed.length() <= 20 ? trimmed : trimmed.substring(0, 20) + "…";
    }
}
