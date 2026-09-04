# Contributing to RoboLab 🤖

Thank you for your interest in contributing to **RoboLab**! We welcome contributions from students, researchers, developers, and open-source enthusiasts.

---

## 🚀 Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/your-username/SQL_PBL.git
   cd SQL_PBL
   ```
3. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux / macOS
   source venv/bin/activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Set up your environment configuration**:
   ```bash
   cp .env.example .env
   ```
   *(By default, RoboLab runs out-of-the-box using the embedded SQLite database if MySQL is not detected).*

6. **Run the local development server**:
   ```bash
   python app.py
   # Or using Python Launcher on Windows:
   py app.py
   ```

---

## 🛠️ Contribution Guidelines

### 1. Branching Workflow
- Create a feature branch with a descriptive name:
  ```bash
  git checkout -b feature/your-feature-name
  # Or for bug fixes:
  git checkout -b fix/issue-description
  ```

### 2. Code Style & Standards
- **Python Backend**: Follow PEP 8 guidelines. Keep database queries clean and parameterized to prevent SQL injection.
- **Frontend**: Keep the UI clean, minimalist, and lightweight. Ensure any new static assets remain 100% offline-compatible.
- **Database**: When modifying schema or adding queries, ensure compatibility with both MySQL (`database/schema.sql`) and SQLite (`database/robolab.db`).

### 3. Submitting a Pull Request (PR)
- Commit your changes with clear, concise commit messages.
- Push your branch to your fork:
  ```bash
  git push origin feature/your-feature-name
  ```
- Open a Pull Request against the `master` or `main` branch with a clear summary of your changes and test results.

---

## 🐛 Reporting Bugs & Requesting Features
If you discover a bug or have an idea for a feature, please open an Issue on GitHub with:
* A clear description of the bug or requested feature.
* Steps to reproduce (for bugs).
* Relevant logs or screenshots.
