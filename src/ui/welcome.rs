use cosmic::widget::{Column, Button, Text};
use crate::app::Message;

pub fn view() -> iced::Element<'static, Message> {
    Column::new()
        .spacing(20)
        .padding(40)
        .push(Text::new("🌌 Welcome to NebulaOS Installer").size(32))
        .push(Text::new("Get started with installation or explore options."))
        .push(
            Button::new("Start Install")
                .on_press(Message::Next)
                .style(cosmic::theme::Button::Primary),
        )
        .push(
            Button::new("Quit")
                .on_press(Message::Quit)
                .style(cosmic::theme::Button::Secondary),
        )
        .into()
}
