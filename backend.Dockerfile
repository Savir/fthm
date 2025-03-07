# Use Python 3.11 as the base image
FROM python:3.11

# Set the working directory

# Copy and install dependencies from requirements.txt
WORKDIR /backend
COPY ./backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
