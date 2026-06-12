use std::collections::HashMap;
use teloxide::types::ChatId;

pub struct PerUserModel {
    default: String,
    storage: HashMap<ChatId, String>,
}

impl PerUserModel {
    pub fn new(default: impl Into<String>) -> Self {
        Self {
            default: default.into(),
            storage: HashMap::new(),
        }
    }

    pub fn get(&self, chat_id: &ChatId) -> String {
        self.storage
            .get(chat_id)
            .cloned()
            .unwrap_or_else(|| self.default.clone())
    }

    pub fn set(&mut self, chat_id: ChatId, model: String) {
        self.storage.insert(chat_id, model);
    }
}
