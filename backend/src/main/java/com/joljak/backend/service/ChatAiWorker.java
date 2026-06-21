package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ChatAiWorker {

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AiService aiService;
    private final SignalService signalService;

    public ChatAiWorker(
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            AiService aiService,
            SignalService signalService
    ) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.aiService = aiService;
        this.signalService = signalService;
    }

    @Async
    @Transactional
    public void generateAndSaveAiAnswer(Long roomId, String userEmail, String userMessage, String savedFilePath) {
        try {
            signalService.start(roomId);

            ChatRoom room = chatRoomRepository.findById(roomId)
                    .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

            String aiAnswer = aiService.generateAnswer(userMessage, savedFilePath, roomId);
            chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, aiAnswer));

            room.touch();
            signalService.finish(roomId);
        } catch (Exception e) {
            signalService.fail(roomId, "AI 답변 생성 중 오류가 발생했습니다: " + e.getMessage());
        }
    }
}
