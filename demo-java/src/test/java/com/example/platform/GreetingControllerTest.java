package com.example.platform;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(GreetingController.class)
class GreetingControllerTest {
    @Autowired MockMvc mvc;
    @Test void greetsDefaultName() throws Exception {
        mvc.perform(get("/api/greeting"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.message").value("Hello, world"));
    }
    @Test void greetsNamedUser() throws Exception {
        mvc.perform(get("/api/greeting").param("name", "platform"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.message").value("Hello, platform"));
    }
    @Test void rejectsBlankName() throws Exception {
        mvc.perform(get("/api/greeting").param("name", "   ")).andExpect(status().isBadRequest());
    }
    @Test void rejectsLongName() throws Exception {
        mvc.perform(get("/api/greeting").param("name", "x".repeat(65))).andExpect(status().isBadRequest());
    }
}
