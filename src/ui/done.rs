use cosmic::widget::{Column, Button, Text};
use crate::app::Message;

pub fn view() -> iced::Element<'static, Message> {
    Column::new()
        .spacing(20)
        .padding(40)
        .push(Text::new("✅ Installation Complete!").size(30))
        .push(Text::new("You can now reboot into NebulaOS."))
        .push(
            Button::new("Reboot Now")
                .on_press(Message::Quit)
                .style(cosmic::theme::Button::Primary),
        )
        .into()
}
