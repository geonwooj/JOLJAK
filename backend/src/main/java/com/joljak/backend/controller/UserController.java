package com.joljak.backend.controller;

import java.util.Map;

import com.joljak.backend.domain.user.User;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.joljak.backend.config.JwtUtil;
import com.joljak.backend.service.AuthService;

@CrossOrigin(origins = {
    "http://127.0.0.1:5500",
    "http://localhost:5500"
})
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
        @RequestHeader("Authorization") String authHeader
    ) {
        String token = authHeader.replace("Bearer ", "");
        String email = jwtUtil.extractEmail(token);

        User user = authService.findByEmail(email);

        return ResponseEntity.ok(
            Map.of(
                "name", user.getName(),
                "email", user.getEmail()
            )
        );
    }
}
