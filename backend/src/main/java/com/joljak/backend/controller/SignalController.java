package com.joljak.backend.controller;

import com.joljak.backend.service.SignalService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class SignalController {

    private final SignalService signalService;

    public SignalController(SignalService signalService) {
        this.signalService = signalService;
    }

    @PostMapping("/signal/{id}")
    public ResponseEntity<String> receiveSignal(
            @PathVariable String id,
            @RequestParam(value = "chatId", required = false) Long chatId
    ) {
        signalService.update(id, chatId);
        return ResponseEntity.ok("received");
    }

    @GetMapping("/signal/status")
    public ResponseEntity<Map<String, Object>> getStatus(
            @RequestParam(value = "chatId", required = false) Long chatId
    ) {
        return ResponseEntity.ok(signalService.getStatus(chatId));
    }
}
