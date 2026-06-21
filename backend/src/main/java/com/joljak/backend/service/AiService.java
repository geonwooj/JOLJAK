package com.joljak.backend.service;

import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Service
public class AiService {

    // 기존 코드와 호환용: 텍스트만 있을 때 사용
    public String generateAnswer(String userMessage) {
        return generateAnswer(userMessage, null, null);
    }

    // 텍스트 + 파일 경로 둘 다 처리하는 메서드
    public String generateAnswer(String userMessage, String savedFilePath, Long chatId) {
        try {
            Path backendDir = Path.of(System.getProperty("user.dir")).toAbsolutePath();
            Path projectRoot = backendDir.getParent();
            Path aiDir = projectRoot.resolve("ai");

            Path pythonExe = aiDir.resolve("venv").resolve("Scripts").resolve("python.exe");

            String outputFileName = chatId == null
                    ? "out.txt"
                    : "out_" + chatId + ".txt";

            Path resultFile = aiDir.resolve("data").resolve(outputFileName);

            Files.createDirectories(resultFile.getParent());
            Files.deleteIfExists(resultFile);

            List<String> command = new ArrayList<>();

            command.add(pythonExe.toString());
            command.add("RUN.py");

            if (userMessage != null && !userMessage.isBlank()) {
                command.add("--text");
                command.add(userMessage);
            }

            if (savedFilePath != null && !savedFilePath.isBlank()
                    && savedFilePath.toLowerCase().endsWith(".pdf")) {
                command.add("--pdf");
                command.add(savedFilePath);
            }

            command.add("--output");
            command.add("data/" + outputFileName);

            ProcessBuilder pb = new ProcessBuilder(command);

            pb.directory(aiDir.toFile());
            pb.redirectErrorStream(true);

            // Windows 한글/이모지 깨짐 방지
            pb.environment().put("PYTHONUTF8", "1");
            pb.environment().put("PYTHONIOENCODING", "utf-8");

            if (chatId != null) {
                pb.environment().put("CHAT_ID", String.valueOf(chatId));
                pb.environment().put("WEB_LINK", "http://localhost:8080/api/signal/");
            }

            // Spring 실행 CMD에 등록한 OPENAI_API_KEY를 Python으로 전달
            String openAiKey = System.getenv("OPENAI_API_KEY");
            if (openAiKey != null && !openAiKey.isBlank()) {
                pb.environment().put("OPENAI_API_KEY", openAiKey);
            }

            Process process = pb.start();

            StringBuilder log = new StringBuilder();
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {

                String line;
                while ((line = br.readLine()) != null) {
                    log.append(line).append("\n");
                }
            }

            boolean finished = process.waitFor(10, TimeUnit.MINUTES);

            if (!finished) {
                process.destroyForcibly();
                return "AI 처리 시간이 너무 오래 걸려 중단되었습니다.\n\n[실행 로그]\n" + log;
            }

            int exitCode = process.exitValue();

            if (!Files.exists(resultFile)) {
                return "AI 결과 파일이 생성되지 않았습니다."
                        + "\naiDir=" + aiDir
                        + "\npythonExe=" + pythonExe
                        + "\nresultFile=" + resultFile
                        + "\ncommand=" + command
                        + "\nexitCode=" + exitCode
                        + "\n\n[실행 로그]\n" + log;
            }

            String result = Files.readString(resultFile, StandardCharsets.UTF_8).trim();

            if (result.isEmpty()) {
                return "AI 결과가 비어 있습니다."
                        + "\nexitCode=" + exitCode
                        + "\ncommand=" + command
                        + "\n\n[실행 로그]\n" + log;
            }

            return result;

        } catch (Exception e) {
            return "AI 응답 생성 실패:\n" + e;
        }
    }
}