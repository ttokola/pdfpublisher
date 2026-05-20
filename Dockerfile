FROM python:3.13-slim

WORKDIR /pdfpublisher
# Copy project files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#run the program
CMD ["python", "pdfpublisher.py"]