# SlideGenius - AI Presentation & Analysis Platform

SlideGenius is an advanced AI-powered platform that transforms documents (PDF, DOCX, EPUB) into professional assets. It leverages **Google Gemini 2.0 & 1.5** models to generate **PowerPoint presentations**, **Deep Dive Summaries**, and **Expert Book Reviews**.

Built with **Python** and **Mesop**, it features a modern, reactive interface with robust error handling and "Smart AI" orchestration.

## 🚀 Key Features

### 1. AI Presentation Generator
*   **Automatic Slide Creation**: Converts raw text into structured slides.
*   **Smart Layout Engine**: Dynamically calculates text sizing and spacing for professional aesthetics.
*   **Template Support**: Upload your own `.pptx` template to maintain brand identity.

### 2. Syntopic Book Review (New!)
A cutting-edge "Multi-Agent Chain-of-Thought" system involving 3 specialized AI Agents:
*   **The Librarian**: Classifies the book's DNA (Genre, Tone, Audience).
*   **The Analyst**: Performs deep-dive analysis (using distinct logic for Fiction vs. Non-Fiction).
*   **The Editor**: Synthesizes a premium review with **Scoring (0-10)**, **Similar Books**, and **Key Mental Models**.

### 3. Deep Dive Summarizer
*   **Chain of Density**: Creates high-signal summaries that are dense with information but easy to read.
*   **PDF Report**: Exports summaries as clean, readable PDF documents.

### 4. Robust AI Engine ("Smart Switch")
*   **Strict Priority**: Prioritizes models in a specific order: `Gemini 3.0 Pro` > `3.0 Flash` > `2.5 Pro` > `2.5 Flash` > `2.0 Flash`...
*   **10-Cycle Retry**: If a model fails or is rate-limited, the system automatically retries with the next model, looping up to **10 times**.
*   **Smart Delay**: Enforces a minimum cooldown (20s) before reusing a model to prevent `429 Resource Exhausted` errors.

---

## 🛠 System Architecture

The application is modularized into three core engines:

1.  **`ai_engine.py`**: The brain. Handles all LLM interactions, model selection, and the retry loop.
2.  **`summarizer.py`**: Handles text extraction, the 3-Agent Review logic, and PDF generation.
3.  **`slide_engine.py`**: Handles PPTX manipulation and layout calculations.

**Frontend**: Powered by **Mesop** (`main.py`), utilizing reactive state management for a smooth user experience.

---

## 📦 Installation Guide

### Prerequisites
*   **OS**: Windows 10/11, macOS, or Linux.
*   **Python**: 3.10+ (Recommended Python 3.12).
*   **API Key**: A valid [Google AI Studio](https://aistudio.google.com/) key.

### Steps
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-repo/slide-genius.git
    cd slide-genius
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file in the root directory:
    ```env
    GOOGLE_API_KEY=your_actual_api_key_here
    ```

4.  **Run the App**:
    ```bash
    mesop main.py
    # Or using python directly:
    python main.py
    ```
    Access at: `http://localhost:32123`

---

## 📖 User Guide

### A. Generating Slides
1.  **Upload**: Drag & drop your source file (PDF/Word/Ebook).
2.  **Template (Optional)**: Upload a `.pptx` file to use as a base.
3.  **Topic**: Enter a specific focus topic.
4.  **Mode**: Choose "Detailed" for longer presentations.
5.  Click **"Generate Slides"**.
6.  Status Logs will show the progress. When done, click **"Download PowerPoint"**.

### B. Creating an Expert Review
1.  **Upload**: Upload your book file.
2.  Click **"Generate Expert Review"**.
3.  The system will activate the 3 Agents (Librarian -> Analyst -> Editor).
4.  Once complete, a **"Download Review PDF"** button will appear in the "Status & Output" panel.

### C. Summarizing Documents
1.  **Upload**: Upload your document.
2.  Click **"Generate Summary"**.
3.  Download the resulting PDF.

---

## ⚠️ Troubleshooting

*   **Red Error Box**: If an error appears, simply try a new action. The system auto-clears old errors.
*   **429 Resource Exhausted**: The "Smart Switch" system will handle this automatically. You might see "Sleeping..." logs; this is normal behavior to protect your quota.
*   **Stuck Spinner**: Refresh the browser (F5). The app uses Hot Reload and state might persist in the browser cache.

---
*Powered by Google Gemini Models (Flash 2.0, Pro 1.5, Pro 2.5).*
