use cosmic::iced::{Application, Command, Element, Theme};
use crate::ui::*;

#[derive(Debug, Clone)]
pub enum Message {
    Next,
    Back,
    Quit,
}

pub struct InstallerApp {
    step: Step,
}

#[derive(Debug, Clone, Copy)]
pub enum Step {
    Welcome,
    Partition,
    UserSetup,
    Packages,
    Summary,
    Install,
    Done,
}

impl Application for InstallerApp {
    type Executor = iced::executor::Default;
    type Message = Message;
    type Flags = ();

    fn new(_flags: ()) -> (Self, Command<Self::Message>) {
        (InstallerApp { step: Step::Welcome }, Command::none())
    }

    fn title(&self) -> String {
        "Nebula Installer".to_string()
    }

    fn theme(&self) -> Theme {
        Theme::Light
    }

    fn update(&mut self, msg: Message) -> Command<Message> {
        match msg {
            Message::Next => {
                self.step = match self.step {
                    Step::Welcome => Step::Partition,
                    Step::Partition => Step::UserSetup,
                    Step::UserSetup => Step::Packages,
                    Step::Packages => Step::Summary,
                    Step::Summary => Step::Install,
                    Step::Install => Step::Done,
                    Step::Done => Step::Done,
                }
            }
            Message::Back => {
                self.step = match self.step {
                    Step::Partition => Step::Welcome,
                    Step::UserSetup => Step::Partition,
                    Step::Packages => Step::UserSetup,
                    Step::Summary => Step::Packages,
                    Step::Install => Step::Summary,
                    _ => self.step,
                }
            }
            Message::Quit => std::process::exit(0),
        }
        Command::none()
    }

    fn view(&self) -> Element<Message> {
        match self.step {
            Step::Welcome => welcome::view(),
            Step::Partition => partition::view(),
            Step::UserSetup => user_setup::view(),
            Step::Packages => packages::view(),
            Step::Summary => summary::view(),
            Step::Install => install::view(),
            Step::Done => done::view(),
        }
    }
}
