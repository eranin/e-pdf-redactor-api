# Bắt đầu từ image Python chính thức
FROM python:3.9.6

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Sao chép yêu cầu dependencies vào container
COPY requirements.txt /app/

# Cài đặt các dependencies từ requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn của bạn vào container
COPY . /app/

# Mở cổng mà FastAPI sẽ chạy
EXPOSE 3000

# Chạy ứng dụng FastAPI khi container bắt đầu
CMD ["uvicorn", "index:app", "--host", "0.0.0.0", "--port", "3000"]

#uvicorn index:app --host 0.0.0.0 --port 3000