mod app;
mod ui;
mod backend;

use app::InstallerApp;

fn main() -> iced::Result {
    InstallerApp::run(iced::Settings::default())
}
