# 
FROM python:3.9

# 
WORKDIR /app
# 
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./pyproject.toml /app
COPY ./xoloapi /app/xoloapi
# COPY ./xoloapi/* /app/
# COPY ./src/server.py /app/
# COPY ./src/interfaces /app/interfaces 

# 
# CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10001"]

