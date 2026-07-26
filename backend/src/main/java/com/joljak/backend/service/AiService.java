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

    public String generateAnswer(String userMessage) {
        return generateAnswer(userMessage, null, null);
    }

    public String generateAnswer(String userMessage, String savedFilePath, Long chatId) {
        try {
            Path backendDir = Path.of(System.getProperty("user.dir")).toAbsolutePath();
            Path projectRoot = backendDir.getParent();
            Path aiDir = projectRoot.resolve("ai");

            Path pythonExe = resolvePythonExe(aiDir);

            String outputFileName = chatId == null
                    ? "out.txt"
                    : "out_" + chatId + ".txt";

            Path resultFile = aiDir.resolve("data").resolve(outputFileName);

            Files.createDirectories(resultFile.getParent());
            Files.deleteIfExists(resultFile);

            List<String> command = new ArrayList<>();

            command.add(pythonExe.toString());
            command.add("RUN.py");

            boolean hasPdf = savedFilePath != null
                    && !savedFilePath.isBlank()
                    && savedFilePath.toLowerCase().endsWith(".pdf");

            if (hasPdf) {
                command.add("--pdf");
                command.add(savedFilePath);
            } else if (userMessage != null && !userMessage.isBlank()) {
                command.add("--text");
                command.add(userMessage);
            } else {
                throw new IllegalArgumentException("AI에 전달할 텍스트 또는 PDF 파일이 없습니다.");
            }

            command.add("--output");
            command.add("data/" + outputFileName);

            ProcessBuilder pb = new ProcessBuilder(command);
            pb.directory(aiDir.toFile());
            pb.redirectErrorStream(true);

            pb.environment().put("PYTHONUTF8", "1");
            pb.environment().put("PYTHONIOENCODING", "utf-8");

            if (chatId != null) {
                pb.environment().put("CHAT_ID", String.valueOf(chatId));
                pb.environment().put("WEB_LINK", "http://localhost:8080/api/signal/");
            }

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

    private Path resolvePythonExe(Path aiDir) {
        Path windowsVenvPython = aiDir.resolve("venv").resolve("Scripts").resolve("python.exe");
        if (Files.exists(windowsVenvPython)) {
            return windowsVenvPython;
        }

        Path linuxVenvPython = aiDir.resolve("venv").resolve("bin").resolve("python");
        if (Files.exists(linuxVenvPython)) {
            return linuxVenvPython;
        }

        Path linuxPython3 = Path.of("/usr/bin/python3");
        if (Files.exists(linuxPython3)) {
            return linuxPython3;
        }

        return Path.of("python3");
    }
}