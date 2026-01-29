# Giải thích các thư viện trong requirements.txt

## 📦 Phân loại thư viện

### 🔴 BẮT BUỘC (Core - Phải cài)
Các thư viện cần thiết để chạy ứng dụng FastAPI cơ bản.

### 🟡 QUAN TRỌNG (Highly Recommended)
Các thư viện cần thiết cho các tính năng chính của dự án.

### 🟢 TÙY CHỌN (Optional)
Có thể bỏ qua nếu không dùng tính năng đó.

### 🔵 DEVELOPMENT (Chỉ cần khi phát triển)
Chỉ cần khi viết test, không cần trong production.

---

## 🔴 BẮT BUỘC - Phải cài

### 1. `fastapi[standard]==0.112.0`
**Công dụng:** Framework chính để xây dựng API
- Tạo REST API endpoints
- Xử lý HTTP requests/responses
- Tự động generate API documentation
- Data validation

**Có trong code:** ✅ `app/main.py` - `from fastapi import FastAPI`

**Nên cài:** ✅ **BẮT BUỘC** - Không có FastAPI thì không chạy được dự án

---

### 2. `uvicorn[standard]==0.40.0`
**Công dụng:** ASGI server để chạy FastAPI
- Server để chạy ứng dụng FastAPI
- Hỗ trợ async/await
- Hot reload khi development (--reload flag)
- `[standard]` bao gồm thêm các dependencies tối ưu

**Có trong code:** ✅ Dùng để chạy: `uvicorn app.main:app --reload`

**Nên cài:** ✅ **BẮT BUỘC** - Không có uvicorn thì không chạy được server

---

## 🟡 QUAN TRỌNG - Nên cài

### 3. `pydantic==2.12.5`
**Công dụng:** Data validation và serialization
- Validate dữ liệu đầu vào/đầu ra
- Tự động convert types
- Tạo models cho request/response
- FastAPI sử dụng Pydantic để validate

**Có trong code:** ✅ FastAPI dùng Pydantic internally

**Nên cài:** ✅ **QUAN TRỌNG** - FastAPI phụ thuộc vào Pydantic

---

### 4. `pydantic-settings==2.12.0`
**Công dụng:** Quản lý settings từ environment variables
- Load settings từ file `.env`
- Validate settings
- Type-safe configuration

**Có trong code:** ✅ `app/core/config.py` - `from pydantic_settings import BaseSettings`

**Nên cài:** ✅ **QUAN TRỌNG** - Đang dùng trong config.py

---

**Lưu ý:** `pydantic-settings` đã tự động đọc file `.env` thông qua `env_file = ".env"` trong Config class, nên không cần thêm `python-dotenv`.

---

## 🟡 QUAN TRỌNG - Nếu dùng Database

### 6. `sqlalchemy==2.0.45`
**Công dụng:** ORM (Object-Relational Mapping) cho database
- Tương tác với database bằng Python objects
- Hỗ trợ nhiều loại database (MySQL, PostgreSQL, SQLite)
- Query builder, migrations

**Có trong code:** Có thể dùng trong `app/db/` hoặc `app/modules/`

**Nên cài:** ✅ **Nên cài** - Nếu dự án có database (thường FastAPI project nào cũng có)

---

### 7. `alembic==1.17.2`
**Công dụng:** Database migration tool
- Tạo, cập nhật schema database
- Version control cho database
- Tự động generate migration từ models

**Có trong code:** ✅ Có thư mục `app/alembic/`

**Nên cài:** ✅ **Nên cài** - Nếu dùng SQLAlchemy thì nên dùng Alembic

---

### 8. `pymysql==1.1.2`
**Công dụng:** MySQL database driver
- Kết nối với MySQL database
- SQLAlchemy cần driver này để nói chuyện với MySQL

**Có trong code:** Có thể dùng trong `DATABASE_URL`

**Nên cài:** 
- ✅ **Nên cài** - Nếu dùng MySQL
- ❌ **Không cần** - Nếu dùng PostgreSQL (thay bằng `psycopg2-binary`)
- ❌ **Không cần** - Nếu dùng SQLite (có sẵn trong Python)

---

## 🟡 QUAN TRỌNG - Nếu dùng Authentication

### 9. `python-jose[cryptography]==3.5.0`
**Công dụng:** Tạo và verify JWT (JSON Web Tokens)
- Tạo access token, refresh token
- Verify token khi user gửi request
- `[cryptography]` cần cho encryption mạnh

**Có trong code:** Có thể dùng trong `app/modules/auth/`

**Nên cài:** ✅ **Nên cài** - Nếu dự án có authentication/login

---

### 10. `passlib[bcrypt]==1.7.4`
**Công dụng:** Hash và verify passwords
- Hash password trước khi lưu vào database
- Verify password khi user login
- `[bcrypt]` là thuật toán hash mạnh

**Có trong code:** Có thể dùng trong `app/modules/auth/` hoặc `app/core/security.py`

**Nên cài:** ✅ **Nên cài** - Nếu có authentication (không nên lưu password dạng plain text)

---

## 🟢 TÙY CHỌN

### 11. `python-multipart==0.0.21`
**Công dụng:** Xử lý form data và file uploads
- Nhận file upload từ client
- Xử lý form data (multipart/form-data)
- Cần khi có endpoint upload file

