# Tiktok_clone_backend

FastAPI backend server for Tiktok Backend application.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- MySQL (optional, for database)

### Setup Steps

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd tiktok_clone_backend
   ```

2. **Create virtual environment** (IMPORTANT: Do this FIRST)
   ```bash
   python -m venv .venv
   ```

3. **Activate virtual environment**
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Create .env file**
   Create `.env` file in root directory with:
   ```env
   DATABASE_URL=mysql+pymysql://user:password@localhost:3306/tiktok_clone_backend_db
   SECRET_KEY=your-secret-key-here-minimum-32-characters
   ```

6. **Run the application**
   
   **Development mode (with auto-reload):**
   ```bash
   # Option 1: FastAPI CLI (recommended)
   fastapi dev app/main.py
   
   # Option 2: Uvicorn
   uvicorn app.main:app --reload
   ```
   
   **Production mode:**
   ```bash
   # Option 1: FastAPI CLI
   fastapi run app/main.py
   
   # Option 2: Uvicorn with workers
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

7. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc

## 📚 Documentation

- [Setup Guide](./docs/SETUP.md) - Detailed setup instructions for new developers
- [Dependencies Guide](./docs/DEPENDENCIES.md) - How to manage external libraries

## ⚠️ Important Notes

- **Always activate virtual environment before working**
- **Create venv BEFORE installing libraries** (not the other way around)
- **Never commit venv/** folder (already in .gitignore)
- **Always commit requirements.txt** when adding new libraries

## 🛠️ Development

```bash
# Activate venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run development server (choose one)
fastapi dev app/main.py          # FastAPI CLI (recommended, auto-reload)
uvicorn app.main:app --reload    # Uvicorn (traditional)

# Run tests
pytest
```

## 🚀 Production Deployment

```bash
# Option 1: FastAPI CLI
fastapi run app/main.py

# Option 2: Uvicorn with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Option 3: With custom configuration
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

## 📦 Project Structure

```
tiktok_clone_backend/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── core/             # Core configurations
│   │   ├── config.py     # Settings and environment variables
│   │   ├── security.py   # Security utilities
│   │   └── exceptions/   # Custom exceptions and handlers
│   ├── db/               # Database setup
│   │   ├── base.py       # SQLAlchemy Base
│   │   └── database.py   # Database connection and session
│   ├── modules/          # Feature modules
│   │   ├── auth/         # Authentication module
│   │   └── users/        # Users module
│   │       ├── models.py      # SQLAlchemy models
│   │       ├── schemas.py     # Pydantic schemas
│   │       ├── repository.py  # Database operations
│   │       ├── service.py     # Business logic
│   │       └── router.py      # API endpoints
│   └── enum/             # Enums and constants
├── alembic/              # Database migrations
├── docs/                 # Documentation
├── tests/                # Test files
├── .env                  # Environment variables (create this)
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Technologies

- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migrations
- **Pydantic** - Data validation and settings
- **Uvicorn** - ASGI server
- **PyMySQL** - MySQL database driver

## 📝 Additional Commands

```bash
# Create database migration
alembic revision --autogenerate -m "migration message"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check current migration
alembic current
```