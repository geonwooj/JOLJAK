package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.dto.chat.ChatMessageResponse;
import org.springframework.stereotype.Service;

@Service
public class AnswerFormatService {

    public ChatMessageResponse toResponse(ChatMessage message) {
        String formattedContent = null;

        if (message.getRole() == ChatMessage.Role.AI) {
            formattedContent = formatPatentAnswer(message.getContent());
        }

        return ChatMessageResponse.from(message, formattedContent);
    }

    private String formatPatentAnswer(String raw) {
        if (raw == null || raw.isBlank()) {
            return "<p></p>";
        }

        String text = escapeHtml(raw.trim());

        text = text.replace("\r\n", "\n").replace("\r", "\n");

        // 청구항 번호 앞에서 문단 구분. 문장 중간의 일반 '청구항' 단어는 최대한 건드리지 않음.
        text = text.replaceAll("(?m)(^|\\n)\\s*(청구항\\s*\\d+\\.?)(\\s*)", "$1<h3>$2</h3>");

        // 가. 나. 다. 같은 항목 구분
        text = text.replaceAll("(?m)(^|\\n)\\s*([가-힣])\\.\\s+", "$1<br><strong>$2.</strong> ");

        String[] blocks = text.split("\\n{2,}");
        StringBuilder html = new StringBuilder();

        for (String block : blocks) {
            String trimmed = block.trim();
            if (trimmed.isEmpty()) continue;

            if (trimmed.startsWith("<h3>")) {
                html.append(trimmed.replace("\n", "<br>")).append("\n");
            } else {
                html.append("<p>").append(trimmed.replace("\n", "<br>")).append("</p>\n");
            }
        }

        return html.toString();
    }

    private String escapeHtml(String value) {
        return value
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }
}
