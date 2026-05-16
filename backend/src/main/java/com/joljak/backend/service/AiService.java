package com.joljak.backend.service;

import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

@Service
public class AiService {

    public String generateAnswer(String userMessage) {
        try {
            Path backendDir = Path.of(System.getProperty("user.dir")).toAbsolutePath();
            Path projectRoot = backendDir.getParent();
            Path aiDir = projectRoot.resolve("ai");

            Path pythonExe = aiDir.resolve("venv").resolve("Scripts").resolve("python.exe");
            Path resultFile = aiDir.resolve("data").resolve("out.txt");

            Files.createDirectories(resultFile.getParent());
            Files.deleteIfExists(resultFile);

            ProcessBuilder pb = new ProcessBuilder(
                    pythonExe.toString(),
                    "RUN.py",
                    "--text",
                    userMessage,
                    "--output",
                    "data/out.txt"
            );

            pb.directory(aiDir.toFile());
            pb.redirectErrorStream(true);

            // Windows 한글/이모지 깨짐 방지
            pb.environment().put("PYTHONUTF8", "1");
            pb.environment().put("PYTHONIOENCODING", "utf-8");

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

            boolean finished = process.waitFor(5, TimeUnit.MINUTES);

            if (!finished) {
                process.destroyForcibly();
                return "AI 처리 시간이 너무 오래 걸려 중단되었습니다.\n\n[실행 로그]\n" + log;
            }

            int exitCode = process.exitValue();

            if (!Files.exists(resultFile)) {
                return "AI 결과 파일(out.txt)이 생성되지 않았습니다."
                        + "\naiDir=" + aiDir
                        + "\npythonExe=" + pythonExe
                        + "\nresultFile=" + resultFile
                        + "\nexitCode=" + exitCode
                        + "\n\n[실행 로그]\n" + log;
            }

            String result = Files.readString(resultFile, StandardCharsets.UTF_8).trim();

            if (result.isEmpty()) {
                return "AI 결과가 비어 있습니다."
                        + "\nexitCode=" + exitCode
                        + "\n\n[실행 로그]\n" + log;
            }

            return result;

        } catch (Exception e) {
            return "AI 응답 생성 실패:\n" + e;
        }
    }
}