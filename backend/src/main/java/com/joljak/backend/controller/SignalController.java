package com.joljak.backend.controller;

import com.joljak.backend.service.Phase1ImageService;
import com.joljak.backend.service.SignalService;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class SignalController {

    private final SignalService signalService;
    private final Phase1ImageService phase1ImageService;

    public SignalController(SignalService signalService, Phase1ImageService phase1ImageService) {
        this.signalService = signalService;
        this.phase1ImageService = phase1ImageService;
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

    @GetMapping(value = "/signal/phase1-image", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<Resource> getPhase1Image(
            @RequestParam(required = false) Long chatId
    ) {
        return phase1ImageService.findPhase1Image(chatId)
                .map(resource -> ResponseEntity.ok()
                        .cacheControl(CacheControl.noCache())
                        .contentType(MediaType.IMAGE_PNG)
                        .body(resource))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

}
