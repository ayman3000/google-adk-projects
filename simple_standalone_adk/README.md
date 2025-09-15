# Simple Standalone ADK Project 🚀

This project demonstrates how to build and run agents with **Google’s Agent Development Kit (ADK)** **without** using the `adk web` command line.  
It includes both a minimal standalone agent and a Gradio-based chat app for interactive exploration.

---

## 📂 Project Structure

simple_standalone_adk/
├── .env                       # Environment variables (e.g., GEMINI_API_KEY)
├── standalone_agent.py        # Minimal ADK agent that runs in terminal
└── app_gradio_adk_chat.py     # Standalone Gradio app for chatting with the agent

---

## ⚙️ Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/google-adk-projects.git
   cd google-adk-projects/simple_standalone_adk

	2.	Install dependencies

pip install -r requirements.txt


	3.	Set your API key
Create a .env file in the project folder:

GEMINI_API_KEY=your_api_key_here

You can also provide the key inside the Gradio UI if you don’t want to store it in .env.

⸻

▶️ Running the Projects

🖥️ Standalone Agent (terminal)

Run a simple agent directly from the terminal:

python standalone_agent.py

Example interaction:

User: write a python program that calculates the factorial of a number
Agent: 
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
print(factorial(5))  # 120


⸻

🌐 Gradio Chat App

Launch a web-based chat interface powered by ADK:

python app_gradio_adk_chat.py

Then open the provided URL in your browser (default: http://127.0.0.1:7860).

Features:
	•	Start/reset chat sessions with one click
	•	Enter your Gemini API key in the UI or use .env
	•	Choose model (gemini-2.0-flash, gemini-2.0-flash-lite, gemini-2.0-pro)
	•	Stream responses token by token when available

⸻

📚 Learn More
	•	Google ADK Documentation
	•	Gradio Documentation

⸻

✨ Why This Project?
	•	🔹 Runs fully standalone (no adk web needed)
	•	🔹 Minimal, clear code examples to learn ADK basics
	•	🔹 Ready-to-use Gradio interface for fast experimentation
	•	🔹 Great starting point for building your own AI-powered apps