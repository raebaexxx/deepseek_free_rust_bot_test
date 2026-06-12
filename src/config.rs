use std::env;

#[derive(Clone)]
pub struct Config {
    pub telegram_token: String,
    pub api_url: String,
    pub default_model: String,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        Ok(Self {
            telegram_token: env::var("TELOXIDE_TOKEN")
                .map_err(|_| "TELOXIDE_TOKEN must be set in .env".to_string())?,
            api_url: env::var("DEEPSEEK_API_URL")
                .unwrap_or_else(|_| "http://localhost:9655/v1".to_string()),
            default_model: env::var("DEFAULT_MODEL")
                .unwrap_or_else(|_| "deepseek-chat".to_string()),
        })
    }
}
