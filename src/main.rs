mod api_client;
mod config;
mod conversation;
mod handler;
mod model_state;

use std::sync::Arc;
use teloxide::{
    dispatching::{HandlerExt, UpdateFilterExt},
    dptree,
    prelude::*,
};
use tokio::sync::Mutex;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    dotenvy::dotenv().ok();
    let cfg = config::Config::from_env()?;

    let bot = Bot::new(&cfg.telegram_token);

    let history = Arc::new(Mutex::new(conversation::ConversationHistory::new(20)));
    let model_state = Arc::new(Mutex::new(model_state::PerUserModel::new(
        &cfg.default_model,
    )));
    let api_client = Arc::new(api_client::ApiClient::new(&cfg.api_url));

    let handler = dptree::entry()
        .branch(
            Update::filter_message()
                .filter_command::<handler::Command>()
                .endpoint(handler::handle_command),
        )
        .branch(
            Update::filter_message()
                .endpoint(handler::handle_message),
        )
        .branch(
            Update::filter_callback_query()
                .endpoint(handler::handle_callback),
        );

    Dispatcher::builder(bot, handler)
        .dependencies(dptree::deps![history, model_state, api_client])
        .enable_ctrlc_handler()
        .build()
        .dispatch()
        .await;

    Ok(())
}
