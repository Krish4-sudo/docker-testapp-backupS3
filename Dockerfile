# Use the official Python image from Docker Hub
FROM python:3.9

# Set the working directory
WORKDIR /app

# Install s3fs-fuse
RUN apt-get update && apt-get install -y s3fs fuse

RUN pip install uv

# Copy requirements.txt for efficient caching
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create mount point directory for S3
RUN mkdir -p /s3data

# Copy the rest of the application files
COPY . .

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the port your app will be running on
EXPOSE 5050

# Use the entrypoint script to mount S3 and then run the application
ENTRYPOINT ["/entrypoint.sh"]

# This will be passed to the entrypoint script
CMD ["python", "server.py"]