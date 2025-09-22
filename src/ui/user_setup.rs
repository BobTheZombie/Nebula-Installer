use cosmic::widget::{Column, Button, Text};
use crate::app::Message;

pub fn view() -> iced::Element<'static, Message> {
    Column::new()
        .spacing(20)
        .padding(40)
        .push(Text::new("👤 User Setup").size(28))
        .push(Text::new("Create your account, hostname, and locale settings."))
        .push(
            Button::new("Back")
                .on_press(Message::Back)
                .style(cosmic::theme::Button::Secondary),
        )
        .push(
            Button::new("Next")
                .on_press(Message::Next)
                .style(cosmic::theme::Button::Primary),
        )
        .into()
}
