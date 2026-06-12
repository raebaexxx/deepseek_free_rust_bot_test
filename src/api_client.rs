use crate::conversation::ChatMessage;
use futures_util::StreamExt;
use reqwest::Client;
use serde::Serialize;
use tokio::sync::mpsc::UnboundedSender;

#[derive(Debug, Serialize)]
struct ChatCompletionRequest {
    model: String,
    messages: Vec<ChatMessage>,
    stream: bool,
}

#[derive(Debug)]
pub enum ApiError {
    RequestFailed(String),
    ApiError(u16, String),
    StreamError(String),
}

impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ApiError::RequestFailed(e) => write!(f, "Request failed: {}", e),
            ApiError::ApiError(code, body) => write!(f, "API error {}: {}", code, body),
            ApiError::StreamError(e) => write!(f, "Stream error: {}", e),
        }
    }
}

pub struct ApiClient {
    client: Client,
    api_url: String,
}

impl ApiClient {
    pub fn new(api_url: impl Into<String>) -> Self {
        Self {
            client: Client::new(),
            api_url: api_url.into(),
        }
    }

    pub async fn stream_completion(
        &self,
        model: &str,
        messages: &[ChatMessage],
        tx: UnboundedSender<String>,
    ) -> Result<(), ApiError> {
        let body = ChatCompletionRequest {
            model: model.to_string(),
            messages: messages.to_vec(),
            stream: true,
        };

        let response = self
            .client
            .post(format!("{}/chat/completions", self.api_url))
            .json(&body)
            .send()
            .await
            .map_err(|e| ApiError::RequestFailed(e.to_string()))?;

        if !response.status().is_success() {
            let status = response.status().as_u16();
            let text = response.text().await.unwrap_or_default();
            return Err(ApiError::ApiError(status, text));
        }

        let mut stream = response.bytes_stream();
        let mut buf = Vec::new();

        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|e| ApiError::StreamError(e.to_string()))?;
            buf.extend_from_slice(&chunk);

            loop {
                let newline_pos = match buf.iter().position(|&b| b == b'\n') {
                    Some(pos) => pos,
                    None => break,
                };

                let line: Vec<u8> = buf.drain(..=newline_pos).collect();
                let line_str = String::from_utf8_lossy(&line).trim().to_string();

                if line_str.is_empty() {
                    continue;
                }

                if let Some(data) = line_str.strip_prefix("data: ") {
                    if data.trim() == "[DONE]" {
                        return Ok(());
                    }

                    if let Ok(value) = serde_json::from_str::<serde_json::Value>(data) {
                        if let Some(choices) = value["choices"].as_array() {
                            for choice in choices {
                                if let Some(content) = choice["delta"]["content"].as_str() {
                                    if !content.is_empty() {
                                        if tx.send(content.to_string()).is_err() {
                                            return Ok(());
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Ok(())
    }
}
