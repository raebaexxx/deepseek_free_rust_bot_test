use std::sync::Arc;
use teloxide::{
    prelude::*,
    types::{CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode},
    utils::command::BotCommands,
    Bot,
};
use tokio::sync::Mutex;

use crate::api_client::ApiClient;
use crate::conversation::{ChatMessage, ConversationHistory};
use crate::model_state::PerUserModel;

#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase")]
pub enum Command {
    #[command(description = "Start the bot")]
    Start,
    #[command(description = "Show help")]
    Help,
    #[command(description = "Reset conversation history")]
    Reset,
    #[command(description = "Choose AI model")]
    Model,
}

fn model_keyboard() -> InlineKeyboardMarkup {
    InlineKeyboardMarkup::new(vec![
        vec![InlineKeyboardButton::callback(
            "\u{1f4dd} deepseek-chat",
            "model:deepseek-chat",
        )],
        vec![InlineKeyboardButton::callback(
            "\u{1f9e0} deepseek-reasoner",
            "model:deepseek-reasoner",
        )],
        vec![InlineKeyboardButton::callback(
            "\u{1f310} deepseek-chat-search",
            "model:deepseek-chat-search",
        )],
        vec![InlineKeyboardButton::callback(
            "\u{1f52c} deepseek-expert",
            "model:deepseek-expert",
        )],
        vec![InlineKeyboardButton::callback(
            "\u{1f9ea} deepseek-v4-pro",
            "model:deepseek-v4-pro",
        )],
    ])
}

pub async fn handle_command(
    msg: Message,
    bot: Bot,
    cmd: Command,
    history: Arc<Mutex<ConversationHistory>>,
    _model_state: Arc<Mutex<PerUserModel>>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = msg.chat.id;

    match cmd {
        Command::Start => {
            bot.send_message(
                chat_id,
                "\u{1f44b} Привет! Я DeepSeek бот на Rust.\n\n\
                 Отправь мне любой вопрос, и я отвечу через DeepSeek AI.\n\n\
                 Доступные команды:\n\
                 /help — помощь\n\
                 /reset — сбросить историю диалога\n\
                 /model — выбрать модель",
            )
            .await?;
        }
        Command::Help => {
            bot.send_message(
                chat_id,
                "\u{1f4cb} Доступные команды:\n\
                 /start — начать\n\
                 /help — эта справка\n\
                 /reset — сбросить историю диалога\n\
                 /model — выбрать модель AI\n\n\
                 \u{1f4a1} Просто отправьте сообщение, чтобы начать диалог.",
            )
            .await?;
        }
        Command::Reset => {
            history.lock().await.clear(&chat_id);
            bot.send_message(chat_id, "\u{2705} История диалога сброшена.")
                .await?;
        }
        Command::Model => {
            bot.send_message(chat_id, "\u{1f916} Выберите модель:")
                .reply_markup(model_keyboard())
                .await?;
        }
    }

    Ok(())
}

pub async fn handle_message(
    msg: Message,
    bot: Bot,
    history: Arc<Mutex<ConversationHistory>>,
    model_state: Arc<Mutex<PerUserModel>>,
    api_client: Arc<ApiClient>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = msg.chat.id;
    let text = match msg.text() {
        Some(t) => t.to_string(),
        None => return Ok(()),
    };

    history.lock().await.add_message(
        chat_id,
        ChatMessage {
            role: "user".to_string(),
            content: text,
        },
    );

    let model = model_state.lock().await.get(&chat_id);
    let history_snapshot = history.lock().await.get_history(&chat_id);

    let sent = bot
        .send_message(chat_id, "\u{23f3} Думаю...")
        .await?;
    let msg_id = sent.id;

    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<String>();

    let api = api_client.clone();
    let m = model.clone();
    tokio::spawn(async move {
        let _ = api.stream_completion(&m, &history_snapshot, tx).await;
    });

    let mut accumulated = String::new();
    let mut last_update = tokio::time::Instant::now();
    let update_interval = tokio::time::Duration::from_millis(400);

    while let Some(chunk) = rx.recv().await {
        accumulated.push_str(&chunk);

        if last_update.elapsed() >= update_interval && !accumulated.is_empty() {
            let display = truncate_text(&accumulated, 4000);
            let _ = bot.edit_message_text(chat_id, msg_id, &display).await;
            last_update = tokio::time::Instant::now();
        }
    }

    if !accumulated.is_empty() {
        let display = truncate_text(&accumulated, 4096);
        bot.edit_message_text(chat_id, msg_id, &display).await?;
    } else {
        bot.edit_message_text(
            chat_id,
            msg_id,
            "\u{26a0}\u{fe0f} Не удалось получить ответ от DeepSeek. Попробуйте позже.",
        )
        .await?;
    }

    history.lock().await.add_message(
        chat_id,
        ChatMessage {
            role: "assistant".to_string(),
            content: accumulated,
        },
    );

    Ok(())
}

fn truncate_text(text: &str, max_len: usize) -> String {
    if text.len() <= max_len {
        text.to_string()
    } else {
        let truncated = &text[..max_len.saturating_sub(20)];
        format!("{truncated}\n\n... [\u{2702}\u{fe0f} сокращено]")
    }
}

pub async fn handle_callback(
    query: CallbackQuery,
    bot: Bot,
    model_state: Arc<Mutex<PerUserModel>>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let data = match &query.data {
        Some(d) => d.clone(),
        None => return Ok(()),
    };

    if let Some(model) = data.strip_prefix("model:") {
        let chat_id = match &query.message {
            Some(msg) => msg.chat.id,
            None => return Ok(()),
        };

        model_state.lock().await.set(chat_id, model.to_string());
        bot.answer_callback_query(query.id).await?;

        let escaped = model
            .replace('_', "\\_")
            .replace('-', "\\-")
            .replace('.', "\\.");
        let text = format!("\u{2705} Модель: `{escaped}`");

        if let Some(msg) = &query.message {
            bot.edit_message_text(chat_id, msg.id, text)
                .parse_mode(ParseMode::MarkdownV2)
                .await?;
        }
    }

    Ok(())
}
