# Google ADK Projects 🚀

A curated collection of **hands-on projects, demos, and experiments** built with **Google’s Agent Development Kit (ADK)**.  
This repo is designed to help developers quickly learn, explore, and build with ADK — from simple standalone agents to advanced multi-agent workflows.

---

## 📚 What is ADK?

The **Agent Development Kit (ADK)** makes it easy to build intelligent, tool-using agents powered by Gemini models.  
With ADK you can:
- Create agents with clear roles and instructions
- Add built-in tools (Google Search, Code Execution, Vertex AI Search)
- Define custom function tools
- Orchestrate multi-agent workflows (sequential, parallel, loop)
- Integrate with external frameworks like **LangGraph** and **Gradio**

---

## 📂 Repo Structure

google-adk-projects/
├── simple_standalone_adk/      # Minimal agent + standalone Gradio chat app
│   ├── standalone_agent.py
│   ├── app_gradio_adk_chat.py
│   └── .env (API keys, not committed)
│
├── (coming soon) workflow_agents/   # Sequential, parallel, and loop workflows
├── (coming soon) multi_agent_demos/ # Collaboration and critique/refiner patterns
├── (coming soon) langgraph_hybrid/  # Hybrid ADK + LangGraph integrations
└── README.md

---

## 🚀 Getting Started

1. **Clone the repo**
   ```bash
   git clone https://github.com/your-username/google-adk-projects.git
   cd google-adk-projects

	2.	Pick a project folder
For example, the standalone demo:

cd simple_standalone_adk


	3.	Install dependencies

pip install -r requirements.txt


	4.	Add your API key
Create a .env file with:

GEMINI_API_KEY=your_api_key_here


🌟 Roadmap
	•	Simple standalone agent
	•	Gradio-based chat app
	•	Workflow agents (sequential, parallel, loop)
	•	Critique + Refiner pipelines
	•	Multi-agent collaboration demos
	•	Deployment-ready templates

⸻

📚 Learn More
	•	Google ADK Documentation
	•	Gemini API Docs
	•	Gradio Documentation
	•	LangGraph

⸻

✨ Why this Repo?
	•	📦 Ready-to-run projects — no adk web CLI required
	•	🔧 Shows both built-in tools and custom tools in action
	•	🤝 Demonstrates multi-agent collaboration
	•	🌐 Combines ADK with Gradio and LangGraph
	•	🧑‍💻 Great for learning, teaching, or starting new projects

⸻

📝 License

This repository is open-source under the Apache 2.0 License.
