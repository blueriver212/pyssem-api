# Dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
RUN pip install -i https://test.pypi.org/simple/ pyssem==0.1.dev168

COPY . .

EXPOSE 5000

CMD ["python", "main.py"]