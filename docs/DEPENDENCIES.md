# Hướng dẫn quản lý thư viện ngoài trong dự án FastAPI

## 1. Cài đặt thư viện mới

### Cách 1: Cài đặt trực tiếp (khuyến nghị cho development)
```bash
# Cài đặt thư viện
pip install ten-thu-vien

# Cài đặt với phiên bản cụ thể
pip install ten-thu-vien==1.2.3

# Cài đặt với extras (nếu có)
pip install ten-thu-vien[extra]
```

### Cách 2: Cài đặt từ requirements.txt
```bash
pip install -r requirements.txt
```

## 2. Cập nhật requirements.txt

Sau khi cài đặt thư viện, bạn cần thêm vào `requirements.txt`:

### Cách thủ công (khuyến nghị)
1. Mở file `requirements.txt`
2. Thêm dòng: `ten-thu-vien==x.y.z` (với x.y.z là phiên bản)
3. Lưu file

### Cách tự động (cẩn thận - có thể thêm dependencies phụ)
```bash
pip freeze > requirements.txt
```

**Lưu ý:** `pip freeze` sẽ liệt kê TẤT CẢ các package đã cài, kể cả dependencies phụ. Nên chỉ dùng khi muốn "đóng băng" toàn bộ môi trường.

## 3. Sử dụng thư viện trong code

Sau khi cài đặt, import và sử dụng trong code:

```python
# Ví dụ: sử dụng requests
from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/external-api")
async def call_external_api():
    response = requests.get("https://api.example.com/data")
    return response.json()
```

## 4. Quản lý môi trường ảo (Virtual Environment)

### Tạo virtual environment
```bash
# Windows
python -m venv venv

# Kích hoạt
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Cài đặt dependencies trong venv
```bash
pip install -r requirements.txt
```

## 5. Các thư viện phổ biến cho FastAPI

### Database
- `sqlalchemy` - ORM (đã có)
- `alembic` - Migration (đã có)
- `pymysql` - MySQL driver (đã có)
- `psycopg2-binary` - PostgreSQL driver
- `asyncpg` - Async PostgreSQL driver

### Authentication & Security
- `python-jose[cryptography]` - JWT (đã có)
- `passlib[bcrypt]` - Password hashing (đã có)
- `python-multipart` - Form data (đã có)

### HTTP & API
- `httpx` - Async HTTP client (đã có trong dev)
- `requests` - Sync HTTP client
- `aiohttp` - Async HTTP client/server

### Validation & Serialization
- `pydantic` - Data validation (đã có)
- `pydantic-settings` - Settings management (đã có)

### Testing
- `pytest` - Testing framework (đã có)
- `pytest-asyncio` - Async testing (đã có)
- `httpx` - Test client (đã có)

### Utilities
- `pydantic-settings` - Environment variables & settings (đã có, tự động đọc .env)
- `python-dateutil` - Date utilities
- `email-validator` - Email validation

## 6. Best Practices

1. **Luôn chỉ định phiên bản** trong requirements.txt
   ```txt
   fastapi==0.104.1  # ✅ Tốt
   fastapi          # ❌ Không nên
   ```

2. **Tách dependencies theo môi trường**
   - Production dependencies ở đầu file
   - Development dependencies ở cuối (có comment)

3. **Cập nhật định kỳ**
   ```bash
   pip list --outdated  # Xem packages cần update
   pip install --upgrade package-name  # Update package
   ```

4. **Kiểm tra security vulnerabilities**
   ```bash
   pip install safety
   safety check -r requirements.txt
   ```

## 7. Ví dụ: Thêm thư viện mới

Giả sử bạn muốn thêm `redis` để cache:

```bash
# Bước 1: Cài đặt
pip install redis==5.0.1

# Bước 2: Thêm vào requirements.txt
# Mở file và thêm: redis==5.0.1

# Bước 3: Sử dụng trong code
# app/core/cache.py
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)
```

## 8. Troubleshooting

### Lỗi: ModuleNotFoundError
- Đảm bảo đã cài đặt: `pip install -r requirements.txt`
- Kiểm tra virtual environment đã được kích hoạt
- Kiểm tra Python path

### Lỗi: Version conflict
- Kiểm tra compatibility giữa các packages
- Có thể cần update hoặc downgrade một số packages

### Lỗi: Permission denied
- Windows: Chạy PowerShell/CMD với quyền Administrator
- Linux/Mac: Dùng `sudo` hoặc tốt hơn là dùng virtual environment

