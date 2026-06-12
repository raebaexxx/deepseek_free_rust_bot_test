use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use teloxide::types::ChatId;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

pub struct ConversationHistory {
    max_messages: usize,
    storage: HashMap<ChatId, Vec<ChatMessage>>,
}

impl ConversationHistory {
    pub fn new(max_messages: usize) -> Self {
        Self {
            max_messages,
            storage: HashMap::new(),
        }
    }

    pub fn add_message(&mut self, chat_id: ChatId, msg: ChatMessage) {
        let entry = self.storage.entry(chat_id).or_default();
        entry.push(msg);
        if entry.len() > self.max_messages {
            *entry = entry.split_off(entry.len() - self.max_messages);
        }
    }

    pub fn get_history(&self, chat_id: &ChatId) -> Vec<ChatMessage> {
        self.storage.get(chat_id).cloned().unwrap_or_default()
    }

    pub fn clear(&mut self, chat_id: &ChatId) {
        self.storage.remove(chat_id);
    }
}