**Có trong code:** Có thể dùng nếu có endpoint upload file

**Nên cài:** 
- ✅ **Nên cài** - Nếu có tính năng upload file/ảnh
- ❌ **Không cần** - Nếu chỉ có JSON API

---

### 12. `requests==2.32.5`
**Công dụng:** HTTP client để gọi API bên ngoài
- Gọi API của service khác
- Download files từ URL
- Sync HTTP requests

**Có trong code:** Có thể dùng nếu cần gọi external API

**Nên cài:** 
- ✅ **Nên cài** - Nếu cần gọi API bên ngoài (payment, SMS, email service)
- ❌ **Không cần** - Nếu chỉ có internal API

**Lưu ý:** FastAPI là async, nên có thể dùng `httpx` (async) thay vì `requests` (sync)

---

## 🔵 DEVELOPMENT - Chỉ cần khi viết test

### 13. `pytest==9.0.2`
**Công dụng:** Testing framework
- Viết và chạy unit tests
- Integration tests
- Test coverage

**Có trong code:** Có thể dùng trong thư mục `tests/`

**Nên cài:** 
- ✅ **Nên cài** - Nếu viết tests
- ❌ **Không cần** - Nếu không viết tests (nhưng nên viết!)

---

### 14. `pytest-asyncio==1.3.0`
**Công dụng:** Hỗ trợ async tests với pytest
- Test các async functions
- Test FastAPI endpoints (thường là async)

**Có trong code:** Cần khi test FastAPI endpoints

**Nên cài:** 
- ✅ **Nên cài** - Nếu viết tests cho FastAPI (vì FastAPI dùng async)
- ❌ **Không cần** - Nếu không viết tests

---

### 15. `httpx==0.28.1`
**Công dụng:** Async HTTP client
- Gọi API bên ngoài (async)
- Test client cho FastAPI (thay vì requests)
- Tốt hơn requests cho async code

**Có trong code:** Có thể dùng để test hoặc gọi external API

**Nên cài:** 
- ✅ **Nên cài** - Nếu viết tests (dùng làm test client)
- ✅ **Nên cài** - Nếu cần async HTTP client (thay requests)
- ❌ **Không cần** - Nếu đã có requests và không cần async

---

## 📊 Tóm tắt: Nên cài những gì?

### ✅ BẮT BUỘC (Phải cài - 2 thư viện)
```
fastapi[standard]==0.112.0
uvicorn[standard]==0.40.0
```

### ✅ QUAN TRỌNG (Nên cài - 7 thư viện)
```
pydantic==2.12.5
pydantic-settings==2.12.0
sqlalchemy==2.0.45
alembic==1.17.2
pymysql==1.1.2          # Nếu dùng MySQL
python-jose[cryptography]==3.5.0
passlib[bcrypt]==1.7.4
```

### ⚠️ TÙY CHỌN (Tùy tính năng - 2 thư viện)
```
python-multipart==0.0.21  # Nếu có upload file
requests==2.32.5           # Nếu cần gọi external API
```

### 🔵 DEVELOPMENT (Chỉ khi viết test - 3 thư viện)
```
pytest==9.0.2
pytest-asyncio==1.3.0
httpx==0.28.1
```

---

## 🎯 Khuyến nghị cài đặt

### Cho Production (Chạy thực tế):
```bash
# Cài tất cả trừ development tools
pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy alembic pymysql python-jose[cryptography] passlib[bcrypt] python-multipart requests
```

### Cho Development (Phát triển):
```bash
# Cài tất cả
pip install -r requirements.txt
```

### Minimal Setup (Tối thiểu để chạy):
```bash
# Chỉ cài những gì bắt buộc
pip install fastapi uvicorn[standard] pydantic pydantic-settings
```

---

## 🔄 Thay thế thư viện

### Nếu dùng PostgreSQL thay MySQL:
```txt
# Thay
pymysql==1.1.2
# Bằng
psycopg2-binary==2.9.9
```

### Nếu muốn async HTTP client thay requests:
```txt
# Có thể bỏ
requests==2.32.5
# Vì đã có
httpx==0.28.1  # Async, tốt hơn cho FastAPI
```

---

## 📝 Lưu ý

1. **FastAPI phụ thuộc vào Pydantic** - Không thể bỏ Pydantic
2. **Uvicorn là server** - Không thể bỏ nếu muốn chạy ứng dụng
3. **SQLAlchemy + Alembic** - Thường đi cùng nhau
4. **python-jose + passlib** - Thường đi cùng khi có authentication
5. **Development tools** - Có thể bỏ trong production, nhưng nên giữ để test

---

## ❓ Câu hỏi thường gặp

**Q: Có thể bỏ pytest không?**  
A: Có, nhưng nên giữ để viết tests. Tests giúp code ổn định hơn.

**Q: Có thể bỏ requests nếu đã có httpx?**  
A: Có thể, nhưng requests phổ biến hơn. Giữ cả hai cũng không sao.

**Q: Có thể bỏ pymysql nếu dùng SQLite?**  
A: Có, SQLite có sẵn trong Python, không cần driver riêng.

**Q: Có thể bỏ python-multipart nếu không upload file?**  
A: Có, nhưng nếu sau này cần thì phải cài lại.

