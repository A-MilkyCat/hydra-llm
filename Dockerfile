# Use the official Python lightweight image
FROM python:3.12-slim

# Set environment variables to optimize Python execution in containers
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk
# PYTHONUNBUFFERED: Ensures that Python output is logged directly to the terminal without buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the dependency file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies without storing cache to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the default port (informative purpose for developers)
EXPOSE 8080

# The command to run the application
# Crucial for Cloud Run: We MUST bind to 0.0.0.0 and use the dynamic $PORT environment variable
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]