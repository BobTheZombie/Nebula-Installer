use cosmic::widget::{Column, ProgressBar, Text};
use crate::app::Message;

pub fn view() -> iced::Element<'static, Message> {
    Column::new()
        .spacing(20)
        .padding(40)
        .push(Text::new("🚀 Installing NebulaOS...").size(28))
        .push(ProgressBar::new(0.0..=100.0, 42.0))
        .push(Text::new("Copying files, installing packages..."))
        .into()
}
