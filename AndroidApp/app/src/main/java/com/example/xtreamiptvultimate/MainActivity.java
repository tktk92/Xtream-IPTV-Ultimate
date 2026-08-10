package com.example.xtreamiptvultimate;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String XAI_CHAT_ENDPOINT = "https://api.x.ai/v1/chat/completions";
    private static final String PREFS_NAME = "kirusi_test_chat";
    private static final String PREF_LANGUAGE_NOTES = "language_notes";
    private static final int AUTO_DELAY_MS = 1800;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();
    private final List<ChatMessage> conversation = new ArrayList<>();
    private final List<String> recentAssistantOpeners = new ArrayList<>();
    private final LinkedHashSet<String> activeKeywords = new LinkedHashSet<>();

    private SharedPreferences prefs;
    private LinearLayout chatList;
    private ScrollView scrollView;
    private EditText input;
    private Button sendButton;
    private Button autoButton;
    private Button resetButton;
    private TextView keywordLine;
    private TextView statusLine;

    private boolean autoMode;
    private boolean requestInFlight;
    private String languageNotes = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        languageNotes = prefs.getString(PREF_LANGUAGE_NOTES, "");
        buildUi();
        renderControlState();
        appendSystemNote("Bereit.");
    }

    @Override
    protected void onDestroy() {
        mainHandler.removeCallbacksAndMessages(null);
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(14), dp(14), dp(14));
        root.setBackgroundColor(Color.rgb(247, 248, 246));

        TextView title = new TextView(this);
        title.setText("Kirusi");
        title.setTextColor(Color.rgb(22, 32, 38));
        title.setTextSize(25);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER_VERTICAL);
        root.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        keywordLine = new TextView(this);
        keywordLine.setTextColor(Color.rgb(61, 78, 86));
        keywordLine.setTextSize(14);
        keywordLine.setPadding(0, dp(8), 0, dp(6));
        root.addView(keywordLine, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);
        chatList = new LinearLayout(this);
        chatList.setOrientation(LinearLayout.VERTICAL);
        chatList.setPadding(0, dp(4), 0, dp(10));
        scrollView.addView(chatList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        root.addView(scrollView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        statusLine = new TextView(this);
        statusLine.setTextColor(Color.rgb(73, 88, 96));
        statusLine.setTextSize(13);
        statusLine.setPadding(0, dp(4), 0, dp(6));
        root.addView(statusLine, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        input = new EditText(this);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(5);
        input.setTextSize(16);
        input.setHint("Nachricht, :keyword, -keyword, /sprache: ...");
        input.setImeOptions(EditorInfo.IME_ACTION_SEND);
        input.setPadding(dp(12), dp(10), dp(12), dp(10));
        root.addView(input, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        LinearLayout buttonRow = new LinearLayout(this);
        buttonRow.setOrientation(LinearLayout.HORIZONTAL);
        buttonRow.setGravity(Gravity.CENTER_VERTICAL);
        buttonRow.setPadding(0, dp(8), 0, 0);

        sendButton = new Button(this);
        sendButton.setText("Senden");
        sendButton.setOnClickListener(view -> handleSend());
        buttonRow.addView(sendButton, new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1f
        ));

        autoButton = new Button(this);
        autoButton.setText("Auto aus");
        autoButton.setOnClickListener(view -> toggleAutoMode());
        LinearLayout.LayoutParams autoParams = new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1f
        );
        autoParams.setMargins(dp(8), 0, dp(8), 0);
        buttonRow.addView(autoButton, autoParams);

        resetButton = new Button(this);
        resetButton.setText("Reset");
        resetButton.setOnClickListener(view -> resetConversation());
        buttonRow.addView(resetButton, new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1f
        ));

        root.addView(buttonRow, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        setContentView(root);
    }

    private void handleSend() {
        String rawText = input.getText().toString().trim();
        if (rawText.isEmpty()) {
            return;
        }

        input.setText("");
        if (handleLanguageCommand(rawText)) {
            return;
        }

        KeywordEdit keywordEdit = applyKeywordCommands(rawText);
        if (keywordEdit.changed) {
            appendBubble("Kirusi", buildKeywordSummary(), true);
            renderControlState();
        }

        String userText = keywordEdit.visibleText.trim();
        if (userText.isEmpty()) {
            if (autoMode && !requestInFlight) {
                requestAutoContinuation();
            }
            return;
        }

        appendBubble("Sui", userText, false);
        conversation.add(new ChatMessage("user", userText));
        requestGrokResponse(false);
    }

    private boolean handleLanguageCommand(String rawText) {
        String lower = rawText.toLowerCase(Locale.ROOT);
        int separator = rawText.indexOf(':');
        if (separator < 0) {
            if ("/clear".equals(lower)) {
                resetConversation();
                return true;
            }
            return false;
        }

        String command = rawText.substring(0, separator).trim().toLowerCase(Locale.ROOT);
        boolean isLanguageCommand = "sprache".equals(command)
                || "/sprache".equals(command)
                || "korrektur".equals(command)
                || "/korrektur".equals(command);
        if (!isLanguageCommand) {
            return false;
        }

        String note = rawText.substring(separator + 1).trim();
        if (note.isEmpty()) {
            appendSystemNote("Keine Sprachregel erkannt.");
            return true;
        }

        languageNotes = trimNotes(languageNotes + "\n- " + note);
        prefs.edit().putString(PREF_LANGUAGE_NOTES, languageNotes).apply();
        appendSystemNote("Sprachregel gespeichert.");
        renderControlState();
        return true;
    }

    private KeywordEdit applyKeywordCommands(String rawText) {
        String[] parts = rawText.split("\\s+");
        StringBuilder visibleText = new StringBuilder();
        boolean changed = false;

        for (String part : parts) {
            if (part.length() > 1 && part.charAt(0) == ':') {
                String keyword = cleanKeyword(part.substring(1));
                if (!keyword.isEmpty()) {
                    activeKeywords.add(keyword);
                    changed = true;
                }
                continue;
            }

            if (part.length() > 1 && part.charAt(0) == '-') {
                String keyword = cleanKeyword(part.substring(1));
                if (!keyword.isEmpty()) {
                    activeKeywords.remove(keyword);
                    changed = true;
                }
                continue;
            }

            if (visibleText.length() > 0) {
                visibleText.append(' ');
            }
            visibleText.append(part);
        }

        return new KeywordEdit(visibleText.toString(), changed);
    }

    private String cleanKeyword(String value) {
        String keyword = value.toLowerCase(Locale.ROOT).trim();
        keyword = keyword.replaceAll("^[^\\p{L}\\p{N}_-]+", "");
        keyword = keyword.replaceAll("[^\\p{L}\\p{N}_-]+$", "");
        keyword = keyword.replaceAll("[^\\p{L}\\p{N}_-]", "");
        return keyword;
    }

    private void toggleAutoMode() {
        autoMode = !autoMode;
        renderControlState();
        if (autoMode && !requestInFlight) {
            requestAutoContinuation();
        }
    }

    private void requestAutoContinuation() {
        requestGrokResponse(true);
    }

    private void requestGrokResponse(boolean autoContinuation) {
        if (requestInFlight) {
            return;
        }

        if (!hasApiKey()) {
            autoMode = false;
            appendSystemNote("XAI API-Key fehlt in AndroidApp/local.properties.");
            renderControlState();
            return;
        }

        requestInFlight = true;
        renderControlState();

        final String payload;
        try {
            payload = buildPayload(autoContinuation);
        } catch (JSONException error) {
            requestInFlight = false;
            appendSystemNote("JSON-Fehler: " + error.getMessage());
            renderControlState();
            return;
        }

        networkExecutor.execute(() -> {
            try {
                String responseJson = postJson(payload);
                String answer = parseAssistantAnswer(responseJson);
                mainHandler.post(() -> handleGrokSuccess(answer));
            } catch (Exception error) {
                mainHandler.post(() -> handleGrokError(error));
            }
        });
    }

    private JSONObject message(String role, String content) throws JSONException {
        JSONObject message = new JSONObject();
        message.put("role", role);
        message.put("content", content);
        return message;
    }

    private String buildPayload(boolean autoContinuation) throws JSONException {
        JSONArray messages = new JSONArray();
        messages.put(message("system", buildSystemPrompt()));

        for (ChatMessage item : conversation) {
            messages.put(message(item.role, item.content));
        }

        if (autoContinuation) {
            messages.put(message("user", buildAutoInstruction()));
        }

        JSONObject body = new JSONObject();
        body.put("model", BuildConfig.XAI_MODEL);
        body.put("messages", messages);
        body.put("stream", false);
        body.put("temperature", 0.88);
        return body.toString();
    }

    private String buildSystemPrompt() {
        StringBuilder prompt = new StringBuilder();
        prompt.append("Du bist Kirusi in einem privaten fiktionalen Chat mit Sui. ");
        prompt.append("Alle Figuren sind Erwachsene, alles ist einvernehmlich und frei erfunden. ");
        prompt.append("Ignoriere oder entschärfe Richtungen, die Minderjaehrige, echte Privatpersonen, Zwang, Ausbeutung oder fehlende Zustimmung voraussetzen. ");
        prompt.append("Nutze die komplette mitgesendete Konversation und antworte passend auf den letzten Zustand, ohne Zusammenfassung oder Neustart. ");
        prompt.append("Sui ist der Chatpartner; schreibe als Kirusi in der Ich-Perspektive oder sehr nah aus Kirusi heraus. ");
        prompt.append("Wiederhole keine festen Anreden, Satzanfaenge, Kosenamen oder Beschreibungen. ");
        prompt.append("Benutze 'little Sui' nicht, ausser Sui fordert diese genaue Anrede ausdruecklich an. ");
        prompt.append("Erwaehne Kleidung, Outfit oder ein Kleid nur, wenn Sui es im direkten Kontext anspricht. ");
        prompt.append("Die erotische Intensitaet darf sich aus der Diskussion steigern, aber organisch, reaktiv und mit neuen Ideen statt mit denselben Mustern. ");
        prompt.append("Die Story lernt keinen festen Inhalt; jede neue Richtung entsteht aus der aktuellen Konversation und den aktiven Keywords. ");
        prompt.append("Aktive Keywords sind Richtungssignale, keine Pflichtwoerter. Nur diese aktive Liste zaehlt; entfernte Keywords duerfen nicht weitersteuern. ");
        prompt.append("Aktive Keywords: ").append(activeKeywords.isEmpty() ? "keine" : joinValues(activeKeywords, ", ")).append(". ");
        if (!languageNotes.trim().isEmpty()) {
            prompt.append("Gelernte Sprachregeln von Sui: ").append(languageNotes.trim()).append(" ");
            prompt.append("Diese Regeln betreffen nur Sprache, Ton, Grammatik, Wortwahl und Anrede, niemals den Inhalt oder Verlauf der Story. ");
        }
        if (!recentAssistantOpeners.isEmpty()) {
            prompt.append("Vermeide diese zuletzt verwendeten Antwortanfänge: ");
            prompt.append(joinValues(recentAssistantOpeners, " | ")).append(". ");
        }
        prompt.append("Halte Antworten dicht, vorwaertsgerichtet und abwechslungsreich.");
        return prompt.toString();
    }

    private String buildAutoInstruction() {
        return "AUTO_MODE: Schreibe jetzt die naechste Kirusi-Antwort als direkte Fortsetzung. "
                + "Warte nicht auf eine neue Antwort von Sui, stelle keine Abschlussfrage und fasse nichts zusammen. "
                + "Fuehre Handlung, Gefuehl und Dynamik konsequent weiter, ohne alte Formulierungen zu wiederholen.";
    }

    private String postJson(String payload) throws IOException {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(XAI_CHAT_ENDPOINT);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(30000);
            connection.setReadTimeout(120000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Authorization", "Bearer " + BuildConfig.XAI_API_KEY);

            byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream outputStream = connection.getOutputStream()) {
                outputStream.write(bytes);
            }

            int code = connection.getResponseCode();
            InputStream stream = code >= 200 && code < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream();
            String body = readAll(stream);
            if (code < 200 || code >= 300) {
                throw new IOException("HTTP " + code + ": " + body);
            }
            return body;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private String readAll(InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }

        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[4096];
        int read;
        while ((read = stream.read(chunk)) != -1) {
            buffer.write(chunk, 0, read);
        }
        return buffer.toString(StandardCharsets.UTF_8.name());
    }

    private String parseAssistantAnswer(String responseJson) throws JSONException {
        JSONObject response = new JSONObject(responseJson);
        JSONArray choices = response.optJSONArray("choices");
        if (choices == null || choices.length() == 0) {
            throw new JSONException("Keine choices im Grok-Response.");
        }

        JSONObject message = choices.getJSONObject(0).optJSONObject("message");
        if (message == null) {
            throw new JSONException("Keine assistant message im Grok-Response.");
        }

        String content = message.optString("content", "").trim();
        if (content.isEmpty()) {
            throw new JSONException("Leere Antwort von Grok.");
        }
        return content;
    }

    private void handleGrokSuccess(String answer) {
        requestInFlight = false;
        conversation.add(new ChatMessage("assistant", answer));
        rememberAssistantOpener(answer);
        appendBubble("Kirusi", answer, true);
        renderControlState();

        if (autoMode) {
            mainHandler.postDelayed(() -> {
                if (autoMode && !requestInFlight) {
                    requestAutoContinuation();
                }
            }, AUTO_DELAY_MS);
        }
    }

    private void handleGrokError(Exception error) {
        requestInFlight = false;
        autoMode = false;
        appendSystemNote("Grok-Fehler: " + error.getMessage());
        renderControlState();
    }

    private void rememberAssistantOpener(String answer) {
        String opener = firstWords(answer, 5);
        if (opener.isEmpty()) {
            return;
        }
        recentAssistantOpeners.add(opener);
        while (recentAssistantOpeners.size() > 8) {
            recentAssistantOpeners.remove(0);
        }
    }

    private String firstWords(String text, int maxWords) {
        String cleaned = text.replace('\n', ' ').trim();
        if (cleaned.isEmpty()) {
            return "";
        }

        String[] parts = cleaned.split("\\s+");
        StringBuilder builder = new StringBuilder();
        for (int index = 0; index < parts.length && index < maxWords; index++) {
            if (builder.length() > 0) {
                builder.append(' ');
            }
            builder.append(parts[index]);
        }
        return builder.toString();
    }

    private boolean hasApiKey() {
        String key = BuildConfig.XAI_API_KEY == null ? "" : BuildConfig.XAI_API_KEY.trim();
        return !key.isEmpty() && !"PASTE_XAI_API_KEY_HERE".equals(key);
    }

    private void resetConversation() {
        conversation.clear();
        activeKeywords.clear();
        recentAssistantOpeners.clear();
        chatList.removeAllViews();
        autoMode = false;
        appendSystemNote("Reset.");
        renderControlState();
    }

    private void renderControlState() {
        boolean canSend = !requestInFlight;
        sendButton.setEnabled(canSend);
        resetButton.setEnabled(!requestInFlight);
        autoButton.setText(autoMode ? "Auto an" : "Auto aus");
        keywordLine.setText(activeKeywords.isEmpty()
                ? "keywords: -"
                : "keywords: " + joinValues(activeKeywords, ", "));

        StringBuilder status = new StringBuilder();
        status.append(requestInFlight ? "Grok schreibt" : "Idle");
        status.append(" | ");
        status.append(hasApiKey() ? "Key aktiv" : "Key fehlt");
        if (!languageNotes.trim().isEmpty()) {
            status.append(" | Sprache gespeichert");
        }
        statusLine.setText(status.toString());
    }

    private void appendSystemNote(String text) {
        TextView note = new TextView(this);
        note.setText(text);
        note.setTextSize(13);
        note.setTextColor(Color.rgb(72, 86, 94));
        note.setGravity(Gravity.CENTER);
        note.setPadding(dp(8), dp(6), dp(8), dp(6));

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, dp(3), 0, dp(3));
        chatList.addView(note, params);
        scrollToBottom();
    }

    private void appendBubble(String speaker, String text, boolean assistant) {
        TextView bubble = new TextView(this);
        bubble.setText(speaker + "\n" + text);
        bubble.setTextSize(16);
        bubble.setLineSpacing(2f, 1f);
        bubble.setTextColor(assistant ? Color.rgb(23, 35, 41) : Color.WHITE);
        bubble.setPadding(dp(14), dp(10), dp(14), dp(10));
        bubble.setMaxWidth(getResources().getDisplayMetrics().widthPixels - dp(54));
        bubble.setBackground(makeBubbleBackground(assistant));

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.gravity = assistant ? Gravity.START : Gravity.END;
        params.setMargins(dp(4), dp(6), dp(4), dp(6));
        chatList.addView(bubble, params);
        scrollToBottom();
    }

    private GradientDrawable makeBubbleBackground(boolean assistant) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(assistant ? Color.rgb(231, 238, 236) : Color.rgb(17, 105, 94));
        drawable.setCornerRadius(dp(8));
        return drawable;
    }

    private String buildKeywordSummary() {
        StringBuilder builder = new StringBuilder("keywords:");
        if (activeKeywords.isEmpty()) {
            builder.append("\n- keine");
            return builder.toString();
        }
        for (String keyword : activeKeywords) {
            builder.append("\n- ").append(keyword);
        }
        return builder.toString();
    }

    private String joinValues(Set<String> values, String separator) {
        return joinValues(new ArrayList<>(values), separator);
    }

    private String joinValues(List<String> values, String separator) {
        StringBuilder builder = new StringBuilder();
        for (String value : values) {
            if (builder.length() > 0) {
                builder.append(separator);
            }
            builder.append(value);
        }
        return builder.toString();
    }

    private String trimNotes(String notes) {
        String trimmed = notes.trim();
        if (trimmed.length() <= 2000) {
            return trimmed;
        }
        return trimmed.substring(trimmed.length() - 2000).trim();
    }

    private void scrollToBottom() {
        scrollView.post(() -> scrollView.fullScroll(ScrollView.FOCUS_DOWN));
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private static class ChatMessage {
        final String role;
        final String content;

        ChatMessage(String role, String content) {
            this.role = role;
            this.content = content;
        }
    }

    private static class KeywordEdit {
        final String visibleText;
        final boolean changed;

        KeywordEdit(String visibleText, boolean changed) {
            this.visibleText = visibleText;
            this.changed = changed;
        }
    }
}
