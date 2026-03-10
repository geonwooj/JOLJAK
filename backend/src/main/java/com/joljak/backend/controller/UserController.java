package com.joljak.backend.controller;

import java.util.Map;

import com.joljak.backend.domain.user.User;
import io.jsonwebtoken.JwtException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.joljak.backend.config.JwtUtil;
import com.joljak.backend.service.AuthService;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final AuthService authService;
    private final JwtUtil jwtUtil;

    public UserController(AuthService authService, JwtUtil jwtUtil) {
        this.authService = authService;
        this.jwtUtil = jwtUtil;
    }

    @GetMapping("/me")
    public ResponseEntity<?> getMyInfo(
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body("Unauthorized");
            }

            String token = authHeader.substring("Bearer ".length()).trim();
            if (token.isEmpty()) {
                return ResponseEntity.status(401).body("Unauthorized");
            }

            String email = jwtUtil.extractEmail(token);
            User user = authService.findByEmail(email);

            return ResponseEntity.ok(
                    Map.of(
                            "name", user.getName(),
                            "email", user.getEmail(),
                            "createdAt", user.getCreatedAt()));
        } catch (JwtException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (RuntimeException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        }
    }

    @DeleteMapping("/me")
    public ResponseEntity<?> deleteMyAccount(
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body("Unauthorized");
            }

            String token = authHeader.substring("Bearer ".length()).trim();
            if (token.isEmpty()) {
                return ResponseEntity.status(401).body("Unauthorized");
            }

            String email = jwtUtil.extractEmail(token);
            authService.deleteUserByEmail(email);

            return ResponseEntity.ok("계정이 삭제되었습니다.");
        } catch (JwtException e) {
            e.printStackTrace();
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (RuntimeException e) {
            e.printStackTrace();
            return ResponseEntity.badRequest().body(e.getMessage());
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(500).body("계정 삭제 중 오류: " + e.getMessage());
        }
    }
}