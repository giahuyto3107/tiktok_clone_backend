# Hướng dẫn Setup Dự án cho Người Mới

## ⚠️ QUAN TRỌNG: Thứ tự đúng

**✅ ĐÚNG:** Tạo Virtual Environment TRƯỚC → Sau đó mới cài thư viện  
**❌ SAI:** Cài thư viện trước → Tạo venv sau

## 📋 Yêu cầu hệ thống

- Python 3.11 hoặc cao hơn
- pip (thường đi kèm với Python)
- Git (để clone dự án)
- MySQL (nếu dùng database)

## 🚀 Các bước Setup

### Bước 1: Clone dự án

```bash
git clone <repository-url>
cd nutripal_server_side
```

### Bước 2: Tạo Virtual Environment (QUAN TRỌNG - Làm TRƯỚC)

```bash
# Windows
python -m venv venv

# Linux/Mac
python3 -m venv venv
```

**Tại sao phải tạo venv trước?**
- Virtual environment là môi trường cô lập để cài đặt thư viện
- Nếu cài thư viện trước, chúng sẽ được cài vào Python system-wide
- Sau đó tạo venv sẽ không có các thư viện đó
- Phải cài lại tất cả trong venv

### Bước 3: Kích hoạt Virtual Environment

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate
```

**Kiểm tra:** Bạn sẽ thấy `(venv)` ở đầu dòng terminal:
```
(.venv) C:\D\project\nutripal_server_side>
```

### Bước 4: Cài đặt thư viện từ requirements.txt

```bash
# Đảm bảo venv đã được kích hoạt (có (venv) ở đầu dòng)
pip install -r requirements.txt
```

**Lưu ý:**
- Phải kích hoạt venv trước khi chạy lệnh này
- Nếu không, thư viện sẽ cài vào Python system
- Quá trình cài đặt có thể mất vài phút

### Bước 5: Tạo file .env

Tạo file `.env` ở thư mục gốc của dự án:

```bash
# Windows (PowerShell)
New-Item -Path .env -ItemType File

# Linux/Mac
touch .env
```

Sau đó thêm các biến môi trường cần thiết vào file `.env`:

```env
# Database
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/nutripal_db

# Security
SECRET_KEY=your-secret-key-here-minimum-32-characters-long

# App Settings (optional)
DEBUG=True
APP_NAME=NutriPal API
VERSION=1.0.0
ALGORITHM=HS256
```

**Lưu ý:**
- Thay `username`, `password`, `localhost`, `3306`, `nutripal_db` bằng thông tin database thực tế
- `SECRET_KEY` nên là chuỗi ngẫu nhiên, dài ít nhất 32 ký tự
- File `.env` đã được thêm vào `.gitignore`, không bị commit lên Git

### Bước 6: Kiểm tra cài đặt

```bash
# Kiểm tra Python version
python --version

# Kiểm tra các packages đã cài
pip list

# Kiểm tra FastAPI
python -c "import fastapi; print(fastapi.__version__)"
```

### Bước 7: Chạy dự án

```bash
# Chạy development server
uvicorn app.main:app --reload

# Hoặc với host và port cụ thể
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Kiểm tra:** Mở trình duyệt và truy cập:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

## 🔄 Quy trình làm việc hàng ngày

### Mỗi khi mở dự án:

```bash
# 1. Di chuyển vào thư mục dự án
cd C:\D\project\nutripal_server_side

# 2. Kích hoạt virtual environment
venv\Scripts\activate  # Windows
# hoặc
source venv/bin/activate  # Linux/Mac

# 3. Chạy dự án
uvicorn app.main:app --reload
```

### Khi có thư viện mới:

```bash
# 1. Đảm bảo venv đã được kích hoạt
# 2. Cài đặt thư viện
pip install ten-thu-vien

# 3. Cập nhật requirements.txt
# Mở file requirements.txt và thêm: ten-thu-vien==x.y.z
```

## ❌ Các lỗi thường gặp

### Lỗi 1: "ModuleNotFoundError: No module named 'fastapi'"

**Nguyên nhân:** Chưa kích hoạt venv hoặc chưa cài đặt thư viện

**Giải pháp:**
```bash
# 1. Kích hoạt venv
venv\Scripts\activate

# 2. Cài đặt lại
pip install -r requirements.txt
```

### Lỗi 2: "pip is not recognized"

**Nguyên nhân:** Chưa kích hoạt venv

**Giải pháp:**
```bash
venv\Scripts\activate
```

### Lỗi 3: "venv\Scripts\Activate.ps1 cannot be loaded"

**Nguyên nhân:** PowerShell execution policy

**Giải pháp:**
```powershell
# Chạy PowerShell với quyền Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Hoặc dùng CMD thay vì PowerShell
venv\Scripts\activate.bat
```

### Lỗi 4: "DATABASE_URL not found"

**Nguyên nhân:** Chưa tạo file `.env` hoặc thiếu biến môi trường

**Giải pháp:**
- Tạo file `.env` ở thư mục gốc
- Thêm `DATABASE_URL` và các biến khác vào file

### Lỗi 5: Packages cài vào system Python thay vì venv

**Nguyên nhân:** Quên kích hoạt venv trước khi cài

**Giải pháp:**
```bash
# 1. Kích hoạt venv
venv\Scripts\activate

# 2. Kiểm tra pip đang trỏ đến venv
which pip  # Linux/Mac
where pip  # Windows
# Phải hiển thị đường dẫn trong venv

# 3. Cài lại trong venv
pip install -r requirements.txt
```

## 📝 Checklist Setup

- [ ] Clone dự án từ Git
- [ ] Tạo virtual environment (`python -m venv venv`)
- [ ] Kích hoạt virtual environment
- [ ] Cài đặt thư viện (`pip install -r requirements.txt`)
- [ ] Tạo file `.env` với các biến môi trường
- [ ] Kiểm tra cài đặt (`pip list`, `python --version`)
- [ ] Chạy dự án (`uvicorn app.main:app --reload`)
- [ ] Truy cập http://localhost:8000/docs để kiểm tra

## 🎯 Tóm tắt thứ tự đúng

```
1. Clone dự án
   ↓
2. Tạo Virtual Environment (python -m venv venv)
   ↓
3. Kích hoạt venv (venv\Scripts\activate)
   ↓
4. Cài đặt thư viện (pip install -r requirements.txt)
   ↓
5. Tạo file .env
   ↓
6. Chạy dự án (uvicorn app.main:app --reload)
```

## 💡 Tips

1. **Luôn kích hoạt venv trước khi làm việc**
   - Kiểm tra có `(venv)` ở đầu dòng terminal
   - Nếu không có, chạy lại lệnh activate

2. **Kiểm tra pip đang trỏ đến venv**
   ```bash
   which pip  # Linux/Mac
   where pip  # Windows
   ```
   Đường dẫn phải chứa `venv` hoặc `.venv`

3. **Commit requirements.txt, không commit venv/**
   - `requirements.txt` → ✅ Commit
   - `venv/` → ❌ Không commit (đã có trong .gitignore)

4. **Cập nhật requirements.txt khi thêm thư viện mới**
   - Cài đặt: `pip install ten-thu-vien`
   - Thêm vào `requirements.txt`: `ten-thu-vien==x.y.z`

5. **Nếu venv bị lỗi, xóa và tạo lại**
   ```bash
   # Xóa venv cũ
   Remove-Item -Recurse -Force venv  # Windows PowerShell
   rm -rf venv  # Linux/Mac
   
   # Tạo lại
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```




