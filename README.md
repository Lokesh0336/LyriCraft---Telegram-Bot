# LyriCraft - Telegram Bot 🎧

A Python-based Telegram bot that allows users to search for songs and download their audio directly from Spotify. This project showcases my skills in API integration, bot development, and creating a user-friendly application.

---

## 🚀 Key Features

* **🎧 Song Search:** Instantly search for songs by title or artist.
* **⬇️ Direct Download:** Download the audio file directly within the Telegram chat.
* **🎵 Spotify API Integration:** Utilizes the Spotify API for a wide music library.
* **🤖 Pagination:** Seamlessly browse through search results with "next" and "back" buttons.
* **✅ Multiple Downloads:** Download individual tracks or a full page of songs at once.

---

## 🖼️ Bot Profile

![LyriCraft Bot Profile Picture](https://i.ibb.co/3YNx3kDb/Chat-GPT-Image-Jul-26-2025-01-31-57-PM.png)

---

## 💻 Technologies Used

* **Python:** The core programming language.
* **`python-telegram-bot`:** For handling the bot's interactions and commands.
* **`spotipy`:** A lightweight Python library for the Spotify Web API.
* **`spotdl`:** For downloading audio from Spotify.
* **`python-dotenv`:** To securely manage environment variables like API keys.

---

## ▶️ Getting Started

Follow these steps to set up and run the bot locally on your machine.

### Prerequisites

* Python 3.8+
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
* Spotify API credentials from the [Spotify Developer Dashboard](https://developer.spotify.com/)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Lokesh0336/LyriCraft-Bot.git](https://github.com/Lokesh0336/LyriCraft-Bot.git)
    cd LyriCraft-Bot
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a file named `.env` in the root directory and add your credentials:
    ```
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"
    SPOTIFY_CLIENT_ID="YOUR_SPOTIFY_CLIENT_ID_HERE"
    SPOTIFY_CLIENT_SECRET="YOUR_SPOTIFY_CLIENT_SECRET_HERE"
    ```

5.  **Run the bot:**
    ```bash
    python bot.py
    ```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🌐 Contact

Created with ❤️ by **Lokesh Ragutla**

* **GitHub:** [https://github.com/Lokesh0336](https://github.com/Lokesh0336)
* **LinkedIn:** [Your LinkedIn Profile](https://www.linkedin.com/in/lokesh-ragutla-a8352724a)